"""Recompute every number in the post from data/ and print it next to what the post says.

Run:  pixi run python scripts/fetch_data.py     (once)
      pixi run python scripts/check_numbers.py

Exits non-zero if any recomputed value disagrees with the post.
"""

import sys
from pathlib import Path

import numpy as np
import polars as pl

sys.path.insert(0, str(Path(__file__).parent))
import data  # noqa: E402

LIMIT_YEARS = 5.0
ACTUAL_PEAK = 161  # Cycle 25, SILSO 13-month smoothed (checked below)
NOAA_PANEL_2019 = 115  # official NOAA/NASA panel forecast, Dec 2019
KARAK_MEAN = 132.2  # mean of the 128 forecasts as stated in Karak 2026
# CelesTrak lists Guowang satellites as HULIANWANG and Qianfan ones as SPACESAIL
MEGA = ("STARLINK", "ONEWEB", "KUIPER", "GUOWANG", "HULIANWANG", "QIANFAN", "SPACESAIL")
GOV = r"^(USA |YAOGAN|COSMOS|KOSMOS|SHIJIAN)"  # government / military series

failures: list[str] = []


def claim(text: str, value: str, ok: bool) -> None:
    print(f"{'ok ' if ok else 'BAD'}  {text:<62} {value}")
    if not ok:
        failures.append(text)


def crossing(alt: np.ndarray, y: np.ndarray, level: float) -> float:
    for i in range(len(y) - 1):
        if (y[i] - level) * (y[i + 1] - level) <= 0 and y[i] != y[i + 1]:
            t = (np.log(level) - np.log(y[i])) / (np.log(y[i + 1]) - np.log(y[i]))
            return float(alt[i] + t * (alt[i + 1] - alt[i]))
    raise ValueError("no crossing")


print("\n-- Storms are a dot (Figure 1) --")
storm = {e: data.storm_effect_days(e) for e in ("min", "max")}
claim(
    "typical storms: 17 d sooner (mission ends at solar min), 75 d (max)",
    f"{storm['min']:.1f} / {storm['max']:.1f} d",
    round(storm["min"]) == 17 and round(storm["max"]) == 75,
)
band, one_sided = {}, []
for e in ("min", "max"):
    w = data.fan_wide(e).filter(pl.col("altitude_km") == 550).row(0, named=True)
    sooner, later = (w["forecast"] - w["strong"]) * 365.2425, (w["weak"] - w["forecast"]) * 365.2425
    band[e] = sooner + later
    one_sided += [sooner / storm[e], later / storm[e]]
claim(
    "the Sun spreads the fall over a window 1,243 to 2,505 days wide",
    f"{band['min']:,.0f} / {band['max']:,.0f} d",
    round(band["min"]) == 1243 and round(band["max"]) == 2505,
)
ratios = [band[e] / storm[e] for e in ("min", "max")]
claim(
    "the band is roughly 30 to 70 times wider than the dot",
    f"{min(ratios):.1f}x - {max(ratios):.1f}x",
    30 <= min(ratios) <= 35 and 68 <= max(ratios) <= 73,
)
claim(
    "even a one-sided miss moves it > 10x as far as storms",
    f"smallest {min(one_sided):.1f}x",
    min(one_sided) > 10,
)
w = data.fan_wide("max")
alt = w["altitude_km"].to_numpy().astype(float)
z0, z1 = (
    crossing(alt, w["weak"].to_numpy(), LIMIT_YEARS),
    crossing(alt, w["strong"].to_numpy(), LIMIT_YEARS),
)
claim(
    "Jan 2035: band straddles the 5-year line ~520-560 km",
    f"{z0:.0f}-{z1:.0f} km",
    515 <= z0 <= 525 and 555 <= z1 <= 565,
)
w400 = w.filter(pl.col("altitude_km") == 400).row(0, named=True)
claim(
    "below ~400 km it comes down within a year or two",
    f"400 km: {w400['strong']:.2f}-{w400['weak']:.2f} yr",
    w400["weak"] < 2,
)
w425, w650 = (w.filter(pl.col("altitude_km") == a).row(0, named=True) for a in (425, 650))
claim(
    "in between, the fall takes from under a year to several decades",
    f"425 km: {w425['forecast']:.2f} yr; 650 km: {w650['strong']:.0f}-{w650['weak']:.0f}+ yr",
    w425["forecast"] < 1 and w650["strong"] > 20,
)
fc = w.filter(pl.col("altitude_km") == 550)["forecast"][0]
claim("the forecast's 8 years at 550 km (Figure 1 label)", f"{fc:.2f} yr", round(fc) == 8)

