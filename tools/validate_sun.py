#!/usr/bin/env python3
"""
Developer-only validation for console_dimmer.sun_events.

The bridge itself needs NOTHING to run this feature — the sun math is pure
stdlib. This script exists only to prove that math matches a trusted reference
(the `astral` library) across many locations, dates and the polar edge cases.

It is not imported at runtime and `astral` is never a dependency of the bridge.

Usage (from the repo root):

    python3 -m venv /tmp/astral_venv
    /tmp/astral_venv/bin/pip install astral
    /tmp/astral_venv/bin/python tools/validate_sun.py

Expected result: sunrise/sunset agree with astral to within a few minutes for
every case (far finer than the gradual dusk/dawn ramp needs).
"""
import os
import sys
from datetime import date, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from console_dimmer import sun_events

try:
    from astral import Observer
    from astral.sun import sun
except ImportError:
    sys.exit("astral not installed — see the usage note at the top of this file.")

# name, lat, lon (north/east positive)
CITIES = [
    ("Berlin",        52.5200,  13.4050),
    ("New York",      40.7128, -74.0060),
    ("Sydney",       -33.8688, 151.2093),
    ("Reykjavik",     64.1466, -21.9426),
    ("Singapore",      1.3521, 103.8198),
    ("Anchorage",     61.2181,-149.9003),
    ("Buenos Aires", -34.6037, -58.3816),
    ("Tokyo",         35.6762, 139.6503),
    ("Cape Town",    -33.9249,  18.4241),
    ("Quito",         -0.1807, -78.4678),
]

DATES = [date(2026, 3, 20), date(2026, 6, 21), date(2026, 9, 22), date(2026, 12, 21),
         date(2026, 1, 14), date(2026, 7, 14)]


def diff_min(a, b):
    return abs((a - b).total_seconds()) / 60.0


def astral_events_near(obs, d):
    """astral sunrise/sunset instants for d-1, d, d+1.

    astral labels events by UTC calendar date while sun_events labels by the
    local solar day, so for locations far from UTC the same real event lands on
    an adjacent date. Gathering three days lets us match the nearest instant.
    astral also raises ValueError on near-polar days; those are simply skipped.
    """
    rises, sets = [], []
    for off in (-1, 0, 1):
        try:
            a = sun(obs, date=d + timedelta(days=off), tzinfo=timezone.utc)
            rises.append(a['sunrise'])
            sets.append(a['sunset'])
        except ValueError:
            pass
    return rises, sets


def main():
    max_rise = max_set = 0.0
    n = 0
    for cname, lat, lon in CITIES:
        obs = Observer(latitude=lat, longitude=lon)
        for d in DATES:
            my_rise, my_set, state = sun_events(d, lat, lon)
            if state != 'normal':
                print(f"{cname:14} {d}  mine={state}")
                continue
            rises, sets = astral_events_near(obs, d)
            if not rises or not sets:
                print(f"{cname:14} {d}  astral undefined (near-polar), mine=normal")
                continue
            dr = min(diff_min(my_rise, r) for r in rises)
            ds = min(diff_min(my_set, s) for s in sets)
            max_rise = max(max_rise, dr)
            max_set = max(max_set, ds)
            n += 1
            flag = "  <-- >5min" if (dr > 5 or ds > 5) else ""
            print(f"{cname:14} {d}  rise d{dr:4.1f}m  set d{ds:4.1f}m{flag}")

    # Polar edge cases (Longyearbyen, 78N)
    _, _, st_dec = sun_events(date(2026, 12, 21), 78.22, 15.63)
    _, _, st_jun = sun_events(date(2026, 6, 21), 78.22, 15.63)
    print(f"\nLongyearbyen 2026-12-21 -> {st_dec} (expect polar_night)")
    print(f"Longyearbyen 2026-06-21 -> {st_jun} (expect polar_day)")

    print(f"\nCompared {n} city/date pairs")
    print(f"Max sunrise diff: {max_rise:.1f} min")
    print(f"Max sunset  diff: {max_set:.1f} min")
    ok = (max(max_rise, max_set) < 5
          and st_dec == 'polar_night' and st_jun == 'polar_day')
    print("RESULT:", "PASS" if ok else "CHECK")
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
