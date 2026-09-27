"""Cover art for the post: a schematic of drag, storms and the solar cycle (dark, for g15n.net).

Not a chart: a picture of the idea. A small satellite starts high on the left; its possible fall
paths fan out (blue), from a strong Sun that pulls it into the swollen atmosphere in ~3.6 years to
a weak one that lets it last ~10.5 (the 550 km, Jan 2035 case in data/fan.csv). The atmosphere
(bottom glow) breathes slowly with the eleven-year cycle; storms are the brief orange spikes on
top of it. The Sun sits in the corner as the driver; three small labels name the parts.

Run:  pixi run python scripts/cover.py     -> figures/cover.png (site card) + figures/og.png (share)
"""

import sys
from pathlib import Path

import numpy as np
from matplotlib import patches
from matplotlib.collections import LineCollection
from matplotlib.figure import Figure
from matplotlib.transforms import Affine2D

sys.path.insert(0, str(Path(__file__).parent))
import style  # noqa: E402

style.apply()
OUT = Path(__file__).parent.parent / "figures"
BG = "#0b1224"  # between the site's slate-950 page and slate-900 cards
CYAN = "#22d3ee"  # the site's grid accent
BLUE = "#60a5fa"  # style.BLUE, lifted for a dark ground
ORANGE = style.ORANGE
T_STRONG, T_FORECAST, T_WEAK = 3.62, 7.79, 10.48  # years, 550 km from Jan 2035 (data/fan.csv)
Y0, SCALE = 0.60, 0.047  # start height and "scale height" of the schematic atmosphere
YEARS = 13.0
MONO = "DejaVu Sans Mono"  # echoes the site's monospace accents
LABEL = "#9fb3c8"


def edge(t: np.ndarray) -> np.ndarray:
    """Top of the atmosphere: slow eleven-year swell plus short storm spikes."""
    cycle = 0.465 + 0.028 * np.cos(2 * np.pi * (t - 0.4) / 11.0)
    rng = np.random.default_rng(3)
    spikes = np.zeros_like(t)
    for c in (0.4, 11.4):  # storms cluster around the two maxima in view
        for t0 in c + rng.normal(0, 1.6, 7):
            spikes += rng.uniform(0.008, 0.026) * np.exp(-0.5 * ((t - t0) / 0.035) ** 2)
    return cycle + spikes, cycle


def fall(t: np.ndarray, lifetime: float) -> np.ndarray:
    """Exponential-atmosphere decay: slow at first, then a plunge (y = Y0 + s ln(1 - t/T))."""
    with np.errstate(divide="ignore", invalid="ignore"):
        return Y0 + SCALE * np.log(np.clip(1 - t / (lifetime * 1.004), 1e-9, None))


def draw(fig, ax, t, ed, cyc) -> None:
    ax.set_facecolor(BG)
    ax.set_xlim(-0.9, YEARS)
    ax.set_ylim(0.20, 0.90)
    ax.axis("off")
    # atmosphere: a limb glow, brightest at its top edge and fading with depth
    ys = np.linspace(0.20, 0.90, 700)
    depth = np.interp(t, t, cyc)[None, :] - ys[:, None]
    alpha = np.where(depth > 0, 0.55 * np.exp(-depth / 0.06), 0.0)
    rgba = np.zeros((len(ys), len(t), 4))
    rgba[..., :3] = (0.133, 0.827, 0.933)  # CYAN
    rgba[..., 3] = alpha
    ax.imshow(
        rgba,
        extent=(t[0], t[-1], ys[0], ys[-1]),
        origin="lower",
        aspect="auto",
        interpolation="bilinear",
        zorder=1,
    )
    ax.plot(t, cyc, color=CYAN, lw=1.4, alpha=0.8, zorder=2)
    # storms: the spikes above the slow swell, in the one accent colour
    ax.fill_between(t, cyc, ed, where=ed > cyc + 0.002, color=ORANGE, alpha=0.95, lw=0, zorder=4)
    # the fan of fall paths
    lifetimes = np.linspace(T_STRONG, T_WEAK, 11)
    paths = []
    for T in lifetimes:
        y = fall(t, T)
        hit = np.argmax(y <= ed) if np.any(y <= ed) else len(t)
        paths.append((t[: hit + 1], y[: hit + 1]))
    for (x, y), T in zip(paths, lifetimes, strict=True):
        main = abs(T - T_FORECAST) < 0.4
        seg = np.stack([np.column_stack([x[:-1], y[:-1]]), np.column_stack([x[1:], y[1:]])], axis=1)
        fade = np.clip(
            (y[:-1] - np.interp(x[:-1], t, cyc)) / 0.12, 0, 1
        )  # dim as it enters the air
        lc = LineCollection(
            seg,
            colors=[(0.376, 0.647, 0.98, (0.95 if main else 0.35) * f) for f in fade],
            linewidths=2.6 if main else 1.1,
            zorder=3,
        )
        ax.add_collection(lc)
    satellite(fig, ax, 0.0, Y0)
    sun(fig)
    labels(ax, t, ed, cyc)
    # a few stars
    rng = np.random.default_rng(11)
    sx, sy = rng.uniform(-0.9, YEARS, 110), rng.uniform(0.40, 0.90, 110)
    keep = sy > np.interp(sx, t, cyc) + 0.04
    ax.scatter(
        sx[keep], sy[keep], s=rng.uniform(0.5, 3.5, keep.sum()), color="white", alpha=0.35, lw=0
    )


