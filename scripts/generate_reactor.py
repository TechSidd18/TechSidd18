#!/usr/bin/env python3
"""Reactor Output: radial 52-week contribution chart (self-hosted SVG, no external images).
Data: GitHub GraphQL (GITHUB_TOKEN) -> falls back to scraping the public contributions page.
Usage: python3 scripts/generate_reactor.py [--sample]"""
import os, re, sys, json, math, html, datetime as dt, urllib.request

USER = os.environ.get("GH_USER") or os.environ.get("GITHUB_REPOSITORY_OWNER") or "TechSidd18"
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "reactor.svg")
GOLD, GOLD2, RED, RED2 = "#C8A45C", "#E6C77E", "#A4161A", "#C8242A"
TXT, MUT, HAIR, BG = "#E8E6E1", "#8C867A", "#2A2620", "#0D0D0F"
MONO = "'SF Mono','Cascadia Mono',Consolas,'Liberation Mono',monospace"
SANS = "'Segoe UI',-apple-system,Helvetica,Arial,sans-serif"

def http(url, data=None, headers=None):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def from_graphql(token):
    q = {"query": "query($u:String!){user(login:$u){contributionsCollection{contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}}}}",
         "variables": {"u": USER}}
    raw = http("https://api.github.com/graphql", json.dumps(q).encode(),
               {"Authorization": f"bearer {token}", "Content-Type": "application/json", "User-Agent": "reactor-gen"})
    weeks = json.loads(raw)["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    return {d["date"]: d["contributionCount"] for w in weeks for d in w["contributionDays"]}

def from_html():
    page = http(f"https://github.com/users/{USER}/contributions", headers={"User-Agent": "Mozilla/5.0"})
    days = {}
    tips = {m.group(1): m.group(2) for m in re.finditer(r'for="([^"]+)"[^>]*>\s*([^<]+?)\s*</tool-tip>', page)}
    for m in re.finditer(r'<td\b[^>]*>', page):
        tag = m.group(0)
        d = re.search(r'data-date="(\d{4}-\d{2}-\d{2})"', tag)
        i = re.search(r'\bid="([^"]+)"', tag)
        if not d or not i: continue
        t = tips.get(i.group(1), "")
        n = re.match(r"(\d+) contribution", t)
        days[d.group(1)] = int(n.group(1)) if n else 0
    if not days: raise RuntimeError("no calendar data")
    return days

def sample():
    # placeholder used only for local preview; the workflow replaces it with live data
    return {"2026-09-30": 4, "2026-10-23": 34}

def fill_year(days):
    end = dt.date.today()
    if days: end = max(end, max(dt.date.fromisoformat(d) for d in days))
    start = end - dt.timedelta(days=363)
    series = []
    d = start
    while d <= end:
        series.append((d, days.get(d.isoformat(), 0))); d += dt.timedelta(days=1)
    return series

def esc(s): return html.escape(str(s), quote=True)

def build(series):
    total = sum(v for _, v in series)
    active = sum(1 for _, v in series if v > 0)
    peak_d, peak_v = max(series, key=lambda x: x[1])
    longest = cur = 0
    for _, v in series:
        cur = cur + 1 if v > 0 else 0; longest = max(longest, cur)
    cs = 0
    for _, v in reversed(series):
        if v > 0: cs += 1
        elif cs == 0 and _ == series[-1][0]: continue  # today empty doesn't break a streak yet
        else: break
    weeks = [series[i:i + 7] for i in range(0, len(series), 7)]
    wsum = [sum(v for _, v in w) for w in weeks]
    nW = len(weeks); wmax = max(wsum) or 1
    bw_i = max(range(nW), key=lambda i: wsum[i])
    CX, CY, RIN, RMAX = 270, 258, 74, 170
    W, H = 1000, 470
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Contribution reactor: {total} contributions in the last 52 weeks">']
    o.append(f'<defs><radialGradient id="rc" cx="50%" cy="50%" r="50%"><stop offset="0" stop-color="#F3E2B5" stop-opacity=".55"/><stop offset=".5" stop-color="{GOLD}" stop-opacity=".18"/><stop offset="1" stop-color="{RED}" stop-opacity="0"/></radialGradient></defs>')
    o.append(f'<rect width="{W}" height="{H}" rx="10" fill="{BG}"/>')
    o.append(f'<circle cx="40" cy="34" r="4" fill="{RED}"><animate attributeName="opacity" values="1;.35;1" dur="2.4s" repeatCount="indefinite"/></circle>')
    o.append(f'<text x="54" y="38" font-family="{MONO}" font-size="11" letter-spacing="2.2" fill="{GOLD}">REACTOR OUTPUT</text>')
    o.append(f'<text x="960" y="38" text-anchor="end" font-family="{MONO}" font-size="11" letter-spacing="2.2" fill="{MUT}">{nW} WEEKS · {total} CONTRIBUTIONS</text>')
    o.append(f'<line x1="40" y1="52" x2="960" y2="52" stroke="{HAIR}"/>')
    for r, op in ((RIN, .5), ((RIN + RMAX) / 2, .25), (RMAX, .35)):
        o.append(f'<circle cx="{CX}" cy="{CY}" r="{r}" fill="none" stroke="{GOLD}" stroke-dasharray="2 5" opacity="{op}"/>')
    # sweep (trailing wedges)
    sw = ['<g>', f'<animateTransform attributeName="transform" type="rotate" from="0 {CX} {CY}" to="360 {CX} {CY}" dur="14s" repeatCount="indefinite"/>']
    for k in range(12):
        a0, a1 = -k * 2.5, -(k + 1) * 2.5
        p = lambda a, r: (CX + r * math.sin(math.radians(a)), CY - r * math.cos(math.radians(a)))
        x0, y0 = p(a0, RMAX); x1, y1 = p(a1, RMAX)
        sw.append(f'<path d="M{CX} {CY} L{x0:.1f} {y0:.1f} A{RMAX} {RMAX} 0 0 0 {x1:.1f} {y1:.1f} Z" fill="{GOLD}" opacity="{0.10 * (1 - k / 12):.3f}"/>')
    sw.append(f'<line x1="{CX}" y1="{CY - RIN}" x2="{CX}" y2="{CY - RMAX}" stroke="{GOLD2}" stroke-width="1" opacity=".55"/></g>')
    o.append("".join(sw))
    # spokes (one per week, clockwise from oldest at top)
    for i, s in enumerate(wsum):
        a = math.radians(i * 360 / nW - 90)
        ca, sa = math.cos(a), math.sin(a)
        if s == 0:
            r2 = RIN + 7
            o.append(f'<line x1="{CX + RIN * ca:.1f}" y1="{CY + RIN * sa:.1f}" x2="{CX + r2 * ca:.1f}" y2="{CY + r2 * sa:.1f}" stroke="{GOLD}" stroke-width="2" stroke-linecap="round" opacity=".28"/>')
        else:
            ln = 22 + (RMAX - RIN - 22) * math.sqrt(s / wmax)
            r2 = RIN + ln
            x2, y2 = CX + r2 * ca, CY + r2 * sa
            o.append(f'<line x1="{CX + RIN * ca:.1f}" y1="{CY + RIN * sa:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{GOLD}" stroke-width="12" stroke-linecap="round" opacity=".16"/>')
            o.append(f'<line x1="{CX + RIN * ca:.1f}" y1="{CY + RIN * sa:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{GOLD}" stroke-width="4.5" stroke-linecap="round"/>')
            o.append(f'<circle cx="{x2:.1f}" cy="{y2:.1f}" r="4.5" fill="{RED2}"><animate attributeName="r" values="3.5;6;3.5" dur="2.6s" repeatCount="indefinite"/></circle>')
            if i == bw_i:
                lx, ly = CX + (r2 + 16) * ca, CY + (r2 + 16) * sa
                anchor = "start" if ca >= 0 else "end"
                o.append(f'<text x="{lx:.1f}" y="{ly + 3:.1f}" text-anchor="{anchor}" font-family="{MONO}" font-size="10.5" letter-spacing="1" fill="{GOLD2}">PEAK {s}</text>')
    # core
    o.append(f'<circle cx="{CX}" cy="{CY}" r="62" fill="url(#rc)"><animate attributeName="r" values="56;66;56" dur="3.2s" repeatCount="indefinite"/></circle>')
    o.append(f'<circle cx="{CX}" cy="{CY}" r="52" fill="{BG}" stroke="{GOLD}" stroke-width="1.2"/>')
    o.append(f'<circle cx="{CX}" cy="{CY}" r="45" fill="none" stroke="{RED}" stroke-width="1.5" stroke-dasharray="8 6"><animateTransform attributeName="transform" type="rotate" from="0 {CX} {CY}" to="-360 {CX} {CY}" dur="16s" repeatCount="indefinite"/></circle>')
    o.append(f'<text x="{CX}" y="{CY + 8}" text-anchor="middle" font-family="{SANS}" font-weight="700" font-size="28" fill="{GOLD2}">{total}</text>')
    o.append(f'<text x="{CX}" y="{CY + 24}" text-anchor="middle" font-family="{MONO}" font-size="7.5" letter-spacing="1.6" fill="{MUT}">OUTPUT</text>')
    o.append(f'<text x="{CX}" y="{CY - 212 + 0}" text-anchor="middle" font-family="{MONO}" font-size="9" letter-spacing="1.5" fill="{MUT}"></text>')
    o.append(f'<text x="{CX}" y="{CY + RMAX + 26}" text-anchor="middle" font-family="{MONO}" font-size="9" letter-spacing="1.6" fill="{MUT}">{series[0][0].strftime("%b %Y").upper()}  →  {series[-1][0].strftime("%b %Y").upper()}  ·  CLOCKWISE</text>')
    # right: stats
    X0, X1 = 560, 960
    rows = [("TOTAL CONTRIBUTIONS", str(total), "last 52 weeks"),
            ("ACTIVE DAYS", str(active), f"of {len(series)} days"),
            ("PEAK DAY", str(peak_v), peak_d.strftime("%d %b %Y") if peak_v else "—"),
            ("CURRENT STREAK", f"{cs}", "day" if cs == 1 else "days"),
            ("LONGEST STREAK", f"{longest}", "day" if longest == 1 else "days")]
    y = 96
    for lab, val, sub in rows:
        o.append(f'<rect x="{X0 - 14}" y="{y - 14}" width="3" height="34" fill="{RED}" opacity=".7"/>')
        o.append(f'<text x="{X0}" y="{y}" font-family="{MONO}" font-size="10.5" letter-spacing="1.4" fill="{GOLD}">{lab}</text>')
        o.append(f'<text x="{X0}" y="{y + 22}" font-family="{SANS}" font-weight="700" font-size="22" fill="{TXT}">{esc(val)}</text>')
        o.append(f'<text x="{X1}" y="{y + 22}" text-anchor="end" font-family="{MONO}" font-size="10.5" fill="{MUT}">{esc(sub)}</text>')
        o.append(f'<line x1="{X0}" y1="{y + 34}" x2="{X1}" y2="{y + 34}" stroke="{HAIR}"/>')
        y += 56
    # last 30 days strip (always visible: min height for active days)
    last = series[-30:]; mx = max(v for _, v in last) or 1
    o.append(f'<text x="{X0}" y="{y + 6}" font-family="{MONO}" font-size="10.5" letter-spacing="1.4" fill="{GOLD}">LAST 30 DAYS</text>')
    base, bh = y + 66, 44; bwid = (X1 - X0) / 30
    o.append(f'<line x1="{X0}" y1="{base}" x2="{X1}" y2="{base}" stroke="{HAIR}"/>')
    for k, (d, v) in enumerate(last):
        x = X0 + k * bwid + 2
        if v == 0:
            o.append(f'<rect x="{x:.1f}" y="{base - 2}" width="{bwid - 4:.1f}" height="2" fill="{GOLD}" opacity=".3"/>')
        else:
            h = 8 + (bh - 8) * math.sqrt(v / mx)
            o.append(f'<rect x="{x:.1f}" y="{base - h:.1f}" width="{bwid - 4:.1f}" height="{h:.1f}" fill="{GOLD}"><animate attributeName="opacity" values="1;.6;1" dur="3s" begin="{(k % 6) * .3:.1f}s" repeatCount="indefinite"/></rect>')
    o.append('</svg>')
    return "\n".join(o)

def main():
    days = None
    if "--sample" in sys.argv: days = sample()
    else:
        tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
        for fn in ([lambda: from_graphql(tok)] if tok else []) + [from_html]:
            try: days = fn(); break
            except Exception as e: print("source failed:", e, file=sys.stderr)
    if days is None:
        print("no data source worked; keeping existing SVG", file=sys.stderr); return 0
    svg = build(fill_year(days))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write(svg)
    print("wrote", os.path.normpath(OUT), "total", sum(days.values()))
    return 0
if __name__ == "__main__": sys.exit(main())
