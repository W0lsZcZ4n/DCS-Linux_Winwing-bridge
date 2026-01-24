#!/usr/bin/env python3
"""Diagnostic tool to check DCS-BIOS connectivity and PTO2 LED functionality"""

import time
import sys
from dcsbios_parser import DCSBIOSParser, FA18CAddresses

print("=== DCS-BIOS Connection Diagnostic ===\n")

# Create parser
parser = DCSBIOSParser()

# Connect
if not parser.connect():
    print("ERROR: Could not bind to DCS-BIOS port!")
    exit(1)

print("Listening for DCS-BIOS multicast data on port 5010...")
print("Make sure DCS is running and you're in the F/A-18C cockpit\n")

# Track which addresses we've seen
seen_addresses = set()
last_activity = time.time()
packet_count = 0

# Subscribe to PTO2-related addresses for debugging
pto2_addresses = {
    FA18CAddresses.GEAR_NOSE_LT.address: "GEAR_NOSE_LT",
    FA18CAddresses.GEAR_LEFT_LT.address: "GEAR_LEFT_LT",
    FA18CAddresses.GEAR_RIGHT_LT.address: "GEAR_RIGHT_LT",
    FA18CAddresses.FLAPS_LT.address: "FLAPS_LT",
    FA18CAddresses.MASTER_CAUTION_LT.address: "MASTER_CAUTION_LT",
    FA18CAddresses.STATION_CTR.address: "STATION_CTR",
}

for addr, name in pto2_addresses.items():
    def make_callback(addr, name):
        def callback(value):
            # Extract the specific bit
            for addr_obj in [FA18CAddresses.GEAR_NOSE_LT, FA18CAddresses.GEAR_LEFT_LT,
                            FA18CAddresses.GEAR_RIGHT_LT, FA18CAddresses.FLAPS_LT,
                            FA18CAddresses.MASTER_CAUTION_LT, FA18CAddresses.STATION_CTR]:
                if addr_obj.address == addr and addr_obj.description == name:
                    extracted = (value & addr_obj.mask) >> addr_obj.shift
                    print(f"  [{name}] = {extracted}")
                    break
        return callback
    parser.subscribe(addr, make_callback(addr, name))

print("Waiting for data... (Ctrl+C to stop)\n")
print("Status updates every 5 seconds:")
print("-" * 50)

try:
    last_status = time.time()
    while True:
        if parser.process_packet():
            packet_count += 1
            last_activity = time.time()

        # Print status every 5 seconds
        current_time = time.time()
        if current_time - last_status >= 5:
            time_since_activity = current_time - last_activity

            if packet_count == 0:
                status = "❌ NO DATA RECEIVED - Is DCS running?"
            elif time_since_activity < 5:
                status = f"✓ RECEIVING DATA ({packet_count} packets)"
            else:
                status = f"⚠ No data for {time_since_activity:.0f}s ({packet_count} packets total)"

            print(f"[{time.strftime('%H:%M:%S')}] {status}")
            last_status = current_time

        time.sleep(0.01)

except KeyboardInterrupt:
    print("\n\n=== Diagnostic Summary ===")
    print(f"Packets received: {packet_count}")

    if packet_count == 0:
        print("\n❌ PROBLEM: No DCS-BIOS data received")
        print("   Solutions:")
        print("   1. Make sure DCS World is running")
        print("   2. Make sure you're loaded into an aircraft cockpit")
        print("   3. Check that DCS-BIOS is installed and enabled")
        print("   4. Verify port 5010 multicast is not blocked by firewall")
    else:
        print("\n✓ DCS-BIOS is working correctly")
        print("   If LEDs still don't work, the issue is in the bridge code")
        print("   Try: ./winwing_bridge.py --aircraft FA18C")

    parser.disconnect()
