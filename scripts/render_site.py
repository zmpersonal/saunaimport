#!/usr/bin/env python3
"""Render crawlable static HTML and release artifacts from data/trade.json.

The browser JS remains as progressive enhancement, but the important facts are committed
into HTML so crawlers and non-JS clients receive the same published snapshot.
"""
from __future__ import annotations

import html
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "trade.json"


def money(n):
    if n is None:
        return "—"
    n = float(n)
    if abs(n) >= 1_000_000_000:
        return f"${n/1_000_000_000:.2f}B".replace(".00B", "B")
    if abs(n) >= 1_000_000:
        return f"${n/1_000_000:.1f}M"
    if abs(n) >= 1_000:
        return f"${n/1_000:.1f}K"
    return f"${n:,.0f}"


def pct(n):
    if n is None:
        return "—"
    return f"{'+' if n >= 0 else ''}{n:.1f}%"


def month_label(month):
    return datetime.strptime(month, "%Y-%m").strftime("%B %Y")


def short_month(month):
    return datetime.strptime(month, "%Y-%m").strftime("%b %Y")


def date_label(ts):
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.strftime("%B %-d, %Y")
    except Exception:
        return ts


def change(current, previous):
    if current is None or not previous:
        return None
    return (current / previous - 1) * 100


def get_prev(series, index_from_end):
    if len(series) >= index_from_end:
        return series[-index_from_end]
    return None


def replace_generated(path: Path, key: str, content: str):
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(
        rf"(<!-- GENERATED:{re.escape(key)}:START -->)(.*?)(<!-- GENERATED:{re.escape(key)}:END -->)",
        re.S,
    )
    text2, count = pattern.subn(lambda m: m.group(1) + content + m.group(3), text)
    if count != 1:
        raise RuntimeError(f"Expected one generated block {key} in {path}, found {count}")
    path.write_text(text2, encoding="utf-8")


def category_link(slug):
    return f"/classifications/{slug}.html"


def render_home(data):
    primary = data["categories"][0]
    series = primary.get("series", [])
    latest = series[-1]
    yoyrow = get_prev(series, 13)
    yoy = change(latest.get("general_imports"), yoyrow.get("general_imports") if yoyrow else None)
    countries = "".join(
        f'<div class="country-row"><span>{html.escape(c["name"])}</span><span class="amount">{money(c.get("general_imports"))}</span></div>'
        for c in primary.get("countries", [])[:6]
    )
    coverage = f'{short_month(series[0]["month"])}–{short_month(series[-1]["month"])}'
    p = ROOT / "index.html"
    replace_generated(p, "HOME_STATUS", "Live Census data" if data.get("status") == "live" else "Data unavailable")
    replace_generated(p, "HOME_MONTH", month_label(data["latest_month"]))
    replace_generated(p, "HOME_VALUE", money(latest.get("general_imports")))
    replace_generated(p, "HOME_YOY", pct(yoy))
    replace_generated(p, "HOME_COVERAGE", coverage)
    replace_generated(p, "HOME_COUNTRIES", countries)
    replace_generated(p, "HOME_REPORT_TEXT", f'Read the {month_label(data["latest_month"])} report')
    text = p.read_text(encoding="utf-8")
    text = re.sub(r'(data-latest-report-href[^>]*?href="|href=")(/reports/\d{4}-\d{2}/)("[^>]*data-latest-report-href)', lambda m: m.group(1) + f'/reports/{data["latest_month"]}/' + m.group(3), text, count=1)
    p.write_text(text, encoding="utf-8")
    replace_generated(p, "HOME_UPDATED", date_label(data["last_updated"]))


