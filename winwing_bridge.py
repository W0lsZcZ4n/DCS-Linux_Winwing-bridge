#!/usr/bin/env python3
"""
WinWing DCS-BIOS Bridge
Main bridge application connecting DCS-BIOS to WinWing devices
"""
import time
import signal
import sys
from winwing_devices import DeviceManager
from dcsbios_parser import DCSBIOSParser
from aircraft_mappings import MappingManager


class WinWingBridge:
    """Main bridge application"""

    def __init__(self, aircraft: str = None, dcsbios_port: int = 5010, daemon: bool = False):
        self.aircraft = aircraft  # None = auto-detect
        self.dcsbios_port = dcsbios_port
        self.current_aircraft = None
        self.daemon = daemon  # Quiet mode for background operation

        self.devices = DeviceManager()
        self.parser = DCSBIOSParser(port=dcsbios_port)
        self.mappings = MappingManager(self.devices)

        self.running = False
        self.stats = {
            'packets_received': 0,
            'last_packet_time': 0,
            'start_time': 0,
            'aircraft_changes': 0
        }

    def log(self, message: str, force: bool = False):
        """Print message unless in daemon mode"""
        if force or not self.daemon:
            print(message)

    def on_aircraft_change(self, aircraft: str):
        """Handle aircraft change"""
        if aircraft == self.current_aircraft:
            return

        self.log(f"\n{'=' * 50}")
        self.log(f"Aircraft Changed: {aircraft}", force=True)
        self.log(f"{'=' * 50}")

        self.current_aircraft = aircraft
        self.stats['aircraft_changes'] += 1

        # Clear existing subscriptions
        self.parser.subscriptions.clear()
        self.mappings.active_mappings.clear()

        # Load new mappings
        self._load_aircraft_mappings(aircraft)

        # Re-subscribe
        subscriptions = self.mappings.get_all_subscriptions()
        for address, callback in subscriptions:
            self.parser.subscribe(address, callback)

        self.log(f"Loaded {len(subscriptions)} subscriptions for {aircraft}\n")

    def _load_aircraft_mappings(self, aircraft: str):
        """Load mappings for a specific aircraft"""
        aircraft_upper = aircraft.upper()

        if aircraft_upper == "FA18C":
            self.mappings.load_fa18c()
        else:
            self.log(f"WARNING: No mappings available for '{aircraft}'", force=True)
            self.log(f"Supported aircraft: FA18C")

    def setup(self) -> bool:
        """Initialize all components"""
        self.log("=" * 50)
        self.log("WinWing DCS-BIOS Bridge")
        self.log("=" * 50)

        # Connect to hardware
        if not self.devices.connect_all():
            self.log("ERROR: No devices connected!", force=True)
            return False

        # Connect to DCS-BIOS
        if not self.parser.connect():
            self.log("ERROR: Failed to bind DCS-BIOS UDP socket!", force=True)
            self.devices.disconnect_all()
            return False

        # Setup aircraft detection
        if self.aircraft:
            # Manual aircraft selection
            self.log(f"\n=== Manual Aircraft Mode: {self.aircraft} ===")
            self.current_aircraft = self.aircraft
            self._load_aircraft_mappings(self.aircraft)

            subscriptions = self.mappings.get_all_subscriptions()
            for address, callback in subscriptions:
                self.parser.subscribe(address, callback)

            self.log(f"Loaded {len(subscriptions)} subscriptions")
        else:
            # Auto-detect mode
            self.log(f"\n=== Auto-Detect Mode ===")
            self.log("Waiting for DCS-BIOS to detect aircraft...")
            self.parser.on_aircraft_change(self.on_aircraft_change)

        self.log("\n=== Bridge Ready ===", force=True)
        self.log(f"DCS-BIOS Port: {self.dcsbios_port}")
        self.log(f"Devices: {len(self.devices.devices)}")
        if not self.daemon:
            self.log("\nWaiting for DCS-BIOS data...")
            self.log("(Start DCS and load into any supported aircraft)")
            self.log("\nPress Ctrl+C to stop\n")

        return True

    def shutdown(self):
        """Clean shutdown"""
        self.log("\n\n=== Shutting Down ===")
        self.running = False

        # Turn off motors
        if self.devices.throttle.handle:
            self.devices.throttle.set_motor(0)
        if self.devices.joystick.handle:
            self.devices.joystick.set_motor(0)

        # Disconnect everything
        self.parser.disconnect()
        self.devices.disconnect_all()

        # Print stats
        runtime = time.time() - self.stats['start_time']
        self.log(f"\nRuntime: {runtime:.1f}s")
        self.log(f"Packets received: {self.stats['packets_received']}")
        if runtime > 0:
            self.log(f"Average rate: {self.stats['packets_received']/runtime:.1f} packets/sec")

        self.log("\nBridge stopped.", force=True)

    def run(self):
        """Main event loop"""
        self.running = True
        self.stats['start_time'] = time.time()
        last_status_time = time.time()
        status_interval = 10.0  # Print status every 10 seconds

        try:
            while self.running:
                # Process DCS-BIOS packets
                if self.parser.process_packet():
                    self.stats['packets_received'] += 1
                    self.stats['last_packet_time'] = time.time()

                # Print periodic status
                current_time = time.time()
                if current_time - last_status_time >= status_interval:
                    time_since_packet = current_time - self.stats['last_packet_time']
                    if self.stats['packets_received'] > 0:
                        if time_since_packet < 5.0:
                            status = "✓ RECEIVING DATA"
                        else:
                            status = f"⚠ No data for {time_since_packet:.0f}s"
                    else:
                        status = "⏳ Waiting for DCS..."

                    aircraft_str = self.current_aircraft if self.current_aircraft else "None"
                    self.log(f"[Status] {status} | Aircraft: {aircraft_str} | Packets: {self.stats['packets_received']}")
                    last_status_time = current_time

                # Small sleep to prevent CPU spinning
                time.sleep(0.001)

        except KeyboardInterrupt:
            self.log("\n\nInterrupted by user")

    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print("\nReceived shutdown signal")
        self.running = False


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description='WinWing DCS-BIOS Bridge - Auto-sync DCS cockpit to WinWing hardware',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                    # Auto-detect aircraft (recommended)
  %(prog)s --aircraft FA18C   # Force F/A-18C mappings
  %(prog)s --test-leds        # Test hardware
  %(prog)s --daemon           # Run in background (no status output)