def _inset(fig, ax, x: float, y: float, size_in: float):
    """An equal-aspect axes centred on data point (x, y), `size_in` inches wide."""
    fx, fy = fig.transFigure.inverted().transform(ax.transData.transform((x, y)))
    w, h = fig.get_size_inches()
    sub = fig.add_axes((fx - size_in / w / 2, fy - size_in / h / 2, size_in / w, size_in / h))
    sub.set_xlim(0, 1)
    sub.set_ylim(0, 1)
    sub.set_aspect("equal")
    sub.axis("off")
    sub.patch.set_alpha(0)
    return sub


def satellite(fig, ax, x: float, y: float) -> None:
    """A small cartoon CubeSat: body, two solar wings, an antenna; tilted as if tumbling in."""
    sub = _inset(fig, ax, x, y, 0.52)
    tilt = Affine2D().rotate_deg_around(0.5, 0.5, -14) + sub.transData
    for x0 in (0.02, 0.66):  # solar wings with a cell grid
        sub.add_patch(
            patches.Rectangle(
                (x0, 0.40),
                0.32,
                0.20,
                facecolor="#1d4ed8",
                edgecolor="#93c5fd",
                lw=0.9,
                transform=tilt,
            )
        )
        for k in (1, 2, 3):
            sub.plot([x0 + 0.08 * k] * 2, [0.40, 0.60], color="#93c5fd", lw=0.5, transform=tilt)
        sub.plot([x0, x0 + 0.32], [0.50, 0.50], color="#93c5fd", lw=0.5, transform=tilt)
    sub.plot([0.34, 0.40], [0.5, 0.5], color="#cbd5e1", lw=1.2, transform=tilt)
    sub.plot([0.60, 0.66], [0.5, 0.5], color="#cbd5e1", lw=1.2, transform=tilt)
    sub.add_patch(
        patches.FancyBboxPatch(
            (0.40, 0.38),
            0.20,
            0.24,
            boxstyle="round,pad=0,rounding_size=0.03",
            facecolor="#e2e8f0",
            edgecolor="#64748b",
            lw=0.9,
            transform=tilt,
        )
    )
    sub.plot([0.5, 0.5], [0.62, 0.74], color="#cbd5e1", lw=1.0, transform=tilt)
    sub.add_patch(patches.Circle((0.5, 0.76), 0.022, color=ORANGE, transform=tilt))


def sun(fig) -> None:
    """The driver, half off the top-right corner: a warm glow, no rays needed."""
    w, h = fig.get_size_inches()
    size = 0.8  # inches: the disc; the glow spills past the axes (clip_on=False)
    cx, cy = 1 - 0.55 / w, 1 - 0.55 / h
    sub = fig.add_axes((cx - size / w / 2, cy - size / h / 2, size / w, size / h), zorder=0)
    sub.set_xlim(0, 1)
    sub.set_ylim(0, 1)
    sub.set_aspect("equal")
    sub.axis("off")
    sub.patch.set_alpha(0)
    for r, a in zip(np.linspace(1.6, 0.36, 48), np.linspace(0.004, 0.035, 48), strict=True):
        sub.add_patch(patches.Circle((0.5, 0.5), r, color="#fdba74", alpha=a, lw=0, clip_on=False))
    sub.add_patch(patches.Circle((0.5, 0.5), 0.32, color="#fbbf24", lw=0, clip_on=False))


def labels(ax, t, ed, cyc) -> None:
    """Three quiet labels so the picture reads without the article."""
    kw = dict(family=MONO, fontsize=9.5, color=LABEL, zorder=6)
    ax.text(2.4, 0.603, "possible fall paths", ha="left", va="bottom", **kw)
    x_atm = 4.4
    ax.text(
        x_atm,
        np.interp(x_atm, t, cyc) - 0.03,
        "atmosphere: swells with the Sun's 11-year cycle",
        ha="left",
        va="top",
        **{**kw, "color": "#a5f3fc", "alpha": 0.85},
    )
    window = (t > 9.5) & (t < 12.8)
    i = np.flatnonzero(window)[np.argmax((ed - cyc)[window])]
    ax.annotate(
        "storms",
        (t[i], ed[i]),
        xytext=(t[i] - 1.3, ed[i] + 0.06),
        textcoords="data",
        ha="right",
        va="center",
        arrowprops=dict(arrowstyle="-", color=LABEL, lw=0.7),
        **kw,
    )


def main() -> None:
    t = np.linspace(-0.9, YEARS, 4000)
    ed, cyc = edge(t)

    fig = Figure(figsize=(12, 5), facecolor=BG)
    ax = fig.add_axes((0, 0, 1, 1))
    draw(fig, ax, t, ed, cyc)
    fig.savefig(OUT / "cover.png", dpi=200, facecolor=BG)

    og = Figure(figsize=(12, 6.3), facecolor=BG)  # 1200x630 at 100 dpi x2
    ax = og.add_axes((0, 0, 1, 0.80))
    draw(og, ax, t, ed, cyc)
    og.text(
        0.045,
        0.93,
        "Solar drag is uninsurable",
        family=style.SERIF,
        weight="semibold",
        fontsize=34,
        color="white",
        va="top",
    )
    og.text(
        0.045,
        0.835,
        "and not because the risk is small  ·  g15n.net",
        fontsize=17,
        color="#94a3b8",
        va="top",
    )
    og.savefig(OUT / "og.png", dpi=200, facecolor=BG)
    print("wrote figures/cover.png, figures/og.png")


if __name__ == "__main__":
    main()