def render_data_page(data):
    primary = data["categories"][0]
    series = primary["series"]
    coverage = f'{short_month(series[0]["month"])}–{short_month(series[-1]["month"])}'
    country_rows = "".join(
        f'<div class="country-row"><span>{html.escape(c["name"])}</span><span class="amount">{money(c.get("general_imports"))}</span></div>'
        for c in primary.get("countries", [])[:8]
    )
    cat_rows = []
    for cat in data["categories"]:
        last = cat["series"][-1]
        cat_rows.append(
            f'<tr><td><strong>{html.escape(cat["label"])}</strong><br><span class="small">{html.escape(cat["scope_note"])}</span></td>'
            f'<td><span class="code">{html.escape(cat["code"])}</span></td>'
            f'<td>{money(last.get("general_imports"))}</td><td>{money(last.get("consumption_imports"))}</td>'
            f'<td><a href="{category_link(cat["slug"])}">Context</a></td></tr>'
        )
    monthly = []
    for row in series[-12:][::-1]:
        idx = next((i for i, x in enumerate(series) if x["month"] == row["month"]), None)
        prev = series[idx - 12] if idx is not None and idx >= 12 else None
        y = change(row.get("general_imports"), prev.get("general_imports") if prev else None)
        monthly.append(
            f'<tr><td>{html.escape(row["month"])}</td><td>{money(row.get("general_imports"))}</td>'
            f'<td>{money(row.get("consumption_imports"))}</td><td>{pct(y)}</td></tr>'
        )
    citation = (
        f'Sauna Import. “Sauna-Relevant U.S. Import Categories.” U.S. Census Bureau International Trade API. '
        f'Data through {month_label(data["latest_month"])}; site dataset refreshed {date_label(data["last_updated"])}. '
        f'https://saunaimport.com/data/'
    )
    p = ROOT / "data" / "index.html"
    replace_generated(p, "DATA_STATUS", "Live Census data" if data.get("status") == "live" else "Data unavailable")
    replace_generated(p, "DATA_MONTH", month_label(data["latest_month"]))
    replace_generated(p, "DATA_UPDATED", date_label(data["last_updated"]))
    replace_generated(p, "DATA_COVERAGE", coverage)
    replace_generated(p, "DATA_COUNTRIES", country_rows)
    replace_generated(p, "DATA_CATEGORY_TABLE", "".join(cat_rows))
    replace_generated(p, "DATA_MONTHLY_TABLE", "".join(monthly))
    replace_generated(p, "DATA_CITATION", html.escape(citation))
    # Keep the archive link current.
    text = p.read_text(encoding="utf-8")
    text = re.sub(r'/data/archive/\d{4}-\d{2}/', f'/data/archive/{data["latest_month"]}/', text)
    p.write_text(text, encoding="utf-8")


def render_countries(data):
    cards = []
    for cat in data["categories"]:
        rows = "".join(
            f'<div class="country-row"><span>{html.escape(c["name"])}</span><span class="amount">{money(c.get("general_imports"))}</span></div>'
            for c in cat.get("countries", [])[:10]
        )
        cards.append(
            f'<article class="card"><span class="tag">{html.escape(cat["code"])}</span><h3>{html.escape(cat["label"])}</h3>'
            f'<p class="small">{html.escape(cat["scope_note"])}</p><div class="country-list">{rows}</div>'
            f'<p><a class="link" href="{category_link(cat["slug"])}">Classification context →</a></p></article>'
        )
    p = ROOT / "countries" / "index.html"
    replace_generated(p, "COUNTRIES_MONTH", month_label(data["latest_month"]))
    replace_generated(p, "COUNTRIES_BLOCKS", '<div class="grid-3">' + "".join(cards) + '</div>')


