content = open('spy_gamma_execution.py', encoding='utf-8').read()

old_import = "import options_trade_log\nfrom zoneinfo import ZoneInfo\n"
new_import = old_import + "from trade_reviewer import review_and_store_trade\n"

if old_import not in content:
    print("Could not find import line -- no changes made.")
else:
    content = content.replace(old_import, new_import, 1)
    print("Added trade_reviewer import.")

    old = '''            closed_count += 1
            print("  Closed " + contract_symbol + ": " + exit_reason + ", P&L $" + str(round(pnl_dollars, 2)))
        except Exception as exc:
            print("  Failed to close " + contract_symbol + ": " + str(exc))'''

    new = '''            closed_count += 1
            print("  Closed " + contract_symbol + ": " + exit_reason + ", P&L $" + str(round(pnl_dollars, 2)))

            try:
                _review_data = {
                    "ticker": pos.get("ticker", "SPY"),
                    "contract_symbol": contract_symbol,
                    "option_type": pos["option_type"],
                    "entry_premium": entry_premium,
                    "exit_premium": real_exit_premium,
                    "contracts": contracts,
                    "pnl_dollars": pnl_dollars,
                    "pnl_pct": pnl_pct,
                    "exit_reason": exit_reason,
                    "entry_date": pos["entry_date"],
                    "expiry_date": pos["expiry_date"],
                    "strategy_note": "SPY gamma/charm day-trading bot, tranche: " + _tranche,
                }
                review_and_store_trade(trade_id, _review_data)
                print("  AI review generated for " + contract_symbol)
            except Exception as review_exc:
                print("  AI review failed (trade still closed correctly): " + str(review_exc))
        except Exception as exc:
            print("  Failed to close " + contract_symbol + ": " + str(exc))'''

    if old not in content:
        print("Could not find target -- no changes made to that part.")
    else:
        content = content.replace(old, new, 1)
        print("Wired AI review into the SPY gamma bot's exit logic.")

    with open('spy_gamma_execution.py', 'w', encoding='utf-8') as f:
        f.write(content)