"""
DCS-BIOS Protocol Parser
Handles UDP communication and binary protocol parsing
"""
import socket
import struct
from typing import Callable, Dict, Optional
from dataclasses import dataclass


@dataclass
class DCSBIOSAddress:
    """Represents a DCS-BIOS memory address subscription"""
    address: int
    mask: int
    shift: int
    max_value: int
    description: str


class DCSBIOSParser:
    """
    Parses DCS-BIOS UDP protocol

    Protocol format:
    - Sync bytes: 0x55 0x55
    - Address: 2 bytes (little-endian)
    - Count: 2 bytes (little-endian)
    - Data: variable bytes
    - Repeat...
    """

    SYNC_BYTE = 0x55
    BUFFER_SIZE = 65536

    # Special addresses for metadata
    METADATA_START_ADDR = 0xFFFE
    METADATA_END_ADDR = 0xFFFF

    def __init__(self, port: int = 5010, multicast_group: str = '239.255.50.10'):
        self.port = port
        self.multicast_group = multicast_group
        self.socket: Optional[socket.socket] = None
        self.subscriptions: Dict[int, list] = {}  # address -> [callbacks]
        self.state: Dict[int, int] = {}  # address -> current value
        self.receive_buffer = bytearray()
        self.write_buffer = bytearray()

        # Aircraft detection
        self.current_aircraft = None
        self.aircraft_change_callbacks = []
        self._metadata_buffer = bytearray()

    def connect(self) -> bool:
        """Open UDP socket for receiving DCS-BIOS multicast data"""
        try:
            import struct

            # Create UDP socket
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)

            # Allow multiple listeners on the same port
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Bind to the port (use INADDR_ANY to receive multicast)
            self.socket.bind(('', self.port))

            # Join multicast group
            mreq = struct.pack('4sL', socket.inet_aton(self.multicast_group), socket.INADDR_ANY)
            self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

            self.socket.settimeout(0.1)  # Non-blocking with timeout
            print(f"[DCS-BIOS] Listening on multicast {self.multicast_group}:{self.port}")
            return True
        except Exception as e:
            print(f"[DCS-BIOS] Failed to bind socket: {e}")
            return False

    def disconnect(self):
        """Close socket"""
        if self.socket:
            self.socket.close()
            self.socket = None
            print("[DCS-BIOS] Disconnected")

    def subscribe(self, address: int, callback: Callable[[int], None]):
        """
        Subscribe to updates at a specific address

        Args:
            address: Memory address to monitor
            callback: Function called with new value when address changes
        """
        if address not in self.subscriptions:
            self.subscriptions[address] = []
        self.subscriptions[address].append(callback)

    def subscribe_with_mask(self, address: int, mask: int, shift: int, callback: Callable[[int], None]):
        """
        Subscribe to a specific bit field within an address

        Args:
            address: Memory address
            mask: Bit mask to extract value
            shift: Number of bits to right-shift after masking
            callback: Function called with extracted value
        """
        def masked_callback(raw_value: int):
            extracted = (raw_value & mask) >> shift
            callback(extracted)

        self.subscribe(address, masked_callback)

    def on_aircraft_change(self, callback: Callable[[str], None]):
        """
        Register callback for aircraft changes

        Args:
            callback: Function called with aircraft name when it changes
        """
        self.aircraft_change_callbacks.append(callback)

    def process_packet(self):
        """
        Receive and process one UDP packet
        Returns True if packet was processed, False if no data available
        """
        if not self.socket:
            return False

        try:
            data, addr = self.socket.recvfrom(self.BUFFER_SIZE)
            self.receive_buffer.extend(data)
            self._parse_buffer()
            return True
        except socket.timeout:
            return False
        except Exception as e:
            print(f"[DCS-BIOS] Error receiving packet: {e}")
            return False

    def _parse_buffer(self):
        """
        Parse received data buffer for DCS-BIOS protocol

        Format: Each UDP packet contains:
        - 4 sync bytes (0x55 0x55 0x55 0x55)
        - Multiple frames: [address(2) count(2) data(count)]
        - NO sync bytes between frames within same packet
        """
        while len(self.receive_buffer) >= 8:
            # Look for sync bytes (FOUR 0x55 bytes) at start
            if (self.receive_buffer[0] == self.SYNC_BYTE and
                self.receive_buffer[1] == self.SYNC_BYTE and
                self.receive_buffer[2] == self.SYNC_BYTE and
                self.receive_buffer[3] == self.SYNC_BYTE):

                # Found sync - skip them and parse frames
                self.receive_buffer = self.receive_buffer[4:]
                continue

            # Parse a frame: address(2) + count(2) + data(count)
            if len(self.receive_buffer) < 4:
                break  # Need at least address + count

            address = struct.unpack('<H', self.receive_buffer[0:2])[0]
            count = struct.unpack('<H', self.receive_buffer[2:4])[0]

            # Check if we have enough data for this frame
            if len(self.receive_buffer) < 4 + count:
                break  # Wait for more data

            # Extract data bytes
            data = self.receive_buffer[4:4 + count]

            # Process the data
            self._process_data(address, data)

            # Remove processed frame from buffer
            self.receive_buffer = self.receive_buffer[4 + count:]

    def _process_data(self, address: int, data: bytearray):
        """Process data for a specific address"""
        # Handle metadata
        if address == self.METADATA_START_ADDR:
            # Start of metadata - clear buffer
            self._metadata_buffer.clear()
            return
        elif address == self.METADATA_END_ADDR:
            # End of metadata - process it
            self._process_metadata()
            return
        elif len(self._metadata_buffer) > 0 and len(self._metadata_buffer) < 1000:
            # Collecting metadata
            self._metadata_buffer.extend(data)
            return

        # Convert data to integers (2-byte values)
        for i in range(0, len(data), 2):
            if i + 1 >= len(data):
                break

            value = struct.unpack('<H', data[i:i+2])[0]
            current_address = address + i

            # Check if value changed
            old_value = self.state.get(current_address)
            if old_value != value:
                self.state[current_address] = value

                # Notify subscribers
                if current_address in self.subscriptions:
                    for callback in self.subscriptions[current_address]:
                        try:
                            callback(value)
                        except Exception as e:
                            print(f"[DCS-BIOS] Callback error at {current_address:04X}: {e}")

    def _process_metadata(self):
        """Process metadata to extract aircraft name"""
        try:
            # Metadata is null-terminated string
            metadata_str = self._metadata_buffer.decode('utf-8', errors='ignore').rstrip('\x00')

            # Extract aircraft name (format varies, but usually contains aircraft ID)
            # Common formats: "FA-18C_hornet", "F-16C_50", "A-10C", etc.
            if metadata_str and metadata_str != self.current_aircraft:
                old_aircraft = self.current_aircraft
                self.current_aircraft = metadata_str

                # Normalize aircraft name
                aircraft_normalized = self._normalize_aircraft_name(metadata_str)

                print(f"[DCS-BIOS] Aircraft detected: {aircraft_normalized}")

                # Notify callbacks
                for callback in self.aircraft_change_callbacks:
                    try:
                        callback(aircraft_normalized)
                    except Exception as e:
                        print(f"[DCS-BIOS] Aircraft change callback error: {e}")

        except Exception as e:
            print(f"[DCS-BIOS] Error processing metadata: {e}")
        finally:
            self._metadata_buffer.clear()

    def _normalize_aircraft_name(self, raw_name: str) -> str:
        """Normalize aircraft name to standard format"""
        # Map common DCS-BIOS names to our internal names
        name_upper = raw_name.upper()

        if 'FA-18C' in name_upper or 'F/A-18C' in name_upper or 'HORNET' in name_upper:
            return 'FA18C'
        elif 'F-16C' in name_upper or 'VIPER' in name_upper:
            return 'F16C'
        elif 'A-10C' in name_upper or 'WARTHOG' in name_upper:
            return 'A10C'
        elif 'F-15E' in name_upper or 'STRIKE EAGLE' in name_upper:
            return 'F15E'
        elif 'AH-64D' in name_upper or 'APACHE' in name_upper:
            return 'AH64D'
        else:
            # Return as-is if unknown
            return raw_name

    def get_value(self, address: int) -> Optional[int]:
        """Get current cached value at address"""
        return self.state.get(address)

    def run_loop(self, callback: Optional[Callable[[], None]] = None):
        """
        Run processing loop

        Args:
            callback: Optional function to call each iteration (for custom logic)
        """
        print("[DCS-BIOS] Starting receive loop (Ctrl+C to stop)")
        try:
            while True:
                self.process_packet()
                if callback:
                    callback()
        except KeyboardInterrupt:
            print("\n[DCS-BIOS] Stopped by user")


