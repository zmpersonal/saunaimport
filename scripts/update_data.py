#!/usr/bin/env python3
"""Fetch Census trade data for sauna-relevant HTS categories and regenerate static outputs.

Requires CENSUS_API_KEY. Uses official Census International Trade hsimport endpoint.
The configured categories are broad proxies. The script never sums them into a claimed
'sauna market size' because each category contains non-sauna merchandise.
"""
from __future__ import annotations
import csv, json, os, sys, urllib.parse, urllib.request
from datetime import date, datetime
from pathlib import Path
from collections import defaultdict

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.census.gov/data/timeseries/intltrade/imports/hsimport"
KEY = os.environ.get("CENSUS_API_KEY")


def month_shift(y: int, m: int, delta: int):
    idx = y * 12 + (m - 1) + delta
    return idx // 12, idx % 12 + 1


def api_get(params):
    q = urllib.parse.urlencode(
        params,
        quote_via=urllib.parse.quote_plus,
        safe=':*+'
    )

    req = urllib.request.Request(
        f"{API}?{q}",
        headers={"User-Agent": "SaunaImport.com data updater/1.0"}
    )

    with urllib.request.urlopen(req, timeout=45) as r:
        raw = r.read().decode("utf-8")

    # Census may return an empty response when a requested
    # statistical month has not been released yet.
    if not raw.strip():
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"Census API returned a non-JSON response: {raw[:500]!r}"
        ) from e

    if not isinstance(data, list) or len(data) < 2:
        return []

    headers = data[0]
    return [dict(zip(headers, row)) for row in data[1:]]


def find_latest(code: str) -> str:
    today = date.today()
    # Trade releases lag the calendar month; start at previous month and walk back.
    for back in range(1, 7):
        y, m = month_shift(today.year, today.month, -back)
        month = f"{y:04d}-{m:02d}"
        rows = api_get({
            "get":"NAME,YEAR,MONTH,GEN_VAL_MO",
            "for":"world:1",
            "time":month,
            "I_COMMODITY":code,
            "key":KEY,
        })
        if rows and any(int(r.get("GEN_VAL_MO") or 0) >= 0 for r in rows):
            return month
    raise RuntimeError("Could not identify a recent Census trade month.")


def series_for(code: str, end_month: str, months: int = 36):
    ey, em = map(int, end_month.split('-'))
    sy, sm = month_shift(ey, em, -(months-1))
    start_month = f"{sy:04d}-{sm:02d}"
    rows = api_get({
        "get":"NAME,YEAR,MONTH,GEN_VAL_MO,GEN_VAL_YR,CON_VAL_MO,CON_VAL_YR,LAST_UPDATE",
        "for":"world:1",
        "time":f"from+{start_month}+to+{end_month}",
        "I_COMMODITY":code,
        "key":KEY,
    })
    out = {}
    for r in rows:
        key = f"{r['YEAR']}-{r['MONTH']}"
        values = {
            "month": key,
            "general_imports": int(r.get("GEN_VAL_MO") or 0),
            "consumption_imports": int(r.get("CON_VAL_MO") or 0),
            "general_ytd": int(r.get("GEN_VAL_YR") or 0),
            "consumption_ytd": int(r.get("CON_VAL_YR") or 0),
            "census_last_update": r.get("LAST_UPDATE") or None,
        }
        if key in out and out[key] != values:
            raise RuntimeError(f"Ambiguous duplicate Census rows for {code} {key}; refusing to publish silently.")
        out[key] = values
    return [out[k] for k in sorted(out)]


def countries_for(code: str, month: str):
    rows = api_get({
        "get":"NAME,GEN_VAL_MO,CON_VAL_MO",
        "for":"usitc standard countries and areas:*",
        "time":month,
        "I_COMMODITY":code,
        "key":KEY,
    })
    seen = {}
    for r in rows:
        name = r.get("NAME", "").strip()
        if not name or name.lower().startswith("world"):
            continue
        item = {"name":name, "general_imports":int(r.get("GEN_VAL_MO") or 0), "consumption_imports":int(r.get("CON_VAL_MO") or 0)}
        if name in seen and seen[name] != item:
            raise RuntimeError(f"Ambiguous duplicate country rows for {code} {month} {name}.")
        seen[name] = item
    return sorted(seen.values(), key=lambda x:x["general_imports"], reverse=True)


def write_csv(categories):
    path = ROOT / "data" / "trade.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["hts_code","category","month","general_imports_usd","consumption_imports_usd"])
        for cat in categories:
            for row in cat["series"]:
                w.writerow([cat["code"],cat["label"],row["month"],row["general_imports"],row["consumption_imports"]])


def main():
    if not KEY:
        print("CENSUS_API_KEY is required.", file=sys.stderr)
        sys.exit(2)
    classifications = json.loads((ROOT / "data" / "classifications.json").read_text())
    latest = find_latest(classifications[0]["code"])
    categories = []
    for c in classifications:
        print(f"Fetching {c['code']}…")
        categories.append({
            "code": c["short_code"],
            "api_code": c["code"],
            "slug": c["slug"],
            "label": c["label"],
            "scope_note": c["scope_note"],
            "series": series_for(c["code"], latest),
            "countries": countries_for(c["code"], latest),
        })
    payload = {
        "status":"live",
        "last_updated":datetime.utcnow().replace(microsecond=0).isoformat()+"Z",
        "latest_month":latest,
        "source":"U.S. Census Bureau International Trade API",
        "methodology":"Category-level proxy data only. HTS categories include non-sauna merchandise; categories are not summed into a sauna market-size estimate.",
        "categories":categories,
    }
    (ROOT / "data" / "trade.json").write_text(json.dumps(payload, indent=2)+"\n")
    write_csv(categories)
    print(f"Updated through {latest}")

if __name__ == "__main__":
    main()
