"""g15n chart style: one look for every figure posted on g15n.substack.com.

Matched to the blog's Substack theme (accent #FF6719, print #363737 / #757575 / #b6b6b6,
detail #e6e6e6, Spectral serif). The rules, in the order they bite:

* Colour carries meaning, the same in every figure. BLUE = the model or the forecast,
  INK = what actually happened, ORANGE (the blog accent) = the one thing the figure is
  about, GREY = context. Nothing else gets a colour.
* Palette check (dataviz validate_palette.js, light): blue/orange pass CVD (worst dE 32)
  and normal vision (dE 42). Orange is 2.84:1 on white, so every orange mark carries a
  direct text label; text itself is always INK/INK2, never orange.
* Anatomy: title = the claim (Spectral SemiBold), subtitle = what is plotted, footer =
  source and licence, so a figure stays honest when it travels without the post.
* Size for phones: 6 in wide at 300 dpi (1800 px). Substack shows ~728 px on desktop and
  ~360 px on a phone, so annotations are >= 10.5 pt and titles 15.5 pt.
"""

from pathlib import Path

import matplotlib as mpl
from matplotlib import font_manager
from matplotlib.backends.backend_agg import FigureCanvasAgg

BLUE = "#2563EB"
BLUE_LIGHT = "#A8C0F7"  # the same hue, for a second, lesser model element
ORANGE = "#FF6719"  # Substack accent
INK = "#363737"  # Substack print primary
INK2 = "#757575"  # Substack print secondary
MUTED = "#B6B6B6"  # Substack print tertiary
GRID = "#E6E6E6"  # Substack detail
ZONE = "#F2F2F0"  # shaded context band
SURFACE = "#FFFFFF"

W = 6.0  # inches
DPI = 300
SERIF = "Spectral"
SANS = ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"]

FS_TITLE, FS_SUB, FS_NOTE, FS_TICK, FS_FOOT = 15.5, 10.5, 10.5, 10, 7.5

_FONTS = Path(__file__).parent.parent / "fonts"  # Spectral, SIL Open Font License


def apply() -> None:
    for ttf in _FONTS.glob("*.ttf"):
        font_manager.fontManager.addfont(str(ttf))
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": SANS,
            "font.size": FS_TICK,
            "axes.edgecolor": MUTED,
            "axes.linewidth": 0.8,
            "axes.labelcolor": INK2,
            "axes.labelsize": FS_TICK,
            "xtick.color": MUTED,
            "ytick.color": MUTED,
            "xtick.labelcolor": INK2,
            "ytick.labelcolor": INK2,
            "xtick.labelsize": FS_TICK,
            "ytick.labelsize": FS_TICK,
            "axes.grid": True,
            "grid.color": GRID,
            "grid.linewidth": 0.7,
            "axes.axisbelow": True,
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
            "savefig.facecolor": SURFACE,
            "savefig.dpi": DPI,
            "legend.frameon": False,
        }
    )


def clean(ax) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.tick_params(length=0)


def frame(fig, title: str, subtitle: str, footer: str) -> tuple[float, float]:
    """Title, subtitle and footer, left-aligned; returns (header, footer) heights in inches.

    Heights are measured from the rendered text, so callers place the axes below the header
    and above the footer (style.axes) without guessing line heights per font.
    """
    w, h = fig.get_size_inches()
    renderer = FigureCanvasAgg(fig).get_renderer()
    pad = 0.12

    def bottom_in(artist) -> float:  # distance from the figure top to the artist's bottom, inches
        return h - artist.get_window_extent(renderer).y0 / fig.dpi

    t = fig.text(
        pad / w,
        1 - pad / h,
        title,
        ha="left",
        va="top",
        family=SERIF,
        weight="semibold",
        fontsize=FS_TITLE,
        color=INK,
        linespacing=1.0,
    )
    s = fig.text(
        pad / w,
        1 - (bottom_in(t) + 0.07) / h,
        subtitle,
        ha="left",
        va="top",
        fontsize=FS_SUB,
        color=INK2,
        linespacing=1.25,
    )
    ft = fig.text(
        pad / w,
        0.08 / h,
        footer,
        ha="left",
        va="bottom",
        fontsize=FS_FOOT,
        color=INK2,
        linespacing=1.3,
    )
    footer_h = ft.get_window_extent(renderer).y1 / fig.dpi
    return bottom_in(s), footer_h


def axes(fig, left: float, right: float, top: float, bottom: float):
    """An axes placed by margins in inches (robust across figure heights)."""
    w, h = fig.get_size_inches()
    return fig.add_axes((left / w, bottom / h, 1 - (left + right) / w, 1 - (top + bottom) / h))
