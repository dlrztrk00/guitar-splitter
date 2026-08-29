"""Draws the app icon.

Rendered pixel by pixel rather than through a rasteriser. macOS's `qlmanage`
was the obvious tool and it is wrong for this: it renders an SVG as a *document
thumbnail*, on an opaque white page, so the rounded corners come out white
instead of transparent. Here the alpha channel is ours.

Anti-aliasing is analytic: every shape is a signed distance field, and coverage
is the distance clamped across one pixel. No supersampling, no fringing.

    ./venv/bin/python icon.py /Applications/GuitarSplit.app/Contents/Resources/GuitarSplit.icns
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

# The design is drawn in a 1024-unit square and scaled to whatever size is asked
# for, so every icon size comes from the same geometry.
DESIGN = 1024.0

CREAM_HI, CREAM_LO = (0xFD, 0xFA, 0xF3), (0xDD, 0xD3, 0xC0)
RED_HI, RED_MID, RED_LO = (0xE0, 0x2B, 0x21), (0xA0, 0x1C, 0x15), (0x68, 0x0F, 0x0B)
BG_HI, BG_LO = (0x1C, 0x17, 0x15), (0x05, 0x04, 0x04)
GREEN = (0x6F, 0xD4, 0x4F)
INK = (0x1A, 0x15, 0x12)
MARKER_RED = (0xC9, 0x24, 0x1C)
REEL_OUTER, REEL_HUB, WINDOW = (0x63, 0x10, 0x0C), (0x14, 0x11, 0x10), (0x2B, 0x07, 0x05)


def render(size: int) -> bytes:
    """One icon at `size` px, as straight-alpha RGBA bytes."""
    k = size / DESIGN
    yy, xx = np.mgrid[0:size, 0:size].astype(np.float64)
    xx = (xx + 0.5) / k          # work in design units
    yy = (yy + 0.5) / k
    px = 1.0 / k                 # one output pixel, in design units

    img = np.zeros((size, size, 4), dtype=np.float64)

    def coverage(sdf: np.ndarray) -> np.ndarray:
        """Distance field to per-pixel alpha, one pixel wide at the edge."""
        return np.clip(0.5 - sdf / px, 0.0, 1.0)

    def rrect(cx, cy, w, h, r, x=xx, y=yy):
        qx = np.abs(x - cx) - (w / 2 - r)
        qy = np.abs(y - cy) - (h / 2 - r)
        return (np.minimum(np.maximum(qx, qy), 0.0)
                + np.hypot(np.maximum(qx, 0.0), np.maximum(qy, 0.0)) - r)

    def circle(cx, cy, r):
        return np.hypot(xx - cx, yy - cy) - r

    def ellipse(cx, cy, rx, ry):
        d = np.hypot((xx - cx) / rx, (yy - cy) / ry)
        return (d - 1.0) * min(rx, ry)

    def rotated(cx, cy, w, h, r, degrees):
        t = np.radians(degrees)
        dx, dy = xx - cx, yy - cy
        return rrect(0, 0, w, h, r,
                     x=dx * np.cos(t) + dy * np.sin(t),
                     y=-dx * np.sin(t) + dy * np.cos(t))

    def vgrad(stops):
        """Vertical gradient. stops: [(y_in_design_units, (r,g,b)), ...]"""
        ys = [s[0] for s in stops]
        out = np.zeros((size, size, 3))
        for ch in range(3):
            out[..., ch] = np.interp(yy, ys, [s[1][ch] for s in stops])
        return out

    def paint(colour, alpha):
        """Composite `colour` over the image using straight alpha."""
        a = np.clip(alpha, 0.0, 1.0)
        c = np.asarray(colour, dtype=np.float64)
        if c.ndim == 1:
            c = np.broadcast_to(c, (size, size, 3))
        dst_a = img[..., 3]
        out_a = a + dst_a * (1 - a)
        num = c * a[..., None] + img[..., :3] * (dst_a * (1 - a))[..., None]
        safe = np.maximum(out_a, 1e-9)[..., None]
        img[..., :3] = np.where(out_a[..., None] > 0, num / safe, 0.0)
        img[..., 3] = out_a

    # Background plate. Everything outside it stays fully transparent — this is
    # the whole point of not using a thumbnailer.
    plate = coverage(rrect(512, 512, 1024, 1024, 228))
    paint(vgrad([(0, BG_HI), (1024, BG_LO)]), plate)

    # Cassette body, clipped to the plate so nothing bleeds past the corners.
    body = coverage(rrect(512, 512, 768, 508, 38)) * plate
    paint(vgrad([(258, RED_HI), (538, RED_MID), (766, RED_LO)]), body)

    # Gloss across the top of the shell.
    paint((255, 255, 255), coverage(ellipse(512, 168, 460, 150)) * body * 0.16)

    # Top label, with two marker strokes on it.
    label = coverage(rrect(512, 383, 660, 142, 9)) * body
    paint(vgrad([(312, CREAM_HI), (454, CREAM_LO)]), label)
    paint(INK, coverage(rrect(457, 371, 474, 30, 15)) * label * 0.85)
    paint(MARKER_RED, coverage(rrect(363, 414, 286, 20, 10)) * label * 0.80)

    # Reels: dark disc, cream ring, dark hub.
    for cx in (336, 688):
        paint(REEL_OUTER, coverage(circle(cx, 596, 106)) * body)
        ring = np.clip(coverage(circle(cx, 596, 70.5)) - coverage(circle(cx, 596, 53.5)), 0, 1)
        paint(CREAM_HI, ring * body)
        paint(REEL_HUB, coverage(circle(cx, 596, 53.5)) * body)

    paint(WINDOW, coverage(rrect(512, 596, 120, 68, 12)) * body)

    # Bottom strip and the tilted sticker.
    paint(CREAM_HI, coverage(rrect(512, 722, 660, 44, 7)) * body * 0.93)
    paint(GREEN, coverage(rotated(808, 726, 164, 80, 7, -9)) * plate)

    rgba = np.clip(np.concatenate([img[..., :3], img[..., 3:] * 255], axis=2), 0, 255)
    return rgba.astype(np.uint8).tobytes()


def png(size: int, dest: Path) -> None:
    """Raw pixels to PNG through ffmpeg, so there is no encoder to maintain."""
    proc = subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgba",
         "-s", f"{size}x{size}", "-i", "-", str(dest)],
        input=render(size), capture_output=True,
    )
    if proc.returncode != 0:
        raise SystemExit("ffmpeg failed: " + proc.stderr.decode()[:400])


# iconutil insists on this exact set of names.
NAMES = {
    16: ["icon_16x16.png"],
    32: ["icon_32x32.png", "icon_16x16@2x.png"],
    64: ["icon_32x32@2x.png"],
    128: ["icon_128x128.png"],
    256: ["icon_256x256.png", "icon_128x128@2x.png"],
    512: ["icon_512x512.png", "icon_256x256@2x.png"],
    1024: ["icon_512x512@2x.png"],
}


def build(dest_icns: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        iconset = Path(tmp) / "GuitarSplit.iconset"
        iconset.mkdir()
        for size, names in NAMES.items():
            first = iconset / names[0]
            png(size, first)
            for extra in names[1:]:
                subprocess.run(["cp", str(first), str(iconset / extra)], check=True)
        dest_icns.parent.mkdir(parents=True, exist_ok=True)
        proc = subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(dest_icns)],
                              capture_output=True)
        if proc.returncode != 0:
            raise SystemExit("iconutil failed: " + proc.stderr.decode()[:400])


if __name__ == "__main__":
    out = Path(sys.argv[1] if len(sys.argv) > 1 else "GuitarSplit.icns")
    build(out)
    print(f"wrote {out} ({out.stat().st_size / 1024:.0f} KB)")