print("\n-- Nobody can forecast the band (Figure 2) --")
k = data.karak()
y = k["value_v2"].to_numpy()
claim("128 forecasts in Karak's review give a number", f"{len(y)}", len(y) == 128)
claim(
    "106 came in below the actual peak of 161",
    f"{int((y < ACTUAL_PEAK).sum())}",
    int((y < ACTUAL_PEAK).sum()) == 106,
)
early = k.filter(pl.col("year").is_between(2020, 2021))["value_v2"]
claim(
    "28 of 29 made in the cycle's first two years too low",
    f"{int((early < ACTUAL_PEAK).sum())} of {early.len()}",
    (int((early < ACTUAL_PEAK).sum()), early.len()) == (28, 29),
)
y24 = k.filter(pl.col("year") == 2024)["value_v2"]
claim(
    "14 of the 16 published in 2024 still too low",
    f"{int((y24 < ACTUAL_PEAK).sum())} of {y24.len()}",
    (int((y24 < ACTUAL_PEAK).sum()), y24.len()) == (14, 16),
)
claim(
    "Cycle 25 peaked 22% above the average forecast",
    f"our mean {y.mean():.1f} (paper {KARAK_MEAN}); +{ACTUAL_PEAK / KARAK_MEAN - 1:.0%}",
    abs(y.mean() - KARAK_MEAN) < 0.5 and round(100 * (ACTUAL_PEAK / KARAK_MEAN - 1)) == 22,
)
claim(
    "... and 40% above the official 2019 forecast (115)",
    f"+{ACTUAL_PEAK / NOAA_PANEL_2019 - 1:.0%}",
    round(100 * (ACTUAL_PEAK / NOAA_PANEL_2019 - 1)) == 40,
)

print("\n-- Why the cycle can't be insured (Figure 3) --")
tp, vp = data.cycle_peaks()
cycles, c25 = vp[:-1], vp[-1]
claim("24 complete cycles since 1755", f"{len(cycles)} (first peak {tp[0]:.0f})", len(cycles) == 24)
claim(
    "peaking anywhere from 81 to 285",
    f"{cycles.min():.1f} - {cycles.max():.1f}",
    round(cycles.min()) == 81 and round(cycles.max()) == 285,
)
claim("Cycle 25 peak (the '161')", f"{c25:.1f} in {tp[-1]:.1f}", round(c25) == ACTUAL_PEAK)
mean = cycles.mean()
claim("history's average of 24 cycles: 179", f"{mean:.1f}", round(mean) == 179)
claim(
    "115 forecasts below history's average",
    f"{int((y < mean).sum())}",
    int((y < mean).sum()) == 115,
)
sd = cycles.std(ddof=1)
claim(
    "one standard deviation is a third of an average cycle",
    f"sd {sd:.1f} = {sd / mean:.0%} of mean",
    0.30 <= sd / mean <= 0.36,
)
miss = [abs(cycles[n] - cycles[:n].mean()) / cycles[:n].mean() > 0.25 for n in range(2, 24)]
claim(
    "in more than half of past cycles the peak missed the prior average by >25%",
    f"{sum(miss)} of {len(miss)} (cycles 3-24)",
    sum(miss) > len(miss) / 2,
)
weaker = [i + 1 for i, c in enumerate(cycles[:-1]) if c < cycles[-1]]
claim(
    "Cycle 24 the weakest in a century",
    f"{cycles[-1]:.1f}; weaker: cycle(s) {weaker} (peak {tp[weaker[-1] - 1]:.0f})",
    tp[weaker[-1] - 1] < tp[23] - 100,
)
strong_side = [(cycles[n] - cycles[:n].mean()) / cycles[:n].mean() >= 0.25 for n in range(2, 24)]
claim(
    "a miss on the strong side came in about one cycle in three",
    f"{sum(strong_side)} of {len(strong_side)} (cycles 3-24)",
    0.25 <= sum(strong_side) / len(strong_side) <= 0.4,
)
s = data.storm_peaks()
claim(
    "about 390 intense storms in almost 70 years since 1957",
    f"{s.height} storms, Dst < -100 nT: {bool((s['peak_value'] < -100).all())}, "
    f"peaks {s['peak_time'].min():%Y}-{s['peak_time'].max():%Y}",
    s.height == 392 and bool((s["peak_value"] < -100).all()),
)
riley = s.filter(pl.col("peak_time") <= pl.datetime(2022, 8, 31, 23))
claim(
    "... matching Riley & Ben-Nun's 367 on their window to Aug 2022",
    f"{riley.height}",
    riley.height == 367,
)

