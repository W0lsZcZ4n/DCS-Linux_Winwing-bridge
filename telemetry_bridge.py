#!/usr/bin/env python3
"""
WinWing DCS Native Telemetry Bridge

Complete replacement for DCS-BIOS based winwing_bridge.py
Uses DCS native telemetry for both LED control and haptic feedback

Benefits:
- Simpler installation (one Export.lua vs. full DCS-BIOS)
- 100% accurate haptics (internal sim state, not cockpit approximations)
- Lower overhead (direct UDP, no protocol translation)
- Linux-friendly (pure Lua + Python)
"""

import sys
import time
import argparse

from telemetry_parser import TelemetryParser, FA18C_TelemetryHelper
from telemetry_mappings import TelemetryMappingManager
from winwing_devices import PTO2Controller, OrionThrottleController, OrionJoystickController


class TelemetryBridge:
    """
    Main bridge application using DCS native telemetry

    Architecture:
        DCS World → Export.lua → UDP → TelemetryParser → Mappings → WinWing Hardware
    """

    def __init__(self, port: int = 7780, test_mode: bool = False, debug: bool = False):
        self.port = port
        self.test_mode = test_mode
        self.debug = debug

        # Components
        self.parser = None
        self.mapping_manager = None

        # Hardware controllers
        self.throttle = None
        self.pto2 = None
        self.joystick = None

        # State
        self.running = False

    def initialize_hardware(self):
        """Detect and initialize WinWing hardware"""
        print("=== Detecting WinWing Hardware ===")

        try:
            self.throttle = OrionThrottleController()
            if self.throttle.device.hidraw_path and self.throttle.connect():
                print(f"✓ Throttle: {self.throttle.device.hidraw_path}")
            else:
                print(f"✗ Throttle: Not found or failed to connect")
                self.throttle = None
        except Exception as e:
            print(f"✗ Throttle: Not found ({e})")
            self.throttle = None

        try:
            self.pto2 = PTO2Controller()
            if self.pto2.device.hidraw_path and self.pto2.connect():
                print(f"✓ PTO2 Panel: {self.pto2.device.hidraw_path}")
            else:
                print(f"✗ PTO2 Panel: Not found or failed to connect")
                self.pto2 = None
        except Exception as e:
            print(f"✗ PTO2 Panel: Not found ({e})")
            self.pto2 = None

        try:
            self.joystick = OrionJoystickController()
            if self.joystick.device.hidraw_path and self.joystick.connect():
                print(f"✓ Joystick: {self.joystick.device.hidraw_path}")
            else:
                print(f"✗ Joystick: Not found or failed to connect")
                self.joystick = None
        except Exception as e:
            print(f"✗ Joystick: Not found ({e})")
            self.joystick = None

        if not any([self.throttle, self.pto2, self.joystick]):
            print("\n❌ No WinWing devices found!")
            print("Check USB connections and udev rules (99-winwing.rules)")
            return False

        print()
        return True

    def initialize_telemetry(self):
        """Initialize telemetry parser and mappings"""
        print("=== Initializing Telemetry System ===")

        # Create parser
        self.parser = TelemetryParser(port=self.port, debug=self.debug)

        if not self.parser.connect():
            print("❌ Failed to start telemetry receiver")
            return False

        # Create mapping manager and load universal mappings
        self.mapping_manager = TelemetryMappingManager(self.parser, debug=self.debug)
        self.mapping_manager.load_mappings(
            throttle=self.throttle,
            pto2=self.pto2,
            joystick=self.joystick
        )

        print()
        return True

    # Adaptive sleep: idle when DCS isn't sending, responsive when it is
    SLEEP_ACTIVE = 0.01   # 100Hz when receiving data
    SLEEP_IDLE = 1.0      # 1Hz when no data (near-zero CPU)
    IDLE_TIMEOUT = 5.0    # Seconds without data before going idle

    def run(self):
        """Main loop with adaptive sleep"""
        print("=== Bridge Running ===")
        print("Waiting for DCS telemetry...")
        print("Press Ctrl+C to stop\n")

        self.running = True
        last_status_print = 0
        was_idle = True

        # Start dark — DCS will set correct state when it connects
        self._all_off()

        try:
            while self.running:
                # Process telemetry
                received = self.parser.process()

                stats = self.parser.get_stats()
                now = time.time()
                idle = not stats['connected']

                # Update time-based effects only when active
                if not idle and self.mapping_manager:
                    self.mapping_manager.update()

                # State transitions
                if idle and not was_idle:
                    self._all_off()
                    print("[Status] No data — idling (1Hz polling, LEDs off)")
                elif not idle and was_idle:
                    # Restore hardware brightness groups so flag LEDs are visible
                    if self.pto2:
                        self.pto2.set_brightness(self.pto2.FLAG_BRIGHTNESS, 255)
                        self.pto2.set_brightness(self.pto2.SL_BRIGHTNESS, 255)
                    print(f"[Status] Data received — active (100Hz)")
                was_idle = idle

                # Print status every 5 seconds when active, every 30 when idle
                status_interval = 30.0 if idle else 5.0
                if now - last_status_print > status_interval:
                    self._print_status(stats)
                    last_status_print = now

                time.sleep(self.SLEEP_IDLE if idle else self.SLEEP_ACTIVE)

        except KeyboardInterrupt:
            print("\n\nShutting down...")

        self.shutdown()

    def _print_status(self, stats):
        """Print status line"""
        status = "✓ RECEIVING DATA" if stats['connected'] else "✗ NO DATA"
        aircraft = stats['aircraft'] or "N/A"
        packets = stats['packets']

        print(f"[Status] {status} | Aircraft: {aircraft} | Packets: {packets}")

    def test_leds(self):
        """Test LED functionality (quick flash pattern)"""
        print("=== Testing LEDs ===")
        print("All LEDs should flash 3 times\n")

        throttle_leds = [self.throttle.AA_BUTTON, self.throttle.AG_BUTTON] if self.throttle else []
        pto2_leds = [
            self.pto2.MASTER_CAUTION, self.pto2.STATION_CTR, self.pto2.STATION_LI,
            self.pto2.STATION_LO, self.pto2.STATION_RI, self.pto2.STATION_RO,
            self.pto2.FLAPS, self.pto2.NOSE, self.pto2.FULL, self.pto2.RIGHT,
            self.pto2.LEFT, self.pto2.HALF, self.pto2.HOOK
        ] if self.pto2 else []

        for _ in range(3):
            if self.throttle:
                print(f"  Throttle: ON")
                for led_id in throttle_leds:
                    self.throttle.set_led(led_id, True)

            if self.pto2:
                print(f"  PTO2: ON")
                for led_id in pto2_leds:
                    self.pto2.set_led(led_id, True)

            time.sleep(0.3)

            if self.throttle:
                print(f"  Throttle: OFF")
                for led_id in throttle_leds:
                    self.throttle.set_led(led_id, False)

            if self.pto2:
                print(f"  PTO2: OFF")
                for led_id in pto2_leds:
                    self.pto2.set_led(led_id, False)

            time.sleep(0.3)

        print("\n✓ LED test complete")

    def _all_off(self):
        """Turn off all LEDs, backlights, and motors"""
        if self.throttle:
            self.throttle.set_led(self.throttle.AA_BUTTON, False)
            self.throttle.set_led(self.throttle.AG_BUTTON, False)
            self.throttle.set_led(self.throttle.BACKLIGHT, 0)
            self.throttle.set_motor(0)

        if self.pto2:
            self.pto2.set_led(self.pto2.MASTER_CAUTION, False)
            self.pto2.set_led(self.pto2.STATION_CTR, False)
            self.pto2.set_led(self.pto2.STATION_LI, False)
            self.pto2.set_led(self.pto2.STATION_LO, False)
            self.pto2.set_led(self.pto2.STATION_RI, False)
            self.pto2.set_led(self.pto2.STATION_RO, False)
            self.pto2.set_led(self.pto2.FLAPS, False)
            self.pto2.set_led(self.pto2.NOSE, False)
            self.pto2.set_led(self.pto2.FULL, False)
            self.pto2.set_led(self.pto2.RIGHT, False)
            self.pto2.set_led(self.pto2.LEFT, False)
            self.pto2.set_led(self.pto2.HALF, False)
            self.pto2.set_led(self.pto2.HOOK, False)
            self.pto2.set_brightness(self.pto2.BACKLIGHT, 0)
            self.pto2.set_brightness(self.pto2.GEAR_HANDLE, 0)

        if self.joystick:
            self.joystick.set_motor(0)

    def shutdown(self):
        """Clean shutdown"""
        print("Cleaning up...")
        self._all_off()

        # Disconnect telemetry
        if self.parser:
            self.parser.disconnect()

        print("✓ Shutdown complete")


