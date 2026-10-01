from dotenv import load_dotenv
load_dotenv()

from options_evaluator import get_live_premium
from options_data import get_options_chain

contracts_to_verify = [
    "TSLA260831P00342500",
    "AMD260831P00480000",
    "AMD260831P00465000",
]

print("Verifying today's shadow-selected contracts are real, tradeable contracts:\n")

for symbol in contracts_to_verify:
    try:
        premium = get_live_premium(symbol)
        print(symbol + ": VALID -- current live premium $" + str(round(premium, 2)))
    except Exception as exc:
        print(symbol + ": ERROR -- " + str(exc))