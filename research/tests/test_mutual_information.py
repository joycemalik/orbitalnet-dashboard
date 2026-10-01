import numpy as np
import pytest

from research.inference.mutual_information import expected_information_gain


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
