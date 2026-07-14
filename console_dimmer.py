#!/usr/bin/env python3
"""
Console Backlight Night Dimmer

Gradually caps the WinWing console backlight range after dark so the physical
panel lights don't blind you at night (and drown out the in-game consoles).

How it works:
  - Uses the PC clock + an approximate location derived from the system timezone
    to compute local sunrise/sunset (stdlib only — no external libraries, no
    network, no install step).
  - Returns a "dimming factor" in the range [FLOOR .. 1.0] that the brightness
    mappings multiply into the console backlight:
        * Daytime                          -> 1.0  (full range)
        * Over RAMP minutes after sunset   -> 1.0 fading down to FLOOR
        * Deep night                       -> FLOOR (e.g. 30%)
        * Over RAMP minutes before sunrise -> FLOOR rising back up to 1.0

Everything is tunable via environment variables so it needs no code edits to
adjust or disable:
    WINWING_NIGHT_DIM=0            disable entirely (factor always 1.0)
    WINWING_NIGHT_FLOOR=0.30       minimum factor at deep night (0.0-1.0)
    WINWING_NIGHT_RAMP_MIN=85      ramp length in minutes
    WINWING_LAT / WINWING_LON      override auto-detected location (decimal deg)

The sun-position math is the standard NOAA / Wikipedia "sunrise equation". It is
validated against the `astral` library in tools/validate_sun.py (accuracy is a
couple of minutes, which is far finer than the gradual ramp needs).
"""

import os
import re
import math
import time
from datetime import datetime, timedelta, timezone


# ============================================================================
# Sun position — NOAA / Wikipedia "sunrise equation" (stdlib only)
# ============================================================================

def _julian_day_number(year: int, month: int, day: int) -> int:
    """Integer Julian Day Number for a Gregorian calendar date."""
    a = (14 - month) // 12
    y = year + 4800 - a
    m = month + 12 * a - 3
    return day + (153 * m + 2) // 5 + 365 * y + y // 4 - y // 100 + y // 400 - 32045


def _julian_to_utc(jd: float) -> datetime:
    """Convert a Julian date (UTC) to an aware UTC datetime."""
    unix_seconds = (jd - 2440587.5) * 86400.0
    return datetime.fromtimestamp(unix_seconds, tz=timezone.utc)


def sun_events(d, lat: float, lon: float):
    """
    Sunrise and sunset (UTC) for calendar date `d` at lat/lon.

    lat: decimal degrees, north positive
    lon: decimal degrees, east positive

    Returns (sunrise_utc, sunset_utc, state) where state is one of
    'normal', 'polar_day' (sun never sets) or 'polar_night' (sun never rises).
    On the polar states sunrise/sunset are None.
    """
    rad = math.radians

    jdn = _julian_day_number(d.year, d.month, d.day)
    n = jdn - 2451545 + 0.0008
    # Mean solar time (the equation uses west longitude as positive)
    j_star = n + (-lon) / 360.0

    # Solar mean anomaly
    M = (357.5291 + 0.98560028 * j_star) % 360.0
    M_rad = rad(M)

    # Equation of the center
    C = (1.9148 * math.sin(M_rad)
         + 0.0200 * math.sin(2 * M_rad)
         + 0.0003 * math.sin(3 * M_rad))

    # Ecliptic longitude
    lam = (M + C + 180.0 + 102.9372) % 360.0
    lam_rad = rad(lam)

    # Solar transit (Julian date of solar noon)
    j_transit = (2451545.0 + j_star
                 + 0.0053 * math.sin(M_rad)
                 - 0.0069 * math.sin(2 * lam_rad))

    # Declination of the sun
    sin_dec = math.sin(lam_rad) * math.sin(rad(23.4397))
    cos_dec = math.cos(math.asin(sin_dec))

    lat_rad = rad(lat)
    # Hour angle, with -0.833deg for atmospheric refraction + solar radius
    cos_omega = ((math.sin(rad(-0.833)) - math.sin(lat_rad) * sin_dec)
                 / (math.cos(lat_rad) * cos_dec))

    if cos_omega > 1.0:
        return (None, None, 'polar_night')   # sun never rises
    if cos_omega < -1.0:
        return (None, None, 'polar_day')      # sun never sets

    omega = math.degrees(math.acos(cos_omega))
    j_rise = j_transit - omega / 360.0
    j_set = j_transit + omega / 360.0
    return (_julian_to_utc(j_rise), _julian_to_utc(j_set), 'normal')


# ============================================================================
# Approximate location from the system timezone (Linux, stdlib only)
# ============================================================================

def _local_timezone_name():
    """Best-effort IANA timezone name, e.g. 'Europe/Berlin'."""
    # Debian/Ubuntu keep the plain zone name here
    try:
        with open('/etc/timezone', 'r') as f:
            name = f.read().strip()
            if name:
                return name
    except OSError:
        pass

    # Universal on systemd distros: /etc/localtime -> .../zoneinfo/<Zone>
    # realpath resolves relative symlinks (e.g. ../usr/share/zoneinfo/...)
    try:
        target = os.path.realpath('/etc/localtime')
        marker = 'zoneinfo/'
        if marker in target:
            return target.split(marker, 1)[1]
    except OSError:
        pass

    return None


