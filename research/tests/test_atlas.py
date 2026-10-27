"""Atlas pipeline on synthetic decaying objects with an injected density factor."""

import numpy as np
import pandas as pd

from research.atlas import density_ratio as dr


def _synthetic(n_obj=60, factor=3.0, seed=0):
    rng = np.random.default_rng(seed)
    t_start, t_peak0 = pd.Timestamp("2024-04-27"), pd.Timestamp("2024-05-10 18:00")
    rows = []
    for i in range(n_obj):
        a = dr.RE + 420 + rng.uniform(-10, 10)
        rate = -rng.uniform(80, 200) / 1000.0  # km/day, quiet
        t = t_start
        while t < pd.Timestamp("2024-05-14"):
            f = factor if t_peak0 <= t < t_peak0 + pd.Timedelta(hours=24) else 1.0
            step = 0.5
            a += rate * f * step + rng.normal(0, 0.002)
            t += pd.Timedelta(days=step)
            n = np.sqrt(dr.MU / a**3) * 86400 / (2 * np.pi)
            rows.append((1000 + i, t.isoformat(), n))
    return pd.DataFrame(rows, columns=["NORAD_CAT_ID", "EPOCH", "MEAN_MOTION"])


def test_sma_roundtrip():
    n = np.array([15.5])
    a = dr.sma_km(n)
    assert abs(np.sqrt(dr.MU / a**3) * 86400 / (2 * np.pi) - 15.5) < 1e-9


def test_recovers_injected_factor():
    gp = _synthetic(factor=3.0)
    rates = dr.decay_rates(gp)
    days = list(pd.date_range("2024-04-27", "2024-05-08"))
    base = dr.object_baselines(rates, days)
    assert len(base) == 60
    cell = dr.shell_ratio(rates, base, set(base.index))
    shell = cell[cell.shell == 400].set_index("bin").R
    assert 2.5 < shell.max() < 3.5
    assert shell[shell.index < "2024-05-09"].median() < 1.3
