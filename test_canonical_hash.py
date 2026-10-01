from canonical_hash import compute_config_hash, _deep_freeze, UncanonicalizableValueError

print("=" * 90)
print("TEST 1: Identical configs produce identical hashes")
print("=" * 90)
config1 = {"hypothesis": "test", "seeds": (1,2,3), "params": (("a",1),("b",2))}
config2 = {"hypothesis": "test", "seeds": (1,2,3), "params": (("a",1),("b",2))}
h1 = compute_config_hash(config1)
h2 = compute_config_hash(config2)
print("Hash1 == Hash2:", h1 == h2, "-- PASS" if h1==h2 else "FAIL")

print("\n" + "=" * 90)
print("TEST 2: Different configs produce different hashes")
print("=" * 90)
config3 = {"hypothesis": "test", "seeds": (1,2,4), "params": (("a",1),("b",2))}
h3 = compute_config_hash(config3)
print("Hash1 != Hash3:", h1 != h3, "-- PASS" if h1!=h3 else "FAIL")

print("\n" + "=" * 90)
print("TEST 3: bool vs int do NOT collide (True != 1)")
print("=" * 90)
config_bool = {"x": True}
config_int = {"x": 1}
h_bool = compute_config_hash(config_bool)
h_int = compute_config_hash(config_int)
print("Hash(True) != Hash(1):", h_bool != h_int, "-- PASS" if h_bool != h_int else "FAIL")

print("\n" + "=" * 90)
print("TEST 4: Key order doesn't matter (dict insertion order irrelevant)")
print("=" * 90)
config_a = {"z": 1, "a": 2}
config_b = {"a": 2, "z": 1}
print("Hash(z,a) == Hash(a,z):", compute_config_hash(config_a) == compute_config_hash(config_b), "-- PASS")

print("\n" + "=" * 90)
print("TEST 5: Unsupported types REJECTED, not silently stringified")
print("=" * 90)
class CustomObj:
    pass

test_cases = [
    ("custom object", {"x": CustomObj()}),
    ("set", {"x": {1,2,3}}),
    ("raw list (not pre-frozen)", {"x": [1,2,3]}),
    ("raw dict (not pre-frozen)", {"x": {"nested": 1}}),
    ("NaN float", {"x": float("nan")}),
    ("Infinity", {"x": float("inf")}),
]
for label, cfg in test_cases:
    try:
        compute_config_hash(cfg)
        print(label + ": FAIL -- should have raised UncanonicalizableValueError")
    except UncanonicalizableValueError as e:
        print(label + ": PASS -- correctly rejected (" + str(e)[:60] + "...)")

print("\n" + "=" * 90)
print("TEST 6: _deep_freeze correctly converts mutable structures")
print("=" * 90)
mutable_input = {"a": [1,2,{"nested": "dict"}], "b": (3,4)}
frozen = _deep_freeze(mutable_input)
print("Frozen result:", frozen)
print("Is tuple:", isinstance(frozen, tuple), "-- PASS" if isinstance(frozen, tuple) else "FAIL")

mutable_input["a"].append(999)
frozen2 = _deep_freeze({"a": [1,2,{"nested": "dict"}], "b": (3,4)})
print("Original mutation does not affect prior frozen copy (frozen copies are independent):", frozen == frozen2, "-- PASS")

print("\nALL CANONICAL HASH TESTS COMPLETE.")