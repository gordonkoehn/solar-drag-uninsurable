"""Loaders for everything the post's numbers and figures are computed from.

Pinned in data/ (our own results, or small derived tables with attribution):
  fan.csv                        lifetime runs behind Figure 1 (scripts/lifetime_one.py
                                 recomputes any row)
  storm_mc_550km.csv             100 simulated storm histories per case at 550 km, and
  storm_free_baselines_550km.csv the storm-free runs they are measured against
  karak_c25_predictions.csv      Karak 2026, Table 1: 128 numeric Cycle 25 peak forecasts
  dst_storm_peaks.csv            intense storms (Dst < -100 nT), 1957-2022, from Kyoto Dst
  leo_payloads_2026-08-28.csv    CelesTrak SATCAT subset: on-orbit payloads, perigee < 2,000 km

Downloaded by scripts/fetch_data.py into data/raw/ (not redistributed here):
  SN_m_tot_V2.0.csv, SN_ms_tot_V2.0.csv   SILSO sunspot numbers (CC BY-NC 4.0)
"""

from pathlib import Path

import numpy as np
import polars as pl
from scipy.signal import find_peaks

DATA = Path(__file__).parent.parent / "data"
RAW = DATA / "raw"
YEAR_DAYS = 365.2425
EPOCHS = {"min": "2030-08-16", "max": "2035-01-16"}  # mission end near solar min / near max


def fan() -> pl.DataFrame:
    return pl.read_csv(DATA / "fan.csv")


def fan_wide(epoch: str) -> pl.DataFrame:
    """One row per altitude: lifetime (years) for a quarter weaker / forecast / quarter stronger."""
    w = fan().filter(pl.col("epoch") == epoch)
    w = w.pivot(on="k", index="altitude_km", values="lifetime_years").sort("altitude_km")
    return w.rename({"0.75": "weak", "1.0": "forecast", "1.25": "strong"})


def storm_effect_days(epoch: str) -> float:
    """Median life lost to storms at 550 km: storm-free run minus each simulated history."""
    base = pl.read_csv(DATA / "storm_free_baselines_550km.csv")
    base_years = base.filter(pl.col("epoch") == epoch)["baseline_years"][0]
    mc = pl.read_csv(DATA / "storm_mc_550km.csv").filter(
        pl.col("conditioned") & (pl.col("deploy") == EPOCHS[epoch])
    )
    return float(((base_years - mc["lifetime_years"]) * YEAR_DAYS).median())


def karak() -> pl.DataFrame:
    return pl.read_csv(DATA / "karak_c25_predictions.csv")


def storm_peaks() -> pl.DataFrame:
    return pl.read_csv(DATA / "dst_storm_peaks.csv", try_parse_dates=True)


def leo_payloads() -> pl.DataFrame:
    return pl.read_csv(DATA / "leo_payloads_2026-08-28.csv")


def _silso(name: str) -> pl.DataFrame:
    path = RAW / name
    if not path.exists():
        raise SystemExit(f"{path} missing: run `pixi run python scripts/fetch_data.py` first")
    rows = [
        [p.strip() for p in line.split(";")][:4]
        for line in path.read_text().splitlines()
        if line.strip()
    ]
    frame = pl.DataFrame(rows, schema=["year", "month", "decimal_year", "sunspots"], orient="row")
    frame = frame.with_columns(pl.all().cast(pl.Float64))
    return frame.filter(pl.col("sunspots") >= 0)  # -1 marks months that can't be smoothed


def sunspots_monthly() -> pl.DataFrame:
    return _silso("SN_m_tot_V2.0.csv")


def sunspots_smoothed() -> pl.DataFrame:
    return _silso("SN_ms_tot_V2.0.csv")


def cycle_peaks() -> tuple[np.ndarray, np.ndarray]:
    """(decimal year, smoothed sunspot number) of every cycle peak since 1755.

    The last entry is Cycle 25 (peaked late 2024); the ones before it are cycles 1-24.
    """
    sm = sunspots_smoothed()
    t, v = sm["decimal_year"].to_numpy(), sm["sunspots"].to_numpy()
    pk, _ = find_peaks(v, distance=12 * 6, prominence=40)
    return t[pk], v[pk]
