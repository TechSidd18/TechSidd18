#!/usr/bin/env python3
"""Self-updating profile assets (no third-party servers, no extra packages).

Generates:
  assets/stats.svg      - contributions, streaks, repos, stars, followers
  assets/languages.svg  - top languages bar
  README.md             - "Recent activity" list between the RECENT_ACTIVITY markers

Runs inside GitHub Actions with the built-in GITHUB_TOKEN.
"""
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.request

USER = os.environ.get("GH_USER", "TechSidd18")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
OUT = os.environ.get("OUT_DIR", "assets")
README = os.environ.get("README_PATH", "README.md")

GOLD, CRIMSON, BG = "#C8A45C", "#A4161A", "#0E0E10"
LANG_COLORS = ["#C8A45C", "#A4161A", "#8C6A3A", "#6E1216", "#D9D3C4", "#5E5A52", "#B9B2A3"]


def http(url, data=None, accept="application/vnd.github+json"):
    h = {"User-Agent": "profile-generator", "Accept": accept}
    if TOKEN:
        h["Authorization"] = f"Bearer {TOKEN}"
    if data is not None:
        data = json.dumps(data).encode()
        h["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode()


def safe(fn, default=None, label=""):
    try:
        return fn()
    except Exception as e:  # keep going, show "-" instead of failing the whole run
        print(f"[warn] {label}: {e}", file=sys.stderr)
        return default


# ---------- data ----------
def get_profile():
    return json.loads(http(f"https://api.github.com/users/{USER}"))


def get_repos():
    repos, page = [], 1
    while True:
        chunk = json.loads(http(f"https://api.github.com/users/{USER}/repos?per_page=100&type=owner&page={page}"))
        repos += chunk
        if len(chunk) < 100:
            return repos
        page += 1


def get_languages(repos):
    totals = {}
    for r in repos:
        if r.get("fork"):
            continue
        langs = safe(lambda: json.loads(http(r["languages_url"])), {}, f"languages {r['name']}")
        for k, v in langs.items():
            totals[k] = totals.get(k, 0) + v
    return sorted(totals.items(), key=lambda kv: -kv[1])


def get_calendar():
    """{date: count} for the last year. GraphQL first (token), HTML fallback."""
    if TOKEN:
        q = """query($l:String!){user(login:$l){contributionsCollection{contributionCalendar{
               weeks{contributionDays{date contributionCount}}}}}}"""
        res = json.loads(http("https://api.github.com/graphql", {"query": q, "variables": {"l": USER}}))
        weeks = res["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
        return {d["date"]: d["contributionCount"] for w in weeks for d in w["contributionDays"]}
    page = http(f"https://github.com/users/{USER}/contributions", accept="text/html")
    cells = re.findall(r'<td[^>]*data-date="([\d-]+)"[^>]*id="(contribution-day-component-\d+-\d+)"', page)
    tips = dict(re.findall(r'for="(contribution-day-component-\d+-\d+)"[^>]*>([^<]*)<', page))
    cal = {}
    for date, cid in cells:
        m = re.match(r"(\d+) contribution", tips.get(cid, ""))
        cal[date] = int(m.group(1)) if m else 0
    return cal


def streaks(cal):
    today = dt.date.today()
    days = sorted(d for d in cal if d <= today.isoformat())
    longest = run = 0
    for d in days:
        run = run + 1 if cal[d] > 0 else 0
        longest = max(longest, run)
    cur, idx = 0, len(days) - 1
    if idx >= 0 and cal[days[idx]] == 0:  # today not done yet, streak is still alive
        idx -= 1
    while idx >= 0 and cal[days[idx]] > 0:
        cur += 1
        idx -= 1
    return cur, longest


# ---------- svg ----------
STYLE = f"""
.mono{{font-family:'SFMono-Regular',Consolas,'Liberation Mono',monospace}}
.sans{{font-family:'Helvetica Neue',Helvetica,Arial,sans-serif}}
@keyframes rise{{from{{opacity:0;transform:translateY(8px)}}to{{opacity:1;transform:none}}}}
@keyframes dot{{0%,100%{{opacity:.4}}50%{{opacity:1}}}}
@keyframes grow{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}
.dot{{animation:dot 2.6s ease-in-out infinite}}
"""


def header(title, right):
    return (
        f'<circle class="dot" cx="34" cy="26" r="3.5" fill="{CRIMSON}"/>'
        f'<text class="mono" x="46" y="30" font-size="11" letter-spacing="1.6" fill="{GOLD}">{title}</text>'
        f'<text class="mono" x="920" y="30" font-size="10.5" letter-spacing="1.6" fill="#7E786B" text-anchor="end">{right}</text>'
        f'<line x1="30" y1="46" x2="920" y2="46" stroke="{GOLD}" stroke-opacity=".25"/>'
    )


def fmt(n):
    return "-" if n is None else f"{n:,}"


def stats_svg(m):
    cols = [
        ("CONTRIBUTIONS", "last 12 months", m["total"]),
        ("CURRENT STREAK", "days", m["cur"]),
        ("LONGEST STREAK", "days", m["longest"]),
        ("PUBLIC REPOS", "owned", m["repos"]),
        ("STARS EARNED", "across repos", m["stars"]),
        ("FOLLOWERS", "on GitHub", m["followers"]),
    ]
    w, H, cw = 950, 150, 890 / 6
    parts = []
    for i, (label, sub, val) in enumerate(cols):
        x = 30 + i * cw
        if i:
            parts.append(f'<line x1="{x:.1f}" y1="64" x2="{x:.1f}" y2="124" stroke="{GOLD}" stroke-opacity=".18"/>')
        parts.append(
            f'<g style="animation:rise .8s ease-out {i*0.12:.2f}s both">'
            f'<text class="sans" x="{x+18:.1f}" y="95" font-size="34" font-weight="700" fill="#F3EEE2">{fmt(val)}</text>'
            f'<text class="mono" x="{x+18:.1f}" y="113" font-size="9.5" letter-spacing="1.2" fill="{GOLD}">{label}</text>'
            f'<text class="mono" x="{x+18:.1f}" y="127" font-size="9.5" fill="#7E786B">{sub}</text></g>'
        )
    today = dt.date.today().isoformat()
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {H}" width="{w}" height="{H}"><style>{STYLE}</style>'
        f'<rect width="{w}" height="{H}" rx="14" fill="{BG}"/>'
        + header("GITHUB STATS", f"UPDATED {today}")
        + "".join(parts)
        + f'<line x1="30" y1="{H-12}" x2="920" y2="{H-12}" stroke="{GOLD}" stroke-opacity=".25"/></svg>'
    )


def languages_svg(langs):
    top = langs[:7]
    total = sum(v for _, v in top) or 1
    w, bar_x, bar_w = 950, 30, 890
    segs, legend, x = [], [], bar_x
    for i, (name, v) in enumerate(top):
        pct = v / total * 100
        sw = bar_w * v / total
        c = LANG_COLORS[i % len(LANG_COLORS)]
        segs.append(f'<rect x="{x:.1f}" y="70" width="{max(sw-2,1):.1f}" height="10" fill="{c}"/>')
        x += sw
        col, row = i % 4, i // 4
        lx, ly = 30 + col * 225, 112 + row * 24
        legend.append(
            f'<g style="animation:rise .8s ease-out {0.5+i*0.1:.1f}s both"><circle cx="{lx+4}" cy="{ly-4}" r="4" fill="{c}"/>'
            f'<text class="sans" x="{lx+16}" y="{ly}" font-size="13" font-weight="600" fill="#F3EEE2">{html.escape(name)}</text>'
            f'<text class="mono" x="{lx+205}" y="{ly}" font-size="11" fill="#9A9384" text-anchor="end">{pct:.1f}%</text></g>'
        )
    rows = (len(top) + 3) // 4 or 1
    H = 112 + rows * 24 + 14
    if not top:
        legend = [f'<text class="mono" x="30" y="112" font-size="12" fill="#7E786B">no language data yet</text>']
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {H}" width="{w}" height="{H}"><style>{STYLE}'
        f'.bar{{transform-origin:{bar_x}px 0;animation:grow 1.4s ease-out both}}</style>'
        f'<rect width="{w}" height="{H}" rx="14" fill="{BG}"/>'
        + header("TOP LANGUAGES", "BY CODE SIZE")
        + f'<g class="bar">{"".join(segs)}</g>'
        + "".join(legend)
        + f'<line x1="30" y1="{H-10}" x2="920" y2="{H-10}" stroke="{GOLD}" stroke-opacity=".25"/></svg>'
    )



