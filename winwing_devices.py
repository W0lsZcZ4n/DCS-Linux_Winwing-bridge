"""
WinWing Device Controller
Handles HID communication with WinWing devices
"""
import os
import glob
import time
from dataclasses import dataclass
from typing import Optional


@dataclass
class WinWingDevice:
    """Represents a WinWing device configuration"""
    vendor_id: int
    product_id: int
    name: str
    hidraw_path: Optional[str] = None

    def __post_init__(self):
        """Find the hidraw device path"""
        if not self.hidraw_path:
            self.hidraw_path = self._find_hidraw()

    def _find_hidraw(self) -> Optional[str]:
        """Find hidraw device by vendor and product ID"""
        for hidraw in glob.glob('/dev/hidraw*'):
            try:
                # Get device info from sysfs
                device_num = hidraw.split('hidraw')[1]
                info_path = f'/sys/class/hidraw/hidraw{device_num}/device/uevent'

                if os.path.exists(info_path):
                    with open(info_path, 'r') as f:
                        uevent = f.read()

                    # Parse vendor and product IDs
                    if f'HID_ID=0003:0000{self.vendor_id:04X}:0000{self.product_id:04X}' in uevent:
                        return hidraw
            except Exception:
                continue
        return None


class PTO2Controller:
    """Controls WinWing PTO2 Panel LEDs"""

    VENDOR_ID = 0x4098
    PRODUCT_ID = 0xBF05
    PREFIX = [0x02, 0x05, 0xBF]

    # LED IDs
    BACKLIGHT = 0x00
    GEAR_HANDLE = 0x01
    SL_BRIGHTNESS = 0x02
    FLAG_BRIGHTNESS = 0x03

    MASTER_CAUTION = 0x04
    JETTISON = 0x05
    STATION_CTR = 0x06
    STATION_LI = 0x07
    STATION_LO = 0x08
    STATION_RO = 0x09
    STATION_RI = 0x0A

    FLAPS = 0x0B
    NOSE = 0x0C
    FULL = 0x0D
    RIGHT = 0x0E
    LEFT = 0x0F
    HALF = 0x10
    HOOK = 0x11

    def __init__(self):
        self.device = WinWingDevice(self.VENDOR_ID, self.PRODUCT_ID, "PTO2 Panel")
        self.handle = None
        self._led_state = {}  # Track LED states
        self._logged_disconnect = False  # Suppress repeated disconnect messages

    def connect(self) -> bool:
        """Open connection to device"""
        if not self.device.hidraw_path:
            return False

        try:
            self.handle = open(self.device.hidraw_path, 'wb', buffering=0)
            self._logged_disconnect = False
            print(f"[PTO2] Connected to {self.device.hidraw_path}")

            # Initialize with sensible defaults
            self.set_brightness(self.SL_BRIGHTNESS, 255)    # Station lights full (100%)
            self.set_brightness(self.FLAG_BRIGHTNESS, 255)  # Flag/warning lights full (100%)
            self.set_brightness(self.BACKLIGHT, 128)        # Backlight at 50%
            self.set_brightness(self.GEAR_HANDLE, 0)        # Gear handle off initially

            return True
        except Exception as e:
            print(f"[PTO2] Failed to open device: {e}")
            return False

    def disconnect(self):
        """Close device connection"""
        if self.handle:
            self.handle.close()
            self.handle = None
            print("[PTO2] Disconnected")

    def _reconnect(self) -> bool:
        """Try to re-find and reopen the device"""
        try:
            if self.handle:
                self.handle.close()
                self.handle = None
            self.device.hidraw_path = self.device._find_hidraw()
            if self.device.hidraw_path:
                self.handle = open(self.device.hidraw_path, 'wb', buffering=0)
                self._logged_disconnect = False
                print(f"[PTO2] Reconnected to {self.device.hidraw_path}")
                return True
        except Exception:
            pass
        self.handle = None
        return False

    def _send_command(self, led_id: int, value: int):
        """Send HID command to device, auto-reconnect on failure"""
        if not self.handle:
            return

        cmd = bytes(self.PREFIX + [0x00, 0x00, 0x03, 0x49, led_id, value, 0x00, 0x00, 0x00, 0x00, 0x00])
        try:
            self.handle.write(cmd)
            self.handle.flush()
        except Exception as e:
            if not self._logged_disconnect:
                print(f"[PTO2] Device disconnected: {e}")
                self._logged_disconnect = True
            if self._reconnect():
                try:
                    self.handle.write(cmd)
                    self.handle.flush()
                except Exception:
                    pass

    def set_led(self, led_id: int, state: bool):
        """Set LED on/off (for individual LEDs 0x04-0x11)"""
        value = 0x01 if state else 0x00
        self._send_command(led_id, value)
        self._led_state[led_id] = state

    def set_brightness(self, control_id: int, brightness: int):
        """Set brightness (for controls 0x00-0x03)"""
        brightness = max(0, min(255, brightness))
        self._send_command(control_id, brightness)
        self._led_state[control_id] = brightness

    def get_state(self, led_id: int):
        """Get cached LED state"""
        return self._led_state.get(led_id, False)


