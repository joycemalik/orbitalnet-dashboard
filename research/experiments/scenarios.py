"""Phase 2 scenarios, realigned to Hypothesis-Discriminating Observation
Campaigns....pdf ("the manuscript"). The manuscript lists five scenarios
(Nominal, Communication sweep, Node loss, Crowding, Model error) without
saying which belong to which phase. Communication sweep and node loss are
about multi-spacecraft belief staleness, which only exists once Phase 4
(decentralization) is built — they are reserved for Phase 4's own
contact-fraction sweep and node-loss test. Phase 2 (a single centralized
planner) runs the three that are meaningful without decentralization:
Nominal, Crowding, and Model error (the scenario that stresses H3's h0
false-alarm behavior under misspecified forward models).
"""

from __future__ import annotations

SCENARIOS = {
    "S1_nominal": {
        "n_satellites": 8,
        "limiting_magnitude_choices": (19.0, 20.0, 21.0),
        "withheld_weight": 1.0,
        "crowding_fraction": 0.0,
        "model_error_factor": 1.0,
        "description": "Full constellation, reference instrument mix, uniform class prior, no contention or model error.",
    },
    "S2_crowding": {
        "n_satellites": 8,
        "limiting_magnitude_choices": (19.0, 20.0, 21.0),
        "withheld_weight": 1.0,
        "crowding_fraction": 0.5,
        "model_error_factor": 1.0,
        "description": "Same as nominal, but half of each event's (time, satellite) cells are unavailable, "
                        "standing in for other events competing for the same instruments.",
    },
    "S3_model_error": {
        "n_satellites": 8,
        "limiting_magnitude_choices": (19.0, 20.0, 21.0),
        "withheld_weight": 1.0,
        "crowding_fraction": 0.0,
        "model_error_factor": 1.3,
        "description": "Same as nominal, but every modeled class's decay timescale is perturbed 30% away from "
                        "the truth in the planner's own belief, stressing h0's false-alarm rate under "
                        "realistic model misspecification (manuscript Scenario 5).",
    },
}


def class_prior_for_scenario(withheld_weight: float, modeled_classes, withheld_classes) -> dict[str, float]:
    weights = {c: 1.0 for c in modeled_classes}
    for c in withheld_classes:
        weights[c] = withheld_weight
    total = sum(weights.values())
    return {c: w / total for c, w in weights.items()}
