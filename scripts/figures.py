"""The four figures of 'Solar drag is uninsurable', rebuilt from data/ into figures/.

Every image carries its own title, subtitle and source footer (style.frame), so it stays
honest when it travels without the post. Style rules live in style.py.

Run:  pixi run python scripts/fetch_data.py      (once: SILSO sunspots for figures 2 and 3)
      pixi run python scripts/figures.py [fig0|fig1|fig2|fig3 ...]
"""

import sys
from pathlib import Path

import numpy as np
import polars as pl
from matplotlib.figure import Figure
from matplotlib.patches import FancyBboxPatch, Rectangle
from matplotlib.ticker import FixedLocator, NullLocator

sys.path.insert(0, str(Path(__file__).parent))
import style  # noqa: E402
from style import BLUE, BLUE_LIGHT, FS_NOTE, INK, INK2, MUTED, ORANGE, SURFACE, ZONE  # noqa: E402

import data  # noqa: E402

style.apply()
OUT = Path(__file__).parent.parent / "figures"


def note(ax, text, xy, xytext, ha="left", bold_first=False, **kw):
    """Direct label with a hairline leader; the first line optionally bold."""
    if bold_first and "\n" in text:
        head, tail = text.split("\n", 1)
        ax.annotate(
            head,
            xy,
            xytext=xytext,
            textcoords="data",
            ha=ha,
            va="bottom",
            fontsize=FS_NOTE,
            color=INK,
            weight="bold",
            arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.7, shrinkA=3, shrinkB=5),
            **kw,
        )
        ax.annotate(
            tail,
            xytext,
            xytext=(0, -2),
            textcoords="offset points",
            ha=ha,
            va="top",
            fontsize=FS_NOTE,
            color=INK2,
        )
    else:
        ax.annotate(
            text,
            xy,
            xytext=xytext,
            textcoords="data",
            ha=ha,
            va="center",
            fontsize=FS_NOTE,
            color=INK,
            arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.7, shrinkA=3, shrinkB=5),
            **kw,
        )


# ------------------------------------------------------------------ Figure 0: what can be insured
def fig0():
    stops = {"Factory": 0.0, "Launch": 1.0, "+1 year": 1.9, "Mission ends": 4.2, "Re-entry": 5.3}
    rows = [  # label, start, end, colour, caption
        ("Pre-launch", 0.0, 1.0, BLUE, "damage in transport, fuelling, integration"),
        ("Launch + first year", 1.0, 1.9, BLUE, "launch failure, failed deployment, early faults"),
        ("In-orbit", 1.9, 4.2, BLUE, "failure, radiation, debris; renewed yearly"),
        ("Third-party liability", 1.0, 4.2, MUTED, "damage to others, at launch and in orbit"),
        ("Space weather", 1.9, 4.2, BLUE_LIGHT, "parametric: storm disruption, radiation (2026)"),
        ("Solar-cycle drag", 1.9, 5.3, None, "falls years early, or a dead one stays up too long"),
    ]
    fig = Figure(figsize=(style.W, 4.9))
    header, footer = style.frame(
        fig,
        "Most policies pay when something breaks.\nDrag breaks nothing.",
        "What a satellite can insure, stage by stage (time not to scale)",
        "Sources: Lockton (policy types and terms), Orbway (space-weather cover, 2026).",
    )
    ax = style.axes(fig, left=1.62, right=0.15, top=header + 0.1, bottom=footer + 0.12)
    ax.grid(False)
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(False)
    ax.set_xlim(-0.05, 5.62)
    ax.set_ylim(len(rows) - 0.35, -0.9)
    ax.set_xticks([])
    ax.set_yticks([])
    for name, x in stops.items():
        ax.axvline(x, color=style.GRID, lw=0.8, zorder=0)
        ax.text(x, -0.72, name, ha="center", va="bottom", fontsize=9.5, color=INK2)
    ax.annotate(
        "",
        xy=(5.35, -0.55),
        xytext=(0, -0.55),
        arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=0.9),
    )
    for i, (label, x0, x1, colour, caption) in enumerate(rows):
        ax.text(
            -0.12,
            i,
            label,
            ha="right",
            va="center",
            fontsize=FS_NOTE,
            color=INK,
            weight="bold",
            transform=ax.transData,
            clip_on=False,
        )
        if colour is None:  # the gap: hatched, the figure's one orange element
            ax.add_patch(
                Rectangle(
                    (x0, i - 0.17),
                    x1 - x0,
                    0.34,
                    facecolor=SURFACE,
                    edgecolor=ORANGE,
                    hatch="////",
                    lw=1.2,
                    ls=(0, (4, 2)),
                )
            )
            ax.text(
                (x0 + x1) / 2,
                i,
                " NO COVER ",
                ha="center",
                va="center",
                fontsize=FS_NOTE,
                weight="bold",
                color=INK,
                bbox=dict(facecolor=SURFACE, edgecolor="none", pad=1.5),
            )
        else:
            ax.add_patch(
                FancyBboxPatch(
                    (x0, i - 0.15),
                    x1 - x0,
                    0.30,
                    boxstyle="round,pad=0,rounding_size=0.08",
                    facecolor=colour,
                    edgecolor="none",
                )
            )
        ax.text(x0, i + 0.24, caption, ha="left", va="top", fontsize=9, color=INK2)
    fig.savefig(OUT / "fig0_cover.png")