Supported Aircraft: FA18C (more coming soon)
        """
    )
    parser.add_argument('--aircraft', type=str, default=None,
                        help='Force specific aircraft (FA18C, F16C, etc). Default: auto-detect')
    parser.add_argument('--port', type=int, default=5010,
                        help='DCS-BIOS UDP port (default: 5010)')
    parser.add_argument('--test-leds', action='store_true',
                        help='Run LED test pattern and exit')
    parser.add_argument('--daemon', action='store_true',
                        help='Run in background mode (minimal output)')

    args = parser.parse_args()

    # Test mode
    if args.test_leds:
        print("=== LED Test Mode ===")
        devices = DeviceManager()
        if devices.connect_all():
            print("\nTesting LEDs (3 seconds each)...")

            if devices.pto2.handle:
                print("PTO2: All LEDs ON")
                for led_id in range(0x04, 0x12):
                    devices.pto2.set_led(led_id, True)
                time.sleep(3)

                print("PTO2: All LEDs OFF")
                for led_id in range(0x04, 0x12):
                    devices.pto2.set_led(led_id, False)

            if devices.throttle.handle:
                print("Throttle: Backlight full")
                devices.throttle.set_led(devices.throttle.BACKLIGHT, 255)
                time.sleep(2)
                print("Throttle: A/A and A/G ON")
                devices.throttle.set_led(devices.throttle.AA_BUTTON, True)
                devices.throttle.set_led(devices.throttle.AG_BUTTON, True)
                time.sleep(2)
                devices.throttle.set_led(devices.throttle.AA_BUTTON, False)
                devices.throttle.set_led(devices.throttle.AG_BUTTON, False)

            print("Test complete")
            devices.disconnect_all()
        return

    # Normal bridge mode
    bridge = WinWingBridge(aircraft=args.aircraft, dcsbios_port=args.port, daemon=args.daemon)

    # Setup signal handlers
    signal.signal(signal.SIGINT, bridge.signal_handler)
    signal.signal(signal.SIGTERM, bridge.signal_handler)

    # Initialize
    if not bridge.setup():
        if args.daemon:
            # In daemon mode, write to stderr for logging
            sys.stderr.write("Failed to initialize bridge\n")
        else:
            print("\nFailed to initialize bridge")
        sys.exit(1)

    # Run main loop
    try:
        bridge.run()
    finally:
        bridge.shutdown()


if __name__ == "__main__":
    main()