def _parse_iso6709(coord: str):
    """
    Parse a zone.tab ISO-6709 coordinate like '+523200+0132400' into
    (lat, lon) decimal degrees. Latitude is +DDMM[SS], longitude +DDDMM[SS].
    """
    m = re.match(r'^([+-]\d{2})(\d{2})(\d{2})?([+-]\d{3})(\d{2})(\d{2})?$', coord)
    if not m:
        return None

    lat_d, lat_m, lat_s, lon_d, lon_m, lon_s = m.groups()

    def to_deg(deg, minute, sec):
        val = abs(int(deg)) + int(minute) / 60.0 + (int(sec) if sec else 0) / 3600.0
        return -val if deg.startswith('-') else val

    return (to_deg(lat_d, lat_m, lat_s), to_deg(lon_d, lon_m, lon_s))


def _location_from_timezone():
    """
    Map the local timezone to an approximate (lat, lon) via the system zone tab.
    Returns (lat, lon) or None.
    """
    tzname = _local_timezone_name()
    if not tzname:
        return None

    for path in ('/usr/share/zoneinfo/zone1970.tab',
                 '/usr/share/zoneinfo/zone.tab'):
        try:
            with open(path, 'r') as f:
                for line in f:
                    if line.startswith('#') or not line.strip():
                        continue
                    fields = line.rstrip('\n').split('\t')
                    if len(fields) < 3:
                        continue
                    coords, zone = fields[1], fields[2]
                    if zone == tzname:
                        parsed = _parse_iso6709(coords)
                        if parsed:
                            return parsed
        except OSError:
            continue

    return None


def resolve_location():
    """
    Determine (lat, lon, source) for sun calculations.
    Priority: WINWING_LAT/WINWING_LON env vars, then timezone lookup.
    Returns None if nothing usable is found.
    """
    lat_env = os.environ.get('WINWING_LAT')
    lon_env = os.environ.get('WINWING_LON')
    if lat_env and lon_env:
        try:
            return (float(lat_env), float(lon_env), 'env override')
        except ValueError:
            pass

    loc = _location_from_timezone()
    if loc:
        return (loc[0], loc[1], 'timezone')

    return None


# ============================================================================
# ConsoleDimmer
# ============================================================================

class ConsoleDimmer:
    """
    Computes the day/night brightness factor for the console backlight.

    factor() returns a value in [floor .. 1.0]; multiply it into the raw DCS
    console brightness before sending to the hardware. Results are cached and
    only recomputed every RECOMPUTE_INTERVAL seconds (the sun moves slowly).
    """

    RECOMPUTE_INTERVAL = 30.0  # seconds between sun/factor recomputations

    def __init__(self, debug: bool = False):
        self.debug = debug

        self.enabled = os.environ.get('WINWING_NIGHT_DIM', '1') not in ('0', 'false', 'no')
        self.floor = _clamp(_env_float('WINWING_NIGHT_FLOOR', 0.30), 0.0, 1.0)
        ramp_min = max(1.0, _env_float('WINWING_NIGHT_RAMP_MIN', 85.0))
        self.ramp = timedelta(minutes=ramp_min)

        loc = resolve_location() if self.enabled else None
        if loc:
            self.lat, self.lon, source = loc
        else:
            self.lat = self.lon = None
            source = 'none'

        # Cache
        self._cached_factor = 1.0
        self._last_compute = 0.0

        if not self.enabled:
            print("[Dimmer] Night console dimming disabled (WINWING_NIGHT_DIM=0)")
        elif self.lat is None:
            print("[Dimmer] Could not determine location — night dimming disabled. "
                  "Set WINWING_LAT and WINWING_LON to enable.")
            self.enabled = False
        else:
            print(f"[Dimmer] Night console dimming active — floor {self.floor:.0%}, "
                  f"ramp {int(ramp_min)} min, location {self.lat:.2f},{self.lon:.2f} "
                  f"({source})")

    def factor(self) -> float:
        """Current brightness factor in [floor .. 1.0]. Cached for a while."""
        if not self.enabled:
            return 1.0

        now = time.time()
        if now - self._last_compute >= self.RECOMPUTE_INTERVAL:
            now_utc = datetime.now(timezone.utc)
            self._cached_factor, phase = self._evaluate(now_utc)
            self._last_compute = now
            if self.debug:
                local = now_utc.astimezone().strftime('%H:%M:%S')
                print(f"[Dimmer] {local} phase={phase:5s} "
                      f"factor={self._cached_factor:.3f} "
                      f"(backlight cap {self._cached_factor:.0%})")
        return self._cached_factor

    def scale(self, raw, floor: int) -> int:
        """
        Scale a raw DCS console value (0.0-1.0) to a 0-255 hardware value,
        applying the current night factor — but never below `floor`, so the
        backlight never goes fully dark.
        """
        if raw is None:
            return floor
        value = int(float(raw) * self.factor() * 255)
        return max(floor, value)

    def _compute_factor(self, now_utc: datetime) -> float:
        """Brightness factor for `now_utc` (see _evaluate)."""
        return self._evaluate(now_utc)[0]

    def _evaluate(self, now_utc: datetime):
        """
        Brightness factor and phase label for `now_utc` from sun events.
        Checks yesterday/today/tomorrow so the ramps behave correctly across
        midnight (e.g. a sunset ramp that spills past 00:00 at high latitudes).

        Returns (factor, phase) where phase is one of
        'day', 'dusk', 'night', 'dawn', 'p-day', 'p-night'.
        """
        floor = self.floor
        for day_offset in (-1, 0, 1):
            d = (now_utc + timedelta(days=day_offset)).date()
            sunrise, sunset, state = sun_events(d, self.lat, self.lon)

            if state == 'polar_day':
                return 1.0, 'p-day'
            if state == 'polar_night':
                continue  # try neighbouring days; if all polar, fall to floor

            # Sunrise ramp: floor -> 1.0 across [sunrise - ramp, sunrise]
            if sunrise - self.ramp <= now_utc < sunrise:
                frac = (now_utc - (sunrise - self.ramp)) / self.ramp
                return floor + (1.0 - floor) * frac, 'dawn'

            # Daytime: full brightness
            if sunrise <= now_utc <= sunset:
                return 1.0, 'day'

            # Sunset ramp: 1.0 -> floor across [sunset, sunset + ramp]
            if sunset < now_utc <= sunset + self.ramp:
                frac = (now_utc - sunset) / self.ramp
                return 1.0 - (1.0 - floor) * frac, 'dusk'

        # Deep night (or all-polar-night): the floor
        return floor, 'night'


