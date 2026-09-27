"""Recompute one point of Figure 1: how long a satellite without thrusters stays in orbit.

A standalone copy of the lifetime engine behind data/fan.csv, so anyone can check a single
point of the fan without the rest of the research code:

* orekit (Apache-2.0) via orekit-jpype, NRLMSISE-00 atmosphere, zonal gravity to J6;
* semi-analytical DSST mean elements from the start altitude down to 300 km, then a numerical
  Cartesian propagation through the final spiral to the 78 km re-entry line;
* solar input: AGI's SpaceWeather-All file shipped with orekit-data (pinned in
  pixi.toml). Its predicted F10.7 above the 68.6 sfu quiet level is scaled by --scale for every
  future day (after the last observed day, 2026-06-03); the observed record and Ap are untouched.

Run (the `model` environment brings Java, orekit and the pinned orekit-data):

    pixi run -e model python scripts/lifetime_one.py --altitude 550 --scale 1.25 --start 2035-01-16

Expected for that call: about 3.62 years (data/fan.csv row: altitude 550, k 1.25, epoch max).
One run takes a few seconds to a minute; the JVM start adds a few seconds.
"""

import argparse
import math
from datetime import UTC, date, datetime, timedelta
from importlib.util import find_spec
from pathlib import Path

import numpy as np
import polars as pl

FLOOR_SFU = 68.6  # quiet-Sun F10.7 level; only the amplitude above it is scaled
OBSERVED_UNTIL = date(2026, 6, 3)  # last observed day in the pinned space-weather file
REENTRY_KM = 78.0  # NASA DAS burn-up altitude
HANDOVER_KM = 300.0  # DSST -> numerical switch
YEAR_S = 365.2425 * 86400.0


def cssi_file() -> Path:
    spec = find_spec("orekitdata")
    if spec is None or not spec.submodule_search_locations:
        raise SystemExit("orekitdata not installed: run `pixi install -e model`")
    root = Path(next(iter(spec.submodule_search_locations)))
    return root / "CSSI-Space-Weather-Data" / "SpaceWeather-All-v1.2.txt"


def daily_activity(scale: float) -> pl.DataFrame:
    """Daily F10.7, its 81-day mean and Ap from the CSSI file, future amplitude scaled."""
    rows, monthly, section = [], [], ""
    for line in cssi_file().read_text().splitlines():
        s = line.strip()
        if s.startswith(("BEGIN ", "END ")):
            section = s.split(maxsplit=1)[1] if s.startswith("BEGIN") else ""
            continue
        if section not in ("OBSERVED", "DAILY_PREDICTED", "MONTHLY_PREDICTED"):
            continue
        t = s.split()
        if len(t) != 33:
            continue
        row = (date(int(t[0]), int(t[1]), int(t[2])), float(t[30]), float(t[31]), float(t[22]))
        (monthly if section == "MONTHLY_PREDICTED" else rows).append(row)
    frame = (
        pl.DataFrame(rows + monthly, schema=("date", "f107", "f107_ctr81", "ap"), orient="row")
        .with_columns(pl.col("date").cast(pl.Date))
        .sort("date")
        .upsample("date", every="1d")  # monthly predictions -> daily
        .fill_null(strategy="forward")
    )
    future = pl.col("date") > OBSERVED_UNTIL
    return frame.with_columns(
        [
            pl.when(future)
            .then(FLOOR_SFU + (pl.col(c) - FLOOR_SFU) * scale)
            .otherwise(pl.col(c))
            .alias(c)
            for c in ("f107", "f107_ctr81")
        ]
    )


