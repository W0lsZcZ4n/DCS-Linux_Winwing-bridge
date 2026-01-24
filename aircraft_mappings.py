"""
Aircraft-to-Hardware Mappings
Defines how DCS-BIOS data maps to WinWing device controls
"""
from dcsbios_parser import FA18CAddresses
from typing import Callable, Any


class MappingRule:
    """Represents a mapping from DCS-BIOS to hardware action"""

    def __init__(self, address_info, transform: Callable[[int], Any], action: Callable[[Any], None], description: str, debug: bool = False):
        """
        Args:
            address_info: DCSBIOSAddress object
            transform: Function to convert DCS value to hardware value
            action: Function to execute on hardware (e.g., led.set_led)
            description: Human-readable description
            debug: Enable debug logging for this rule
        """
        self.address_info = address_info
        self.transform = transform
        self.action = action
        self.description = description
        self.last_value = None
        self.debug = debug

    def process(self, raw_value: int):
        """Process a value change and execute action if needed"""
        # Apply mask and shift
        extracted = (raw_value & self.address_info.mask) >> self.address_info.shift

        # Transform value
        transformed = self.transform(extracted)

        # Only execute if value changed
        if transformed != self.last_value:
            if self.debug:
                print(f"[Mapping] {self.description}: {self.last_value} → {transformed}")
            self.last_value = transformed
            try:
                self.action(transformed)
            except Exception as e:
                print(f"[Mapping] Error in '{self.description}': {e}")


class FA18C_PTO2_Mapping:
    """F/A-18C Hornet mappings to PTO2 Panel"""

    def __init__(self, pto2_controller, device_manager=None):
        self.pto2 = pto2_controller
        self.device_manager = device_manager  # For controlling all devices
        self.rules = []
        self._build_mappings()

    @staticmethod
    def scale_brightness(dcs_value: int) -> int:
        """Scale DCS-BIOS brightness (0-65535) to LED brightness (0-255)"""
        return int((dcs_value / 65535.0) * 255)

    def _build_mappings(self):
        """Define all DCS-BIOS -> PTO2 mappings"""

        # === GEAR HANDLE LIGHT ===
        # Red light in gear handle (variable brightness 0-255)
        self.rules.append(MappingRule(
            FA18CAddresses.GEAR_HANDLE_LT,
            lambda v: 255 if v else 0,  # Full brightness when on, off when off
            lambda brightness: self.pto2.set_brightness(self.pto2.GEAR_HANDLE, brightness),
            "Gear Handle Light → GEAR_HANDLE LED"
        ))

        # === GEAR LIGHTS ===
        # These are direct light indicators from the cockpit gear panel
        self.rules.append(MappingRule(
            FA18CAddresses.GEAR_NOSE_LT,
            lambda v: bool(v),  # Light on = 1, off = 0
            lambda state: self.pto2.set_led(self.pto2.NOSE, state),
            "Nose Gear Light → NOSE LED"
        ))

        self.rules.append(MappingRule(
            FA18CAddresses.GEAR_LEFT_LT,
            lambda v: bool(v),
            lambda state: self.pto2.set_led(self.pto2.LEFT, state),
            "Left Gear Light → LEFT LED"
        ))

        self.rules.append(MappingRule(
            FA18CAddresses.GEAR_RIGHT_LT,
            lambda v: bool(v),
            lambda state: self.pto2.set_led(self.pto2.RIGHT, state),
            "Right Gear Light → RIGHT LED"
        ))

        # === FLAPS ===
        # Flaps light (yellow - indicates transit/in motion)
        self.rules.append(MappingRule(
            FA18CAddresses.FLAPS_LT,
            lambda v: bool(v),
            lambda state: self.pto2.set_led(self.pto2.FLAPS, state),
            "Flaps Transit Light → FLAPS LED"
        ))

        # Half flaps indicator
        self.rules.append(MappingRule(
            FA18CAddresses.HALF_FLAPS_LT,
            lambda v: bool(v),
            lambda state: self.pto2.set_led(self.pto2.HALF, state),
            "Half Flaps Light → HALF LED"
        ))

        # Full flaps indicator
        self.rules.append(MappingRule(
            FA18CAddresses.FULL_FLAPS_LT,
            lambda v: bool(v),
            lambda state: self.pto2.set_led(self.pto2.FULL, state),
            "Full Flaps Light → FULL LED"
        ))

        # === HOOK ===
        self.rules.append(MappingRule(
            FA18CAddresses.HOOK_LT,
            lambda v: bool(v),
            lambda state: self.pto2.set_led(self.pto2.HOOK, state),
            "Arresting Hook Light → HOOK LED"
        ))

        # === MASTER CAUTION ===
        self.rules.append(MappingRule(
            FA18CAddresses.MASTER_CAUTION_LT,
            lambda v: bool(v),
            lambda state: self.pto2.set_led(self.pto2.MASTER_CAUTION, state),
            "Master Caution → MASTER_CAUTION LED"
        ))

        # === BRIGHTNESS CONTROLS ===
        # Consoles dimmer -> All device backlights
        self.rules.append(MappingRule(
            FA18CAddresses.CONSOLES_DIMMER,
            self.scale_brightness,
            self._on_consoles_brightness_change,
            "Consoles Dimmer → All Backlights"
        ))

        # Warning/Caution dimmer -> Flag lights brightness
        self.rules.append(MappingRule(
            FA18CAddresses.WARN_CAUTION_DIMMER,
            self.scale_brightness,
            lambda brightness: self.pto2.set_brightness(self.pto2.FLAG_BRIGHTNESS, brightness),
            "Warn/Caution Dimmer → Flag Lights Brightness"
        ))

        # === STATION SELECT LIGHTS ===
        # These would map to stores management system
        # For now, we can leave them unmapped or add test patterns


        # CTR- Center jettison station button 
        self.rules.append(MappingRule(
            FA18CAddresses.STATION_CTR,
            lambda v: bool(v),
            lambda state: self.pto2.set_led(self.pto2.STATION_CTR, state),
            "CTR jettison station Light → CTR LED"
        ))

        # LI- Left inboard jettison station button 
        self.rules.append(MappingRule(
            FA18CAddresses.STATION_LI,
            lambda v: bool(v),
            lambda state: self.pto2.set_led(self.pto2.STATION_LI, state),
            "LI jettison station Light → LI LED"
        ))

        # RI- Right inboard jettison station button 
        self.rules.append(MappingRule(
            FA18CAddresses.STATION_RI,
            lambda v: bool(v),
            lambda state: self.pto2.set_led(self.pto2.STATION_RI, state),
            "RI jettison station Light → RI LED"
        ))
        
        # LO- Left outboard jettison station button
        self.rules.append(MappingRule(
            FA18CAddresses.STATION_LO,
            lambda v: bool(v),
            lambda state: self.pto2.set_led(self.pto2.STATION_LO, state),
            "LO jettison station Light → LO LED"
        ))

        # RO- Right outboard jettison station button 
        self.rules.append(MappingRule(
            FA18CAddresses.STATION_RO,
            lambda v: bool(v),
            lambda state: self.pto2.set_led(self.pto2.STATION_RO, state),
            "RO jettison station Light → RO LED"
        ))

        print(f"[FA18C->PTO2] Loaded {len(self.rules)} mapping rules")

    def _on_consoles_brightness_change(self, brightness: int):
        """Update all device backlights when consoles dimmer changes"""
        # PTO2 backlight
        self.pto2.set_brightness(self.pto2.BACKLIGHT, brightness)

        # Orion Throttle backlight (if available)
        if self.device_manager and self.device_manager.throttle.handle:
            self.device_manager.throttle.set_led(
                self.device_manager.throttle.BACKLIGHT,
                brightness
            )

        # Skywalker Rudder backlights (if available)
        # Note: Rudder controller not implemented yet in bridge
        # When implemented, uncomment:
        # if self.device_manager and self.device_manager.rudder.handle:
        #     for led_id in [0x00, 0x01, 0x03]:
        #         self.device_manager.rudder.set_brightness(led_id, brightness)

    def get_subscriptions(self):
        """
        Get all DCS-BIOS addresses this mapping needs to subscribe to

        Returns:
            List of (address, callback) tuples
        """
        subscriptions = []
        for rule in self.rules:
            addr = rule.address_info.address

            # Create callback that processes this rule
            def make_callback(r):
                return lambda value: r.process(value)

            subscriptions.append((addr, make_callback(rule)))

        return subscriptions


