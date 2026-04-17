"""Alfred — shared halo circle renderer."""
import math
from rich.text import Text

C_HOT    = "#00ff88"
C_SCAN   = "#00ffff"
C_ELEC   = "#0088ff"
C_DIM    = "#005577"
C_DEEP   = "#001122"
C_WHITE  = "#e0f8ff"
C_MUTED  = "#4a8fa8"
C_ACCENT = "#ff3399"
C_BORDER = "#0077bb"


def halo(t: float, state: str, w: int = 70) -> Text:
    """
    Render an animated halo circle.

    state: 'idle' | 'listening' | 'thinking' | 'speaking'
    w:     canvas width in terminal columns
    """
    R  = 6          # ring radius (rows)
    H  = R * 2 + 5  # canvas height
    AX = 2.4        # horizontal stretch (chars are ~2× taller than wide)
    cx = w // 2
    cy = H // 2

    grid = [[(' ', '')] * w for _ in range(H)]

    def put(x: int, y: int, ch: str, sty: str) -> None:
        if 0 <= x < w and 0 <= y < H:
            grid[y][x] = (ch, sty)

    # ── ring ─────────────────────────────────────────────────────────────────
    for i in range(720):
        a = 2 * math.pi * i / 720
        x = int(round(cx + R * AX * math.cos(a)))
        y = int(round(cy + R       * math.sin(a)))

        if state == 'idle':
            b = (math.sin(t * 1.2 + a * 2) + 1) / 2
            if   b > 0.65: ch, sty = '◉', C_SCAN
            elif b > 0.35: ch, sty = '◌', C_DIM
            else:          ch, sty = '·', C_DEEP

        elif state == 'listening':
            b = (math.sin(t * 5 + a) + 1) / 2
            if   b > 0.70: ch, sty = '●', C_HOT
            elif b > 0.40: ch, sty = '◉', C_SCAN
            else:          ch, sty = '○', C_ELEC

        elif state == 'thinking':
            spin = (t * 2.2) % (2 * math.pi)
            diff = abs(((a - spin) + math.pi) % (2 * math.pi) - math.pi)
            if diff < 0.12:
                ch, sty = '◉', C_ACCENT
            elif diff < 0.70:
                fade = 1 - diff / 0.70
                ch  = '◌' if fade > 0.5 else '·'
                sty = C_SCAN if fade > 0.6 else C_ELEC if fade > 0.3 else C_DIM
            else:
                ch, sty = '·', C_DEEP

        elif state == 'speaking':
            wave = (math.sin(t * 7 + a * 2) + 1) / 2
            if   wave > 0.75: ch, sty = '●', C_HOT
            elif wave > 0.50: ch, sty = '◉', C_SCAN
            elif wave > 0.25: ch, sty = '◌', C_ELEC
            else:             ch, sty = '·', C_DIM

        else:
            ch, sty = '·', C_DEEP

        put(x, y, ch, sty)

    # ── centre label ──────────────────────────────────────────────────────────
    if state == 'idle':
        label, lstyle = 'ALFRED', C_WHITE
    elif state == 'listening':
        n = int(t * 3) % 4
        label, lstyle = ('···'[:n]).ljust(3), C_HOT
    elif state == 'thinking':
        n = int(t * 4) % 4
        label, lstyle = ('···'[:n]).ljust(3), C_ACCENT
    else:  # speaking
        label, lstyle = 'ALFRED', C_SCAN

    lx = cx - len(label) // 2
    for i, ch in enumerate(label):
        put(lx + i, cy, ch, lstyle)

    # ── render ────────────────────────────────────────────────────────────────
    result = Text(no_wrap=True, overflow='crop')
    for row in grid:
        for ch, sty in row:
            result.append(ch, style=sty) if sty else result.append(ch)
        result.append('\n')
    return result
