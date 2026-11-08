# WinWing DCS Telemetry Bridge

Synchronize your WinWing hardware LEDs and haptic motors with DCS World in real-time on Linux.

## What is it for?

This bridge reads telemetry data directly from DCS World and maps it to your WinWing hardware:

- **LEDs** light up to match cockpit indicators (gear, flaps, master caution, stations, etc.)
- **Haptic motors** provide physical feedback for flight events (gun fire, weapon release, gear transit, AOA buffeting, landing impact, ground roll)

When your landing gear indicator lights up in the cockpit, the LED on your physical panel lights up too. When you fire the gun, you feel it through the throttle and stick.

> 

## Supported Hardware

- **WinWing Orion 2 Throttle** — Backlight, master mode LEDs (A/A, A/G), haptic motor
- **WinWing Orion 2 PTO2 Panel** — Backlight, 13 LEDs (gear, flaps, hook, master caution, stations, gear handle)
- **WinWing Orion 2 Joystick** — Haptic motor

## Supported Aircraft

| Aircraft       | LEDs                                | Haptics |
| -------------- | ----------------------------------- | ------- |
| F/A-18C Hornet | Full (all indicators)               | Full    |
| F-16C Viper    | Partial (gear, master caution) | Full    |

Haptic effects are universal — they work on any aircraft without per-module configuration. LED support requires per-aircraft cockpit argument mappings (see [Adding Aircraft](#adding-aircraft-led-support)).

## Haptic Effects

| Effect                    | Trigger                                                                       
| ------------------------- | ----------------------------------------------------------------------------- |
| Gun fire                  | Ammo count decrease                                                           |
| Weapon/ fuel tank release | Station count decrease (weight-scaled intensity)                              |
| Ground wobble             | G-force while on ground (carrier compatible, detects acceleration, not speed) |
| Gear transit              | Gear position between 0 and 1                                                 |
| Gear lock clunk           | Gear reaches locked position                                                  |
| AOA buffeting             | AOA > 15° (scales to 35°)                                                     |
| Landing impact            | Strut compression spike on touchdown                                          |

## Night Console Dimming

At night the physical WinWing console backlight can be blindingly bright compared to
the in-game consoles. This feature gradually **caps** the backlight range after dark so
the real panel never overpowers the sim.

It works out of the box with **no setup**. Your PC's clock and an approximate location
taken from your system timezone work out where the sun is (no internet, no extra
libraries), and the panel follows it:

- **Daytime** — full brightness range (unchanged).
- **After sunset** — the range squeezes down to a 30% floor as the sun sinks from the
  horizon to 6° below it (civil twilight — "properly dark").
- **Night** — capped at that floor.
- **Before sunrise** — the range stretches back up to 100% by sunrise.

Because it tracks the real sun, the twilight ramp **adapts to your latitude and the
season** — long and shallow in high-latitude summers, short near the equator. The DCS
cockpit brightness knob still works normally; only the range it maps into shrinks.
The changes are gradual, so a slightly-off location guess is unnoticeable.

### Tuning it

If the defaults don't suit you, pass any of these to the bridge — add them to
`ExecStart` in the systemd unit, or run the bridge directly:

| Flag | What it does |
| ---- | ------------ |
| `--nodim` | Keeps the backlight at full range all the time — dimming off entirely. |
| `--floor 0.5` | How bright the panel may get at night, as a fraction of full (0.0–1.0). Default `0.30` — higher is easier to read, lower is easier on the eyes. |
| `--sun-low -12` | How dark the sky has to be before the panel sits at the floor. It's the sun's angle below the horizon in degrees: `-3` starts dimming sooner after sunset, `-12` (nautical twilight) later. Default `-6`. |
| `--lat 52.53 --lon 13.40` | Tells it where you are, if the timezone guess is off (decimal degrees, north/east positive — you can copy values from any map site). |

```bash
# e.g. in the service unit:
ExecStart=/usr/bin/python3 -u %h/Documents/DCS-Linux_Winwing-bridge/telemetry_bridge.py --floor 0.5
```

### Seeing what it would do

Preview today's sunrise/sunset and the full dimming curve for your machine — no DCS,
no hardware needed (it takes the same tuning flags):

```bash
python3 console_dimmer.py
python3 console_dimmer.py --lat 69.6 --lon 18.9    # e.g. Tromsø — long summer twilight
```

Watch it **live** — phase, factor and resulting backlight, updating in real time:

```bash
python3 console_dimmer.py --watch                  # updates every 5s
python3 console_dimmer.py --watch --interval 1 --floor 0.5
```

```
time      phase   factor   cap  throttle   pto2
21:48:59  dusk     0.805   80%       205    205
21:49:59  dusk     0.734   73%       187    187
```

While the bridge is running, `--debug` logs a dimmer line you can follow in the
journal:

```bash
journalctl --user -u winwing-dcs-bridge -f | grep Dimmer
#   [Dimmer] 21:49:36 phase=dusk  factor=0.800 (backlight cap 80%)
```

(There are also `WINWING_*` environment variables for every knob — useful with
`Environment=` in systemd. Flags win over the environment; run `--help` for details.)

## Requirements

- **Linux** (tested on Ubuntu/Debian)
- **Python 3.6+**
- **DCS World** (via Steam/Proton)
- WinWing Orion 2 devices (PTO2, Throttle, and/or Joystick)

## Installation

### 1. Clone This Repository

```bash
git clone https://github.com/W0lsZcZ4n/DCS-Linux_Winwing-bridge.git
cd DCS-Linux_Winwing-bridge
```

### 2. Install Export.lua

Copy the telemetry export script to your DCS ../Saved Games/DCS/Scripts folder:

```bash
# For Steam .deb install:
cp Export.lua ~/.local/share/Steam/steamapps/compatdata/223750/pfx/drive_c/users/steamuser/Saved\ Games/DCS/Scripts/Export.lua
```

```bash
# For Flatpak Steam:
cp Export.lua ~/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/compatdata/223750/pfx/drive_c/users/steamuser/Saved\ Games/DCS/Scripts/Export.lua
```

### 3. Set Up USB Permissions

```bash
sudo cp 99-winwing.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
sudo usermod -a -G input $USER
```

**Log out and log back in** for the group change to take effect.

### 4. Run the Bridge

**Directly:**

```bash
python3 telemetry_bridge.py
```

**As a systemd service (recommended):**

```bash
# Edit the ExecStart path in the service file to match your install location
cp winwing-dcs-bridge.service ~/.config/systemd/user/
systemctl --user enable winwing-dcs-bridge
systemctl --user start winwing-dcs-bridge
```

The bridge uses adaptive sleep — it idles at 1Hz when DCS isn't running (near-zero CPU) and ramps up to 100Hz when telemetry data is flowing. Safe to leave running permanently.

### 5. Use It

1. Start the bridge (or let systemd handle it)
2. Launch DCS World
3. Enter a cockpit
4. LEDs sync and haptics activate automatically

## Service Management

```bash
# Check status
systemctl --user status winwing-dcs-bridge

# View logs
journalctl --user -u winwing-dcs-bridge -f

# Restart after code changes
systemctl --user restart winwing-dcs-bridge

# Test LEDs (run directly, not via service)
python3 telemetry_bridge.py --test-leds

# Debug mode — verbose output showing LED state changes, haptic triggers, AOA, etc.
python3 telemetry_bridge.py --debug
```

## Troubleshooting

### No WinWing devices found

```bash
# Check if devices are connected
lsusb | grep 4098

# Check USB device files
ls -la /dev/hidraw*

# Verify you're in the input group
groups
```

### No telemetry data

1. Make sure DCS World is running and you're in the cockpit
2. Make sure `Export.lua` is installed in the correct ../Saved Games/DCS/Scripts folder 
3. Check the DCS log at `Saved Games/DCS/Logs/WinWing_Export.log`

### LEDs not changing

1. Run `python3 telemetry_bridge.py --test-leds` to verify hardware works
2. Make sure you're flying a supported aircraft (F/A-18C or F-16C)
3. Check bridge output for error messages

## Adding Aircraft LED Support

LED argument numbers differ per aircraft module. To add a new aircraft:

1. Use `ArgDiscover.lua` to find the correct argument numbers
2. Add a new entry to the `AIRCRAFT_ARGS` table in `Export.lua`
3. Copy the updated Export.lua to your DCS Scripts folder

Haptic effects require no per-aircraft configuration — they use universal DCS telemetry APIs.

## Architecture

```
DCS World → Export.lua (Lua, UDP) → telemetry_parser.py → telemetry_mappings.py → WinWing Hardware
                                                                    ↓
                                                        ┌───────────┴───────────┐
                                                        ↓                       ↓
                                                  LEDs (PTO2, Throttle)   Motors (Throttle, Joystick)
```

- `Export.lua` runs inside DCS, reads cockpit arguments and telemetry APIs, sends JSON via UDP at 30Hz
- `telemetry_parser.py` receives packets, tracks state changes, fires callbacks
- `telemetry_mappings.py` maps telemetry data to hardware outputs (LEDs and haptic effects)
- `winwing_devices.py` communicates with WinWing hardware via HID

## Credits

- **Protocol reverse engineering**: Based on [PTO2-for-BMS](https://github.com/ExoLightFR/PTO2-for-BMS) by ExoLightFR
- [**DCS-Bios**](https://github.com/DCS-Skunkworks/dcs-bios): tool was helpful in initial version and reverse engineering efforts, now deprecated, still great project!
- **Development**: Built for the DCS Linux community

## Other DCS on Linux with WinCtrl troubleshooting

- **The Orion2 Throttle 80 buttons cap:** There's an great kernel module for that-**[linux-winwing](https://github.com/igorinov/linux-winwing).** Should be by default on kernels above v.6.10. The setup is pretty straightforward.
- **The Orion2 joystick buttons not reading:** I tried to write something to fix that, but I mostly did break stuff. It could be related to the weird naming convention, which is rejected by the way proton/wine handles those. Personally i use  [**input-remapper**](https://github.com/sezanzeb/input-remapper) and map everything to the keyboard combinations with right ctrl key. Axes work fine, and if there are issues, i map those to the virtual gamepad. Not elegant, but works.
- **OpenTrack- head tracking:** I recommend using [**opentrack-launcher**](https://github.com/markx86/opentrack-launcher) that runs [opentrack](https://github.com/opentrack/opentrack) inside proton layer. There was issue with proton versions >10.17, so i just stick to 10.17 at the time of writing this. Generally it's pretty reliable.
