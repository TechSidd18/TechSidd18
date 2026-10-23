#!/usr/bin/env python3
"""Connect Four vs JARVIS, played through GitHub issues + Actions.

A visitor clicks a column badge in the README -> a pre-filled issue
("c4|drop|3") opens -> this script applies the move, JARVIS answers,
and the board SVG + README log are regenerated.
Only stdlib. Issue title is read from the environment, never from a shell.
"""
import json
import os
import re
import sys

ROWS, COLS = 6, 7
STATE = os.environ.get("STATE_PATH", "game/state.json")
SVG = os.environ.get("SVG_PATH", "assets/connect4.svg")
README = os.environ.get("README_PATH", "README.md")
COMMENT = os.environ.get("COMMENT_PATH", "/tmp/c4_comment.md")
GOLD, CRIM, BG = "#C8A45C", "#A4161A", "#0E0E10"


# ---------------- game logic ----------------
def new_state(stats=None):
    return {
        "board": [[0] * COLS for _ in range(ROWS)],
        "status": "playing",  # playing | won | lost | draw
        "stats": stats or {"games": 0, "visitors": 0, "jarvis": 0, "draws": 0},
        "log": [],
        "last": [],  # cells dropped in the most recent turn (for the drop animation)
        "win": [],  # winning four cells
    }


def drop(board, col, p):
    for r in range(ROWS - 1, -1, -1):
        if board[r][col] == 0:
            board[r][col] = p
            return r
    return None


def valid(board):
    return [c for c in range(COLS) if board[0][c] == 0]


def find_win(board):
    for r in range(ROWS):
        for c in range(COLS):
            p = board[r][c]
            if not p:
                continue
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                cells = [(r + i * dr, c + i * dc) for i in range(4)]
                if all(0 <= x < ROWS and 0 <= y < COLS and board[x][y] == p for x, y in cells):
                    return p, cells
    return 0, []