# ------------------------------------------------------------------ Figure 1: the fan
HORIZON, LIMIT, YEAR = 40.0, 5.0, 365.2425


def crossing(alt, y, level):
    for i in range(len(y) - 1):
        if (y[i] - level) * (y[i + 1] - level) <= 0 and y[i] != y[i + 1]:
            t = (np.log(level) - np.log(y[i])) / (np.log(y[i + 1]) - np.log(y[i]))
            return alt[i] + t * (alt[i + 1] - alt[i])
    return None


def fig1():
    w = data.fan_wide("max")
    alt = w["altitude_km"].to_numpy().astype(float)
    weak, fc, strong = w["weak"].to_numpy(), w["forecast"].to_numpy(), w["strong"].to_numpy()
    storm_days = data.storm_effect_days("max")

    fig = Figure(figsize=(style.W, 5.6))
    header, footer = style.frame(
        fig,
        "Storms, which I set out to insure, are the dot.\nThe solar cycle is the whole band.",
        "Years a satellite without thrusters stays up, from each altitude: its\n"
        "remaining life if it works, its time as debris if it's dead",
        "Model: orekit + NRLMSISE-00; circular orbit, 51.6°, area-to-mass 0.014 m²/kg. "
        "Band: predicted F10.7 above\n"
        "its 68.6 sfu quiet level ×0.75 / ×1.25 for every future cycle; Ap unchanged. "
        "Storms: median of 100 simulated\n"
        "histories; orange dot enlarged (to scale it is thinner than the line). "
        "Data: AGI SpaceWeather-All (via orekit), WDC Kyoto.",
    )
    ax = style.axes(fig, left=0.62, right=0.15, top=header + 0.2, bottom=footer + 0.5)
    z0, z1 = crossing(alt, weak, LIMIT), crossing(alt, strong, LIMIT)
    ax.axvspan(z0, z1, color=ZONE, lw=0, zorder=0)
    ax.text(
        (z0 + z1) / 2,
        50,
        "can't tell if\nit's down\nin 5 years",
        ha="center",
        va="top",
        fontsize=9.5,
        color=INK2,
        linespacing=1.15,
    )
    ax.fill_between(alt, strong, weak, color=BLUE, alpha=0.13, lw=0, zorder=1)
    ax.plot(alt, weak, color=BLUE, lw=0.8, alpha=0.55, zorder=2)
    ax.plot(alt, strong, color=BLUE, lw=0.8, alpha=0.55, zorder=2)
    ax.plot(alt, fc, color=BLUE, lw=2.2, zorder=3, solid_capstyle="round")
    ax.axhline(LIMIT, color=INK, lw=1.0, zorder=2)
    ax.text(
        655,
        LIMIT * 0.93,
        "5-year disposal\nrule (FCC)",
        fontsize=9.5,
        color=INK2,
        va="top",
        ha="right",
    )
    if weak[-1] >= HORIZON - 1e-6:
        ax.annotate(
            "",
            xy=(alt[-1], 58),
            xytext=(alt[-1], HORIZON),
            arrowprops=dict(arrowstyle="-|>", color=BLUE, lw=0.9),
        )
        ax.text(
            alt[-1] - 4,
            50,
            "still up\nafter 40 yr",
            fontsize=9.5,
            color=INK2,
            ha="right",
            va="center",
        )

    i = int(np.where(alt == 550)[0][0])
    later, sooner = (weak[i] - fc[i]) * YEAR, (fc[i] - strong[i]) * YEAR
    for y in (weak[i], strong[i]):
        ax.plot([550], [y], "o", ms=6.5, color=BLUE, mec=SURFACE, mew=1.4, zorder=6)
    ax.plot([550], [fc[i]], "o", ms=8, color=ORANGE, mec=SURFACE, mew=1.6, zorder=7)
    note(
        ax,
        f"Sun a quarter weaker\n{later:,.0f} days later",
        (550, weak[i]),
        (450, 26),
        ha="center",
        bold_first=True,
    )
    note(
        ax,
        f"storms\n{storm_days:.0f} days sooner than\nthe forecast's {fc[i]:.0f} years",
        (550, fc[i]),
        (405, 11.5),
        bold_first=True,
    )
    note(
        ax,
        f"Sun a quarter stronger\n{sooner:,.0f} days sooner",
        (550, strong[i]),
        (605, 1.3),
        ha="center",
        bold_first=True,
    )

    ax.set_yscale("log")
    ax.set_ylim(0.15, 60)
    ax.yaxis.set_major_locator(FixedLocator([0.25, 1, 5, 10, 40]))
    ax.yaxis.set_minor_locator(NullLocator())
    ax.set_yticklabels(["3 mo", "1 yr", "5", "10", "40 yr"])
    ax.set_xlim(395, 660)
    ax.set_xticks(range(400, 651, 50))
    ax.set_xticklabels([f"{x}" for x in range(400, 651, 50)])
    ax.set_xlabel("altitude in January 2035 (km)")
    style.clean(ax)
    fig.savefig(OUT / "fig1_fan.png")
    return z0, z1


