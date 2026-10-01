"""
ONE script that applies every patch needed to support robustness.py:
- experiment_config.py: adds declared_robustness_checks field
- db_interface.py: persists the new field
- verdict.py: fixes the applicability-lock bug (Fix 1)
- all 5 existing test files: adds declared_robustness_checks=[] to their helpers
"""

def patch_file(filename, old, new, label):
    content = open(filename, encoding='utf-8').read()
    if old not in content:
        print(filename + " (" + label + "): PATTERN NOT FOUND -- skipped")
        return False
    content = content.replace(old, new, 1)
    open(filename, 'w', encoding='utf-8').write(content)
    print(filename + " (" + label + "): patched successfully")
    return True

# ============================================================
# 1. experiment_config.py
# ============================================================
patch_file('experiment_config.py',
    '''    applicability_lock: Tuple[Tuple[str, bool], ...]
    oos_validation_claimed: bool
    config_hash: str = field(init=False)''',
    '''    applicability_lock: Tuple[Tuple[str, bool], ...]
    oos_validation_claimed: bool
    declared_robustness_checks: Tuple[str, ...]
    config_hash: str = field(init=False)''',
    "add field")

patch_file('experiment_config.py',
    '''            object.__setattr__(self, "applicability_lock", _deep_freeze(tuple(self.applicability_lock)))''',
    '''            object.__setattr__(self, "applicability_lock", _deep_freeze(tuple(self.applicability_lock)))
            object.__setattr__(self, "declared_robustness_checks", _deep_freeze(tuple(self.declared_robustness_checks)))''',
    "freeze field")

# ============================================================
# 2. db_interface.py
# ============================================================
patch_file('db_interface.py',
    '''        new_cols = {
            "config_hash": "TEXT",
            "applicability_lock": "TEXT",       # JSON-serialized tuple-of-pairs
            "oos_validation_claimed": "INTEGER", # boolean
            "testing_family_declaration": "TEXT",
            "state": "TEXT",                     # DRAFT / PREREGISTERED / ... (state machine)
        }''',
    '''        new_cols = {
            "config_hash": "TEXT",
            "applicability_lock": "TEXT",       # JSON-serialized tuple-of-pairs
            "oos_validation_claimed": "INTEGER", # boolean
            "testing_family_declaration": "TEXT",
            "state": "TEXT",                     # DRAFT / PREREGISTERED / ... (state machine)
            "declared_robustness_checks": "TEXT", # JSON-serialized tuple of check names
        }''',
    "add column")

patch_file('db_interface.py',
    '''                config_hash, applicability_lock, oos_validation_claimed, testing_family_declaration, state
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
    '''                config_hash, applicability_lock, oos_validation_claimed, testing_family_declaration, state,
                declared_robustness_checks
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
    "extend INSERT columns")

patch_file('db_interface.py',
    '''            config.config_hash, json.dumps([list(a) for a in config.applicability_lock]),
            int(config.oos_validation_claimed), config.testing_family_declaration, "PREREGISTERED",
        ))''',
    '''            config.config_hash, json.dumps([list(a) for a in config.applicability_lock]),
            int(config.oos_validation_claimed), config.testing_family_declaration, "PREREGISTERED",
            json.dumps(list(config.declared_robustness_checks)),
        ))''',
    "extend INSERT values")

# ============================================================
# 3. verdict.py -- Fix 1 (applicability_lock authoritative)
# ============================================================
patch_file('verdict.py',
    '''def _check_gate_list(experiment_id: str, gate_names: list):
    """Returns {'missing': [...], 'failed': [...]} for a list of gate names,
    using the effective (latest) result for each."""
    missing = []
    failed = []
    for name in gate_names:
        result = get_effective_gate_result(experiment_id, name)
        if result is None:
            missing.append(name)
            continue
        if not result.applicable:
            # A gate locked as not-applicable is simply skipped -- never
            # treated as missing or failed, per the locked semantics.
            continue
        if not result.run:
            missing.append(name)
            continue
        if result.passed is False:
            failed.append(name)
    return {"missing": missing, "failed": failed}''',
    '''def _check_gate_list(experiment_id: str, gate_names: list, experiment_record: dict):
    """
    Returns {'missing': [...], 'failed': [...]} for a list of gate names.
    FIX: applicability_lock is AUTHORITATIVE, checked FIRST, before any
    gate-result row is consulted. A gate locked applicable=False is
    skipped immediately regardless of whether evaluate_gate() was ever
    called for it. Only locked applicable=True requires a result.
    """
    missing = []
    failed = []
    for name in gate_names:
        try:
            is_applicable = gates.get_locked_applicability(experiment_record, name)
        except gates.ApplicabilityNotLockedError:
            missing.append(name)
            continue
        if not is_applicable:
            continue
        result = get_effective_gate_result(experiment_id, name)
        if result is None or not result.run:
            missing.append(name)
            continue
        if result.passed is False:
            failed.append(name)
    return {"missing": missing, "failed": failed}''',
    "fix _check_gate_list")

