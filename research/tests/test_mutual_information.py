import numpy as np
import pytest

from research.inference.mutual_information import expected_information_gain, expected_information_gain_batch


def test_eig_is_zero_when_predictives_are_identical():
    """If both hypothesis cells predict the exact same distribution, a
    measurement carries zero information about which cell is true."""
    log_weights = np.log(np.array([0.5, 0.5]))
    means = np.array([3.0, 3.0])
    group_idx = np.array([0, 1])
    eig = expected_information_gain(log_weights, means, sigma=1.0, group_idx=group_idx, n_groups=2)
    assert eig == pytest.approx(0.0, abs=1e-3)


def test_eig_approaches_prior_entropy_in_noiseless_separated_limit():
    """As sigma -> 0 with well-separated means, a measurement perfectly
    reveals which hypothesis is true, so EIG -> H[prior] = ln(2) for a
    uniform binary prior."""
    log_weights = np.log(np.array([0.5, 0.5]))
    means = np.array([-1.0, 1.0])
    group_idx = np.array([0, 1])
    eig = expected_information_gain(
        log_weights, means, sigma=0.01, group_idx=group_idx, n_groups=2,
        n_y=4001, pad_sigmas=12.0,
    )
    assert eig == pytest.approx(np.log(2), abs=1e-2)


def test_eig_is_between_zero_and_prior_entropy_for_partial_separation():
    log_weights = np.log(np.array([0.5, 0.5]))
    means = np.array([-0.5, 0.5])
    group_idx = np.array([0, 1])
    eig = expected_information_gain(log_weights, means, sigma=1.0, group_idx=group_idx, n_groups=2)
    assert 0.0 < eig < np.log(2)


def test_batch_matches_scalar_for_several_candidates():
    """The vectorized multi-candidate EIG must agree with calling the
    single-candidate function once per candidate (this is purely a
    performance refactor, not a different estimator)."""
    rng = np.random.default_rng(0)
    log_weights = np.log(np.array([0.3, 0.3, 0.4]))
    group_idx = np.array([0, 1, 2])
    means_batch = rng.uniform(-2, 2, size=(5, 3))
    sigma = 0.7

    # Note: the batch version shares one quadrature grid (sized to cover all
    # candidates) while the scalar version uses a grid sized per candidate,
    # so results agree only up to quadrature discretization error, not bit
    # for bit — hence the looser tolerance than the other known-answer tests.
    batch_result = expected_information_gain_batch(log_weights, means_batch, sigma, group_idx, 3, n_y=4001)
    for k in range(5):
        scalar_result = expected_information_gain(log_weights, means_batch[k], sigma, group_idx, 3, n_y=4001)
        assert batch_result[k] == pytest.approx(scalar_result, abs=1e-3)
