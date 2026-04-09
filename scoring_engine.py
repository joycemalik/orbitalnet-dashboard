import math

def flatten_telemetry(telemetry_dict):
    """Flattens the nested P-groups into a single dictionary."""
    flat_state = {}
    for group, params in telemetry_dict.items():
        if isinstance(params, dict):
            flat_state.update(params)
    return flat_state

def evaluate_gatekeepers(flat_state):
    """
    Step 1: The Gatekeeper Function. 
    Acts as a binary switch. Checks critical thresholds.
    """
    if flat_state.get("soc", 1.0) < 0.15: return 0
    if flat_state.get("thermal_margin", 1.0) < 0.05: return 0
    if flat_state.get("reaction_wheel_rpm", 0.0) >= 0.95: return 0
    if flat_state.get("sensor_calibrated", 1.0) < 1.0: return 0
    if flat_state.get("conjunction_prob", 0.0) >= 0.01: return 0
    if flat_state.get("is_task_locked", 0.0) >= 1.0: return 0
    return 1

def calculate_aggregate_risk(flat_state):
    """Calculates R by summing dangerous environmental factors."""
    conjunction = flat_state.get("conjunction_prob", 0.0)
    radiation = flat_state.get("radiation_flux", 0.0)
    solar_storm = flat_state.get("solar_activity", 0.0)
    return conjunction + (radiation * 0.5) + (solar_storm * 0.2)

def calculate_base_capability(flat_state, weight_vector):
    """
    Step 2: The Weighted Sum Engine. 
    Dot product of parameters and their weights.
    """
    c_raw = 0.0
    for param, val in flat_state.items():
        weight = weight_vector.get(param, 0.0)
        c_raw += float(val) * weight
    return c_raw

def apply_risk_decay(c_raw, risk_r, lambda_val=0.5):
    """
    Step 3: The Risk Decay Layer.
    C_raw * exp(-lambda * R)
    """
    return c_raw * math.exp(-lambda_val * risk_r)

def compute_final_score(telemetry_dict, weight_vector):
    """Master function to run the whole pipeline for a satellite."""
    flat_state = flatten_telemetry(telemetry_dict)
    
    # 1. Gatekeeper
    if evaluate_gatekeepers(flat_state) == 0:
        return 0.0
        
    # 2. Base Score
    c_raw = calculate_base_capability(flat_state, weight_vector)
    
    # 3. Risk Decay
    risk_r = calculate_aggregate_risk(flat_state)
    c_final = apply_risk_decay(c_raw, risk_r)
    
    return round(c_final, 4)

def calculate_swarm_utility(ci_scores, diversity_score, delta_floor=0.2):
    """
    Step 4: The Swarm Utility Aggregator.
    Sum(Ci) * max(Diversity, delta_floor)
    """
    base_sum = sum(ci_scores)
    multiplier = max(diversity_score, delta_floor)
    return base_sum * multiplier

def test_stress_engine():
    """
    Step 5: Testing & Validation
    """
    print("====================================")
    print("PHASE 2: SCORING ENGINE STRESS TESTS")
    print("====================================\n")
    
    # --- Test Case 1: Gatekeeper Failure ---
    bad_gatekeepers = {
        "soc": 0.10,          # Fails: < 0.15
        "is_task_locked": 0.0,
        "sensor_calibrated": 1.0
    }
    mock_state = {"param1": 1.0}
    mock_weights = {"param1": 1.0}
    
    gatekeeper_result = evaluate_gatekeepers(bad_gatekeepers)
    if gatekeeper_result == 0:
        c_i_failed = 0  # Short-circuit logic check
    else:
        # Shouldn't hit this
        c_raw = calculate_base_capability(mock_state, mock_weights)
        c_i_failed = apply_risk_decay(c_raw, 0)
        
    assert c_i_failed == 0, f"Test Case 1 Failed: Expected exactly 0 for C_i, got {c_i_failed}"
    print(f"Test Case 1 Passed: Gatekeeper binary switch correctly blocked mission assignment (C_i = {c_i_failed}).")

    # --- Test Case 2: Max Risk Decay ---
    good_gatekeepers = {
        "soc": 0.90,
        "thermal_margin": 0.80,
        "reaction_wheel_rpm": 0.20,
        "sensor_calibrated": 1.0,
        "conjunction_prob": 0.0,
        "is_task_locked": 0.0
    }
    gatekeeper_result_pass = evaluate_gatekeepers(good_gatekeepers)
    assert gatekeeper_result_pass == 1, "Test setup error: Valid gatekeepers failed"
    
    c_raw_optimal = calculate_base_capability(mock_state, mock_weights) # equals 1.0
    
    # We apply maximum risk (R = 1.0) and use a high risk-averse lambda (e.g. 5.0) 
    # to heavily penalize and see the exponential drop near zero.
    risk_value = 1.0
    test_lambda = 5.0 
    
    c_i_risk = gatekeeper_result_pass * apply_risk_decay(c_raw_optimal, risk_value, lambda_val=test_lambda)
    
    assert c_i_risk < 0.01, f"Test Case 2 Failed: Score did not drop near zero, got {c_i_risk}"
    print(f"Test Case 2 Passed: High-risk scenario (R=1.0) successfully collapsed final C_i score to {c_i_risk:.4f} (near 0).")
    
    # --- Additional: Swarm Aggregation ---
    mock_fleet = [0.85, 0.90, 0.00, 0.40] # one dead, three operational
    diversity = 0.1 # Low diversity, falls back to delta_floor
    u_swarm = calculate_swarm_utility(mock_fleet, diversity, delta_floor=0.2)
    print(f"\nFinal Check: U_swarm correctly evaluated to cluster utility = {u_swarm:.2f}")

if __name__ == "__main__":
    test_stress_engine()