class FA18CAddresses:
    """
    F/A-18C Hornet DCS-BIOS address mappings

    Source: Extracted from FA-18C_hornet.json in DCS-BIOS doc/json folder
    All addresses verified against installed DCS-BIOS version
    """

    # Master Caution Panel (address 29704 = 0x7408)
    MASTER_CAUTION_LT = DCSBIOSAddress(0x7408, 0x0200, 9, 1, "Master Caution Light")

    # Landing Gear Lights (all at address 29744 = 0x7430)
    GEAR_NOSE_LT = DCSBIOSAddress(0x7430, 0x0800, 11, 1, "Nose Gear Light")
    GEAR_LEFT_LT = DCSBIOSAddress(0x7430, 0x1000, 12, 1, "Left Gear Light")
    GEAR_RIGHT_LT = DCSBIOSAddress(0x7430, 0x2000, 13, 1, "Right Gear Light")

    # Landing Gear Handle Light (address 29822 = 0x747E)
    GEAR_HANDLE_LT = DCSBIOSAddress(0x747E, 0x0800, 11, 1, "Landing Gear Handle Light")

    # Flaps Lights (address 29798 = 0x7466 for yellow, 29744 = 0x7430 for green half/full)
    FLAPS_LT = DCSBIOSAddress(0x7466, 0x0001, 0, 1, "Flaps Transit Light (Yellow)")
    HALF_FLAPS_LT = DCSBIOSAddress(0x7430, 0x4000, 14, 1, "Half Flaps Light (Green)")
    FULL_FLAPS_LT = DCSBIOSAddress(0x7430, 0x8000, 15, 1, "Full Flaps Light (Green)")

    # Hook Light (address 29856 = 0x74A0)
    HOOK_LT = DCSBIOSAddress(0x74A0, 0x0400, 10, 1, "Arresting Hook Light")

    # Brightness Controls (address 30020 = 0x7544, address 30028 = 0x754C)
    CONSOLES_DIMMER = DCSBIOSAddress(0x7544, 0xFFFF, 0, 65535, "Consoles Brightness")
    WARN_CAUTION_DIMMER = DCSBIOSAddress(0x754C, 0xFFFF, 0, 65535, "Warning/Caution Brightness")

    # Station Jettison Select Button Lights (addresses 29742 = 0x742E, 29744 = 0x7430)
    STATION_CTR = DCSBIOSAddress(0x742E, 0x4000, 14, 1, "CTR Jettison Station Light")
    STATION_LI = DCSBIOSAddress(0x742E, 0x8000, 15, 1, "LI Jettison Station Light")
    STATION_LO = DCSBIOSAddress(0x7430, 0x0100, 8, 1, "LO Jettison Station Light")
    STATION_RI = DCSBIOSAddress(0x7430, 0x0200, 9, 1, "RI Jettison Station Light")
    STATION_RO = DCSBIOSAddress(0x7430, 0x0400, 10, 1, "RO Jettison Station Light")

    # Master Mode Buttons (address 29708 = 0x740C)
    MASTER_MODE_AA = DCSBIOSAddress(0x740C, 0x0200, 9, 1, "Master Mode A/A Light")
    MASTER_MODE_AG = DCSBIOSAddress(0x740C, 0x0400, 10, 1, "Master Mode A/G Light")


# Test mode
if __name__ == "__main__":
    parser = DCSBIOSParser()

    def on_master_caution(value: int):
        state = "ON" if value else "OFF"
        print(f"Master Caution: {state}")

    def on_gear_nose(value: int):
        pct = (value / 65535) * 100
        print(f"Nose Gear: {pct:.1f}%")

    if parser.connect():
        # Subscribe to some test addresses
        parser.subscribe_with_mask(
            FA18CAddresses.MASTER_CAUTION_LT.address,
            FA18CAddresses.MASTER_CAUTION_LT.mask,
            FA18CAddresses.MASTER_CAUTION_LT.shift,
            on_master_caution
        )

        parser.subscribe(
            FA18CAddresses.GEAR_NOSE_POS.address,
            on_gear_nose
        )

        print("Listening for DCS-BIOS data...")
        print("Start DCS and load into an F/A-18C cockpit")
        parser.run_loop()
        parser.disconnect()
