#!/usr/bin/env python3
"""Connect Four vs JARVIS — runs inside GitHub Actions on issue open.
Issue title must be exactly  c4|drop|1..7  or  c4|new.   `python3 scripts/connect4.py --init` rebuilds the board/README only."""
import os, re, sys, json, time, html, random

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
STATE = os.path.join(ROOT, "game", "state.json")
BOARD_SVG = os.path.join(ROOT, "assets", "connect4.svg")
README = os.path.join(ROOT, "README.md")
COMMENT = os.environ.get("C4_COMMENT_FILE", "/tmp/c4_comment.md")
R, C = 6, 7
GOLD, GOLD2, RED, RED2 = "#C8A45C", "#E6C77E", "#A4161A", "#C8242A"
TXT, MUT, HAIR, BG = "#E8E6E1", "#8C867A", "#2A2620", "#0D0D0F"
MONO = "'SF Mono','Cascadia Mono',Consolas,'Liberation Mono',monospace"
SANS = "'Segoe UI',-apple-system,Helvetica,Arial,sans-serif"

def fresh():
    return {"board": [[0] * C for _ in range(R)], "status": "playing", "last": [], "win": [],
            "score": {"visitor": 0, "jarvis": 0, "draw": 0}, "log": [], "version": 0, "games": 1}

def load():
    try:
        s = json.load(open(STATE)); base = fresh(); base.update(s); return base
    except Exception:
        return fresh()

def save(s):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(s, open(STATE, "w"), indent=1)

# ---------- game logic ----------
def drop(b, col, p):
    for r in range(R - 1, -1, -1):
        if b[r][col] == 0:
            b[r][col] = p; return r
    return None

def find_win(b, p):
    for r in range(R):
        for c in range(C):
            if b[r][c] != p: continue
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                cells = [(r + k * dr, c + k * dc) for k in range(4)]
                if all(0 <= y < R and 0 <= x < C and b[y][x] == p for y, x in cells):
                    return cells
    return None

def full(b): return all(b[0][c] != 0 for c in range(C))
ORDER = [3, 2, 4, 1, 5, 0, 6]

def score_window(w, p):
    o = 3 - p
    if w.count(p) == 4: return 1000
    if w.count(p) == 3 and w.count(0) == 1: return 6
    if w.count(p) == 2 and w.count(0) == 2: return 2
    if w.count(o) == 3 and w.count(0) == 1: return -8
    return 0

def heuristic(b, p):
    s = sum(3 for r in range(R) if b[r][3] == p) - sum(3 for r in range(R) if b[r][3] == 3 - p)
    for r in range(R):
        for c in range(C):
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                cells = [(r + k * dr, c + k * dc) for k in range(4)]
                if all(0 <= y < R and 0 <= x < C for y, x in cells):
                    s += score_window([b[y][x] for y, x in cells], p)
    return s

def minimax(b, depth, alpha, beta, me, turn):
    if find_win(b, me): return 100000 + depth, None
    if find_win(b, 3 - me): return -100000 - depth, None
    if full(b): return 0, None
    if depth == 0: return heuristic(b, me), None
    best_col = None
    if turn == me:
        best = -10 ** 9
        for c in ORDER:
            if b[0][c]: continue
            r = drop(b, c, turn); v, _ = minimax(b, depth - 1, alpha, beta, me, 3 - turn); b[r][c] = 0
            if v > best: best, best_col = v, c
            alpha = max(alpha, best)
            if alpha >= beta: break
    else:
        best = 10 ** 9
        for c in ORDER:
            if b[0][c]: continue
            r = drop(b, c, turn); v, _ = minimax(b, depth - 1, alpha, beta, me, 3 - turn); b[r][c] = 0
            if v < best: best, best_col = v, c
            beta = min(beta, best)
            if alpha >= beta: break
    return best, best_col

def bot_move(b):
    _, col = minimax(b, 4, -10 ** 9, 10 ** 9, 2, 2)
    if col is None or b[0][col]: col = next(c for c in ORDER if not b[0][c])
    return col

# ---------- rendering ----------
def esc(x): return html.escape(str(x), quote=True)