patch_file('verdict.py', 'import db_interface\n', 'import db_interface\nimport gates\n', "import gates")

patch_file('verdict.py',
    '''    validity_check = _check_gate_list(experiment_id, reqs["validity_required"])''',
    '''    validity_check = _check_gate_list(experiment_id, reqs["validity_required"], experiment_record)''',
    "validity call site")

patch_file('verdict.py',
    '''    evidence_check = _check_gate_list(experiment_id, reqs["evidence_required"])''',
    '''    evidence_check = _check_gate_list(experiment_id, reqs["evidence_required"], experiment_record)''',
    "evidence call site")

patch_file('verdict.py',
    '''    conditional_check = _check_gate_list(experiment_id, claimed_conditional)''',
    '''    conditional_check = _check_gate_list(experiment_id, claimed_conditional, experiment_record)''',
    "conditional call site")

patch_file('verdict.py',
    '''        else:
            # Other conditional evidence types (multiple_testing_survived, robustness_survived
            # when used conditionally) are claimed based on their own applicability_lock entry --
            # if locked applicable=True, they're claimed; if False, they're not.
            result = get_effective_gate_result(experiment_id, cond_name)
            if result is not None and result.applicable:
                claimed_conditional.append(cond_name)''',
    '''        else:
            try:
                is_applicable = gates.get_locked_applicability(experiment_record, cond_name)
            except gates.ApplicabilityNotLockedError:
                is_applicable = False
            if is_applicable:
                claimed_conditional.append(cond_name)''',
    "fix conditional claiming")

# ============================================================
# 4. Patch all 5 existing test files' config helpers
# ============================================================
test_patches = [
    ('test_experiment_config.py',
     '        applicability_lock=[("lookahead_audit", True), ("timestamp_safety", False)],\n        oos_validation_claimed=False,',
     '        applicability_lock=[("lookahead_audit", True), ("timestamp_safety", False)],\n        oos_validation_claimed=False,\n        declared_robustness_checks=[],'),
    ('test_preregistration.py',
     '        applicability_lock=[("lookahead_audit", True), ("timestamp_safety", False)],\n        oos_validation_claimed=False,',
     '        applicability_lock=[("lookahead_audit", True), ("timestamp_safety", False)],\n        oos_validation_claimed=False,\n        declared_robustness_checks=[],'),
    ('test_gates.py',
     '        applicability_lock=applicability_lock,\n        oos_validation_claimed=False,',
     '        applicability_lock=applicability_lock,\n        oos_validation_claimed=False,\n        declared_robustness_checks=[],'),
    ('test_verdict.py',
     '        applicability_lock=applicability_lock,\n        oos_validation_claimed=oos_claimed,',
     '        applicability_lock=applicability_lock,\n        oos_validation_claimed=oos_claimed,\n        declared_robustness_checks=[],'),
    ('test_multiple_testing.py',
     '        applicability_lock=[("lookahead_audit", True)],\n        oos_validation_claimed=False,',
     '        applicability_lock=[("lookahead_audit", True)],\n        oos_validation_claimed=False,\n        declared_robustness_checks=[],'),
]
for fname, old, new in test_patches:
    patch_file(fname, old, new, "add declared_robustness_checks")

# Two extra inline constructions inside test_multiple_testing.py
patch_file('test_multiple_testing.py',
    '''    testing_family_declaration="EXISTING_FAMILY:bad_method_family",
    applicability_lock=[("lookahead_audit", True)], oos_validation_claimed=False,
)''',
    '''    testing_family_declaration="EXISTING_FAMILY:bad_method_family",
    applicability_lock=[("lookahead_audit", True)], oos_validation_claimed=False,
    declared_robustness_checks=[],
)''',
    "config_bad inline")

patch_file('test_multiple_testing.py',
    '''    testing_family_declaration="EXISTING_FAMILY:bh_family",
    applicability_lock=[("lookahead_audit", True)], oos_validation_claimed=False,
)''',
    '''    testing_family_declaration="EXISTING_FAMILY:bh_family",
    applicability_lock=[("lookahead_audit", True)], oos_validation_claimed=False,
    declared_robustness_checks=[],
)''',
    "config_bh inline")

print("\nALL PATCHES COMPLETE.")