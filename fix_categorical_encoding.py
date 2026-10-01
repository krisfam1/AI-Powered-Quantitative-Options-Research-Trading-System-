content = open('ml_experiment1_final_executor.py', encoding='utf-8').read()

old = '''    def extract(rows, feature_names):
        X = np.array([[r[f] for f in feature_names] for r in rows])
        y = np.array([r["target"] for r in rows])
        return X, y'''

new = '''    def _encode_value(v):
        if isinstance(v, str):
            return {"bullish": 1.0, "neutral": 0.0, "bearish": -1.0}.get(v, 0.0)
        return float(v)

    def extract(rows, feature_names):
        X = np.array([[_encode_value(r[f]) for f in feature_names] for r in rows])
        y = np.array([r["target"] for r in rows])
        return X, y'''

if old not in content:
    print("PATCH A not found -- aborting.")
else:
    content = content.replace(old, new, 1)

    old2 = '''    return {
        "gate_results": gate_results,'''
    new2 = '''    spy_trend_values = set(r.get("spy_trend_state") for r in train_rows + val_rows + primary_rows)

    return {
        "gate_results": gate_results,'''
    if old2 not in content:
        print("PATCH B not found -- aborting.")
    else:
        content = content.replace(old2, new2, 1)

        old3 = '''            "alpha_baseline": alpha_a, "alpha_full": alpha_b,
        }
    }'''
        new3 = '''            "alpha_baseline": alpha_a, "alpha_full": alpha_b,
            "spy_trend_state_unique_values": list(spy_trend_values),
        }
    }'''
        if old3 not in content:
            print("PATCH C not found -- aborting.")
        else:
            content = content.replace(old3, new3, 1)
            with open('ml_experiment1_final_executor.py', 'w', encoding='utf-8') as f:
                f.write(content)
            print("All patches applied successfully.")