def render(s):
    b = s["board"]; W, H = 760, 520
    CELL, OX, OY = 62, 40, 96
    last = {(m["row"], m["col"]): m["by"] for m in s.get("last", [])}
    win = {tuple(x) for x in s.get("win", [])}
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Connect Four board: visitors in gold versus JARVIS in crimson">']
    o.append(f'<rect width="{W}" height="{H}" rx="10" fill="{BG}"/>')
    o.append(f'<circle cx="40" cy="34" r="4" fill="{RED}"><animate attributeName="opacity" values="1;.35;1" dur="2.4s" repeatCount="indefinite"/></circle>')
    o.append(f'<text x="54" y="38" font-family="{MONO}" font-size="11" letter-spacing="2.2" fill="{GOLD}">CONNECT FOUR · VISITORS vs JARVIS</text>')
    o.append(f'<text x="720" y="38" text-anchor="end" font-family="{MONO}" font-size="11" letter-spacing="2.2" fill="{MUT}">GAME #{s["games"]}</text>')
    o.append(f'<line x1="40" y1="52" x2="720" y2="52" stroke="{HAIR}"/>')
    bw, bh = C * CELL, R * CELL
    o.append(f'<rect x="{OX - 8}" y="{OY - 8}" width="{bw + 16}" height="{bh + 16}" rx="10" fill="#151518" stroke="{GOLD}" stroke-opacity=".5"/>')
    for c in range(C):
        o.append(f'<text x="{OX + c * CELL + CELL / 2}" y="{OY - 18}" text-anchor="middle" font-family="{MONO}" font-size="11" fill="{MUT}">{c + 1}</text>')
    for r in range(R):
        for c in range(C):
            cx, cy = OX + c * CELL + CELL / 2, OY + r * CELL + CELL / 2
            o.append(f'<circle cx="{cx}" cy="{cy}" r="24" fill="{BG}" stroke="{HAIR}"/>')
            v = b[r][c]
            if not v: continue
            col = GOLD if v == 1 else RED
            hi = GOLD2 if v == 1 else RED2
            disc = f'<circle cx="{cx}" cy="{cy}" r="24" fill="{col}"/><circle cx="{cx}" cy="{cy}" r="18" fill="none" stroke="{hi}" stroke-opacity=".55"/>'
            if (r, c) in last:
                fall = OY + r * CELL + 40
                o.append(f'<g>{disc}<animateTransform attributeName="transform" type="translate" from="0 -{fall}" to="0 0" dur="0.7s" begin="{0 if last[(r, c)] == "visitor" else 0.5}s" fill="freeze" calcMode="spline" keyTimes="0;1" keySplines="0.3 0 0.7 1"/></g>')
            else:
                o.append(disc)
            if (r, c) in win:
                o.append(f'<circle cx="{cx}" cy="{cy}" r="27" fill="none" stroke="{TXT}" stroke-width="2"><animate attributeName="opacity" values="1;.25;1" dur="1.4s" repeatCount="indefinite"/></circle>')
    # right panel
    X = 520
    st = s["status"]
    head = {"playing": "YOUR MOVE", "visitor_win": "VISITOR WINS", "jarvis_win": "JARVIS WINS", "draw": "DRAW"}[st]
    sub = "Pick a column below to drop a disc." if st == "playing" else "Drop any column to start a new game."
    o.append(f'<text x="{X}" y="96" font-family="{MONO}" font-size="10.5" letter-spacing="1.4" fill="{GOLD}">STATUS</text>')
    o.append(f'<text x="{X}" y="122" font-family="{SANS}" font-weight="700" font-size="22" fill="{TXT}">{head}</text>')
    o.append(f'<text x="{X}" y="142" font-family="{MONO}" font-size="10" fill="{MUT}">{esc(sub)}</text>')
    o.append(f'<line x1="{X}" y1="156" x2="720" y2="156" stroke="{HAIR}"/>')
    o.append(f'<text x="{X}" y="182" font-family="{MONO}" font-size="10.5" letter-spacing="1.4" fill="{GOLD}">SCOREBOARD</text>')
    for k, (lab, key, colr) in enumerate((("VISITORS", "visitor", GOLD), ("JARVIS", "jarvis", RED2), ("DRAWS", "draw", MUT))):
        y = 212 + k * 34
        o.append(f'<circle cx="{X + 6}" cy="{y - 5}" r="5" fill="{colr}"/>')
        o.append(f'<text x="{X + 20}" y="{y}" font-family="{SANS}" font-weight="600" font-size="13" fill="{TXT}">{lab}</text>')
        o.append(f'<text x="720" y="{y}" text-anchor="end" font-family="{SANS}" font-weight="700" font-size="18" fill="{TXT}">{s["score"][key]}</text>')
    o.append(f'<line x1="{X}" y1="306" x2="720" y2="306" stroke="{HAIR}"/>')
    o.append(f'<text x="{X}" y="332" font-family="{MONO}" font-size="10.5" letter-spacing="1.4" fill="{GOLD}">LAST MOVES</text>')
    lm = s["log"][-3:][::-1]
    if not lm:
        o.append(f'<text x="{X}" y="358" font-family="{MONO}" font-size="10.5" fill="{MUT}">No moves yet. Be the first.</text>')
    for k, m in enumerate(lm):
        o.append(f'<text x="{X}" y="{358 + k * 22}" font-family="{MONO}" font-size="10.5" fill="{TXT}">@{esc(m["user"][:18])} → col {m["col"]}</text>')
        o.append(f'<text x="720" y="{358 + k * 22}" text-anchor="end" font-family="{MONO}" font-size="10.5" fill="{MUT}">JARVIS → {m["bot"]}</text>' if m.get("bot") else "")
    o.append(f'<text x="40" y="504" font-family="{MONO}" font-size="9.5" letter-spacing="1.2" fill="{MUT}">GOLD = VISITORS · CRIMSON = JARVIS · CONNECT FOUR IN A ROW TO WIN</text>')
    o.append("</svg>")
    return "\n".join(x for x in o if x)