def heuristic(board, me):
    opp = 1 if me == 2 else 2
    score = sum(1 for r in range(ROWS) if board[r][COLS // 2] == me) * 3
    wins = []
    for r in range(ROWS):
        for c in range(COLS):
            for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
                cells = [(r + i * dr, c + i * dc) for i in range(4)]
                if all(0 <= x < ROWS and 0 <= y < COLS for x, y in cells):
                    wins.append([board[x][y] for x, y in cells])
    for w in wins:
        m, o, e = w.count(me), w.count(opp), w.count(0)
        if m == 4: score += 1000
        elif m == 3 and e == 1: score += 6
        elif m == 2 and e == 2: score += 2
        if o == 3 and e == 1: score -= 8
    return score


def minimax(board, depth, alpha, beta, maxing, me=2):
    opp = 1
    w, _ = find_win(board)
    if w == me: return 100000 + depth, None
    if w == opp: return -100000 - depth, None
    cols = valid(board)
    if not cols or depth == 0:
        return heuristic(board, me), None
    order = sorted(cols, key=lambda c: abs(c - COLS // 2))
    best_col = order[0]
    if maxing:
        val = -10**9
        for c in order:
            b = [row[:] for row in board]; drop(b, c, me)
            s, _ = minimax(b, depth - 1, alpha, beta, False, me)
            if s > val: val, best_col = s, c
            alpha = max(alpha, val)
            if alpha >= beta: break
        return val, best_col
    val = 10**9
    for c in order:
        b = [row[:] for row in board]; drop(b, c, opp)
        s, _ = minimax(b, depth - 1, alpha, beta, True, me)
        if s < val: val, best_col = s, c
        beta = min(beta, val)
        if alpha >= beta: break
    return val, best_col


def jarvis_move(board):
    return minimax(board, 5, -10**9, 10**9, True)[1]


# ---------------- rendering ----------------
def render(st):
    W, H = 950, 420
    cell, x0, y0 = 50, 70, 78
    board, last = st["board"], {tuple(x) for x in st["last"]}
    win = {tuple(x) for x in st["win"]}
    parts = []
    for c in range(COLS):
        parts.append(f'<text class="mono" x="{x0+c*cell+cell/2}" y="{y0-12}" font-size="10" fill="#7E786B" text-anchor="middle">{c+1}</text>')
    parts.append(f'<rect x="{x0-8}" y="{y0-4}" width="{COLS*cell+16}" height="{ROWS*cell+8}" rx="10" fill="none" stroke="{GOLD}" stroke-opacity=".3"/>')
    for r in range(ROWS):
        for c in range(COLS):
            cx, cy = x0 + c * cell + cell / 2, y0 + r * cell + cell / 2 + 2
            p = board[r][c]
            parts.append(f'<circle cx="{cx}" cy="{cy}" r="19" fill="#161517" stroke="{GOLD}" stroke-opacity=".12"/>')
            if p:
                col = GOLD if p == 1 else CRIM
                cls = "disc fall" if (r, c) in last else "disc"
                delay = f' style="animation-delay:{0.0 if p == 1 else 0.55}s"' if (r, c) in last else ""
                parts.append(
                    f'<g class="{cls}"{delay}><circle cx="{cx}" cy="{cy}" r="18" fill="{col}"/>'
                    f'<circle cx="{cx}" cy="{cy}" r="11" fill="none" stroke="#0E0E10" stroke-opacity=".35" stroke-width="2"/></g>'
                )
            if (r, c) in win:
                parts.append(f'<circle class="winring" cx="{cx}" cy="{cy}" r="22" fill="none" stroke="#F3EEE2" stroke-width="2"/>')
    status = st["status"]
    msg, sub = {
        "playing": ("YOUR MOVE", "Pick a column. JARVIS answers right after."),
        "won": ("YOU WON", "Nicely played. Drop a disc to start a new game."),
        "lost": ("JARVIS WON", "Better luck next time. Drop a disc to rematch."),
        "draw": ("DRAW", "Board is full. Drop a disc to start again."),
    }[status]
    s = st["stats"]
    rx = 520
    panel = [
        f'<text class="mono" x="{rx}" y="94" font-size="10" letter-spacing="1.6" fill="#7E786B">STATUS</text>',
        f'<text class="sans" x="{rx}" y="130" font-size="30" font-weight="700" fill="#F3EEE2">{msg}</text>',
        f'<text class="mono" x="{rx}" y="152" font-size="10.5" fill="#9A9384">{sub}</text>',
        f'<line x1="{rx}" y1="176" x2="920" y2="176" stroke="{GOLD}" stroke-opacity=".2"/>',
    ]
    for i, (lab, val, colr) in enumerate((("VISITORS", s["visitors"], GOLD), ("JARVIS", s["jarvis"], CRIM), ("DRAWS", s["draws"], "#B9B2A3"))):
        x = rx + i * 133
        panel.append(f'<text class="sans" x="{x}" y="222" font-size="34" font-weight="700" fill="#F3EEE2">{val}</text>')
        panel.append(f'<circle cx="{x+4}" cy="238" r="3.5" fill="{colr}"/><text class="mono" x="{x+14}" y="242" font-size="10" letter-spacing="1.3" fill="{colr}">{lab}</text>')
    panel += [
        f'<line x1="{rx}" y1="268" x2="920" y2="268" stroke="{GOLD}" stroke-opacity=".2"/>',
        f'<text class="mono" x="{rx}" y="296" font-size="10" letter-spacing="1.6" fill="#7E786B">HOW TO PLAY</text>',
        f'<text class="mono" x="{rx}" y="320" font-size="11" fill="#D9D3C4"><tspan fill="{CRIM}">01</tspan>  Click a column badge under the board</text>',
        f'<text class="mono" x="{rx}" y="341" font-size="11" fill="#D9D3C4"><tspan fill="{CRIM}">02</tspan>  Press "Submit new issue" (no edits)</text>',
        f'<text class="mono" x="{rx}" y="362" font-size="11" fill="#D9D3C4"><tspan fill="{CRIM}">03</tspan>  Refresh after about a minute</text>',
        f'<circle cx="{rx+4}" cy="388" r="4" fill="{GOLD}"/><text class="mono" x="{rx+14}" y="392" font-size="10" fill="#9A9384">YOU</text>',
        f'<circle cx="{rx+74}" cy="388" r="4" fill="{CRIM}"/><text class="mono" x="{rx+84}" y="392" font-size="10" fill="#9A9384">JARVIS</text>',
    ]
    style = """
.mono{font-family:'SFMono-Regular',Consolas,'Liberation Mono',monospace}
.sans{font-family:'Helvetica Neue',Helvetica,Arial,sans-serif}
@keyframes dot{0%,100%{opacity:.4}50%{opacity:1}}
@keyframes fall{from{transform:translateY(-320px);opacity:0}15%{opacity:1}70%{transform:translateY(6px)}85%{transform:translateY(-3px)}to{transform:none}}
@keyframes win{0%,100%{opacity:.25}50%{opacity:1}}
.dot{animation:dot 2.6s ease-in-out infinite}
.fall{animation:fall .75s ease-in both}
.winring{animation:win 1.4s ease-in-out infinite}
"""
    head = (
        f'<circle class="dot" cx="34" cy="26" r="3.5" fill="{CRIM}"/>'
        f'<text class="mono" x="46" y="30" font-size="11" letter-spacing="1.6" fill="{GOLD}">GAME MODE // CONNECT FOUR</text>'
        f'<text class="mono" x="920" y="30" font-size="10.5" letter-spacing="1.6" fill="#7E786B" text-anchor="end">VISITORS VS JARVIS</text>'
        f'<line x1="30" y1="46" x2="920" y2="46" stroke="{GOLD}" stroke-opacity=".25"/>'
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}"><style>{style}</style>'
        f'<rect width="{W}" height="{H}" rx="14" fill="{BG}"/>{head}{"".join(parts)}{"".join(panel)}'
        f'<line x1="30" y1="{H-12}" x2="920" y2="{H-12}" stroke="{GOLD}" stroke-opacity=".25"/></svg>'
    )


def update_readme(st):
    if not os.path.exists(README):
        return
    lines = [f"- {e}" for e in st["log"][-5:][::-1]] or ["- No moves yet. Be the first to play."]
    s = open(README, encoding="utf-8").read()
    a, b = "<!--C4_LOG:START-->", "<!--C4_LOG:END-->"
    if a in s and b in s:
        s = re.sub(re.escape(a) + r".*?" + re.escape(b), a + "\n" + "\n".join(lines) + "\n" + b, s, flags=re.S)
        open(README, "w", encoding="utf-8").write(s)


# ---------------- main ----------------
def say(text):
    open(COMMENT, "w", encoding="utf-8").write(text)
    print(text)


def load():
    if os.path.exists(STATE):
        return json.load(open(STATE, encoding="utf-8"))
    return new_state()


def save(st):
    os.makedirs(os.path.dirname(STATE) or ".", exist_ok=True)
    json.dump(st, open(STATE, "w", encoding="utf-8"), indent=1)
    os.makedirs(os.path.dirname(SVG) or ".", exist_ok=True)
    open(SVG, "w", encoding="utf-8").write(render(st))
    update_readme(st)


def main():
    if "--init" in sys.argv:
        save(new_state()); return
    title = os.environ.get("ISSUE_TITLE", "").strip()
    user = re.sub(r"[^A-Za-z0-9-]", "", os.environ.get("ISSUE_USER", "someone")) or "someone"
    st = load()

    if title == "c4|new":
        st = new_state(st["stats"]); st["log"] = st["log"][-4:] + [f"@{user} started a new game"]
        save(st); say("New game started. Pick a column!"); return

    m = re.fullmatch(r"c4\|drop\|([1-7])", title)
    if not m:
        say("Sorry, I could not read that move. Please use the column badges in the README without editing the title.")
        return
    col = int(m.group(1)) - 1

    if st["status"] != "playing":
        st = new_state(st["stats"]) | {"log": st["log"]}
    board = st["board"]
    if board[0][col] != 0:
        say(f"Column {col+1} is full. Try another one."); return

    r = drop(board, col, 1)
    st["last"] = [[r, col]]
    st["win"] = []
    w, cells = find_win(board)
    entry = f"@{user} dropped in column {col+1}"
    if w == 1:
        st["status"], st["win"] = "won", [list(x) for x in cells]
        st["stats"]["visitors"] += 1; st["stats"]["games"] += 1
        entry += " and **won**"
    elif not valid(board):
        st["status"] = "draw"; st["stats"]["draws"] += 1; st["stats"]["games"] += 1
        entry += " (draw)"
    else:
        jc = jarvis_move(board)
        jr = drop(board, jc, 2)
        st["last"].append([jr, jc])
        entry += f", JARVIS answered in column {jc+1}"
        w, cells = find_win(board)
        if w == 2:
            st["status"], st["win"] = "lost", [list(x) for x in cells]
            st["stats"]["jarvis"] += 1; st["stats"]["games"] += 1
            entry += " and **won**"
        elif not valid(board):
            st["status"] = "draw"; st["stats"]["draws"] += 1; st["stats"]["games"] += 1
            entry += " (draw)"
    st["log"] = (st["log"] + [entry])[-20:]
    save(st)
    final = {"playing": "Your move!", "won": "You won! Drop another disc to play again.",
             "lost": "JARVIS won this round. Drop another disc for a rematch.", "draw": "It is a draw."}[st["status"]]
    say(f"{entry.replace('**', '')}. {final}\n\nThe board in the README updates in about a minute.")


if __name__ == "__main__":
    main()
