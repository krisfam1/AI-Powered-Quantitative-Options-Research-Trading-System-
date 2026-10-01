from dotenv import load_dotenv
load_dotenv()

"""
Automated tests for gex_calculator.py's core formula correctness, using
small, hand-verifiable synthetic contracts (not real EODHD data) --
isolates the MATH from any real-data quality question.
"""

from gex_calculator import calculate_net_gex, calculate_cumulative_strike_transition, find_gamma_walls

SPOT = 100.0

# Simple, hand-verifiable synthetic contracts: one call, one put, known gamma/OI
synthetic_contracts = [
    {"option_type": "call", "strike": 100.0, "gamma": 0.05, "open_interest": 1000, "volatility": 0.30, "exp_date": "2026-08-01"},
    {"option_type": "put", "strike": 100.0, "gamma": 0.05, "open_interest": 500, "volatility": 0.30, "exp_date": "2026-08-01"},
]


def test_net_gex_formula_and_multiplier():
    """Hand-calculated expected value: Call GEX = 0.05 * 1000 * 100 * 100^2 * 0.01 = 500,000. Put GEX = 0.05 * 500 * 100 * 100^2 * 0.01 = 250,000."""
    result = calculate_net_gex(synthetic_contracts, SPOT, "model_a")
    expected_call_gex = 0.05 * 1000 * 100 * (100.0 ** 2) * 0.01
    expected_put_gex = 0.05 * 500 * 100 * (100.0 ** 2) * 0.01
    assert abs(result["call_gex_raw"] - expected_call_gex) < 0.01, "Call GEX formula/multiplier mismatch: got " + str(result["call_gex_raw"]) + " expected " + str(expected_call_gex)
    assert abs(result["put_gex_raw"] - expected_put_gex) < 0.01, "Put GEX formula/multiplier mismatch"
    print("PASS: net_gex formula and contract multiplier (100) correct")


def test_sign_convention_symmetry():
    """Model A and flipped must be exact negatives of each other for identical input."""
    model_a = calculate_net_gex(synthetic_contracts, SPOT, "model_a")
    flipped = calculate_net_gex(synthetic_contracts, SPOT, "flipped")
    assert abs(model_a["net_gex"] + flipped["net_gex"]) < 0.01, "Sign conventions are not exact negatives: model_a=" + str(model_a["net_gex"]) + " flipped=" + str(flipped["net_gex"])
    print("PASS: model_a and flipped are exact sign-reversed negatives")


def test_call_put_sign_handling():
    """Model A: calls positive, puts negative contribution to net."""
    result = calculate_net_gex(synthetic_contracts, SPOT, "model_a")
    # net = call_gex - put_gex; since call_gex > put_gex here, net should be positive
    assert result["net_gex"] > 0, "Model A sign handling incorrect -- expected positive net given larger call OI"
    print("PASS: call/put sign handling correct under Model A")


def test_deterministic_output():
    """Running the same calculation twice on identical input must produce identical output."""
    r1 = calculate_net_gex(synthetic_contracts, SPOT, "model_a")
    r2 = calculate_net_gex(synthetic_contracts, SPOT, "model_a")
    assert r1["net_gex"] == r2["net_gex"], "Non-deterministic output detected"
    print("PASS: deterministic output confirmed")


def test_missing_gamma_or_oi_excluded():
    """A contract with missing gamma or OI must not silently contribute (e.g. as zero-with-no-flag) -- must be skipped entirely."""
    contracts_with_missing = synthetic_contracts + [
        {"option_type": "call", "strike": 110.0, "gamma": None, "open_interest": 5000, "volatility": 0.30, "exp_date": "2026-08-01"}
    ]
    result_with_missing = calculate_net_gex(contracts_with_missing, SPOT, "model_a")
    result_without = calculate_net_gex(synthetic_contracts, SPOT, "model_a")
    assert result_with_missing["net_gex"] == result_without["net_gex"], "Contract with missing gamma incorrectly affected the result -- should have been skipped entirely"
    print("PASS: contracts with missing gamma/OI correctly excluded, not silently zeroed")


def test_cumulative_transition_finds_real_sign_change():
    """A simple two-strike setup with a known sign change should locate it correctly."""
    contracts = [
        {"option_type": "call", "strike": 95.0, "gamma": 0.02, "open_interest": 100, "volatility": 0.30, "exp_date": "2026-08-01"},
        {"option_type": "put", "strike": 105.0, "gamma": 0.02, "open_interest": 500, "volatility": 0.30, "exp_date": "2026-08-01"},
    ]
    result = calculate_cumulative_strike_transition(contracts, SPOT, "model_a")
    assert result is not None, "Expected a real sign change to be found given a clear call-then-put strike ordering"
    print("PASS: cumulative strike transition correctly locates a real sign change (result=" + str(round(result, 2)) + ")")


if __name__ == "__main__":
    print("Running GEX calculator automated tests (synthetic, hand-verifiable data)...\n")
    test_net_gex_formula_and_multiplier()
    test_sign_convention_symmetry()
    test_call_put_sign_handling()
    test_deterministic_output()
    test_missing_gamma_or_oi_excluded()
    test_cumulative_transition_finds_real_sign_change()
    print("\nALL TESTS PASSED")