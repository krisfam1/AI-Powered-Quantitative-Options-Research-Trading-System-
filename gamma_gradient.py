from dotenv import load_dotenv
load_dotenv()

from gamma_landscape import build_gamma_landscape


def calculate_gamma_gradient(landscape: list[dict]) -> list[dict]:
    """
    Calculate the rate of change of gamma exposure between adjacent strikes.

    A steep gradient (large jump between neighboring strikes) suggests a
    sharper transition in dealer hedging pressure at that price zone --
    often interpreted as a stronger 'wall' effect than an isolated peak alone.
    """
    if len(landscape) < 2:
        return []

    sorted_landscape = sorted(landscape, key=lambda x: x["strike"])
    gradients = []

    for i in range(1, len(sorted_landscape)):
        prev_strike = sorted_landscape[i - 1]
        curr_strike = sorted_landscape[i]

        strike_diff = curr_strike["strike"] - prev_strike["strike"]
        gamma_diff = curr_strike["gamma_exposure"] - prev_strike["gamma_exposure"]

        if strike_diff <= 0:
            continue

        gradient = gamma_diff / strike_diff
        midpoint = (curr_strike["strike"] + prev_strike["strike"]) / 2

        gradients.append({
            "strike_range": (prev_strike["strike"], curr_strike["strike"]),
            "midpoint": midpoint,
            "gradient": gradient,
        })

    return gradients


def find_steepest_gradient_zones(gradients: list[dict], top_n: int = 3) -> list[dict]:
    """Return the strike zones with the steepest gamma gradient (strongest transition)."""
    sorted_by_magnitude = sorted(gradients, key=lambda x: abs(x["gradient"]), reverse=True)
    return sorted_by_magnitude[:top_n]


if __name__ == "__main__":
    ticker = "AAPL"
    current_price = 309.27

    print("Building gamma landscape for " + ticker + "...")
    landscape = build_gamma_landscape(ticker, current_price)
    print("Found " + str(len(landscape)) + " strikes")

    gradients = calculate_gamma_gradient(landscape)
    print("Calculated " + str(len(gradients)) + " gradient zones")

    steepest = find_steepest_gradient_zones(gradients)
    print("\nSteepest gamma transition zones:")
    for zone in steepest:
        low, high = zone["strike_range"]
        print("  $" + str(low) + " to $" + str(high) + " (midpoint $" + str(round(zone["midpoint"], 2)) + "): gradient=" + str(round(zone["gradient"], 2)))