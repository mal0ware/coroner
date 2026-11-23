"""The barrier simulator against closed forms, and the two bootstraps' structure."""

from __future__ import annotations

import math

import numpy as np
import pytest

from coroner import barrier

# ---- closed forms ----------------------------------------------------------


def test_brownian_formula_as_written() -> None:
    mu, sigma, b, a = 0.005, 0.5, 15.0, 10.0
    direct = (1 - math.exp(-2 * mu * a / sigma**2)) / (1 - math.exp(-2 * mu * (a + b) / sigma**2))
    assert barrier.brownian_hit_probability(mu, sigma, b, a) == pytest.approx(direct)
    # (1 - e^-0.4) / (1 - e^-1)
    assert direct == pytest.approx(0.52155, abs=1e-5)


@pytest.mark.parametrize(("b", "a"), [(1.0, 1.0), (15.0, 10.0), (3.0, 7.0)])
def test_brownian_tends_to_a_over_a_plus_b(b: float, a: float) -> None:
    assert barrier.brownian_hit_probability(0.0, 1.0, b, a) == a / (a + b)
    for mu in (1e-4, -1e-4):
        assert barrier.brownian_hit_probability(mu, 1.0, b, a) == pytest.approx(
            a / (a + b), abs=1e-3
        )


def test_brownian_reflection_symmetry() -> None:
    # Flipping the sign of the path swaps the barriers and the drift.
    p = barrier.brownian_hit_probability(0.3, 1.2, 4.0, 2.5)
    q = barrier.brownian_hit_probability(-0.3, 1.2, 2.5, 4.0)
    assert p + q == pytest.approx(1.0)


def test_brownian_negative_drift_branch_matches_direct_formula() -> None:
    mu, sigma, b, a = -0.2, 1.0, 3.0, 2.0
    direct = (1 - math.exp(-2 * mu * a)) / (1 - math.exp(-2 * mu * (a + b)))
    assert barrier.brownian_hit_probability(mu, sigma, b, a) == pytest.approx(direct)


def test_brownian_extreme_drift_does_not_overflow() -> None:
    assert barrier.brownian_hit_probability(5.0, 0.1, 10.0, 10.0) == pytest.approx(1.0)
    assert barrier.brownian_hit_probability(-5.0, 0.1, 10.0, 10.0) == pytest.approx(0.0)


def test_brownian_rejects_bad_input() -> None:
    with pytest.raises(ValueError):
        barrier.brownian_hit_probability(0.1, 0.0, 1.0, 1.0)


def test_gamblers_ruin_values() -> None:
    assert barrier.gamblers_ruin_probability(0.5, 15, 10) == 10 / 25
    # a = b = 1: reach +1 before -1 is just the first step
    assert barrier.gamblers_ruin_probability(0.6, 1, 1) == pytest.approx(0.6)
    # a = b = 2, p = 0.6: (1 - (2/3)^2) / (1 - (2/3)^4) = 1 / (1 + 4/9) = 9/13
    assert barrier.gamblers_ruin_probability(0.6, 2, 2) == pytest.approx(9 / 13)


def test_gamblers_ruin_approaches_brownian_for_small_drift() -> None:
    # A +-1 walk with up-probability p has mean 2p - 1 and variance near 1.
    p = 0.505
    walk = barrier.gamblers_ruin_probability(p, 30, 20)
    mu, sigma = 2 * p - 1, math.sqrt(1 - (2 * p - 1) ** 2)
    assert walk == pytest.approx(barrier.brownian_hit_probability(mu, sigma, 30, 20), abs=2e-3)


# ---- counting --------------------------------------------------------------


def test_first_barrier_by_hand() -> None:
    increments = np.array(
        [
            [1.0, 1.0, 1.0],  # 1, 2: target at step 2
            [-1.0, -1.0, -1.0],  # -1, -2: loss limit at step 2
            [1.0, -1.0, 0.0],  # never reaches either
            [2.0, -5.0, 9.0],  # target at step 1, before the later fall
            [-3.0, 9.0, 0.0],  # loss limit at step 1, before the later rise
        ]
    )
    result = barrier.first_barrier(increments, target=2.0, loss_limit=2.0)
    assert (result.paths, result.hit_target, result.hit_loss, result.neither) == (5, 2, 2, 1)
    assert result.p_target == 0.4 and result.p_loss == 0.4 and result.p_neither == 0.2
    assert result.p_target_given_hit == 0.5


def test_first_barrier_rejects_non_positive_barriers() -> None:
    with pytest.raises(ValueError):
        barrier.first_barrier(np.zeros((1, 1)), 0.0, 1.0)


# ---- simulator against closed forms ---------------------------------------