print("\n-- Satellite count (footnote 2) --")
leo = data.leo_payloads()
working = pl.col("OPS_STATUS_CODE").is_in(["+", "P", "B", "S", "X"])
mega = pl.any_horizontal(
    [pl.col("OBJECT_NAME").str.to_uppercase().str.contains(m, literal=True) for m in MEGA]
)
small = leo.filter(working & ~mega)
band_ = small.filter(pl.col("PERIGEE").is_between(500, 600))
claim(
    "more than a third (1,262 of 3,451) fly at 500-600 km",
    f"{band_.height:,} of {small.height:,} = {band_.height / small.height:.0%}",
    (band_.height, small.height) == (1262, 3451),
)
gov = pl.col("OBJECT_NAME").str.to_uppercase().str.contains(GOV)
civil, civil_band = small.filter(~gov), band_.filter(~gov)
claim(
    "about 280 of those are government or military",
    f"{band_.height - civil_band.height}",
    abs(band_.height - civil_band.height - 280) <= 10,
)
claim(
    "... without them still about a third (986 of 2,883)",
    f"{civil_band.height:,} of {civil.height:,} = {civil_band.height / civil.height:.0%}",
    (civil_band.height, civil.height) == (986, 2883),
)

print("\n-- The default forecast in radio flux (needs: pixi run -e model) --")
try:
    import lifetime_one
    from scipy.signal import find_peaks

    act = lifetime_one.daily_activity(1.0).select("date", "f107_ctr81")
    act = act.with_columns(pl.col("f107_ctr81").rolling_mean(397, center=True).alias("m"))
    m, d = act["m"].to_numpy(), act["date"].to_numpy()
    pk, _ = find_peaks(np.nan_to_num(m), distance=365 * 8)
    pk = pk[~np.isnan(m[pk])]
    measured = [m[i] for i in pk if d[i] <= np.datetime64(lifetime_one.OBSERVED_UNTIL)]
    forecast = [m[i] for i in pk if d[i] > np.datetime64(lifetime_one.OBSERVED_UNTIL)]
    strong_edge = lifetime_one.FLOOR_SFU + 1.25 * (forecast[0] - lifetime_one.FLOOR_SFU)
    claim(
        "default forecast about as weak as Cycle 24 in radio flux",
        f"forecast peak {forecast[0]:.0f} sfu vs Cycle 24 {measured[-2]:.0f}",
        abs(forecast[0] - measured[-2]) < 10,
    )
    beat = sum(v > strong_edge for v in measured)
    claim(
        "five of the seven radio-era cycles beat the band's strong edge",
        f"{beat} of {len(measured)} above {strong_edge:.0f} sfu",
        (beat, len(measured)) == (5, 7),
    )
except SystemExit:
    print("skip  orekit-data not installed; run: pixi run -e model python scripts/check_numbers.py")

print(f"\n{'ALL NUMBERS REPRODUCE' if not failures else f'{len(failures)} MISMATCH(ES)'}")
sys.exit(1 if failures else 0)