# ---------- candlestick chart ----------
def candles_svg(cal):
    """Weekly OHLC candles from daily contributions (open=Sun, close=Sat, high/low=max/min)."""
    weeks = {}
    for d in sorted(cal):
        day = dt.date.fromisoformat(d)
        start = day - dt.timedelta(days=(day.weekday() + 1) % 7)  # Sunday
        weeks.setdefault(start, []).append(cal[d])
    keys = sorted(weeks)[-52:]
    ohlc = [(weeks[k][0], max(weeks[k]), min(weeks[k]), weeks[k][-1], sum(weeks[k])) for k in keys]
    peak = max([c[1] for c in ohlc] + [4])
    vmax = max([c[4] for c in ohlc] + [4])
    w, H = 950, 290
    x0, x1, base, top = 60, 920, 196, 70
    slot = (x1 - x0) / max(len(ohlc), 1)
    fy = lambda v: base - (v / peak) ** 0.5 * (base - top)
    parts = []
    for gy in (top, (top + base) / 2, base):
        parts.append(f'<line x1="{x0}" y1="{gy:.1f}" x2="{x1}" y2="{gy:.1f}" stroke="{GOLD}" stroke-opacity=".12"/>')
    parts.append(f'<text class="mono" x="{x0-8}" y="{top+4}" font-size="9" fill="#7E786B" text-anchor="end">{peak}</text>')
    parts.append(f'<text class="mono" x="{x0-8}" y="{base+4}" font-size="9" fill="#7E786B" text-anchor="end">0</text>')
    for i, (o, h, l, c, tot) in enumerate(ohlc):
        cx = x0 + slot * (i + 0.5)
        delay = f"{i*0.025:.3f}s"
        vh = (tot / vmax) ** 0.5 * 38 if tot else 0
        if vh:
            parts.append(f'<rect class="cd" style="animation-delay:{delay}" x="{cx-4:.1f}" y="{248-vh:.1f}" width="8" height="{vh:.1f}" fill="#5E5A52" fill-opacity=".7"/>')
        if h == 0:
            parts.append(f'<line x1="{cx-4:.1f}" y1="{base}" x2="{cx+4:.1f}" y2="{base}" stroke="{GOLD}" stroke-opacity=".3"/>')
            continue
        col = GOLD if c >= o else CRIMSON
        yo, yc = fy(o), fy(c)
        by, bh = min(yo, yc), max(abs(yo - yc), 1.5)
        parts.append(
            f'<g class="cd" style="animation-delay:{delay}"><line x1="{cx:.1f}" y1="{fy(h):.1f}" x2="{cx:.1f}" y2="{fy(l):.1f}" stroke="{col}" stroke-width="1.2"/>'
            f'<rect x="{cx-4:.1f}" y="{by:.1f}" width="8" height="{bh:.1f}" fill="{col}"/></g>'
        )
    last_m, last_x = None, -99
    for i, k in enumerate(keys):
        if k.month != last_m and x0 + slot * i - last_x > 34:
            last_m, last_x = k.month, x0 + slot * i
            parts.append(f'<text class="mono" x="{x0 + slot*i:.1f}" y="268" font-size="9" fill="#7E786B">{k.strftime("%b").upper()}</text>')
    total = sum(c[4] for c in ohlc)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {H}" width="{w}" height="{H}"><style>{STYLE}'
        f'.cd{{transform-box:fill-box;transform-origin:center bottom;animation:pop .7s ease-out both}}'
        f'@keyframes pop{{from{{opacity:0;transform:scaleY(0)}}to{{opacity:1;transform:none}}}}</style>'
        f'<rect width="{w}" height="{H}" rx="14" fill="{BG}"/>'
        + header("CONTRIBUTION MARKET", f"{len(ohlc)} WEEKS &#183; {total} CONTRIBUTIONS")
        + "".join(parts)
        + f'<line x1="30" y1="{H-12}" x2="920" y2="{H-12}" stroke="{GOLD}" stroke-opacity=".25"/></svg>'
    )

