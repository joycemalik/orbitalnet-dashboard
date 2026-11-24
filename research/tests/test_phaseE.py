import math

from research.experiments.phaseE_analysis import alarmed, cp_lower, cp_upper


def test_alarm_is_anytime():
    # crossing log(10) at any step counts, even if E later falls back
    assert alarmed([-3.0, math.log(10) + 0.01, -8.0], alpha=0.1)
    assert not alarmed([-3.0, math.log(10) - 0.01], alpha=0.1)
    assert not alarmed([], alpha=0.1)


def test_clopper_pearson_known_values():
    # 0 of 100: one-sided 95% upper bound is 1 - 0.05**(1/100)
    assert abs(cp_upper(0, 100) - (1 - 0.05 ** (1 / 100))) < 1e-9
    assert cp_lower(0, 50) == 0.0 and cp_upper(50, 50) == 1.0
    # bounds bracket the point estimate
    assert cp_lower(25, 81) < 25 / 81 < cp_upper(25, 81)
