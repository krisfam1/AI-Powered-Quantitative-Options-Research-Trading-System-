from dotenv import load_dotenv
load_dotenv()

import sqlite3

with sqlite3.connect("trade_reviews.db") as conn:
    cur = conn.cursor()
    cur.execute("SELECT trade_id, reviewed_at, review_text FROM trade_reviews ORDER BY reviewed_at DESC")
    rows = cur.fetchall()

print("Total AI trade reviews: " + str(len(rows)) + "\n")

if not rows:
    print("No reviews yet -- reviews are generated automatically when a real trade closes.")
else:
    for trade_id, reviewed_at, review_text in rows:
        print("=" * 70)
        print("Trade: " + trade_id)
        print("Reviewed: " + reviewed_at)
        print("-" * 70)
        print(review_text)
        print()