# WinWing DCS-BIOS Bridge

Synchronize your WinWing hardware LEDs with DCS World cockpit indicators in real-time on Linux.

## What Does This Do?

This bridge connects DCS-BIOS (which reads your aircraft's cockpit state) to your WinWing hardware, making the LEDs on your panels and controllers match what you see in the game. When your landing gear indicator lights up in the cockpit, the LED on your physical panel lights up too!

**Example:** Flip the landing gear lever in DCS → Gear indicator LEDs light up on your WinWing PTO2 panel → Gear locks down → LEDs turn off. All in real-time!

## Supported Hardware

### Currently Supported

- **WinWing Orion 2 PTO2 Panel** - Backlight, 13 LEDs (gear, flaps, hook, master caution, stations, etc.)
- **WinWing Orion 2 Throttle** - Backlight, master mode buttons (A/A, A/G)
- **WinWing Orion 2 Joystick** - (Ready for future features)

### Supported Aircraft

- **F/A-18C Hornet** - 13 cockpit indicators mapped ✅
- More aircraft coming soon (F-16C, A-10C planned)

## Requirements

### Software

- **Linux** (tested on Ubuntu/Debian-based distros)
- **Python 3.6+** (usually pre-installed)
- **DCS World** (running through Steam/Proton, currently setup to work with steam installed via .deb package)
- **DCS-BIOS** (git clone into the )

### Hardware

- WinWing Orion 2 devices (PTO2 Panel, Throttle, or Joystick)
- USB connection to your PC

## Installation

### 1. Install DCS-BIOS

DCS-BIOS installation on Linux is straightforward - just clone and copy:

```bash
# Clone DCS-BIOS repository
git clone https://github.com/DCS-Skunkworks/dcs-bios.git

# Copy to DCS Scripts folder (adjust path if using standalone DCS)
cp -r dcs-bios/Scripts/DCS-BIOS ~/.local/share/Steam/steamapps/compatdata/223750/pfx/drive_c/users/steamuser/Saved\ Games/DCS/Scripts/

# Create Export.lua to load DCS-BIOS
echo 'dofile(lfs.writedir() .. [[Scripts\DCS-BIOS\BIOS.lua]])' > ~/.local/share/Steam/steamapps/compatdata/223750/pfx/drive_c/users/steamuser/Saved\ Games/DCS/Scripts/Export.lua
```

No configuration changes needed! The bridge works with default DCS-BIOS settings.

### 2. Clone This Repository

```bash
git clone https://github.com/W0lsZcZ4n/DCS-biosCustom.git
```

### 3. Set Up USB Permissions

Copy the udev rules file to allow non-root access to WinWing devices:

```bash
sudo cp 99-winwing.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Add yourself to the `input` group:

```bash
sudo usermod -a -G input $USER
```

**Log out and log back in** for the group change to take effect.

### 4. Verify Setup

Run the setup checker to make sure everything is ready:

```bash
./check_setup.py
```

This will check:

- ✓ Python installation
- ✓ USB permissions
- ✓ WinWing devices detected
- ✓ DCS-BIOS installation
- ✓ Network configuration

Fix any issues it reports before continuing.

## Quick Start

### Test Your Hardware

First, verify the bridge can communicate with your WinWing devices:

```bash
./winwing_bridge.py --test-leds
```

You should see all LEDs flash in a test pattern. If this works, hardware communication is good!

### Run the Bridge

**Simple method (auto-detects aircraft):**

```bash
./winwing_bridge.py
```

**Background mode:**

```bash
./start_bridge.sh start
```

Check status:

```bash
./start_bridge.sh status
```

Stop the bridge:

```bash
./start_bridge.sh stop
```

### Use It!

1. Start the bridge (see above)
2. Launch DCS World
3. Enter an F/A-18C cockpit
4. Watch your LEDs sync automatically! 🎉

The bridge will print status updates:

```
[DCS-BIOS] Listening on multicast 239.255.50.10:5010
Aircraft Changed: FA18C
Loaded 15 LED mappings for FA18C
[Status] ✓ RECEIVING DATA | Aircraft: FA18C | Packets: 1523
```

## How to Use

### In Flight

Once running, the bridge works automatically, following your cockpit inputs.

### Testing Individual Features

Want to test specific LEDs? Use the diagnostic tool:

```bash
./diagnose.py
```

This shows live DCS-BIOS data and confirms which indicators are active.

## Troubleshooting

### No WinWing devices found

```bash
# Check if devices show up
lsusb | grep 4098

# Check USB device files exist
ls -la /dev/hidraw*

# Verify you're in the input group
groups
```

If `input` is not in the list, log out and back in after running the `usermod` command.

### No DCS-BIOS data received

1. Make sure DCS World is running
2. Make sure you're **in the cockpit** (not external view or menu)
3. Verify DCS-BIOS is installed correctly
4. Check firewall isn't blocking UDP multicast (port 5010)

Test DCS-BIOS connection:

```bash
./diagnose.py
```

Should show "✓ RECEIVING DATA" when in cockpit.

### LEDs not changing in flight

1. Run `--test-leds` first to verify hardware works
2. Check the bridge console for error messages
3. Make sure you're flying the F/A-18C (only supported aircraft currently)
4. Verify the specific cockpit indicator is actually active in DCS

### Bridge crashes or freezes

Check the log file:

```bash
tail -f bridge.log
```

Report issues with the log output.

## Updating the Bridge

```bash
cd ~/Documents/DCS-biosCustom
git pull
```

Then restart the bridge.

## Advanced Usage

### Manual Aircraft Selection

If auto-detection isn't working:

```bash
./winwing_bridge.py --aircraft FA18C
```

### Custom Port

If you modified your DCS-BIOS configuration:

```bash
./winwing_bridge.py --port 5010
```

## Contributing

Contributions welcome! If you:

- Add support for new aircraft
- Fix bugs
- Improve documentation
- Add new features

Please open a pull request!

## Credits

- **Protocol reverse engineering**: Based on [PTO2-for-BMS](https://github.com/ExoLightFR/PTO2-for-BMS) by ExoLightFR
- **DCS-BIOS**: By the [DCS-BIOS team](https://github.com/DCS-Skunkworks/dcs-bios)
- **Development**: Built for the DCS Linux community

## License

This is a community tool for personal use with DCS World and WinWing hardware. Use at your own risk.

## Support

- **Issues**: Open an issue on GitHub
- **Discussions**: Use GitHub Discussions
- **DCS-BIOS Help**: Visit the [official DCS-BIOS repository](https://github.com/DCS-Skunkworks/dcs-bios)

## Future changes

- [ ] rewrite the script in order to omit the DCS-BIOS in favor of in-built DCS telemetry for richer data stream

- [ ] implement hardware haptics control

- [ ] adding other jets mappings, logically compatible with Winwing Orion2 devices

- [ ] setup automation, more user environment cases, daemon verision

---

**Happy flying!** 🚀