# ============================================================================
# Main Entry Point
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="WinWing DCS Native Telemetry Bridge",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                          # Run with universal mappings
  %(prog)s --test-leds              # Test LED functionality
  %(prog)s --port 7780              # Use custom port

Note:
  LEDs and haptics work on all supported aircraft — no --aircraft flag needed.
  Make sure Export.lua is installed in DCS Scripts folder.
  See telemetry_prototype/Export.lua for installation.
        """
    )

    parser.add_argument(
        '--port',
        type=int,
        default=7780,
        help='UDP port for telemetry (default: 7780)'
    )

    parser.add_argument(
        '--test-leds',
        action='store_true',
        help='Test LED functionality and exit'
    )

    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable verbose debug output (haptic values, AOA, telemetry data)'
    )

    args = parser.parse_args()

    # Banner
    print("=" * 60)
    print("WinWing DCS Native Telemetry Bridge")
    print("Replaces DCS-BIOS with native telemetry")
    print("=" * 60)
    print()

    # Create bridge
    bridge = TelemetryBridge(
        port=args.port,
        test_mode=args.test_leds,
        debug=args.debug
    )

    # Initialize hardware
    if not bridge.initialize_hardware():
        sys.exit(1)

    # Test mode
    if args.test_leds:
        bridge.test_leds()
        sys.exit(0)

    # Initialize telemetry
    if not bridge.initialize_telemetry():
        sys.exit(1)

    # Run main loop
    bridge.run()


if __name__ == "__main__":
    main()