# ---------- recent activity ----------
def ago(ts):
    t = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    s = int((dt.datetime.now(dt.timezone.utc) - t).total_seconds())
    for n, u in ((86400, "d"), (3600, "h"), (60, "m")):
        if s >= n:
            return f"{s // n}{u} ago"
    return "just now"


def activity_lines(limit=6):
    events = json.loads(http(f"https://api.github.com/users/{USER}/events/public?per_page=50"))
    out = []
    for e in events:
        repo = e["repo"]["name"]
        link = f"[{repo}](https://github.com/{repo})"
        p, t = e["payload"], e["type"]
        if t == "PushEvent":
            n = p.get("size") or len(p.get("commits", [])) or 1
            msg = f"Pushed {n} commit{'s' if n != 1 else ''} to {link}"
        elif t == "PullRequestEvent":
            msg = f"{p['action'].capitalize()} a pull request in {link}"
        elif t == "IssuesEvent":
            msg = f"{p['action'].capitalize()} an issue in {link}"
        elif t == "CreateEvent" and p.get("ref_type") == "repository":
            msg = f"Created repository {link}"
        elif t == "ReleaseEvent":
            msg = f"Published a release in {link}"
        elif t == "ForkEvent":
            msg = f"Forked {link}"
        elif t == "WatchEvent":
            msg = f"Starred {link}"
        else:
            continue
        out.append(f"- {msg} &nbsp;<sub>`{ago(e['created_at'])}`</sub>")
        if len(out) == limit:
            break
    return out or ["- Nothing public yet. Fresh start."]


