from dotenv import load_dotenv
load_dotenv()


def get_trail_pct(gain_pct: float) -> float:
    """Return the trailing stop distance (as % behind peak) based on current gain size.

    Larger gains get tighter trails, protecting more profit as the win grows.
    """
    if gain_pct >= 250:
        return 0.20
    elif gain_pct >= 100:
        return 0.25
    else:
        return 0.30


def update_trailing_stop(
    entry_value: float,
    current_value: float,
    peak_value: float,
    trailing_active: bool,
    activation_threshold_pct: float = 0.40,
) -> dict:
    """
    Determine trailing stop state for an options position.

    Returns updated peak_value, whether trailing is now active, and the current
    trailing stop price (in option value terms) if active.
    """
    peak_value = max(peak_value, current_value)
    gain_pct = (peak_value - entry_value) / entry_value if entry_value > 0 else 0

    if not trailing_active and gain_pct >= activation_threshold_pct:
        trailing_active = True

    trailing_stop_price = None
    if trailing_active:
        trail_pct = get_trail_pct(gain_pct * 100)
        trailing_stop_price = peak_value * (1 - trail_pct)

    return {
        "peak_value": peak_value,
        "trailing_active": trailing_active,
        "trailing_stop_price": trailing_stop_price,
        "current_gain_pct": round(gain_pct * 100, 1),
    }


if __name__ == "__main__":
    # Simulate a contract that runs from $2.00 entry up to $10.00 (400% gain), then check the trail
    entry = 2.00
    peak = 10.00
    state = update_trailing_stop(entry, peak, 0.0, False)
    print(f"At peak ${peak} (gain {state['current_gain_pct']}%):")
    print(f"  Trailing active: {state['trailing_active']}")
    print(f"  Trailing stop price: ${state['trailing_stop_price']:.2f}")
    print(f"  This locks in a minimum gain of: {(state['trailing_stop_price']/entry - 1)*100:.1f}%")