# ------------------------------------------------------------------ Figure 2: the forecasters
CYCLE25_START = 2019.95  # Dec 2019 (SILSO minimum)


def fig2():
    k = data.karak()
    HIST_MEAN = float(data.cycle_peaks()[1][:-1].mean())  # cycles 1-24
    rng = np.random.default_rng(7)
    # Karak lists only the publication YEAR: spread each dot inside its own calendar year
    x = k["year"].to_numpy() + rng.uniform(0.08, 0.92, k.height)
    y = k["value_v2"].to_numpy()
    n_low, n, n_hist = int((y < 161).sum()), len(y), int((y < HIST_MEAN).sum())
    early = k.filter(pl.col("year").is_between(2020, 2021))["value_v2"]
    e_low, e_n = int((early < 161).sum()), early.len()

    fig = Figure(figsize=(style.W, 5.1))
    header, footer = style.frame(
        fig,
        "Five in six forecasts of Cycle 25 came in low,\nmost of them made after it had begun",
        "Each dot is one published forecast of the peak, placed within its year of publication",
        "Data: Karak 2026 (arXiv:2604.16183), Table 1; forecasts to 2015 scaled ×1.43 "
        "to sunspot number v2, as in the\n"
        "paper; dots spread at random within their year. "
        "Actual peak and average (13-month smoothed):\n"
        "WDC-SILSO, Royal Observatory of Belgium, Brussels, doi:10.24414/qnza-ac80.",
    )
    ax = style.axes(fig, left=0.62, right=0.95, top=header + 0.2, bottom=footer + 0.35)
    ax.axvspan(CYCLE25_START, 2025.0, color=ZONE, lw=0, zorder=0)
    ax.text(
        (CYCLE25_START + 2025.0) / 2,
        253,
        "cycle under way",
        ha="center",
        va="top",
        fontsize=9.5,
        color=INK2,
    )
    ax.scatter(x, y, s=18, color=BLUE, edgecolor=SURFACE, linewidth=0.9, zorder=3)
    ax.axhline(161, color=INK, lw=1.3, zorder=2)
    ax.axhline(HIST_MEAN, color=INK2, lw=0.9, ls=(0, (4, 3)), zorder=2)
    ax.text(2025.2, 158, "actual\npeak: 161", fontsize=9.5, color=INK, va="top")
    ax.text(
        2025.2,
        HIST_MEAN + 2,
        f"average of\n24 past\ncycles: {HIST_MEAN:.0f}",
        fontsize=9.5,
        color=INK2,
        va="bottom",
    )
    ax.text(
        2006.1,
        247,
        f"{n_low} of {n} forecasts were too low",
        fontsize=12,
        weight="bold",
        color=INK,
        va="top",
    )
    ax.text(
        2006.1,
        230,
        f"{n_hist} were below history's average",
        fontsize=FS_NOTE,
        color=INK2,
        va="top",
    )
    bx0, bx1, by = 2020.03, 2021.97, 50
    ax.plot([bx0, bx0, bx1, bx1], [by + 6, by, by, by + 6], color=INK2, lw=0.9, zorder=4)
    ax.text(
        (bx0 + bx1) / 2,
        by - 5,
        f"{e_low} of {e_n} made in the\ncycle's first two\nyears were too low",
        ha="center",
        va="top",
        fontsize=9.5,
        color=INK,
    )
    ax.set_xlim(2005.8, 2025.0)
    ax.set_ylim(0, 260)
    ax.set_xticks(range(2006, 2025, 3))
    ax.set_ylabel("predicted peak sunspot number")
    style.clean(ax)
    fig.savefig(OUT / "fig2_forecasters.png")


