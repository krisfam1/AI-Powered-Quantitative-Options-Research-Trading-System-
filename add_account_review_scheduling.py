content = open('account_review.py', encoding='utf-8').read()

addition = '''

def should_run_weekly_account_review() -> bool:
    """Check whether 7+ days have passed since the last account review."""
    import sqlite3
    from datetime import datetime, timezone, timedelta

    with sqlite3.connect("account_reviews.db") as conn:
        row = conn.execute("SELECT generated_at FROM account_reviews ORDER BY generated_at DESC LIMIT 1").fetchone()

    if row is None:
        return True

    last_run = datetime.fromisoformat(row[0])
    return (datetime.now(timezone.utc) - last_run) >= timedelta(days=7)
'''

if "def should_run_weekly_account_review" in content:
    print("Already present -- no changes made.")
else:
    content = content.rstrip() + "\n" + addition
    with open('account_review.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Added should_run_weekly_account_review scheduling function.")