class OrionThrottleController:
    """Controls WinWing Orion 2 Throttle LEDs and Motor"""

    VENDOR_ID = 0x4098
    PRODUCT_ID = 0xBD64  # F15EX handles
    LED_PREFIX = [0x02, 0x60, 0xBE]
    MOTOR_PREFIX = [0x02, 0x01, 0xBF]

    # LED IDs
    BACKLIGHT = 0x00
    AA_BUTTON = 0x01
    AG_BUTTON = 0x02

    # Motor ID
    HAPTIC_MOTOR = 0x00

    def __init__(self):
        self.device = WinWingDevice(self.VENDOR_ID, self.PRODUCT_ID, "Orion Throttle")
        self.handle = None
        self._motor_active = False
        self._logged_disconnect = False

    def connect(self) -> bool:
        """Open connection to device"""
        if not self.device.hidraw_path:
            return False

        try:
            self.handle = open(self.device.hidraw_path, 'wb', buffering=0)
            self._logged_disconnect = False
            print(f"[Orion Throttle] Connected to {self.device.hidraw_path}")

            # Initialize defaults
            self.set_led(self.BACKLIGHT, 200)
            self.set_led(self.AA_BUTTON, False)
            self.set_led(self.AG_BUTTON, False)

            return True
        except Exception as e:
            print(f"[Orion Throttle] Failed to open: {e}")
            return False

    def disconnect(self):
        """Close device connection"""
        if self.handle:
            self.set_motor(0)   # Turn off motor
            self.handle.close()
            self.handle = None
            print("[Orion Throttle] Disconnected")

    def _reconnect(self) -> bool:
        """Try to re-find and reopen the device"""
        try:
            if self.handle:
                self.handle.close()
                self.handle = None
            self.device.hidraw_path = self.device._find_hidraw()
            if self.device.hidraw_path:
                self.handle = open(self.device.hidraw_path, 'wb', buffering=0)
                self._logged_disconnect = False
                print(f"[Orion Throttle] Reconnected to {self.device.hidraw_path}")
                return True
        except Exception:
            pass
        self.handle = None
        return False

    def _write_cmd(self, cmd: bytes, label: str):
        """Write command with auto-reconnect on failure"""
        if not self.handle:
            return False
        try:
            self.handle.write(cmd)
            self.handle.flush()
            return True
        except Exception as e:
            if not self._logged_disconnect:
                print(f"[Orion Throttle] Device disconnected: {e}")
                self._logged_disconnect = True
            if self._reconnect():
                try:
                    self.handle.write(cmd)
                    self.handle.flush()
                    return True
                except Exception:
                    pass
        return False

    def set_led(self, led_id: int, value):
        """Set LED (brightness 0-255 for backlight, bool for buttons)"""
        if not self.handle:
            return

        if isinstance(value, bool):
            value = 0x01 if value else 0x00
        else:
            value = max(0, min(255, value))

        cmd = bytes(self.LED_PREFIX + [0x00, 0x00, 0x03, 0x49, led_id, value, 0x00, 0x00, 0x00, 0x00, 0x00])
        self._write_cmd(cmd, "LED command")

    def set_motor(self, intensity: int):
        """Set haptic motor intensity (0-255)"""
        if not self.handle:
            return

        intensity = max(0, min(255, intensity))
        cmd = bytes(self.MOTOR_PREFIX + [0x00, 0x00, 0x03, 0x49, self.HAPTIC_MOTOR, intensity, 0x00, 0x00, 0x00, 0x00, 0x00])

        if self._write_cmd(cmd, "Motor command"):
            self._motor_active = (intensity > 0)

    def pulse_motor(self, intensity: int, duration_ms: int):
        """Pulse motor for a duration (requires timer in main loop)"""
        # This will need to be handled by the main bridge with timing
        self.set_motor(intensity)
        return duration_ms  # Return duration for caller to handle timing


