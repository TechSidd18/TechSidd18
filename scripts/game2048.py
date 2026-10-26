#!/usr/bin/env python3
"""2048 played by all visitors together. Issue title must be exactly g2k|up|down|left|right or g2k|new.
`python3 scripts/game2048.py --init` rebuilds the board SVG and README blocks only."""
import os, re, sys, json, html, random

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
STATE = os.path.join(ROOT, "game", "2048.json")
SVG = os.path.join(ROOT, "assets", "game2048.svg")
README = os.path.join(ROOT, "README.md")
COMMENT = os.environ.get("G2K_COMMENT_FILE", "/tmp/g2k_comment.md")
N = 4
GOLD, GOLD2, RED, RED2 = "#C8A45C", "#E6C77E", "#A4161A", "#C8242A"
TXT, MUT, HAIR, BG = "#E8E6E1", "#8C867A", "#2A2620", "#0D0D0F"
MONO = "'SF Mono','Cascadia Mono',Consolas,'Liberation Mono',monospace"
SANS = "'Segoe UI',-apple-system,Helvetica,Arial,sans-serif"
# value -> (fill, text colour)
TILE = {2: ("#1E1E22", "#CFC9BB"), 4: ("#2A241A", "#E0D2AE"), 8: ("#4A3A1C", "#F0DDA6"), 16: ("#6B5226", "#F5E6BC"),
        32: ("#8E6C2F", "#FFF3D2"), 64: ("#C8A45C", "#1A1408"), 128: ("#E6C77E", "#1A1408"), 256: ("#7E1014", "#F6E3C0"),
        512: ("#A4161A", "#FFF0D8"), 1024: ("#C8242A", "#FFF0D8"), 2048: ("#F3E2B5", "#2A0B0C")}
DIRS = ("up", "down", "left", "right")

def fresh(prev=None):
    s = {"board": [[0] * N for _ in range(N)], "score": 0, "best": 0, "moves": 0, "games": 1, "status": "playing",
         "last": {"spawn": [], "merged": []}, "log": [], "version": 0, "top": 0}
    if prev:
        for k in ("best", "games", "log", "version", "top"): s[k] = prev[k]
    for _ in range(2): spawn(s["board"])
    return s

def spawn(b):
    empty = [(r, c) for r in range(N) for c in range(N) if b[r][c] == 0]
    if not empty: return None
    r, c = random.choice(empty); b[r][c] = 4 if random.random() < 0.1 else 2
    return [r, c]

def load():
    try:
        s = json.load(open(STATE)); base = fresh(); base.update(s); return base
    except Exception:
        return fresh()

