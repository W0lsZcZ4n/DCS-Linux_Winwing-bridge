# WinWing DCS Telemetry Bridge

Synchronize your WinWing hardware LEDs and haptic motors with DCS World in real-time on Linux.

## What is it for?

This bridge reads telemetry data directly from DCS World and maps it to your WinWing hardware:

- **LEDs** light up to match cockpit indicators (gear, flaps, master caution, stations, etc.)
- **Haptic motors** provide physical feedback for flight events (gun fire, weapon release, gear transit, AOA buffeting, landing impact, ground roll)

When your landing gear indicator lights up in the cockpit, the LED on your physical panel lights up too. When you fire the gun, you feel it through the throttle and stick.

> **Note:** An earlier version of this project used DCS-BIOS for cockpit data. That dependency has been replaced entirely with DCS native telemetry via a custom Export.lua script — simpler installation, lower overhead, and more accurate haptic feedback.

## Supported Hardware

- **WinWing Orion 2 Throttle** — Backlight, master mode LEDs (A/A, A/G), haptic motor
- **WinWing Orion 2 PTO2 Panel** — Backlight, 13 LEDs (gear, flaps, hook, master caution, stations, gear handle)
- **WinWing Orion 2 Joystick** — Haptic motor

## Supported Aircraft

| Aircraft       | LEDs                                | Haptics |
| -------------- | ----------------------------------- | ------- |
| F/A-18C Hornet | Full (all indicators)               | Full    |
| F-16C Viper    | Partial (gear, master caution, A/A) | Full    |

Haptic effects are universal — they work on any aircraft without per-module configuration. LED support requires per-aircraft cockpit argument mappings (see [Adding Aircraft](#adding-aircraft-led-support)).

## Haptic Effects

| Effect                    | Trigger                                                                       | Both Motors |
| ------------------------- | ----------------------------------------------------------------------------- | ----------- |
| Gun fire                  | Ammo count decrease                                                           | Yes         |
| Weapon/ fuel tank release | Station count decrease (weight-scaled intensity)                              | Yes         |
| Ground wobble             | G-force while on ground (carrier compatible, detects acceleration, not speed) | Yes         |
| Gear transit              | Gear position between 0 and 1                                                 | Yes         |
| Gear lock clunk           | Gear reaches locked position                                                  | Yes         |
| AOA buffeting             | AOA > 15° (scales to 35°)                                                     | Yes         |
| Landing impact            | Strut compression spike on touchdown                                          | Yes         |

## Requirements

- **Linux** (tested on Ubuntu/Debian)
- **Python 3.6+**
- **DCS World** (via Steam/Proton)
- WinWing Orion 2 devices (PTO2, Throttle, and/or Joystick)

No DCS-BIOS installation needed.

## Installation

### 1. Clone This Repository

```bash
git clone https://github.com/W0lsZcZ4n/DCS-biosCustom.git
cd DCS-biosCustom
```

### 2. Install Export.lua

Copy the telemetry export script to your DCS Scripts folder:

```bash
# For Steam .deb install:
cp telemetry_prototype/Export.lua ~/.local/share/Steam/steamapps/compatdata/223750/pfx/drive_c/users/steamuser/Saved\ Games/DCS/Scripts/Export.lua
```

```bash
# For Flatpak Steam:
cp telemetry_prototype/Export.lua ~/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/compatdata/223750/pfx/drive_c/users/steamuser/Saved\ Games/DCS/Scripts/Export.lua
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
2. Make sure `Export.lua` is installed in the correct DCS Scripts folder
3. Check the DCS log at `Saved Games/DCS/Logs/WinWing_Export.log`

### LEDs not changing

1. Run `python3 telemetry_bridge.py --test-leds` to verify hardware works
2. Make sure you're flying a supported aircraft (F/A-18C or F-16C)
3. Check bridge output for error messages

## Adding Aircraft LED Support

LED argument numbers differ per aircraft module. To add a new aircraft:

1. Use `telemetry_prototype/ArgDiscover.lua` to find the correct argument numbers
2. Add a new entry to the `AIRCRAFT_ARGS` table in `telemetry_prototype/Export.lua`
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
- [**DCS-Bios**]([GitHub - DCS-Skunkworks/dcs-bios: Data export tool for DCS.](https://github.com/DCS-Skunkworks/dcs-bios)): tool was helpful in initial version and reverse engineering efforts, now deprecated, still great project!
- **Development**: Built for the DCS Linux community

## Other DCS on Linux with WinCtrl troubleshooting

-  **The Orion2 Throttle 80 buttons cap:** There's an great kernel module for that-**[linux-winwing](https://github.com/igorinov/linux-winwing).** Should be by default on kernels above v.6.10. The setup is pretty straightforward.
- **The Orion2 joystick buttons not reading:**I tried to write something to fix that, but I mostly did break stuff. It could be related to the weird naming convention, which is rejected by the way proton/wine handles those. Personally i use  [**input-remapper**](https://github.com/sezanzeb/input-remapper) and map everything to the keyboard combinations with right ctrl key. Axes work fine, and if there are issues, i map those to the virtual gamepad. Not elegant, but works.
- **OpenTrack- head tracking:** I recommend using [**opentrack-launcher**](https://github.com/markx86/opentrack-launcher) that runs [opentrack](https://github.com/opentrack/opentrack) inside proton layer. There was issue with proton versions >10.17, so i just stick to 10.17 at the time of writing this. Generally it's pretty reliable.

## License

GNU GPL v3 License