def test_fair_walk_gives_a_over_a_plus_b() -> None:
    # Resampling {+1, -1} is a fair +-1 walk. Loss limit a = 10, target b = 15:
    # P(target first) = 10 / 25 = 0.4 exactly. 8,000 paths: s.e. 0.0055.
    result = barrier.barrier_odds(
        np.array([1.0, -1.0]), target=15, loss_limit=10, horizon=3000, paths=8000, seed=11
    )
    assert result.p_neither < 0.002
    assert result.p_target == pytest.approx(0.4, abs=0.02)


def test_biased_walk_gives_gamblers_ruin() -> None:
    # Eleven +1 and nine -1: p = 0.55. With a = b = 10 the exact answer is
    # 1 / (1 + (9/11)^10) = 0.8815. 8,000 paths: s.e. 0.0036.
    values = np.array([1.0] * 11 + [-1.0] * 9)
    exact = barrier.gamblers_ruin_probability(0.55, 10, 10)
    assert exact == pytest.approx(1 / (1 + (9 / 11) ** 10))
    result = barrier.barrier_odds(values, 10, 10, horizon=1500, paths=8000, seed=12)
    assert result.neither == 0
    assert result.p_target == pytest.approx(exact, abs=0.015)


def test_gaussian_walk_matches_brownian_closed_form() -> None:
    # Steps N(0.005, 0.5^2), loss limit 10, target 15. Closed form 0.5215.
    # A discrete walk overshoots the barrier by about 0.58 sigma = 0.29, which
    # moves the answer by under 0.01. 6,000 paths: s.e. 0.0064.
    mu, sigma, b, a = 0.005, 0.5, 15.0, 10.0
    rng = np.random.default_rng(13)
    hit_target = hit_loss = paths = 0
    for _ in range(6):
        part = barrier.first_barrier(rng.normal(mu, sigma, size=(1000, 6000)), b, a)
        hit_target += part.hit_target
        hit_loss += part.hit_loss
        paths += part.paths
    assert (paths - hit_target - hit_loss) / paths < 0.005
    exact = barrier.brownian_hit_probability(mu, sigma, b, a)
    assert hit_target / paths == pytest.approx(exact, abs=0.03)


def test_barrier_odds_is_seeded() -> None:
    values = np.random.default_rng(0).normal(0.1, 1.0, size=50)
    for method in ("iid", "stationary"):
        a = barrier.barrier_odds(values, 5, 5, 100, 500, method, seed=7)  # type: ignore[arg-type]
        b = barrier.barrier_odds(values, 5, 5, 100, 500, method, seed=7)  # type: ignore[arg-type]
        assert a == b


def test_barrier_odds_rejects_unknown_method() -> None:
    with pytest.raises(ValueError):
        barrier.barrier_odds(np.array([1.0]), 1, 1, 5, 5, "blocks")  # type: ignore[arg-type]


# ---- bootstrap index structure --------------------------------------------


def test_iid_indices_are_uniform() -> None:
    index = barrier.iid_indices(5, 2000, 100, np.random.default_rng(1))
    assert index.min() == 0 and index.max() == 4
    assert np.bincount(index.ravel()) / index.size == pytest.approx([0.2] * 5, abs=0.01)


def test_stationary_blocks_follow_on_and_wrap() -> None:
    # With a very long mean block every path is one block: start, start + 1, ...
    index = barrier.stationary_indices(3, 50, 7, 1e12, np.random.default_rng(2))
    assert np.all((index[:, 1:] - index[:, :-1]) % 3 == 1)
    assert set(index[:, 0].tolist()) == {0, 1, 2}


def test_stationary_mean_block_length() -> None:
    # A step continues the block with probability 1 - p, or lands on the
    # successor by chance with probability p / n: together 1 - p + p / n.
    n, mean_block = 500, 8.0
    index = barrier.stationary_indices(n, 400, 500, mean_block, np.random.default_rng(3))
    follows = np.mean((index[:, 1:] - index[:, :-1]) % n == 1)
    p = 1 / mean_block
    assert follows == pytest.approx(1 - p + p / n, abs=0.005)
    assert index.min() >= 0 and index.max() < n


def test_stationary_marginal_is_uniform() -> None:
    index = barrier.stationary_indices(4, 3000, 60, 5.0, np.random.default_rng(4))
    assert np.bincount(index.ravel()) / index.size == pytest.approx([0.25] * 4, abs=0.01)


def test_stationary_with_block_one_is_iid() -> None:
    # p = 1: every index is a fresh draw, so successive indices are independent.
    index = barrier.stationary_indices(10, 2000, 50, 1.0, np.random.default_rng(5))
    follows = np.mean((index[:, 1:] - index[:, :-1]) % 10 == 1)
    assert follows == pytest.approx(0.1, abs=0.01)


def test_stationary_rejects_block_below_one() -> None:
    with pytest.raises(ValueError):
        barrier.stationary_indices(5, 1, 5, 0.5, np.random.default_rng(0))