def update_readme(s):
    if not os.path.exists(README): return
    t = open(README, encoding="utf-8").read()
    img = f'<img src="./assets/connect4.svg?v={s["version"]}" alt="Connect Four board" width="100%"/>'
    t = re.sub(r"<!--C4_BOARD:START-->.*?<!--C4_BOARD:END-->", lambda m: f"<!--C4_BOARD:START-->{img}<!--C4_BOARD:END-->", t, flags=re.S)
    if s["log"]:
        lines = [f'- `@{m["user"]}` dropped in column **{m["col"]}**' + (f' · JARVIS replied in column **{m["bot"]}**' if m.get("bot") else "") for m in s["log"][-5:][::-1]]
    else:
        lines = ["_No moves yet. Be the first to play!_"]
    t = re.sub(r"<!--C4_LOG:START-->.*?<!--C4_LOG:END-->", lambda m: "<!--C4_LOG:START-->\n" + "\n".join(lines) + "\n<!--C4_LOG:END-->", t, flags=re.S)
    open(README, "w", encoding="utf-8").write(t)

def write_all(s):
    open(BOARD_SVG, "w", encoding="utf-8").write(render(s)); update_readme(s)

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
    m = re.fullmatch(r"c4\|(drop\|([1-7])|new)", title)
    if not m: return finish("error", "I only understand the move buttons on the profile (`c4|drop|1..7` or `c4|new`). Please use those.") or 0
    s = load()
    if title == "c4|new":
        if s["status"] == "playing" and any(any(row) for row in s["board"]):
            return finish("error", "A game is still in progress. Finish it first (drop a disc in any column).") or 0
        s["board"] = fresh()["board"]; s["status"] = "playing"; s["last"] = []; s["win"] = []; s["games"] += 1
        s["version"] += 1; save(s); write_all(s)
        return finish("ok", "New game started. Your move!") or 0
    col = int(m.group(2)) - 1
    if s["status"] != "playing":
        s["board"] = fresh()["board"]; s["status"] = "playing"; s["last"] = []; s["win"] = []; s["games"] += 1
    b = s["board"]
    if b[0][col]:
        return finish("error", f"Column {col + 1} is full. Pick another column.") or 0
    r = drop(b, col, 1); s["last"] = [{"by": "visitor", "row": r, "col": col}]; s["win"] = []
    entry = {"user": user, "col": col + 1}
    msg = f"@{user} dropped a disc in column **{col + 1}**."
    w = find_win(b, 1)
    if w:
        s["status"], s["win"] = "visitor_win", [list(x) for x in w]; s["score"]["visitor"] += 1
        msg += " **You win!** Drop in any column to start a new game."
    elif full(b):
        s["status"] = "draw"; s["score"]["draw"] += 1; msg += " It's a draw!"
    else:
        bc = bot_move(b); br = drop(b, bc, 2)
        s["last"].append({"by": "jarvis", "row": br, "col": bc}); entry["bot"] = bc + 1
        msg += f" JARVIS replied in column **{bc + 1}**."
        w = find_win(b, 2)
        if w:
            s["status"], s["win"] = "jarvis_win", [list(x) for x in w]; s["score"]["jarvis"] += 1
            msg += " **JARVIS wins.** Drop in any column to try again."
        elif full(b):
            s["status"] = "draw"; s["score"]["draw"] += 1; msg += " It's a draw!"
    s["log"] = (s["log"] + [entry])[-10:]; s["version"] += 1
    save(s); write_all(s)
    msg += "\n\nThe board updates on the profile in a minute or two (GitHub caches images)."
    return finish("ok", msg) or 0

if __name__ == "__main__": sys.exit(main())