# ============================================================================
# Small helpers
# ============================================================================

def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


# ============================================================================
# CLI: print today's sun times and a factor curve for the current location
# ============================================================================

def _demo():
    loc = resolve_location()
    if not loc:
        print("Could not resolve a location. Set WINWING_LAT / WINWING_LON.")
        return
    lat, lon, source = loc
    print(f"Location: {lat:.4f}, {lon:.4f}  ({source})")

    today = datetime.now(timezone.utc).date()
    sr, ss, state = sun_events(today, lat, lon)
    if state == 'normal':
        print(f"Sunrise (local): {sr.astimezone().strftime('%Y-%m-%d %H:%M')}")
        print(f"Sunset  (local): {ss.astimezone().strftime('%Y-%m-%d %H:%M')}")
    else:
        print(f"Sun state today: {state}")

    dimmer = ConsoleDimmer(debug=False)
    now = datetime.now(timezone.utc)
    print("\nFactor around now (local time):")
    for minutes in range(-180, 181, 15):
        t = now + timedelta(minutes=minutes)
        f, phase = dimmer._evaluate(t)
        bar = '#' * int(f * 40)
        print(f"  {t.astimezone().strftime('%H:%M')}  {phase:5s}  {f:5.2f}  {bar}")


def _watch(interval: float):
    """Live diagnostic: print phase / factor / resulting backlight every `interval` s."""
    dimmer = ConsoleDimmer(debug=False)
    if not dimmer.enabled:
        return

    today = datetime.now(timezone.utc).date()
    sr, ss, state = sun_events(today, dimmer.lat, dimmer.lon)
    if state == 'normal':
        print(f"[Watch] Today: sunrise {sr.astimezone():%H:%M}, "
              f"sunset {ss.astimezone():%H:%M} (local)")
    print(f"[Watch] Updating every {interval:g}s — Ctrl+C to stop.")
    print(f"[Watch] 'backlight' columns show output at DCS full brightness "
          f"(throttle floor 13, pto2 floor 3)\n")
    print(f"{'time':8}  {'phase':6}  {'factor':>6}  {'cap':>4}  "
          f"{'throttle':>8}  {'pto2':>5}")

    try:
        while True:
            now_utc = datetime.now(timezone.utc)
            factor, phase = dimmer._evaluate(now_utc)
            # Backlight the hardware would get at full DCS brightness (raw=1.0)
            th = max(13, int(factor * 255))
            pt = max(3, int(factor * 255))
            local = now_utc.astimezone().strftime('%H:%M:%S')
            print(f"{local:8}  {phase:6}  {factor:6.3f}  {factor:4.0%}  "
                  f"{th:>8}  {pt:>5}", flush=True)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[Watch] stopped.")


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(
        description="Console night-dimmer diagnostics.")
    ap.add_argument('--watch', action='store_true',
                    help="Live-monitor phase/factor/backlight in real time.")
    ap.add_argument('--interval', type=float, default=5.0,
                    help="Watch update interval in seconds (default: 5).")
    args = ap.parse_args()

    if args.watch:
        _watch(args.interval)
    else:
        _demo()
