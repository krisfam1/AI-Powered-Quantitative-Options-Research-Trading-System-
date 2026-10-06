"""
Archive pass 4 (2026-10-06, user-approved: CLAUDE.md must be under 150,000 characters counted WITH CRLF).
Moves two blocks of CLAUDE.md verbatim into CLAUDE_ARCHIVE.md under "# Pass 4" and replaces each with a
short stub:
  1. the four "To propagate to the manifest" header bullets;
  2. Section 5's "Phase 6/7 forensic attribution" block (closed V1 work).
Then proves the round trip: replacing each stub in the NEW CLAUDE.md with the archived text (read back from
CLAUDE_ARCHIVE.md, not from memory) must reproduce the backup byte for byte.

  python archive_pass4_20261006.py            # apply + verify
  python archive_pass4_20261006.py --verify   # verify only
"""
import hashlib
import sys

MD, AR = "CLAUDE.md", "CLAUDE_ARCHIVE.md"
MD_BAK, AR_BAK = "CLAUDE.md.pre_archive_pass4_20261006.bak", "CLAUDE_ARCHIVE.md.pre_pass4_20261006.bak"
PASS_HDR = "# Pass 4 — archived 2026-10-06"
END = "<!-- end of pass-4 block -->"
NL = "\r\n"

# (key, archive heading, start marker, end marker [exclusive], stub)
REGIONS = [
    ("header", "## Header: manifest-propagation bullets (pass 4)",
     "- **To propagate to the manifest (2026-10-02):** the cross-sectional",
     NL + NL + "A parallel copy of this content",
     "- **Manifest propagation backlog (condensed 2026-10-06, archive pass 4; the full bullets are verbatim in "
     "`CLAUDE_ARCHIVE.md`, Pass 4):** straddle HELD and ORATS declined (§62); trial #13 registered and REJECTED (§63); "
     "`tiered_v1` and its user-approved judgment calls, no retrofit of IV v2 / SPY GEX v3 (§1); pre-live checklist, "
     "CPCV note, `hypothesis_ledger.csv` (§1); IV literature caution (§33); sleep fixes and Wi-Fi-in-standby (§60); "
     "archive pass 3; F1 HELD (§64); SPY 1-day iron fly HELD (§65). The manifest's section numbers differ from "
     "these (e.g. vol-level control §43, group fixed effects §1/§58, economic check §33 here)."),
    ("5", "## 5. Phase 6/7 forensic attribution block (pass 4)",
     "**Phase 6/7 forensic attribution — expanded with verified numbers, 2026-09-20.**",
     NL + NL + "---" + NL + NL + "## 6.",
     "**Phase 6/7 forensic attribution (condensed 2026-10-06, archive pass 4; the full verified block is verbatim in "
     "`CLAUDE_ARCHIVE.md`, Pass 4; read it before citing a number not repeated here):** Phase 6 day-clustered control "
     "T_obs = −0.2569%, p = 0.996/0.997 (579 signals). Phase 7: stop-loss exits −$66,025.67 vs reversal-guard "
     "+$86,453.30; the top 5 trades are 97.7% of the frozen $20,427.64; position sizing cost −$5,661.48 vs equal "
     "weighting. The underlying back-solve method validated on 251/251 trades. Backfilled rows, not genuine "
     "pre-registration."),
]


def rd(p):
    return open(p, "rb").read().decode("utf-8")


def wr(p, s):
    open(p, "wb").write(s.encode("utf-8"))


def locate(md):
    out = []
    for key, head, sm, em, stub in REGIONS:
        s = md.index(sm)
        assert md.count(sm) == 1, key
        e = md.index(em, s)
        out.append((key, head, s, e, stub))
    return sorted(out, key=lambda t: t[2])


def apply():
    md, ar = rd(MD_BAK), rd(AR_BAK)
    if open(MD, "rb").read() != open(MD_BAK, "rb").read() or open(AR, "rb").read() != open(AR_BAK, "rb").read():
        raise SystemExit("current files differ from the pass-4 backups; refusing to apply")
    regs = locate(md)
    new, pos, blocks = [], 0, []
    for key, head, s, e, stub in regs:
        new += [md[pos:s], stub]
        pos = e
        blocks.append(head + NL + md[s:e] + NL + END + NL + NL)
    new.append(md[pos:])
    pre = (NL + "---" + NL + NL + PASS_HDR + NL + NL +
           "Verbatim from CLAUDE.md as of backup `" + MD_BAK + "` (SHA-256 `"
           + hashlib.sha256(open(MD_BAK, "rb").read()).hexdigest().upper() + "`); archive backup `" + AR_BAK
           + "` (SHA-256 `" + hashlib.sha256(open(AR_BAK, "rb").read()).hexdigest().upper() + "`). User-approved "
           "2026-10-06 to bring CLAUDE.md under 150,000 characters counted with CRLF. Each block below is the exact "
           "text a CLAUDE.md stub replaced, between its heading line and the end marker. Produced and verified by "
           "`archive_pass4_20261006.py`." + NL + NL)
    wr(MD, "".join(new))
    wr(AR, ar + pre + "".join(blocks))


def verify():
    md_new, ar_new, md_bak, ar_bak = rd(MD), rd(AR), rd(MD_BAK), rd(AR_BAK)
    assert ar_new.startswith(ar_bak), "archive: earlier passes were modified"
    p4 = ar_new[ar_new.index(PASS_HDR):]
    rebuilt = md_new
    for key, head, sm, em, stub in REGIONS:
        i = p4.index(head + NL) + len(head + NL)
        j = p4.index(NL + END, i)
        orig = p4[i:j]
        assert rebuilt.count(stub) == 1, f"stub {key} not found exactly once"
        rebuilt = rebuilt.replace(stub, orig)
    ok = rebuilt.encode("utf-8") == md_bak.encode("utf-8")
    print(f"round trip (new CLAUDE.md + archived text == backup, byte for byte): {'PASS' if ok else 'FAIL'}")
    print("archive earlier passes unchanged: PASS")
    for label, s in (("CLAUDE.md before", md_bak), ("CLAUDE.md after", md_new),
                     ("archive before", ar_bak), ("archive after", ar_new)):
        print(f"  {label:17} {len(s):>9,} chars incl. CRLF  {len(s.replace(NL, chr(10))):>9,} chars LF-normalized")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    if "--verify" not in sys.argv:
        apply()
    verify()