def save(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(s, open(STATE, "w"), indent=1)

def lines(d):
    r = range(N)
    if d == "left":  return [[(i, j) for j in r] for i in r]
    if d == "right": return [[(i, N - 1 - j) for j in r] for i in r]
    if d == "up":    return [[(j, i) for j in r] for i in r]
    return [[(N - 1 - j, i) for j in r] for i in r]

def slide(b, d):
    """returns (new_board, gained, merged_cells, changed)"""
    nb = [row[:] for row in b]; gained = 0; merged = []
    for line in lines(d):
        vals = [b[r][c] for r, c in line if b[r][c]]
        out, k, pos = [], 0, 0
        while k < len(vals):
            if k + 1 < len(vals) and vals[k] == vals[k + 1]:
                out.append(vals[k] * 2); gained += vals[k] * 2; merged.append(list(line[len(out) - 1])); k += 2
            else:
                out.append(vals[k]); k += 1
        out += [0] * (N - len(out))
        for (r, c), v in zip(line, out): nb[r][c] = v
    return nb, gained, merged, nb != b

def can_move(b):
    return any(slide(b, d)[3] for d in DIRS)

def esc(x): return html.escape(str(x), quote=True)

def render(s):
    W, H = 760, 520; CELL, GAP, OX, OY = 84, 9, 40, 92
    b = s["board"]; sp = {tuple(x) for x in s["last"]["spawn"]}; mg = {tuple(x) for x in s["last"]["merged"]}
    bw = N * CELL + (N + 1) * GAP
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="2048 played by profile visitors. Score {s["score"]}, best {s["best"]}">']
    o.append(f'<rect width="{W}" height="{H}" rx="10" fill="{BG}"/>')
    o.append(f'<circle cx="40" cy="34" r="4" fill="{RED}"><animate attributeName="opacity" values="1;.35;1" dur="2.4s" repeatCount="indefinite"/></circle>')
    o.append(f'<text x="54" y="38" font-family="{MONO}" font-size="11" letter-spacing="2.2" fill="{GOLD}">2048 · PLAYED BY ALL VISITORS</text>')
    o.append(f'<text x="720" y="38" text-anchor="end" font-family="{MONO}" font-size="11" letter-spacing="2.2" fill="{MUT}">GAME #{s["games"]}</text>')
    o.append(f'<line x1="40" y1="52" x2="720" y2="52" stroke="{HAIR}"/>')
    o.append(f'<rect x="{OX - 6}" y="{OY - 6}" width="{bw + 12}" height="{bw + 12}" rx="10" fill="#151518" stroke="{GOLD}" stroke-opacity=".5"/>')
    for r in range(N):
        for c in range(N):
            x, y = OX + GAP + c * (CELL + GAP), OY + GAP + r * (CELL + GAP)
            o.append(f'<rect x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="6" fill="{BG}" stroke="{HAIR}"/>')
            v = b[r][c]
            if not v: continue
            fill, tc = TILE.get(v, TILE[2048])
            fs = 34 if v < 100 else 28 if v < 1000 else 22
            cx, cy = x + CELL / 2, y + CELL / 2
            tile = (f'<rect x="{-CELL / 2}" y="{-CELL / 2}" width="{CELL}" height="{CELL}" rx="6" fill="{fill}"/>'
                    f'<rect x="{-CELL / 2 + 3}" y="{-CELL / 2 + 3}" width="{CELL - 6}" height="{CELL - 6}" rx="4" fill="none" stroke="{GOLD2}" stroke-opacity=".25"/>'
                    f'<text x="0" y="{fs * 0.36:.1f}" text-anchor="middle" font-family="{SANS}" font-weight="700" font-size="{fs}" fill="{tc}">{v}</text>')
            if (r, c) in sp:
                o.append(f'<g transform="translate({cx} {cy})"><g>{tile}<animateTransform attributeName="transform" type="scale" from="0.4" to="1" dur="0.35s" fill="freeze"/></g></g>')
            elif (r, c) in mg:
                o.append(f'<g transform="translate({cx} {cy})"><g>{tile}<animateTransform attributeName="transform" type="scale" values="1;1.14;1" dur="0.4s" fill="freeze"/></g></g>')
            else:
                o.append(f'<g transform="translate({cx} {cy})">{tile}</g>')
    X = 520
    st = {"playing": "YOUR MOVE", "over": "GAME OVER"}[s["status"]]
    sub = "Use the buttons below." if s["status"] == "playing" else "Any direction starts a new game."
    o.append(f'<text x="{X}" y="96" font-family="{MONO}" font-size="10.5" letter-spacing="1.4" fill="{GOLD}">STATUS</text>')
    o.append(f'<text x="{X}" y="122" font-family="{SANS}" font-weight="700" font-size="22" fill="{TXT}">{st}</text>')
    o.append(f'<text x="{X}" y="142" font-family="{MONO}" font-size="10" fill="{MUT}">{esc(sub)}</text>')
    o.append(f'<line x1="{X}" y1="156" x2="720" y2="156" stroke="{HAIR}"/>')
    rows = (("SCORE", s["score"]), ("BEST SCORE", s["best"]), ("MOVES", s["moves"]), ("HIGHEST TILE", s["top"]))
    for k, (lab, val) in enumerate(rows):
        y = 190 + k * 38
        o.append(f'<rect x="{X - 14}" y="{y - 14}" width="3" height="22" fill="{RED}" opacity=".7"/>')
        o.append(f'<text x="{X}" y="{y}" font-family="{MONO}" font-size="10.5" letter-spacing="1.4" fill="{GOLD}">{lab}</text>')
        o.append(f'<text x="720" y="{y + 2}" text-anchor="end" font-family="{SANS}" font-weight="700" font-size="20" fill="{TXT}">{val}</text>')
    o.append(f'<line x1="{X}" y1="338" x2="720" y2="338" stroke="{HAIR}"/>')
    o.append(f'<text x="{X}" y="362" font-family="{MONO}" font-size="10.5" letter-spacing="1.4" fill="{GOLD}">LAST MOVES</text>')
    lm = s["log"][-4:][::-1]
    if not lm:
        o.append(f'<text x="{X}" y="388" font-family="{MONO}" font-size="10.5" fill="{MUT}">No moves yet. Be the first.</text>')
    for k, m in enumerate(lm):
        y = 388 + k * 22
        o.append(f'<text x="{X}" y="{y}" font-family="{MONO}" font-size="10.5" fill="{TXT}">@{esc(m["user"][:18])}</text>')
        o.append(f'<text x="720" y="{y}" text-anchor="end" font-family="{MONO}" font-size="10.5" fill="{MUT}">{esc(m["dir"].upper())} · +{m["gain"]}</text>')
    o.append(f'<text x="40" y="504" font-family="{MONO}" font-size="9.5" letter-spacing="1.2" fill="{MUT}">MERGE EQUAL TILES · REACH 2048 · EVERY VISITOR PLAYS THE SAME BOARD</text>')
    o.append("</svg>")
    return "\n".join(o)

def update_readme(s):
    if not os.path.exists(README): return
    t = open(README, encoding="utf-8").read()
    img = f'<img src="./assets/game2048.svg?v={s["version"]}" alt="2048 board" width="100%"/>'
    t = re.sub(r"<!--G2K_BOARD:START-->.*?<!--G2K_BOARD:END-->", lambda m: f"<!--G2K_BOARD:START-->{img}<!--G2K_BOARD:END-->", t, flags=re.S)
    lines_ = ([f'- `@{m["user"]}` moved **{m["dir"]}** (+{m["gain"]})' for m in s["log"][-5:][::-1]]
              or ["_No moves yet. Be the first to play!_"])
    t = re.sub(r"<!--G2K_LOG:START-->.*?<!--G2K_LOG:END-->", lambda m: "<!--G2K_LOG:START-->\n" + "\n".join(lines_) + "\n<!--G2K_LOG:END-->", t, flags=re.S)
    open(README, "w", encoding="utf-8").write(t)

def write_all(s):
    open(SVG, "w", encoding="utf-8").write(render(s)); update_readme(s)

def finish(result, msg):
    open(COMMENT, "w").write(msg + "\n")
    out = os.environ.get("GITHUB_OUTPUT")
    if out: open(out, "a").write(f"result={result}\n")
    print(result, "-", msg)

def main():
    if "--init" in sys.argv:
        s = load(); save(s); write_all(s); return 0
    title = (os.environ.get("ISSUE_TITLE") or "").strip()
    user = re.sub(r"[^A-Za-z0-9-]", "", os.environ.get("ISSUE_USER") or "visitor")[:39] or "visitor"
    m = re.fullmatch(r"g2k\|(up|down|left|right|new)", title)
    if not m:
        finish("error", "I only understand the buttons on the profile (`g2k|up`, `g2k|down`, `g2k|left`, `g2k|right`). Please use those."); return 0
    d = m.group(1); s = load()
    if d == "new":
        if s["status"] == "playing" and s["moves"] > 0:
            finish("error", "A game is still in progress. Keep playing with the direction buttons."); return 0
        s = fresh(s); s["games"] += 1; s["version"] += 1; save(s); write_all(s)
        finish("ok", "New game started. Your move!"); return 0
    if s["status"] == "over":
        s = fresh(s); s["games"] += 1
    nb, gained, merged, changed = slide(s["board"], d)
    if not changed:
        finish("error", f"Moving **{d}** doesn't change the board. Try another direction."); return 0
    sp = spawn(nb)
    s["board"] = nb; s["score"] += gained; s["moves"] += 1
    s["best"] = max(s["best"], s["score"]); s["top"] = max(s["top"], max(max(r) for r in nb))
    s["last"] = {"spawn": [sp] if sp else [], "merged": merged}
    s["log"] = (s["log"] + [{"user": user, "dir": d, "gain": gained}])[-10:]
    msg = f"@{user} moved **{d}** (+{gained})."
    if not can_move(nb):
        s["status"] = "over"; msg += f" Game over with a score of **{s['score']}**. Any direction starts a new game."
    s["version"] += 1; save(s); write_all(s)
    msg += "\n\nThe board updates on the profile in a minute or two (GitHub caches images)."
    finish("ok", msg); return 0

if __name__ == "__main__": sys.exit(main())