class OrionJoystickController:
    """Controls WinWing Orion 2 Joystick Haptic Motor"""

    VENDOR_ID = 0x4098
    PRODUCT_ID = 0xBEA8  # F16 grip
    MOTOR_PREFIX = [0x02, 0x01, 0x00]

    HAPTIC_MOTOR = 0x00

    def __init__(self):
        self.device = WinWingDevice(self.VENDOR_ID, self.PRODUCT_ID, "Orion Joystick")
        self.handle = None
        self._logged_disconnect = False

    def connect(self) -> bool:
        """Open connection to device"""
        if not self.device.hidraw_path:
            return False

        try:
            self.handle = open(self.device.hidraw_path, 'wb', buffering=0)
            self._logged_disconnect = False
            print(f"[Orion Joystick] Connected to {self.device.hidraw_path}")
            return True
        except Exception as e:
            print(f"[Orion Joystick] Failed to open: {e}")
            return False

    def disconnect(self):
        """Close device connection"""
        if self.handle:
            self.set_motor(0)
            self.handle.close()
            self.handle = None
            print("[Orion Joystick] Disconnected")

    def _reconnect(self) -> bool:
        """Try to re-find and reopen the device"""
        try:
            if self.handle:
                self.handle.close()
                self.handle = None
            self.device.hidraw_path = self.device._find_hidraw()
            if self.device.hidraw_path:
                self.handle = open(self.device.hidraw_path, 'wb', buffering=0)
                self._logged_disconnect = False
                print(f"[Orion Joystick] Reconnected to {self.device.hidraw_path}")
                return True
        except Exception:
            pass
        self.handle = None
        return False

    def set_motor(self, intensity: int):
        """Set haptic motor intensity (0-255)"""
        if not self.handle:
            return

        intensity = max(0, min(255, intensity))
        cmd = bytes(self.MOTOR_PREFIX + [0x00, 0x00, 0x03, 0x49, self.HAPTIC_MOTOR, intensity, 0x00, 0x00, 0x00, 0x00, 0x00])

        try:
            self.handle.write(cmd)
            self.handle.flush()
        except Exception as e:
            if not self._logged_disconnect:
                print(f"[Orion Joystick] Device disconnected: {e}")
                self._logged_disconnect = True
            if self._reconnect():
                try:
                    self.handle.write(cmd)
                    self.handle.flush()
                except Exception:
                    pass


class DeviceManager:
    """Manages all WinWing devices"""

    def __init__(self):
        self.pto2 = PTO2Controller()
        self.throttle = OrionThrottleController()
        self.joystick = OrionJoystickController()
        self.devices = []

    def connect_all(self):
        """Connect to all available devices"""
        print("=== Connecting to WinWing Devices ===")

        if self.pto2.connect():
            self.devices.append(self.pto2)

        if self.throttle.connect():
            self.devices.append(self.throttle)

        if self.joystick.connect():
            self.devices.append(self.joystick)

        if not self.devices:
            return False

        print(f"Connected to {len(self.devices)} device(s)")
        return True

    def disconnect_all(self):
        """Disconnect all devices"""
        print("=== Disconnecting Devices ===")
        for device in self.devices:
            device.disconnect()
        self.devices.clear()