def common_head(title, desc, canonical):
    return f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)}</title><meta name="description" content="{html.escape(desc)}"><link rel="canonical" href="{canonical}"><link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="/assets/css/style.css"></head><body>'''


def common_header():
    return '''<header class="site-header"><div class="container nav"><a class="brand" href="/"><span class="brand-mark">SI</span>Sauna Import</a><nav class="nav-links"><a href="/data/">Trade data</a><a href="/classifications/">Classifications</a><a href="/tariffs/">Tariffs</a><a href="/rulings/">CBP rulings</a><a href="/methodology/">Methodology</a></nav><a class="mobile-nav" href="/data/">Explore data →</a></div></header>'''


def common_footer():
    return '''<footer class="footer"><div class="container footer-grid"><div><a class="brand" href="/"><span class="brand-mark" style="background:#f4f0e8;color:#11110f">SI</span>Sauna Import</a><p>Independent reference site for U.S. sauna-related trade, tariff classifications and customs rulings. Category totals are not sauna-only market estimates. Not legal, customs, tariff or brokerage advice.</p></div><div><h3>Research</h3><div class="footer-links"><a href="/data/">Trade data</a><a href="/reports/">Monthly reports</a><a href="/countries/">Countries</a><a href="/classifications/">Classifications</a></div></div><div><h3>Reference</h3><div class="footer-links"><a href="/tariffs/">Tariff research</a><a href="/rulings/">CBP rulings</a><a href="/methodology/">Methodology</a><a href="/resources/">Sources</a></div></div><div><h3>Site</h3><div class="footer-links"><a href="/about/">About & editorial policy</a><a href="/guides/sauna-hts-code/">Sauna HTS guide</a><a href="/where-to-buy/">Where to Buy</a></div></div></div></footer>'''


def render_report(data):
    month = data["latest_month"]
    title_month = month_label(month)
    sections = []
    for cat in data["categories"]:
        s = cat["series"]
        latest = s[-1]
        prev = s[-2] if len(s) > 1 else None
        prev12 = s[-13] if len(s) >= 13 else None
        mom = change(latest.get("general_imports"), prev.get("general_imports") if prev else None)
        yoy = change(latest.get("general_imports"), prev12.get("general_imports") if prev12 else None)
        peak = max(s, key=lambda r: r.get("general_imports", 0))
        origins = cat.get("countries", [])[:5]
        origin_rows = "".join(
            f'<div class="country-row"><span>{html.escape(c["name"])}</span><span class="amount">{money(c.get("general_imports"))}</span></div>'
            for c in origins
        )
        sections.append(f'''<section class="card flat" style="margin-top:18px"><span class="tag">{html.escape(cat["code"])}</span><h3>{html.escape(cat["label"])}</h3><p>{html.escape(cat["scope_note"])}</p><div class="stat-row"><div class="stat"><div class="k">{title_month}</div><div class="v">{money(latest.get("general_imports"))}</div></div><div class="stat"><div class="k">Month over month</div><div class="v">{pct(mom)}</div></div><div class="stat"><div class="k">Year over year</div><div class="v">{pct(yoy)}</div></div><div class="stat"><div class="k">Peak in retained series</div><div class="v">{money(peak.get("general_imports"))}</div><div class="small">{html.escape(peak["month"])}</div></div></div><h4>Top origins in {title_month}</h4><div class="country-list">{origin_rows}</div><p><a class="link" href="{category_link(cat["slug"])}">Classification and scope context →</a></p></section>''')
    primary = data["categories"][0]
    ps = primary["series"]
    latest = ps[-1]
    prev12 = ps[-13] if len(ps) >= 13 else None
    primary_yoy = change(latest.get("general_imports"), prev12.get("general_imports") if prev12 else None)
    desc = f"Monthly analysis of sauna-relevant U.S. tariff categories for {title_month}, with origin rankings and a permanent Census data snapshot."
    report = common_head(f'U.S. Sauna Import Intelligence — {title_month} | Sauna Import', desc, f'https://saunaimport.com/reports/{month}/') + common_header() + f'''<main><div class="container breadcrumbs"><a href="/">Home</a> / <a href="/reports/">Reports</a> / {title_month}</div><section class="page-hero"><div class="container"><span class="eyebrow">Monthly release · {title_month}</span><h1>U.S. Sauna Import Intelligence — {title_month}</h1><p>A dated analysis of the three tariff categories currently supported by sauna-specific CBP precedent. These values describe broad categories, not sauna-only imports.</p></div></section><section class="section" style="padding-top:0"><div class="container"><div class="answer-box"><h2>Release summary</h2><p>General imports under the prefabricated-buildings-of-wood proxy were {money(latest.get("general_imports"))} in {title_month}, {pct(primary_yoy)} versus the same month a year earlier. Country and category details below remain subject to the published scope notes.</p></div>{''.join(sections)}<div style="height:24px"></div><div class="grid-2"><div class="citation-box"><strong>Permanent source snapshot</strong><p><a href="/data/archive/{month}/trade.json">JSON snapshot</a> · <a href="/data/archive/{month}/trade.csv">CSV snapshot</a></p><p class="small">This archive is intended to keep the report reproducible after the live dataset moves forward.</p></div><div class="citation-box"><strong>Suggested report citation</strong><p><code>Sauna Import. “U.S. Sauna Import Intelligence — {title_month}.” Published from U.S. Census Bureau International Trade API data; dataset refreshed {date_label(data["last_updated"])}. https://saunaimport.com/reports/{month}/</code></p></div></div><div style="height:24px"></div><div class="warning"><strong>Do not sum the category totals.</strong> The tracked provisions overlap the sauna industry conceptually, but each includes substantial non-sauna merchandise.</div></div></section></main>''' + common_footer() + '</body></html>'
    p = ROOT / "reports" / month / "index.html"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(report, encoding="utf-8")

    # Reports index: preserve all report directories already present and show newest first.
    reports = sorted([d.name for d in (ROOT / "reports").iterdir() if d.is_dir() and re.fullmatch(r"\d{4}-\d{2}", d.name)], reverse=True)
    cards = []
    for m in reports:
        cards.append(f'<article class="card"><span class="tag">{month_label(m)}</span><h3>U.S. Sauna Import Intelligence — {month_label(m)}</h3><p>Dated analysis with category changes, origin rankings and permanent source snapshot.</p><a class="link" href="/reports/{m}/">Read report →</a></article>')
    index = ROOT / "reports" / "index.html"
    replace_generated(index, "REPORT_LIST", '<div class="grid-2">' + ''.join(cards) + '</div>')


