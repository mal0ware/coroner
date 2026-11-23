"""Which comes first: the profit target or the loss limit?

The trades are resampled into many paths. Each path's running total is followed
until it reaches ``+target`` or ``-loss_limit``, or the path runs out. The two
resampling schemes are the i.i.d. bootstrap and the stationary bootstrap of
Politis and Romano (1994). Two closed forms are here to test the simulator
against: Brownian motion with drift, and the gambler's ruin for a +-1 walk.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

import numpy as np
import numpy.typing as npt

FloatArray = npt.NDArray[np.float64]
IntArray = npt.NDArray[np.int64]

Method = Literal["iid", "stationary"]

_MAX_CELLS = 4_000_000


def brownian_hit_probability(mu: float, sigma: float, target: float, loss_limit: float) -> float:
    """P(X reaches +target before -loss_limit) for X_t = mu t + sigma W_t, X_0 = 0.

    ``(1 - exp(-2 mu a / sigma^2)) / (1 - exp(-2 mu (a + b) / sigma^2))`` with
    ``a = loss_limit`` and ``b = target``; ``a / (a + b)`` in the limit mu -> 0.
    """
    if sigma <= 0 or target <= 0 or loss_limit <= 0:
        raise ValueError("sigma, target and loss_limit must be positive")
    a, b = loss_limit, target
    x = 2.0 * mu / sigma**2
    if abs(x) * (a + b) < 1e-9:
        return a / (a + b)
    if x > 0:
        return math.expm1(-x * a) / math.expm1(-x * (a + b))
    y = -x  # same expression multiplied through by exp(x (a + b)), safe for large y
    return math.exp(-y * b) * math.expm1(-y * a) / math.expm1(-y * (a + b))


def gamblers_ruin_probability(p_up: float, target: int, loss_limit: int) -> float:
    """P(a +-1 walk with up-probability ``p_up`` reaches +target before -loss_limit).

    ``(1 - (q/p)^a) / (1 - (q/p)^(a + b))`` with ``q = 1 - p``; ``a / (a + b)``
    when ``p = 1/2``.
    """
    if not 0 < p_up < 1 or target <= 0 or loss_limit <= 0:
        raise ValueError("need 0 < p_up < 1 and positive integer barriers")
    a, b = loss_limit, target
    if p_up == 0.5:
        return a / (a + b)
    r = (1 - p_up) / p_up
    return float((1 - r**a) / (1 - r ** (a + b)))


def iid_indices(n: int, paths: int, horizon: int, rng: np.random.Generator) -> IntArray:
    """Indices for the i.i.d. bootstrap: each draw uniform on 0..n-1."""
    return rng.integers(0, n, size=(paths, horizon), dtype=np.int64)


def stationary_indices(
    n: int, paths: int, horizon: int, mean_block: float, rng: np.random.Generator
) -> IntArray:
    """Indices for the stationary bootstrap of Politis and Romano (1994).

    The first index of each path is uniform on 0..n-1. After that, with
    probability ``p = 1 / mean_block`` the next index is a fresh uniform draw,
    and otherwise it is the previous index plus one, wrapping from n-1 to 0.
    Block lengths are therefore geometric with mean ``mean_block``.
    """
    if mean_block < 1:
        raise ValueError("mean_block must be at least 1")
    fresh = rng.integers(0, n, size=(paths, horizon), dtype=np.int64)
    restart = rng.random((paths, horizon)) < 1.0 / mean_block
    restart[:, 0] = True
    steps = np.arange(horizon, dtype=np.int64)
    block_start = np.maximum.accumulate(np.where(restart, steps, 0), axis=1)
    start_index = np.take_along_axis(fresh, block_start, axis=1)
    return np.asarray((start_index + steps - block_start) % n, dtype=np.int64)


@dataclass(frozen=True)
class BarrierResult:
    """Counts of paths by which barrier the running total reached first."""

    paths: int
    hit_target: int
    hit_loss: int

    @property
    def neither(self) -> int:
        return self.paths - self.hit_target - self.hit_loss

    @property
    def p_target(self) -> float:
        return self.hit_target / self.paths

    @property
    def p_loss(self) -> float:
        return self.hit_loss / self.paths

    @property
    def p_neither(self) -> float:
        return self.neither / self.paths

    @property
    def p_target_given_hit(self) -> float:
        """Share of the paths that reached a barrier which reached the target."""
        decided = self.hit_target + self.hit_loss
        return self.hit_target / decided if decided else float("nan")


def first_barrier(increments: FloatArray, target: float, loss_limit: float) -> BarrierResult:
    """Follow each row's running total and count which barrier it reaches first.

    A path reaches the target when its running total is ``>= target`` and the
    loss limit when it is ``<= -loss_limit``. Rows that reach neither by the
    last column are counted as neither.
    """
    if target <= 0 or loss_limit <= 0:
        raise ValueError("target and loss_limit must be positive")
    totals = np.cumsum(increments, axis=1)
    up = totals >= target
    down = totals <= -loss_limit
    horizon = increments.shape[1]
    first_up = np.where(up.any(axis=1), up.argmax(axis=1), horizon)
    first_down = np.where(down.any(axis=1), down.argmax(axis=1), horizon)
    return BarrierResult(
        paths=int(increments.shape[0]),
        hit_target=int(np.sum(first_up < first_down)),
        hit_loss=int(np.sum(first_down < first_up)),
    )


def barrier_odds(
    values: FloatArray,
    target: float,
    loss_limit: float,
    horizon: int,
    paths: int = 10_000,
    method: Method = "iid",
    mean_block: float = 10.0,
    seed: int = 0,
) -> BarrierResult:
    """Resample ``values`` into ``paths`` paths of ``horizon`` trades and count.

    ``method`` is ``"iid"`` or ``"stationary"``; ``mean_block`` is the mean
    block length in trades for the stationary bootstrap.
    """
    n = int(values.shape[0])
    if n == 0 or horizon <= 0 or paths <= 0:
        raise ValueError("need at least one trade, one step and one path")
    rng = np.random.default_rng(seed)
    batch = max(1, _MAX_CELLS // horizon)
    hit_target = hit_loss = 0
    done = 0
    while done < paths:
        size = min(batch, paths - done)
        if method == "iid":
            index = iid_indices(n, size, horizon, rng)
        elif method == "stationary":
            index = stationary_indices(n, size, horizon, mean_block, rng)
        else:
            raise ValueError(f"unknown method {method!r}")
        part = first_barrier(values[index], target, loss_limit)
        hit_target += part.hit_target
        hit_loss += part.hit_loss
        done += size
    return BarrierResult(paths, hit_target, hit_loss)