def update_readme(lines):
    if not os.path.exists(README):
        return
    s = open(README, encoding="utf-8").read()
    a, b = "<!--RECENT_ACTIVITY:START-->", "<!--RECENT_ACTIVITY:END-->"
    if a not in s or b not in s:
        return
    new = re.sub(re.escape(a) + r".*?" + re.escape(b), a + "\n" + "\n".join(lines) + "\n" + b, s, flags=re.S)
    open(README, "w", encoding="utf-8").write(new)


def main():
    os.makedirs(OUT, exist_ok=True)
    prof = safe(get_profile, {}, "profile")
    repos = safe(get_repos, [], "repos")
    cal = safe(get_calendar, {}, "calendar")
    if cal:  # keep exactly the last 365 days
        cutoff = (dt.date.today() - dt.timedelta(days=364)).isoformat()
        cal = {d: c for d, c in cal.items() if d >= cutoff}
    cur, longest = streaks(cal) if cal else (None, None)
    m = {
        "total": sum(cal.values()) if cal else None,
        "cur": cur,
        "longest": longest,
        "repos": prof.get("public_repos"),
        "followers": prof.get("followers"),
        "stars": sum(r.get("stargazers_count", 0) for r in repos if not r.get("fork")) if repos else None,
    }
    open(f"{OUT}/stats.svg", "w", encoding="utf-8").write(stats_svg(m))
    if cal:
        open(f"{OUT}/candles.svg", "w", encoding="utf-8").write(candles_svg(cal))
    open(f"{OUT}/languages.svg", "w", encoding="utf-8").write(languages_svg(get_languages(repos) if repos else []))
    lines = safe(activity_lines, None, "activity")
    if lines:
        update_readme(lines)
    print("done", m)


if __name__ == "__main__":
    main()
