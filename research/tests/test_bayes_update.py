import numpy as np
import pytest
from scipy.stats import norm

from research.inference.bayes import ClosedWorldBelief
from research.transients.models import MODELED_CLASSES, modeled_flux_fn


def test_single_update_matches_independent_closed_form():
    """One noiseless-mean observation under 'fast'; posterior must match the
    textbook two-hypothesis Bayes formula computed independently via
    scipy.stats.norm (not via this package's own likelihood code)."""
    t, amplitude, sigma = 2.0, 10.0, 1.0
    y = float(modeled_flux_fn("fast")(np.array([t]), amplitude)[0])

    belief = ClosedWorldBelief.with_uniform_prior(
        classes=MODELED_CLASSES, amplitude_grid=np.array([amplitude])
    )
    belief.update(t, y, sigma)

    mean_fast = float(modeled_flux_fn("fast")(np.array([t]), amplitude)[0])
    mean_slow = float(modeled_flux_fn("slow")(np.array([t]), amplitude)[0])
    like_fast = norm.pdf(y, loc=mean_fast, scale=sigma)
    like_slow = norm.pdf(y, loc=mean_slow, scale=sigma)
    expected_post_fast = like_fast / (like_fast + like_slow)

    post = belief.class_posterior()
    assert post["fast"] == pytest.approx(expected_post_fast, abs=1e-9)
    assert post["fast"] + post["slow"] == pytest.approx(1.0, abs=1e-9)


def test_sequential_updates_match_product_of_independent_likelihoods():
    """Three sequential updates must equal one shot with the product (sum of
    logs) of the three independently-computed likelihoods."""
    amplitude, sigma = 10.0, 1.0
    times = [0.5, 2.0, 4.0]
    ys = [
        float(modeled_flux_fn("fast")(np.array([times[0]]), amplitude)[0]) + 0.3,
        float(modeled_flux_fn("fast")(np.array([times[1]]), amplitude)[0]) - 0.2,
        float(modeled_flux_fn("fast")(np.array([times[2]]), amplitude)[0]) + 0.1,
    ]

    belief = ClosedWorldBelief.with_uniform_prior(
        classes=MODELED_CLASSES, amplitude_grid=np.array([amplitude])
    )
    for t, y in zip(times, ys):
        belief.update(t, y, sigma)

    log_like_fast = sum(
        norm.logpdf(y, loc=float(modeled_flux_fn("fast")(np.array([t]), amplitude)[0]), scale=sigma)
        for t, y in zip(times, ys)
    )
    log_like_slow = sum(
        norm.logpdf(y, loc=float(modeled_flux_fn("slow")(np.array([t]), amplitude)[0]), scale=sigma)
        for t, y in zip(times, ys)
    )
    m = max(log_like_fast, log_like_slow)
    expected_post_fast = np.exp(log_like_fast - m) / (np.exp(log_like_fast - m) + np.exp(log_like_slow - m))

    post = belief.class_posterior()
    assert post["fast"] == pytest.approx(expected_post_fast, abs=1e-9)


def test_posterior_concentrates_on_true_class_with_low_noise():
    amplitude, sigma = 10.0, 1e-3
    belief = ClosedWorldBelief.with_uniform_prior(
        classes=MODELED_CLASSES, amplitude_grid=np.array([amplitude])
    )
    rng = np.random.default_rng(0)
    for t in [0.3, 0.8, 1.5, 2.5, 4.0]:
        mean = float(modeled_flux_fn("slow")(np.array([t]), amplitude)[0])
        y = mean + rng.normal(0, sigma)
        belief.update(t, y, sigma)

    post = belief.class_posterior()
    assert post["slow"] > 0.999


def test_discrepancy_widens_likelihood_and_off_is_identical():
    import numpy as np
    from research.inference.bayes import ClosedWorldBelief
    grid = np.array([1.0, 2.0, 4.0])
    flux = lambda cls: (lambda t, a: a * np.ones_like(np.asarray(t, dtype=float)))
    plain = ClosedWorldBelief.with_uniform_prior(("x",), grid, flux)
    off = ClosedWorldBelief.with_uniform_prior(("x",), grid, flux)
    off.discrepancy_resolver = None
    on = ClosedWorldBelief.with_uniform_prior(("x",), grid, flux)
    on.discrepancy_resolver = lambda cls: (lambda t, a: 0.5 * a)
    assert np.array_equal(plain.log_likelihood_grid(0.0, 3.0, 0.1), off.log_likelihood_grid(0.0, 3.0, 0.1))
    ll_plain, ll_on = plain.log_likelihood_grid(0.0, 10.0, 0.1), on.log_likelihood_grid(0.0, 10.0, 0.1)
    assert np.all(ll_on > ll_plain)  # a far-off point is much less surprising with model scatter
