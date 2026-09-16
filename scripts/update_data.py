#!/usr/bin/env python3
"""Fetch Census trade data for sauna-relevant HTS categories and regenerate static outputs.

Requires CENSUS_API_KEY. Uses official Census International Trade hsimport endpoint.
The configured categories are broad proxies. The script never sums them into a claimed
'sauna market size' because each category contains non-sauna merchandise.
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.census.gov/data/timeseries/intltrade/imports/hsimport"
KEY = os.environ.get("CENSUS_API_KEY")
HISTORY_START = "2010-01"


def month_shift(y: int, m: int, delta: int):
    idx = y * 12 + (m - 1) + delta
    return idx // 12, idx % 12 + 1


def month_range(start_month: str, end_month: str, chunk_months: int = 48):
    sy, sm = map(int, start_month.split("-"))
    ey, em = map(int, end_month.split("-"))
    current_y, current_m = sy, sm
    while (current_y, current_m) <= (ey, em):
        cy, cm = month_shift(current_y, current_m, chunk_months - 1)
        if (cy, cm) > (ey, em):
            cy, cm = ey, em
        yield f"{current_y:04d}-{current_m:02d}", f"{cy:04d}-{cm:02d}"
        current_y, current_m = month_shift(cy, cm, 1)


def api_get(params):
    q = urllib.parse.urlencode(params, quote_via=urllib.parse.quote_plus, safe=":*+")
    req = urllib.request.Request(
        f"{API}?{q}", headers={"User-Agent": "SaunaImport.com data updater/2.0"}
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        raw = r.read().decode("utf-8")
    if not raw.strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Census API returned a non-JSON response: {raw[:500]!r}") from e
    if not isinstance(data, list) or len(data) < 2:
        return []
    headers = data[0]
    return [dict(zip(headers, row)) for row in data[1:]]


def find_latest(code: str) -> str:
    today = date.today()
    for back in range(1, 8):
        y, m = month_shift(today.year, today.month, -back)
        month = f"{y:04d}-{m:02d}"
        rows = api_get({
            "get": "NAME,YEAR,MONTH,GEN_VAL_MO",
            "for": "world:1",
            "time": month,
            "I_COMMODITY": code,
            "key": KEY,
        })
        if rows and any(int(r.get("GEN_VAL_MO") or 0) >= 0 for r in rows):
            return month
    raise RuntimeError("Could not identify a recent Census trade month.")


def series_for_segment(code: str, start_month: str, end_month: str, display_code: str):
    out = {}
    for chunk_start, chunk_end in month_range(start_month, end_month):
        rows = api_get({
            "get": "NAME,YEAR,MONTH,GEN_VAL_MO,GEN_VAL_YR,CON_VAL_MO,CON_VAL_YR,LAST_UPDATE,RP,CTY_SUBCODE",
            "for": "world:1",
            "time": f"from+{chunk_start}+to+{chunk_end}",
            "I_COMMODITY": code,
            "key": KEY,
        })
        for r in rows:
            key = f"{r['YEAR']}-{r['MONTH']}"
            if key not in out:
                out[key] = {
                    "month": key,
                    "source_code": display_code,
                    "general_imports": 0,
                    "consumption_imports": 0,
                    "general_ytd": 0,
                    "consumption_ytd": 0,
                    "census_last_update": None,
                }
            out[key]["general_imports"] += int(r.get("GEN_VAL_MO") or 0)
            out[key]["consumption_imports"] += int(r.get("CON_VAL_MO") or 0)
            out[key]["general_ytd"] += int(r.get("GEN_VAL_YR") or 0)
            out[key]["consumption_ytd"] += int(r.get("CON_VAL_YR") or 0)
            last_update = r.get("LAST_UPDATE")
            if last_update:
                current = out[key]["census_last_update"]
                if current is None or last_update > current:
                    out[key]["census_last_update"] = last_update
    return out


def series_for_history(classification: dict, end_month: str):
    combined = {}
    segments = classification.get("history_segments") or [{
        "code": classification["code"],
        "display_code": classification["short_code"],
        "start": HISTORY_START,
        "end": None,
    }]
    for segment in segments:
        seg_start = max(segment.get("start") or HISTORY_START, HISTORY_START)
        seg_end = min(segment.get("end") or end_month, end_month)
        if seg_start > seg_end:
            continue
        rows = series_for_segment(segment["code"], seg_start, seg_end, segment.get("display_code") or segment["code"])
        overlap = set(combined).intersection(rows)
        if overlap:
            raise RuntimeError(f"Historical code segments overlap for {classification['slug']}: {sorted(overlap)[:3]}")
        combined.update(rows)
    return [combined[k] for k in sorted(combined)]


def countries_for(code: str, month: str):
    rows = api_get({
        "get": "NAME,GEN_VAL_MO,CON_VAL_MO,RP,CTY_SUBCODE",
        "for": "usitc standard countries and areas:*",
        "time": month,
        "I_COMMODITY": code,
        "key": KEY,
    })
    seen = {}
    for r in rows:
        name = r.get("NAME", "").strip()
        if not name or name.lower().startswith("world"):
            continue
        if name not in seen:
            seen[name] = {"name": name, "general_imports": 0, "consumption_imports": 0}
        seen[name]["general_imports"] += int(r.get("GEN_VAL_MO") or 0)
        seen[name]["consumption_imports"] += int(r.get("CON_VAL_MO") or 0)
    return sorted(seen.values(), key=lambda x: x["general_imports"], reverse=True)


def write_csv(categories, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "hts_code", "source_code", "category", "month", "general_imports_usd",
            "consumption_imports_usd", "general_ytd_usd", "consumption_ytd_usd",
            "census_last_update", "scope_note"
        ])
        for cat in categories:
            for row in cat["series"]:
                w.writerow([
                    cat["code"], row.get("source_code", cat["code"]), cat["label"], row["month"], row["general_imports"],
                    row["consumption_imports"], row.get("general_ytd"), row.get("consumption_ytd"),
                    row.get("census_last_update"), cat["scope_note"]
                ])


def write_country_csv(categories, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["hts_code", "category", "month", "country", "general_imports_usd", "consumption_imports_usd", "scope_note"])
        for cat in categories:
            month = cat["series"][-1]["month"] if cat["series"] else ""
            for row in cat["countries"]:
                w.writerow([cat["code"], cat["label"], month, row["name"], row["general_imports"], row["consumption_imports"], cat["scope_note"]])


def write_snapshot(payload):
    month = payload["latest_month"]
    archive = ROOT / "data" / "archive" / month
    archive.mkdir(parents=True, exist_ok=True)
    (archive / "trade.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    write_csv(payload["categories"], archive / "trade.csv")
    write_country_csv(payload["categories"], archive / "trade-countries.csv")


def main():
    if not KEY:
        print("CENSUS_API_KEY is required.", file=sys.stderr)
        sys.exit(2)
    classifications = json.loads((ROOT / "data" / "classifications.json").read_text(encoding="utf-8"))
    latest = find_latest(classifications[0]["code"])
    categories = []
    for c in classifications:
        print(f"Fetching {c['code']} history from {HISTORY_START} through {latest}…")
        categories.append({
            "code": c["short_code"],
            "api_code": c["code"],
            "slug": c["slug"],
            "label": c["label"],
            "scope_note": c["scope_note"],
            "series": series_for_history(c, latest),
            "history_segments": c.get("history_segments", []),
            "countries": countries_for(c["code"], latest),
        })
    payload = {
        "status": "live",
        "last_updated": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "latest_month": latest,
        "history_start": HISTORY_START,
        "source": "U.S. Census Bureau International Trade API",
        "methodology": "Category-level proxy data only. HTS categories include non-sauna merchandise; categories are not summed into a sauna market-size estimate.",
        "categories": categories,
    }
    (ROOT / "data" / "trade.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    write_csv(categories, ROOT / "data" / "trade.csv")
    write_country_csv(categories, ROOT / "data" / "trade-countries.csv")
    write_snapshot(payload)

    # Render static HTML after the data files exist.
    sys.path.insert(0, str(ROOT / "scripts"))
    from render_site import render_all
    render_all()
    print(f"Updated and rendered through {latest}")


if __name__ == "__main__":
    main()