def atmosphere_inputs(activity: pl.DataFrame):
    """Wrap the daily frame as orekit NRLMSISE00InputParameters."""
    from jpype import JArray, JDouble, JImplements, JOverride
    from orekit_jpype.pyhelpers import datetime_to_absolutedate

    f107 = activity["f107"].to_numpy()
    f107_avg = activity["f107_ctr81"].to_numpy()
    ap = activity["ap"].to_numpy()
    first, last = activity["date"][0], activity["date"][-1]
    t0 = datetime_to_absolutedate(datetime(first.year, first.month, first.day))
    t1 = datetime_to_absolutedate(datetime(last.year, last.month, last.day))
    n = len(f107)

    def idx(abs_date) -> int:
        return int(np.clip(abs_date.durationFrom(t0) // 86400.0, 0, n - 1))

    @JImplements("org.orekit.models.earth.atmosphere.NRLMSISE00InputParameters")
    class Inputs:
        @JOverride
        def getMinDate(self):
            return t0

        @JOverride
        def getMaxDate(self):
            return t1

        @JOverride
        def getDailyFlux(self, d):
            return float(f107[idx(d)])

        @JOverride
        def getAverageFlux(self, d):
            return float(f107_avg[idx(d)])

        @JOverride
        def getAp(self, d):  # daily resolution: the 7-slot Ap history collapses to daily Ap
            return JArray(JDouble)([float(ap[idx(d)])] * 7)

    return Inputs()


def blew_up(exc: Exception) -> bool:
    msg = str(exc)
    return any(m in msg for m in ("NaN appears", "Infinite value", "eccentric longitude"))


def lifetime_years(
    altitude_km: float,
    scale: float,
    start: datetime,
    a2m: float,
    incl_deg: float,
    horizon_years: float,
) -> tuple[float, bool]:
    import orekit_jpype

    orekit_jpype.initVM()
    from orekit_jpype.pyhelpers import datetime_to_absolutedate, setup_orekit_data

    setup_orekit_data(from_pip_library=True)
    from jpype import JImplements, JOverride
    from org.hipparchus.ode.nonstiff import DormandPrince853Integrator
    from org.orekit.bodies import CelestialBodyFactory, OneAxisEllipsoid
    from org.orekit.forces.drag import DragForce, IsotropicDrag
    from org.orekit.forces.gravity import HolmesFeatherstoneAttractionModel
    from org.orekit.forces.gravity.potential import GravityFieldFactory
    from org.orekit.frames import FramesFactory
    from org.orekit.models.earth.atmosphere import NRLMSISE00
    from org.orekit.orbits import EquinoctialOrbit, KeplerianOrbit, OrbitType, PositionAngleType
    from org.orekit.propagation import PropagationType, SpacecraftState
    from org.orekit.propagation.events import AltitudeDetector
    from org.orekit.propagation.events.handlers import StopOnEvent
    from org.orekit.propagation.numerical import NumericalPropagator
    from org.orekit.propagation.semianalytical.dsst import DSSTPropagator
    from org.orekit.propagation.semianalytical.dsst.forces import DSSTAtmosphericDrag, DSSTZonal
    from org.orekit.utils import Constants, IERSConventions

    itrf = FramesFactory.getITRF(IERSConventions.IERS_2010, True)
    r_eq = Constants.WGS84_EARTH_EQUATORIAL_RADIUS
    earth = OneAxisEllipsoid(r_eq, Constants.WGS84_EARTH_FLATTENING, itrf)
    mu = Constants.WGS84_EARTH_MU
    atmosphere = NRLMSISE00(
        atmosphere_inputs(daily_activity(scale)), CelestialBodyFactory.getSun(), earth
    )
    mass = 6.0  # decay depends only on area-to-mass; mass is a free normalisation
    area = a2m * mass

    def drag():  # a fresh force model per propagator (they carry mutable parameter drivers)
        return DragForce(atmosphere, IsotropicDrag(area, 2.2))

    def stop_at(alt_km: float, max_check: float, threshold: float):
        return (
            AltitudeDetector(alt_km * 1e3, earth)
            .withMaxCheck(max_check)
            .withThreshold(threshold)
            .withHandler(StopOnEvent())
        )

    epoch = datetime_to_absolutedate(start.replace(tzinfo=UTC))
    horizon = epoch.shiftedBy(horizon_years * YEAR_S)
    orbit = KeplerianOrbit(
        r_eq + altitude_km * 1e3,
        1e-4,
        math.radians(incl_deg),
        0.0,
        0.0,
        0.0,
        PositionAngleType.MEAN,
        FramesFactory.getEME2000(),
        epoch,
        mu,
    )
    state = SpacecraftState(orbit).withMass(mass)
    mean = PropagationType.MEAN

    def dsst_leg(state0, target_km: float, max_step_s: float):
        # finer steps only on demand: mean-element integration can go NaN when drag varies
        # violently within a step
        for attempt, step in enumerate((max_step_s, max_step_s / 8, max_step_s / 64)):
            tol = DSSTPropagator.tolerances(1e2, state0.getOrbit())
            dsst = DSSTPropagator(DormandPrince853Integrator(60.0, step, tol[0], tol[1]), mean)
            dsst.setInitialState(state0, mean)
            dsst.addForceModel(DSSTZonal(GravityFieldFactory.getUnnormalizedProvider(6, 0)))
            dsst.addForceModel(DSSTAtmosphericDrag(drag(), mu))
            dsst.addEventDetector(stop_at(target_km, 1800.0, 1.0))
            try:
                return dsst.propagate(horizon)
            except Exception as exc:
                if attempt == 2 or not blew_up(exc):
                    raise
        raise AssertionError("unreachable")

    if altitude_km > HANDOVER_KM + 100:
        state = dsst_leg(state, HANDOVER_KM + 100, 5.0 * 86400.0)
    if horizon.durationFrom(state.getDate()) > 1.0:
        state = dsst_leg(state, HANDOVER_KM, 0.5 * 86400.0)
    if horizon.durationFrom(state.getDate()) <= 1.0:
        return horizon_years, False  # still up at the horizon

    orb2 = EquinoctialOrbit(state.getOrbit())
    tol2 = NumericalPropagator.tolerances(10.0, orb2, OrbitType.CARTESIAN)
    num = NumericalPropagator(DormandPrince853Integrator(1.0, 600.0, tol2[0], tol2[1]))
    num.setOrbitType(OrbitType.CARTESIAN)
    num.setInitialState(SpacecraftState(orb2).withMass(mass))
    num.addForceModel(
        HolmesFeatherstoneAttractionModel(itrf, GravityFieldFactory.getNormalizedProvider(6, 0))
    )
    num.addForceModel(drag())
    num.addEventDetector(stop_at(REENTRY_KM, 60.0, 0.1))
    last: list[tuple[float, float]] = []

    @JImplements("org.orekit.propagation.sampling.OrekitFixedStepHandler")
    class Track:
        @JOverride
        def init(self, s0, t, step):
            pass

        @JOverride
        def handleStep(self, s):
            last.append((s.getDate().durationFrom(epoch), (s.getOrbit().getA() - r_eq) / 1e3))

        @JOverride
        def finish(self, s):
            pass

    num.getMultiplexer().add(600.0, Track())
    try:
        final = num.propagate(horizon)
        if horizon.durationFrom(final.getDate()) <= 1.0:
            return horizon_years, False
        seconds = final.getDate().durationFrom(epoch)
    except Exception as exc:
        # in the last minutes of the plunge the maths can overflow before the detector fires;
        # infinite density is re-entry, but only when the satellite was already low
        if not (blew_up(exc) and last and last[-1][1] < 150.0):
            raise
        seconds = last[-1][0]
    return seconds / YEAR_S, True


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--altitude", type=float, default=550.0, help="start altitude, km (> 300)")
    ap.add_argument("--scale", type=float, default=1.0, help="future solar amplitude factor")
    ap.add_argument("--start", default="2035-01-16", help="start date (mission end), YYYY-MM-DD")
    ap.add_argument("--a2m", type=float, default=0.014, help="area-to-mass ratio, m²/kg")
    ap.add_argument("--incl", type=float, default=51.6, help="inclination, deg")
    ap.add_argument("--horizon", type=float, default=40.0, help="give up after this many years")
    a = ap.parse_args()
    start = datetime.fromisoformat(a.start)
    years, down = lifetime_years(a.altitude, a.scale, start, a.a2m, a.incl, a.horizon)
    when = f"re-enters {(start + timedelta(days=years * 365.2425)).date()}" if down else "still up"
    print(
        f"{a.altitude:.0f} km from {start.date()}, solar amplitude x{a.scale}: "
        f"{years:.4f} years ({when})"
    )


if __name__ == "__main__":
    main()
