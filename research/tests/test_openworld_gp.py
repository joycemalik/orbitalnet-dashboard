import numpy as np
import pytest
from scipy.stats import norm

from research.inference.openworld import SimpleGP


def test_log_marginal_likelihood_matches_closed_form_for_one_point():
    """For a single observation, a zero-mean GP's marginal likelihood is
    exactly Normal(y; 0, var_f + sigma_n^2) — an independent closed-form
    check of the Cholesky-based implementation."""
    gp = SimpleGP(lengthscale=1.2, var_f=100.0, sigma_n=1.0)
    t = np.array([2.0])
    y = np.array([7.3])

    expected = norm.logpdf(y[0], loc=0.0, scale=np.sqrt(gp.var_f + gp.sigma_n ** 2))
    actual = gp.log_marginal_likelihood(t, y)
    assert actual == pytest.approx(expected, abs=1e-9)


def test_log_marginal_likelihood_empty_data_is_zero():
    gp = SimpleGP()
    assert gp.log_marginal_likelihood(np.array([]), np.array([])) == 0.0


def test_predict_matches_prior_with_no_observations():
    gp = SimpleGP(lengthscale=1.2, var_f=100.0, sigma_n=1.0)
    mean, std = gp.predict(np.array([]), np.array([]), 3.0)
    assert mean == pytest.approx(0.0)
    assert std == pytest.approx(np.sqrt(gp.var_f + gp.sigma_n ** 2))
