"""Download the third-party data this repo does not redistribute, into data/raw/.

* SILSO monthly and 13-month smoothed total sunspot number (v2.0).
  Source: WDC-SILSO, Royal Observatory of Belgium, Brussels. Licence: CC BY-NC 4.0.
* Optionally (--satcat) today's CelesTrak satellite catalogue, to compare with the pinned
  August 2026 subset in data/. Source: CelesTrak (Dr. T.S. Kelso); attribution required.

Run:  pixi run python scripts/fetch_data.py [--satcat]
"""

import argparse
import time
import urllib.request
from pathlib import Path

RAW = Path("data/raw")
SOURCES = {
    "SN_m_tot_V2.0.csv": "https://www.sidc.be/SILSO/DATA/SN_m_tot_V2.0.csv",
    "SN_ms_tot_V2.0.csv": "https://www.sidc.be/SILSO/DATA/SN_ms_tot_V2.0.csv",
}
SATCAT = ("satcat.csv", "https://celestrak.org/pub/satcat.csv")


def fetch(name: str, url: str) -> None:
    path = RAW / name
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "solar-drag-uninsurable"})
            with urllib.request.urlopen(req, timeout=60) as r:
                path.write_bytes(r.read())
            print(f"{name}: {path.stat().st_size:,} bytes")
            return
        except OSError as exc:
            if attempt == 2:
                raise SystemExit(f"could not download {url}: {exc}") from exc
            time.sleep(2**attempt)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--satcat", action="store_true", help="also fetch today's CelesTrak SATCAT")
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    for name, url in SOURCES.items():
        fetch(name, url)
    if args.satcat:
        fetch(*SATCAT)


if __name__ == "__main__":
    main()
