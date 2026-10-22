"""Phase C analysis: decision bookkeeping on hand-built records."""

import numpy as np

from research.experiments.phaseC_analysis import arrays, outcomes


def _rec(oid, cls, withheld, score, closed, open_=None):
    s = {"score": score, "closed_posterior": closed, "open_posterior": open_ or closed, "n_obs_used": 2}
    return {"oid": oid, "true_class": cls, "withheld": withheld, "strategies": {"P_open_world_eig": s}}


def test_conformal_outcomes():
    recs = [
        _rec("a", "sn_ia", False, -3.0, {"sn_ia": 0.97, "sn_ii": 0.02, "sn_ibc": 0.01}),   # kept, confident, right
        _rec("b", "sn_ii", False, 2.0, {"sn_ia": 0.97, "sn_ii": 0.02, "sn_ibc": 0.01}),    # flagged: false unknown
        _rec("c", "tde", True, 5.0, {"sn_ia": 0.99, "sn_ii": 0.005, "sn_ibc": 0.005}),     # flagged: caught
        _rec("d", "slsn", True, -1.0, {"sn_ia": 0.99, "sn_ii": 0.005, "sn_ibc": 0.005}),   # missed, confident wrong
    ]
    o = outcomes(arrays(recs, "P_open_world_eig"), tau=0.0)
    assert o["flagged"].tolist() == [False, True, True, False]
    assert o["correct"].tolist() == [True, False, True, False]
    assert o["confident_wrong"].tolist() == [False, False, False, True]


def test_raw_outcomes_use_open_posterior_for_P():
    recs = [_rec("c", "tde", True, 5.0, {"sn_ia": 0.6, "sn_ii": 0.2, "sn_ibc": 0.2},
                 {"sn_ia": 0.01, "sn_ii": 0.01, "sn_ibc": 0.01, "h0": 0.97})]
    o = outcomes(arrays(recs, "P_open_world_eig"), tau=None)
    assert o["correct"].tolist() == [True] and np.all(~o["confident_wrong"])
