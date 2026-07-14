#!/usr/bin/env python3
"""
Manual console backlight tool.

Pushes a raw backlight value straight to the WinWing console backlight so you
can dial in what looks right in real low-light conditions — handy for picking a
good floor for the night dimmer (WINWING_NIGHT_FLOOR) or the hard minimums in
telemetry_mappings.py.

Values are 0-255 (the raw hardware range). You can also pass a percentage.

Usage:
    python3 set_backlight.py              # interactive: type values, panel updates live
    python3 set_backlight.py 40           # set both consoles to 40 and exit
    python3 set_backlight.py 15%          # ~38/255 and exit
    python3 set_backlight.py 40 --device throttle   # only the throttle
    python3 set_backlight.py --device pto2           # interactive, PTO2 only

Note: if the systemd service is running it may fight you for the panel when DCS
starts/stops. For quiet testing, stop it first:
    systemctl --user stop winwing-dcs-bridge
"""

import sys
import argparse

from winwing_devices import PTO2Controller, OrionThrottleController


def parse_value(text: str) -> int:
    """Parse '40', '40.0' or '15%' into a 0-255 backlight value."""
    text = text.strip()
    if text.endswith('%'):
        pct = float(text[:-1])
        value = round(max(0.0, min(100.0, pct)) / 100.0 * 255)
    else:
        value = round(float(text))
    return max(0, min(255, value))


def connect_devices(which: str):
    """Return a list of (name, apply_fn) for the requested, present devices."""
    targets = []

    if which in ('both', 'throttle'):
        t = OrionThrottleController()
        if t.device.hidraw_path and t.connect():
            targets.append(("Throttle", lambda v, t=t: t.set_led(t.BACKLIGHT, v)))
        else:
            print("[!] Throttle not found")

    if which in ('both', 'pto2'):
        p = PTO2Controller()
        if p.device.hidraw_path and p.connect():
            targets.append(("PTO2", lambda v, p=p: p.set_brightness(p.BACKLIGHT, v)))
        else:
            print("[!] PTO2 not found")

    return targets


def apply(targets, value: int):
    for name, fn in targets:
        fn(value)
    names = ", ".join(name for name, _ in targets)
    print(f"  -> {value:3d}/255  ({value / 255:.0%})  [{names}]")


def interactive(targets):
    print("\nType a backlight value (0-255 or e.g. 30%), Enter to apply.")
    print("Empty line or 'q' quits.\n")
    while True:
        try:
            raw = input("backlight> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if raw == '' or raw.lower() in ('q', 'quit', 'exit'):
            break
        try:
            value = parse_value(raw)
        except ValueError:
            print("  ? enter a number 0-255, or a percentage like 25%")
            continue
        apply(targets, value)


def main():
    ap = argparse.ArgumentParser(
        description="Manually push a console backlight value to WinWing hardware.")
    ap.add_argument('value', nargs='?',
                    help="Backlight value 0-255 or a percentage (e.g. 15%%). "
                         "Omit for interactive mode.")
    ap.add_argument('--device', choices=('both', 'throttle', 'pto2'), default='both',
                    help="Which console backlight to drive (default: both).")
    args = ap.parse_args()

    targets = connect_devices(args.device)
    if not targets:
        print("No devices connected — nothing to do.")
        sys.exit(1)

    if args.value is not None:
        try:
            apply(targets, parse_value(args.value))
        except ValueError:
            print(f"Invalid value: {args.value!r} (use 0-255 or a percentage)")
            sys.exit(1)
    else:
        interactive(targets)


if __name__ == '__main__':
    main()
