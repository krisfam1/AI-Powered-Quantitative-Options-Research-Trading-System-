from dotenv import load_dotenv
load_dotenv()

from gamma_landscape import build_gamma_landscape, find_gamma_walls
from charm_landscape import build_charm_landscape, find_charm_pins
from daily_levels import extract_daily_levels


def calculate_size_modifier(ticker: str, current_price: float, direction: str = "long") -> dict:
    """
    Calculate a position-size modifier (0.5x to 1.5x) based on gamma/charm/level context.

    This NEVER blocks a trade — it only adjusts size on trades that already qualified
    through the core validated entry signal (volume + breakout + trend + news).

    NOTE: gamma/charm data is a live snapshot, not historically backtested — this
    modifier's real-world effectiveness is being validated via forward-testing
    (logged and reviewed over time), not retroactive backtesting.
    """
    reasons = []
    modifier = 1.0

    try:
        gamma_landscape = build_gamma_landscape(ticker, current_price)
        walls = find_gamma_walls(gamma_landscape, top_n=3)
    except Exception as exc:
        return {"modifier": 1.0, "reasons": [f"gamma data unavailable: {exc}"]}

    if walls:
        nearest_wall = min(walls, key=lambda w: abs(w["strike"] - current_price))
        distance_pct = abs(nearest_wall["strike"] - current_price) / current_price * 100

        if distance_pct < 1.5:
            modifier *= 0.75
            reasons.append(f"near gamma wall at ${nearest_wall['strike']:.2f} ({distance_pct:.1f}% away) — sizing down")
        elif distance_pct > 5.0:
            modifier *= 1.15
            reasons.append(f"clear of gamma walls (nearest {distance_pct:.1f}% away) — sizing up slightly")
        else:
            reasons.append(f"moderate distance from gamma wall ({distance_pct:.1f}%) — no adjustment")

    try:
        levels = extract_daily_levels(ticker)
        sig_levels = levels.get("significant_levels", [])
    except Exception as exc:
        sig_levels = []
        reasons.append(f"level data unavailable: {exc}")

    if sig_levels:
        nearest_level, touches = min(sig_levels, key=lambda x: abs(x[0] - current_price))
        level_distance_pct = abs(nearest_level - current_price) / current_price * 100

        if level_distance_pct < 0.5 and touches >= 4:
            if direction == "long" and current_price < nearest_level:
                reasons.append(f"approaching resistance at ${nearest_level:.2f} ({touches} touches) — no size change, but caution noted")
            elif direction == "long" and current_price > nearest_level:
                modifier *= 1.10
                reasons.append(f"broke above established level ${nearest_level:.2f} ({touches} touches) — sizing up slightly")

    modifier = max(0.5, min(1.5, modifier))

    return {"modifier": round(modifier, 2), "reasons": reasons}


if __name__ == "__main__":
    ticker = "AAPL"
    current_price = 311.29

    result = calculate_size_modifier(ticker, current_price, direction="long")
    print(f"Size modifier for {ticker} at ${current_price}: {result['modifier']}x")
    print("Reasoning:")
    for r in result["reasons"]:
        print(f"  - {r}")