# ---------------------------------------------------- Figure 3: one draw every eleven years
def fig3():
    raw = data.sunspots_monthly()
    sm = data.sunspots_smoothed()
    t, v = sm["decimal_year"].to_numpy(), sm["sunspots"].to_numpy()
    tp, vp = data.cycle_peaks()
    pk = np.searchsorted(t, tp)
    complete = pk[:-1]  # the last peak is Cycle 25
    fig = Figure(figsize=(style.W, 3.9))
    header, footer = style.frame(
        fig,
        f"The Sun has dealt {len(complete)} complete cycles since 1755",
        "Sunspot number: monthly (grey), 13-month average (dark), a dot per cycle peak",
        "Source: WDC-SILSO, Royal Observatory of Belgium, Brussels, doi:10.24414/qnza-ac80. "
        "CC BY-NC 4.0.",
    )
    ax = style.axes(fig, left=0.5, right=0.15, top=header + 0.2, bottom=footer + 0.35)
    ax.plot(
        raw["decimal_year"].to_numpy(),
        raw["sunspots"].to_numpy(),
        color=MUTED,
        lw=0.4,
        alpha=0.6,
    )
    ax.plot(t, v, color=INK, lw=1.3)
    ax.plot(t[pk], v[pk], "o", ms=4, color=INK, mec=SURFACE, mew=0.8, zorder=4)
    hi, lo = complete[np.argmax(v[complete])], complete[np.argmin(v[complete])]
    for j, (dx, dy) in ((hi, (-14, 25)), (lo, (-4, 75)), (pk[-1], (-26, 95))):
        label = f"Cycle 25: {v[j]:.0f}" if j == pk[-1] else f"{v[j]:.0f} ({int(t[j])})"
        ax.annotate(
            label,
            (t[j], v[j]),
            xytext=(t[j] + dx, v[j] + dy),
            textcoords="data",
            ha="center",
            fontsize=9.5,
            color=INK,
            arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.7, shrinkB=3),
        )
    ax.set_xlim(1749, 2027)
    ax.set_ylim(0, 340)
    ax.set_yticks([0, 100, 200, 300])
    style.clean(ax)
    fig.savefig(OUT / "fig3_sunspots.png")
    return v[complete]


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    wanted = sys.argv[1:] or ["fig0", "fig1", "fig2", "fig3"]
    for name in wanted:
        r = {"fig0": fig0, "fig1": fig1, "fig2": fig2, "fig3": fig3}[name]()
        extra = ""
        if name == "fig1":
            extra = f"  (can't-tell zone {r[0]:.0f}-{r[1]:.0f} km)"
        elif name == "fig3":
            stats = f"mean {r.mean():.1f}, sd {r.std(ddof=1):.1f}, {r.min():.0f}-{r.max():.0f}"
            extra = f"  ({len(r)} complete cycles: {stats})"
        print(f"{name} done{extra}")
