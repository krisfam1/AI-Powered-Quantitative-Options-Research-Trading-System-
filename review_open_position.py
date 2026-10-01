from dotenv import load_dotenv
load_dotenv()

import os
import anthropic
from options_evaluator import get_live_bid_price
from contract_price_extremes import get_contract_price_extremes
from datetime import date

api_key = os.environ.get("ANTHROPIC_API_KEY")
client = anthropic.Anthropic(api_key=api_key)


def review_open_position(contract_symbol: str, entry_premium: float, entry_date: str, ticker: str, option_type: str) -> str:
    """
    Generate an honest, current-status review of an OPEN (not yet closed)
    position -- current standing, not a final outcome.
    """
    current_bid = get_live_bid_price(contract_symbol)
    pct_change = (current_bid - entry_premium) / entry_premium * 100 if entry_premium > 0 else 0

    extremes = get_contract_price_extremes(contract_symbol, entry_date, date.today().isoformat())

    trade_data = {
        "ticker": ticker,
        "contract_symbol": contract_symbol,
        "option_type": option_type,
        "entry_premium": entry_premium,
        "current_premium": round(current_bid, 2),
        "current_pct_change": round(pct_change, 1),
        "entry_date": entry_date,
        "status": "STILL OPEN -- not yet closed",
    }
    if "error" not in extremes:
        trade_data["price_extremes_so_far"] = extremes

    prompt = (
        "This options position is STILL OPEN (not yet closed) -- give an honest, "
        "current-status check-in, not a final verdict. Note its current standing "
        "relative to entry, what the peak/trough so far suggests about its path, "
        "and anything worth watching. Do NOT suggest specific code changes. "
        "Keep it concise, 3-5 sentences.\n\nTrade data:\n" + str(trade_data)
    )

    message = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text


if __name__ == "__main__":
    review = review_open_position(
        contract_symbol="TSLA260831P00345000",
        entry_premium=4.30,
        entry_date="2026-08-25",
        ticker="TSLA",
        option_type="put",
    )
    print(review)