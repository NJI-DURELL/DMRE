"""
generate_icons.py — Build the DMRE Chrome-extension icon set.

Composition:
  • Soft mint rounded background.
  • Stylised brain in mint-500 with darker fold lines (mint-700).
  • Two interlocking puzzle nodes on the brain's right edge — the
    "reconstruction" cue.
  • Three sparkles around the brain — the "AI" cue.

The icon is rendered at 4x the target size and downscaled with LANCZOS
so the puzzle nubs and sparkle tips stay crisp at 16x16.
"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter


# ----- Theme (blue, matching the dashboard) ------------------------------
BG          = (219, 234, 254, 255)   # blue-100
BRAIN       = (37, 99, 235, 255)     # blue-600  ← primary fill
BRAIN_DARK  = (29, 78, 216, 255)     # blue-700
FOLD        = (30, 58, 138, 255)     # blue-900
PUZZLE_LITE = (147, 197, 253, 255)   # blue-300
SPARKLE_FILL = (255, 255, 255, 255)
SPARKLE_OUT  = (30, 58, 138, 255)    # blue-900 outline so sparkles read on white


def _draw_sparkle(d: ImageDraw.ImageDraw, cx: float, cy: float, sz: float, line_w: int) -> None:
    """Four-pointed sparkle/star at (cx,cy)."""
    long  = sz
    short = sz * 0.22
    pts = [
        (cx,         cy - long),
        (cx + short, cy - short),
        (cx + long,  cy),
        (cx + short, cy + short),
        (cx,         cy + long),
        (cx - short, cy + short),
        (cx - long,  cy),
        (cx - short, cy - short),
    ]
    d.polygon(pts, fill=SPARKLE_FILL, outline=SPARKLE_OUT, width=line_w)


def _draw_brain(d: ImageDraw.ImageDraw, W: int) -> None:
    """Compose a brain silhouette out of overlapping circles + an ellipse."""
    cx, cy = W / 2, W * 0.535

    # Two hemispheres approximated by clusters of circles.
    bump = lambda x, y, r: d.ellipse(
        [cx + x - r, cy + y - r, cx + x + r, cy + y + r], fill=BRAIN
    )
    R = W * 0.13

    # Symmetric cluster — top, sides, bottom for each hemisphere
    bumps = [
        # left
        (-W*0.18, -W*0.17, R),
        (-W*0.22, -W*0.02, R*0.95),
        (-W*0.18,  W*0.13, R),
        (-W*0.06, -W*0.21, R*0.95),
        (-W*0.06,  W*0.18, R*0.95),
        # right
        ( W*0.18, -W*0.17, R),
        ( W*0.22, -W*0.02, R*0.95),
        ( W*0.18,  W*0.13, R),
        ( W*0.06, -W*0.21, R*0.95),
        ( W*0.06,  W*0.18, R*0.95),
        # filler
        (0, 0, R*1.1),
    ]
    for x, y, r in bumps:
        bump(x, y, r)

    # Brain stem hint
    d.ellipse(
        [cx - W*0.05, cy + W*0.20, cx + W*0.05, cy + W*0.30],
        fill=BRAIN_DARK,
    )

    # Vertical inter-hemispheric divide
    fold_w = max(2, int(W * 0.012))
    d.line(
        [(cx, cy - W*0.22), (cx, cy + W*0.22)],
        fill=FOLD, width=fold_w,
    )

    # Curvy folds (left then right, mirrored)
    fw = max(2, int(W * 0.010))
    for side in (-1, 1):
        for off, span in [(0.06, 0.16), (0.13, 0.10)]:
            x_a = cx + side * (off - span/2) * W
            x_b = cx + side * (off + span/2) * W
            x0, x1 = sorted((x_a, x_b))
            y0 = cy - span/2 * W
            y1 = cy + span/2 * W
            d.arc(
                [x0, y0, x1, y1],
                start=270 if side < 0 else 90,
                end=90 if side < 0 else 270,
                fill=FOLD, width=fw,
            )


def _draw_puzzle_pieces(d: ImageDraw.ImageDraw, W: int) -> None:
    """A puzzle-piece silhouette docked to the brain's right edge.

    Renders: a small square body with a circular "nub" on its right side and
    a thin neck attaching the body to the brain itself — unmistakable as a
    puzzle piece, not a floating circle.
    """
    cx, cy = W / 2, W * 0.535
    line_w = max(2, int(W * 0.012))

    # Neck connecting brain to the puzzle body — narrow rectangle
    neck = W * 0.045
    nx0 = cx + W * 0.18
    nx1 = cx + W * 0.27
    ny0 = cy - neck / 2
    ny1 = cy + neck / 2
    d.rectangle([nx0, ny0, nx1, ny1], fill=PUZZLE_LITE, outline=FOLD, width=line_w)

    # Square body of the puzzle piece
    body = W * 0.13
    bx0 = cx + W * 0.27
    by0 = cy - body / 2
    bx1 = bx0 + body
    by1 = by0 + body
    d.rounded_rectangle(
        [bx0, by0, bx1, by1],
        radius=W * 0.020,
        fill=PUZZLE_LITE, outline=FOLD, width=line_w,
    )

    # Round nub sticking out of the right of the body
    nub_r = W * 0.050
    nubx = bx1 + nub_r * 0.55
    nuby = (by0 + by1) / 2
    d.ellipse(
        [nubx - nub_r, nuby - nub_r, nubx + nub_r, nuby + nub_r],
        fill=PUZZLE_LITE, outline=FOLD, width=line_w,
    )

    # Cover the seam where the neck meets the brain so the FOLD outline doesn't
    # cross into the brain interior.
    d.rectangle([nx0 - 2, ny0 + line_w, nx0 + line_w + 2, ny1 - line_w], fill=PUZZLE_LITE)


def render(target: int) -> Image.Image:
    SCALE = 4 if target >= 32 else 6           # extra supersample for tiny icons
    W = target * SCALE
    img = Image.new('RGBA', (W, W), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # --- 1. Soft rounded background ---
    margin = W * 0.04
    radius = W * 0.22
    d.rounded_rectangle(
        [margin, margin, W - margin, W - margin],
        radius=radius,
        fill=BG,
    )

    # --- 2. Brain ---
    _draw_brain(d, W)

    # --- 3. Puzzle nodes (omit at 16px — too noisy) ---
    if target >= 32:
        _draw_puzzle_pieces(d, W)

    # --- 4. Sparkles (skip at 16, simplify at 48) ---
    sparkle_outline_w = max(2, int(W * 0.008))
    if target >= 128:
        _draw_sparkle(d, W * 0.18, W * 0.16, W * 0.080, sparkle_outline_w)
        _draw_sparkle(d, W * 0.86, W * 0.84, W * 0.065, sparkle_outline_w)
        _draw_sparkle(d, W * 0.14, W * 0.84, W * 0.050, sparkle_outline_w)
    elif target >= 32:
        _draw_sparkle(d, W * 0.18, W * 0.16, W * 0.085, sparkle_outline_w)
        _draw_sparkle(d, W * 0.85, W * 0.85, W * 0.065, sparkle_outline_w)

    # Slight smoothing pass before downscale tightens the edges.
    if target < 64:
        img = img.filter(ImageFilter.GaussianBlur(radius=0.5))

    return img.resize((target, target), Image.LANCZOS)


def main() -> None:
    out_dir = Path(__file__).parent / "icons"
    out_dir.mkdir(parents=True, exist_ok=True)
    for size in (16, 48, 128):
        icon = render(size)
        icon.save(out_dir / f"icon{size}.png", optimize=True)
        print(f"  wrote icons/icon{size}.png  ({size}x{size})")


if __name__ == "__main__":
    main()
