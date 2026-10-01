content = open('options_shadow_loop.py', encoding='utf-8').read()

old_import = "from daily_price_audit import should_run_daily_audit, run_daily_price_audit\n"
new_import = old_import + "from account_review import should_run_weekly_account_review, generate_account_review\n"

if old_import not in content:
    print("Could not find import line -- no changes made.")
else:
    content = content.replace(old_import, new_import, 1)
    print("Added import.")

    old_check = '''        if should_run_daily_audit():
            try:
                audit_result = run_daily_price_audit()
                print("  Daily price audit: checked " + str(audit_result["trades_checked"]) + " trades, corrected " + str(audit_result["mismatches_found"]) + " mismatch(es).")
            except Exception as _audit_exc:
                print("  Daily price audit failed: " + str(_audit_exc))'''

    new_check = old_check + '''

        if should_run_weekly_account_review():
            try:
                _account_review_text = generate_account_review()
                print("  Weekly account review generated (" + str(len(_account_review_text)) + " chars).")
            except Exception as _review_exc:
                print("  Weekly account review failed: " + str(_review_exc))'''

    if old_check not in content:
        print("Could not find insertion point -- no changes made to that part.")
    else:
        content = content.replace(old_check, new_check, 1)
        print("Wired weekly account review into the automatic loop.")

    with open('options_shadow_loop.py', 'w', encoding='utf-8') as f:
        f.write(content)