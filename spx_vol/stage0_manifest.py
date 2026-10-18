"""Write data_snapshots/spx_vol_engine/manifest.json: source URL, download date, size, SHA-256."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "data_snapshots" / "spx_vol_engine"
ARCHIVE = "https://cdn.cboe.com/resources/futures/archive/volume-and-price/"
DERIVED = {"stage0_audit.json": "derived: spx_vol/stage0_audit.py",
           "eodhd_check/eodhd_coverage_check.json": "derived: spx_vol/stage0_eodhd_check.py (EODHD API; token not stored)",
           "eodhd_check/eodhd_coverage_check_followup.json": "derived: spx_vol/stage0_eodhd_check2.py (EODHD API; token not stored)",
           "_sources.json": "derived: spx_vol/stage0_fetch.py (URL list)"}


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    sources = json.loads((ROOT / "_sources.json").read_text())
    files = {}
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file() or p.name == "manifest.json":
            continue
        rel = p.relative_to(ROOT).as_posix()
        url = sources.get(rel) or DERIVED.get(rel)
        if url is None and rel.startswith("vx_futures/archive/"):
            url = ARCHIVE + p.name
        files[rel] = {
            "source": url or "UNKNOWN",
            "downloaded_utc": datetime.fromtimestamp(p.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "bytes": p.stat().st_size,
            "sha256": sha256(p),
        }
    out = {"created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "purpose": "SPX volatility-state engine, Stage 0 data audit (approved 2026-10-17)",
           "note": "Free public market data only. historicaldata.net sample governed by its LICENSE.txt; "
                   "Yahoo chart data used for research under Yahoo's terms.",
           "files": files}
    (ROOT / "manifest.json").write_text(json.dumps(out, indent=1))
    unknown = [k for k, v in files.items() if v["source"] == "UNKNOWN"]
    print(len(files), "files;", sum(v["bytes"] for v in files.values()), "bytes; unknown source:", unknown)


if __name__ == "__main__":
    main()