def render_archive_index(data):
    month = data["latest_month"]
    p = ROOT / "data" / "archive" / month / "index.html"
    p.parent.mkdir(parents=True, exist_ok=True)
    body = common_head(f'Data Snapshot — {month_label(month)} | Sauna Import', f'Immutable Sauna Import trade-data snapshot for {month_label(month)}.', f'https://saunaimport.com/data/archive/{month}/') + common_header() + f'''<main><div class="container breadcrumbs"><a href="/">Home</a> / <a href="/data/">Data</a> / Archive / {month}</div><section class="page-hero"><div class="container"><span class="eyebrow">Immutable data snapshot</span><h1>{month_label(month)} release archive</h1><p>This directory preserves the trade dataset used by the {month_label(month)} monthly report.</p></div></section><section class="section" style="padding-top:0"><div class="container grid-2"><div class="card"><h3>Download snapshot</h3><ul class="list-clean"><li><a href="trade.json">trade.json</a></li><li><a href="trade.csv">trade.csv</a></li><li><a href="trade-countries.csv">trade-countries.csv</a></li></ul></div><div class="citation-box"><strong>Snapshot metadata</strong><p>Trade month: {month_label(month)}<br>Site refresh: {date_label(data["last_updated"])}<br>Source: U.S. Census Bureau International Trade API</p></div></div></section></main>''' + common_footer() + '</body></html>'
    p.write_text(body, encoding="utf-8")


def render_sitemap(data):
    fixed = [
        '/', '/data/', '/data/dictionary/', '/countries/', '/classifications/',
        '/classifications/prefabricated-saunas.html', '/classifications/electric-sauna-heaters.html',
        '/classifications/portable-infrared-saunas.html', '/tariffs/', '/rulings/', '/methodology/',
        '/resources/', '/about/', '/where-to-buy/', '/guides/sauna-hts-code/',
        '/guides/general-imports-vs-consumption/', '/guides/cbp-binding-ruling/', '/reports/'
    ]
    for d in sorted((ROOT / 'reports').glob('[0-9][0-9][0-9][0-9]-[0-9][0-9]')):
        if d.is_dir():
            fixed.append(f'/reports/{d.name}/')
    for d in sorted((ROOT / 'data' / 'archive').glob('[0-9][0-9][0-9][0-9]-[0-9][0-9]')) if (ROOT/'data'/'archive').exists() else []:
        if d.is_dir():
            fixed.append(f'/data/archive/{d.name}/')
    lastmod = data.get('last_updated','')[:10]
    urls = ''.join(f'<url><loc>https://saunaimport.com{u}</loc><lastmod>{lastmod}</lastmod></url>\n' for u in fixed)
    (ROOT / 'sitemap.xml').write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'+urls+'</urlset>\n', encoding='utf-8')


def render_all():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    if data.get("status") != "live" or not data.get("categories"):
        raise RuntimeError("trade.json is not a live dataset")
    render_home(data)
    render_data_page(data)
    render_countries(data)
    render_report(data)
    render_archive_index(data)
    render_sitemap(data)


if __name__ == "__main__":
    render_all()
