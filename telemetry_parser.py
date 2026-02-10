#!/usr/bin/env python3
"""
DCS Native Telemetry Parser

Receives and parses JSON telemetry packets from DCS World Export.lua
Replaces dcsbios_parser.py for native telemetry approach

Provides:
- LED state changes (via callbacks)
- Weapon telemetry (gun ammo, stations)
- Flight data (AOA, G-forces, altitude, etc.)
- Engine data (RPM, etc.)
"""

import socket
import json
import time
from typing import Dict, Callable, Optional, Any


class TelemetryParser:
    """
    Receives and parses DCS telemetry packets via UDP

    Usage:
        parser = TelemetryParser(port=7780)
        parser.subscribe("cannon_ammo", my_callback)
        parser.connect()

        while True:
            parser.process()
    """

    def __init__(self, port: int = 7780, host: str = '127.0.0.1', debug: bool = False):
        self.port = port
        self.host = host
        self.debug = debug
        self.socket: Optional[socket.socket] = None

        # Subscription system (similar to DCS-BIOS)
        self.subscriptions: Dict[str, list] = {}

        # State tracking
        self.last_packet: Optional[Dict] = None
        self.last_values: Dict[str, Any] = {}
        self.aircraft: Optional[str] = None

        # Statistics
        self.packet_count = 0
        self.last_packet_time = 0
        self.errors = 0

    def connect(self) -> bool:
        """Open UDP socket for receiving telemetry"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.bind((self.host, self.port))
            self.socket.settimeout(0.1)  # 100ms timeout for non-blocking
            print(f"[Telemetry] Listening on {self.host}:{self.port}")
            return True
        except Exception as e:
            print(f"[Telemetry] Failed to bind socket: {e}")
            return False

    def disconnect(self):
        """Close the socket"""
        if self.socket:
            self.socket.close()
            self.socket = None

    def subscribe(self, data_path: str, callback: Callable):
        """
        Subscribe to telemetry data changes

        Examples:
            subscribe("leds.MASTER_CAUTION", lambda v: print(f"Caution: {v}"))
            subscribe("payload.cannon_ammo", lambda v: print(f"Ammo: {v}"))
            subscribe("flight.aoa", lambda v: print(f"AOA: {v}"))
        """
        if data_path not in self.subscriptions:
            self.subscriptions[data_path] = []
        self.subscriptions[data_path].append(callback)

    def process(self) -> bool:
        """
        Process one telemetry packet (non-blocking)

        Returns:
            True if packet received, False otherwise
        """
        if not self.socket:
            return False

        try:
            data, addr = self.socket.recvfrom(4096)
            self._handle_packet(data)
            return True
        except socket.timeout:
            return False
        except Exception as e:
            self.errors += 1
            if self.errors < 10:  # Only print first 10 errors
                print(f"[Telemetry] Error processing packet: {e}")
            return False

    def _handle_packet(self, data: bytes):
        """Parse and process a telemetry packet"""
        try:
            packet = json.loads(data.decode('utf-8'))
        except json.JSONDecodeError as e:
            print(f"[Telemetry] Invalid JSON: {e}")
            return

        self.last_packet = packet
        self.packet_count += 1
        self.last_packet_time = time.time()

        # Debug: Print first packet to see structure
        if self.packet_count == 1:
            print(f"[Telemetry] First packet received:")
            print(f"  Keys: {list(packet.keys())}")
            if 'aircraft' in packet:
                print(f"  Aircraft: {packet['aircraft']}")
            if 'flight' in packet:
                print(f"  Flight data: {packet['flight']}")
            if 'payload' in packet:
                print(f"  Payload: {packet['payload']}")

        # Update aircraft if changed
        if 'aircraft' in packet and packet['aircraft']:
            if self.aircraft != packet['aircraft']:
                self.aircraft = packet['aircraft']
                self._notify_subscribers('aircraft', self.aircraft)

        # Process all data sections
        self._process_section(packet, 'leds')
        self._process_section(packet, 'payload')
        self._process_section(packet, 'flight')
        self._process_section(packet, 'engine')

    def _process_section(self, packet: Dict, section: str):
        """Process a data section and notify subscribers"""
        if section not in packet:
            return

        data = packet[section]
        if not isinstance(data, dict):
            return

        for key, value in data.items():
            data_path = f"{section}.{key}"

            # Check if value changed
            last_value = self.last_values.get(data_path)
            if last_value != value:
                if self.debug and section not in ('flight', 'engine') and key not in ('GEAR_POS', 'GEAR_STATUS', 'ROD_NOSE', 'ROD_LEFT', 'ROD_RIGHT'):
                    print(f"[DEBUG] {data_path}: {last_value} → {value}")
                self.last_values[data_path] = value
                self._notify_subscribers(data_path, value)

    def _notify_subscribers(self, data_path: str, value: Any):
        """Notify all subscribers of a data change"""
        if data_path in self.subscriptions:
            for callback in self.subscriptions[data_path]:
                try:
                    callback(value)
                except Exception as e:
                    print(f"[Telemetry] Error in callback for {data_path}: {e}")

    def get_value(self, data_path: str, default=None) -> Any:
        """
        Get current value of a data path

        Examples:
            ammo = parser.get_value("payload.cannon_ammo", 0)
            aoa = parser.get_value("flight.aoa", 0.0)
        """
        return self.last_values.get(data_path, default)

    def get_stats(self) -> Dict:
        """Get parser statistics"""
        now = time.time()
        age = now - self.last_packet_time if self.last_packet_time > 0 else 999

        return {
            'packets': self.packet_count,
            'errors': self.errors,
            'age': age,
            'connected': age < 2.0,  # Data within last 2 seconds
            'aircraft': self.aircraft
        }


class FA18C_TelemetryHelper:
    """
    Helper class for F/A-18C specific telemetry processing

    Provides high-level functions for common tasks:
    - Gun fire detection
    - Touchdown detection
    - AOA buffeting detection
    - Gear state tracking
    """

    def __init__(self, parser: TelemetryParser):
        self.parser = parser

        # State tracking
        self.last_cannon_ammo = None
        self.last_altitude = None
        self.was_airborne = False

        # Callbacks
        self.on_gun_fire = None
        self.on_touchdown = None
        self.on_aoa_high = None

        # Subscribe to relevant data
        parser.subscribe("payload.cannon_ammo", self._handle_ammo_change)
        parser.subscribe("flight.vertical_velocity", self._handle_vertical_velocity)
        parser.subscribe("flight.aoa", self._handle_aoa)

    def _handle_ammo_change(self, ammo: int):
        """Detect gun firing from ammo decrease"""
        if self.last_cannon_ammo is not None and ammo < self.last_cannon_ammo:
            shots_fired = self.last_cannon_ammo - ammo
            if self.on_gun_fire:
                self.on_gun_fire(ammo, shots_fired)

        self.last_cannon_ammo = ammo

    def _handle_vertical_velocity(self, vv: float):
        """Detect touchdown from vertical velocity"""
        altitude = self.parser.get_value("flight.alt_agl", 999)

        # Touchdown = negative vertical velocity + low altitude
        if vv < -3.0 and altitude < 10 and self.was_airborne:
            if self.on_touchdown:
                impact_force = abs(vv)
                self.on_touchdown(impact_force)
            self.was_airborne = False
        elif altitude > 20:
            self.was_airborne = True

    def _handle_aoa(self, aoa: float):
        """Detect high AOA for buffeting"""
        # F/A-18C buffeting starts around 18-20 degrees AOA
        if aoa > 18.0:
            if self.on_aoa_high:
                self.on_aoa_high(aoa)


# ============================================================================
# Test / Demo
# ============================================================================

def main():
    """Test telemetry parser with live DCS data"""
    print("=== DCS Telemetry Parser Test ===")
    print("Make sure DCS is running with Export.lua installed")
    print("Listening for telemetry packets...")
    print()

    parser = TelemetryParser(port=7780)

    if not parser.connect():
        print("Failed to start telemetry receiver")
        return

    # Subscribe to interesting data
    def on_aircraft_change(name):
        print(f"\n[Aircraft] {name}")

    def on_master_caution(value):
        print(f"[LED] Master Caution: {'ON' if value else 'OFF'}")

    def on_ammo_change(value):
        print(f"[Weapon] Cannon Ammo: {value}")

    def on_aoa_change(value):
        if value > 15:
            print(f"[Flight] High AOA: {value:.1f}°")

    parser.subscribe("aircraft", on_aircraft_change)
    parser.subscribe("leds.MASTER_CAUTION", on_master_caution)
    parser.subscribe("payload.cannon_ammo", on_ammo_change)
    parser.subscribe("flight.aoa", on_aoa_change)

    # Set up FA-18C helper
    fa18_helper = FA18C_TelemetryHelper(parser)

    def gun_fire_detected(ammo, shots):
        print(f"🔫 GUN FIRING! ({shots} rounds, {ammo} remaining)")

    def touchdown_detected(impact):
        print(f"✈️  TOUCHDOWN! (impact force: {impact:.1f} m/s)")

    fa18_helper.on_gun_fire = gun_fire_detected
    fa18_helper.on_touchdown = touchdown_detected

    # Main loop
    print("Waiting for data...")
    last_status = 0

    try:
        while True:
            parser.process()

            # Print status every 5 seconds
            now = time.time()
            if now - last_status > 5.0:
                stats = parser.get_stats()
                status = "✓ RECEIVING" if stats['connected'] else "✗ NO DATA"
                print(f"\n[Status] {status} | Aircraft: {stats['aircraft']} | Packets: {stats['packets']}")
                last_status = now

            time.sleep(0.01)  # 100Hz processing

    except KeyboardInterrupt:
        print("\n\nShutting down...")
        parser.disconnect()


if __name__ == "__main__":
    main()