class FA18C_OrionThrottle_Mapping:
    """F/A-18C mappings to Orion Throttle LEDs"""

    def __init__(self, throttle_controller):
        self.throttle = throttle_controller
        self.rules = []
        self._build_mappings()

    def _build_mappings(self):
        """Define LED mappings"""

        # === LED MAPPINGS ===
        # Master Mode AA button (green LED)
        self.rules.append(MappingRule(
            FA18CAddresses.MASTER_MODE_AA,
            lambda v: bool(v),
            lambda state: self.throttle.set_led(self.throttle.AA_BUTTON, state),
            "Master Mode A/A → AA Button LED"
        ))

        # Master Mode AG button (green LED)
        self.rules.append(MappingRule(
            FA18CAddresses.MASTER_MODE_AG,
            lambda v: bool(v),
            lambda state: self.throttle.set_led(self.throttle.AG_BUTTON, state),
            "Master Mode A/G → AG Button LED"
        ))

        print(f"[FA18C->Orion] Loaded {len(self.rules)} LED mapping rules")

    def get_subscriptions(self):
        """Get DCS-BIOS address subscriptions"""
        subscriptions = []
        for rule in self.rules:
            addr = rule.address_info.address

            def make_callback(r):
                return lambda value: r.process(value)

            subscriptions.append((addr, make_callback(rule)))

        return subscriptions


class MappingManager:
    """Manages all aircraft mappings"""

    def __init__(self, device_manager):
        self.devices = device_manager
        self.active_mappings = []

    def load_fa18c(self):
        """Load F/A-18C Hornet mappings"""
        print("=== Loading F/A-18C Mappings ===")

        # PTO2 Panel LED Mappings
        if self.devices.pto2.handle:
            mapping = FA18C_PTO2_Mapping(self.devices.pto2, self.devices)
            self.active_mappings.append(mapping)

        # Orion Throttle LED Mappings
        if self.devices.throttle.handle:
            mapping = FA18C_OrionThrottle_Mapping(self.devices.throttle)
            self.active_mappings.append(mapping)

        print(f"Loaded {len(self.active_mappings)} mapping module(s)")

    def get_all_subscriptions(self):
        """Get all DCS-BIOS subscriptions from all active mappings"""
        all_subs = []
        for mapping in self.active_mappings:
            all_subs.extend(mapping.get_subscriptions())
        return all_subs
