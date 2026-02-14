#!/usr/bin/env python3
"""
Aircraft Mappings for DCS Native Telemetry

Maps telemetry data paths to WinWing hardware outputs (LEDs and motors)
Replaces aircraft_mappings.py for telemetry-based approach
"""

from typing import Callable, Any


class TelemetryMappingRule:
    """
    Maps a telemetry data path to a hardware action

    Maps a telemetry data path to a hardware action (LED, motor, etc.)
    """

    def __init__(self, data_path: str, transform: Callable, action: Callable, description: str = ""):
        self.data_path = data_path  # e.g., "leds.MASTER_CAUTION"
        self.transform = transform  # Transform value (e.g., bool conversion)
        self.action = action  # Hardware action (e.g., set_led)
        self.description = description

    def __repr__(self):
        return f"TelemetryMappingRule({self.data_path} -> {self.description})"


# ============================================================================
# F/A-18C Mappings
# ============================================================================

class OrionThrottle_TelemetryMapping:
    """
    WinWing Orion 2 Throttle LED mappings
    Universal — LED key names match Export.lua's combined argument table
    """

    def __init__(self, throttle_controller):
        self.throttle = throttle_controller
        self.rules = []
        self._build_mappings()

    def _build_mappings(self):
        """Create all telemetry → throttle mappings"""

        # ====================================================================
        # Master Mode Button LEDs (A/A, A/G)
        # ====================================================================

        self.rules.append(TelemetryMappingRule(
            "leds.MASTER_MODE_AA",
            lambda v: bool(v),
            lambda state: self.throttle.set_led(self.throttle.AA_BUTTON, state),
            "Master Mode A/A LED"
        ))

        self.rules.append(TelemetryMappingRule(
            "leds.MASTER_MODE_AG",
            lambda v: bool(v),
            lambda state: self.throttle.set_led(self.throttle.AG_BUTTON, state),
            "Master Mode A/G LED"
        ))

        # Console Backlight (brightness control, 0.0-1.0 from DCS)
        # Minimum 13 (~5%) — throttle LEDs need higher minimum than PTO2 to be visible
        self.rules.append(TelemetryMappingRule(
            "leds.CONSOLES_BRIGHTNESS",
            lambda v: max(13, int(float(v) * 255)) if v is not None else 13,
            lambda brightness: self.throttle.set_led(self.throttle.BACKLIGHT, brightness),
            "Console Backlight Dimmer"
        ))


class OrionPTO2_TelemetryMapping:
    """
    WinWing Orion 2 PTO2 Panel LED mappings
    Universal — LED key names match Export.lua's combined argument table
    """

    def __init__(self, pto2_controller):
        self.pto2 = pto2_controller
        self.rules = []
        self._build_mappings()

    def _build_mappings(self):
        """Create all telemetry → PTO2 mappings"""

        # ====================================================================
        # Top Row LEDs (Gear, Flaps, Hook)
        # ====================================================================

        # Landing Gear Lights
        self.rules.append(TelemetryMappingRule(
            "leds.NOSE_GEAR",
            lambda v: bool(v),
            lambda state: self.pto2.set_led(self.pto2.NOSE, state),
            "Nose Gear (green)"
        ))

        self.rules.append(TelemetryMappingRule(
            "leds.LEFT_GEAR",
            lambda v: bool(v),
            lambda state: self.pto2.set_led(self.pto2.LEFT, state),
            "Left Gear (green)"
        ))

        self.rules.append(TelemetryMappingRule(
            "leds.RIGHT_GEAR",
            lambda v: bool(v),
            lambda state: self.pto2.set_led(self.pto2.RIGHT, state),
            "Right Gear (green)"
        ))

        # Flaps Lights
        self.rules.append(TelemetryMappingRule(
            "leds.HALF_FLAPS",
            lambda v: bool(v),
            lambda state: self.pto2.set_led(self.pto2.HALF, state),
            "Half Flaps (green)"
        ))

        self.rules.append(TelemetryMappingRule(
            "leds.FULL_FLAPS",
            lambda v: bool(v),
            lambda state: self.pto2.set_led(self.pto2.FULL, state),
            "Full Flaps (green)"
        ))

        self.rules.append(TelemetryMappingRule(
            "leds.FLAPS_YELLOW",
            lambda v: bool(v),
            lambda state: self.pto2.set_led(self.pto2.FLAPS, state),
            "Flaps Transit (yellow)"
        ))

        # Hook
        self.rules.append(TelemetryMappingRule(
            "leds.HOOK",
            lambda v: bool(v),
            lambda state: self.pto2.set_led(self.pto2.HOOK, state),
            "Hook Down (orange)"
        ))

        # Gear Handle LED (brightness control, not on/off)
        self.rules.append(TelemetryMappingRule(
            "leds.GEAR_HANDLE",
            lambda v: bool(v),
            lambda state: self.pto2.set_brightness(self.pto2.GEAR_HANDLE, 255 if state else 0),
            "Gear Handle LED (red)"
        ))

        # Console Backlight (brightness control, 0.0-1.0 from DCS)
        # Minimum 3 (~1%) so backlight never fully turns off — QOL feature
        self.rules.append(TelemetryMappingRule(
            "leds.CONSOLES_BRIGHTNESS",
            lambda v: max(3, int(float(v) * 255)) if v is not None else 3,
            lambda brightness: self.pto2.set_brightness(self.pto2.BACKLIGHT, brightness),
            "Console Backlight Dimmer"
        ))

        # ====================================================================
        # Middle Row LEDs (Station Jettison)
        # ====================================================================

        self.rules.append(TelemetryMappingRule(
            "leds.STATION_LO",
            lambda v: bool(v),
            lambda state: self.pto2.set_led(self.pto2.STATION_LO, state),
            "Station L/O (green)"
        ))

        self.rules.append(TelemetryMappingRule(
            "leds.STATION_LI",
            lambda v: bool(v),
            lambda state: self.pto2.set_led(self.pto2.STATION_LI, state),
            "Station L/I (green)"
        ))

        self.rules.append(TelemetryMappingRule(
            "leds.STATION_CTR",
            lambda v: bool(v),
            lambda state: self.pto2.set_led(self.pto2.STATION_CTR, state),
            "Station CTR (green)"
        ))

        self.rules.append(TelemetryMappingRule(
            "leds.STATION_RI",
            lambda v: bool(v),
            lambda state: self.pto2.set_led(self.pto2.STATION_RI, state),
            "Station R/I (green)"
        ))

        self.rules.append(TelemetryMappingRule(
            "leds.STATION_RO",
            lambda v: bool(v),
            lambda state: self.pto2.set_led(self.pto2.STATION_RO, state),
            "Station R/O (green)"
        ))

        # ====================================================================
        # Bottom Row LED (Master Caution)
        # ====================================================================

        self.rules.append(TelemetryMappingRule(
            "leds.MASTER_CAUTION",
            lambda v: bool(v),
            lambda state: self.pto2.set_led(self.pto2.MASTER_CAUTION, state),
            "Master Caution (yellow)"
        ))


# ============================================================================
# F/A-18C Weapon Weight Table (CLSID → weight in kg)
# Source: https://github.com/pydcs/dcs/blob/master/dcs/weapons_data.py
# Some CLSIDs are pydcs shorthand — verify in-game with debug logging
# and add missing/corrected entries as needed.
# ============================================================================

FA18C_WEAPON_WEIGHTS = {
    # Air-to-Air Missiles
    "{6CEB49FC-DED8-4DED-B053-E1F033FF72D3}": 86,    # AIM-9M
    "{5CE2FF2A-645A-4197-B48D-8720AC69394F}": 84,     # AIM-9X
    "{8D399DDA-FF81-4F14-904D-099B34FE7918}": 231,    # AIM-7M
    "{AIM-7F}": 231,                                    # AIM-7F
    "{AIM-7H}": 231,                                    # AIM-7MH
    "{C8E06185-7CD6-4C90-959F-044679E90751}": 158,    # AIM-120B
    "{40EF17B7-F508-45de-8566-6FFECC0C1AB8}": 161,    # AIM-120C

    # Air-to-Ground Missiles
    "{F16A4DE0-116C-4A71-97F0-2CF85B0313EF}": 286,    # AGM-65E Maverick
    "{B06DD79A-F21E-4EB9-BD9D-AB3844618C9C}": 361,    # AGM-88C HARM
    "{AGM_84D}": 540,                                   # AGM-84D Harpoon
    "{AGM_84H}": 675,                                   # AGM-84H SLAM-ER
    "{AGM-154A}": 485,                                  # AGM-154A JSOW
    "{9BCC2A2B-5708-4860-B1F1-053A18442067}": 484,    # AGM-154C JSOW

    # Bombs
    "{BCE4E030-38E9-423E-98ED-24BE3DA87C32}": 232,    # Mk-82
    "{Mk-83}": 454,                                     # Mk-83
    "{AB8B8299-F1CC-4571-9571-6C22BCA83BFF}": 894,    # Mk-84
    "{51F9AAE5-964F-4D21-83FB-502E3BFE5F8A}": 1162,   # GBU-10
    "{DB769D48-67D7-42ED-A2BE-108D566C8B1E}": 275,    # GBU-12
    "{0D33DDAE-524F-4A4E-B5B8-621754FE3ADE}": 564,    # GBU-16
    "{GBU-31}": 934,                                    # GBU-31 JDAM
    "{GBU-31V3B}": 934,                                 # GBU-31(V)3/B JDAM
    "{GBU-38}": 253,                                    # GBU-38 JDAM
    "{CBU-87}": 430,                                    # CBU-87
    "{5335D97A-35A5-4643-9D9B-026C75961E52}": 417,    # CBU-97
    "{CBU_99}": 222,                                    # CBU-99

    # External Fuel Tanks (empty weight — fuel state unknown at jettison)
    "{FPU_8A_FUEL_TANK}": 520,                          # FPU-8A 330 gal (F/A-18C)
    "{E8D4652F-FD48-45B7-BA5B-2AE05BB5A9CF}": 525,    # PTB-800 (Su-25)
    # F-16C 370 gal: TODO — verify CLSID in-game
    # F-15C tanks: TODO — verify CLSIDs in-game
}


def weapon_weight_to_intensity(weight_kg: float) -> int:
    """
    Map weapon weight to haptic motor intensity.

    Tiers:
        Light    (< 150 kg):  160  — AIM-9, rockets
        Medium   (150-400 kg): 210 — AIM-120, AIM-7, Mk-82, GBU-12, AGM-88
        Heavy    (400-700 kg): 240 — Mk-83, AGM-154, GBU-16, Harpoon, fuel tanks
        Very Heavy (> 700 kg): 255 — Mk-84, GBU-10, GBU-31, SLAM-ER
    """
    if weight_kg < 150:
        return 160
    elif weight_kg < 400:
        return 210
    elif weight_kg < 700:
        return 240
    else:
        return 255


WEAPON_RELEASE_INTENSITY_UNKNOWN = 220  # Fallback for unrecognized CLSIDs


class FA18C_HapticFeedback_TelemetryMapping:
    """
    F/A-18C Haptic Feedback Effects
    Using DCS native telemetry for accurate haptics

    Implemented & Working:
    - Gun fire: 100% accurate via ammo tracking ✅
    - Weapon release: Detects bomb/missile drops via station count decrease ✅
      - Polled every frame in update() loop (not subscription-based)
      - Monitors all weapon stations simultaneously
      - 150ms pulse when weapon is released
      - Intensity: 180 (can be scaled by weapon weight in future)
    - Ground wobble: Acceleration-based (G-force), works on runways AND carriers ✅
      - Uses landing gear strut compression for WOW detection
      - 0.05G threshold, scales to 0.8G
      - Handles acceleration, braking, catapult launch, arrested landing
    - Gear clunks: Via gear lock state transitions ✅
    - Gear transit vibration: Continuous hum while gear extending/retracting ✅
      - Uses universal LoGetMechInfo gear.value (0.0-1.0)
      - Active when 0.01 < gear_pos < 0.99
      - Subtle intensity (65) simulating hydraulic pump

    - AOA buffeting: Joystick-only stick shaker, onset 15° scaling to 35° ✅
      - Intensity 45→255 across AOA range
      - Both joystick and throttle (whole airframe shaking)

    - Landing impact: Strut compression state tracking ✅
      - Detects airborne→compressed transition (rod < 0.05 → rod > 0.3)
      - Full 255 impulse on every touchdown
      - Only tracked when gear is down (gear_pos > 0.99)
    """

    def __init__(self, throttle_controller, joystick_controller, parser=None, debug: bool = False):
        self.throttle = throttle_controller
        self.joystick = joystick_controller
        self.parser = parser  # For accessing full packet in weapon release detection
        self.debug = debug
        self.rules = []

        # Motor intensity tuning
        # Both motors get same base intensity, but joystick can be boosted if too weak
        self.JOYSTICK_MULTIPLIER = 1.4  # Joystick motor is weaker than throttle, compensate

        # State tracking
        self.last_cannon_ammo = None
        self.was_airborne = False
        self.last_gear_locked = False
        self.gun_fire_active = False
        self.gun_fire_time = 0

        # Touchdown tracking
        self.touchdown_active = False
        self.touchdown_time = 0

        # Gear clunk tracking
        self.gear_clunk_active = False
        self.gear_clunk_time = 0

        # AOA buffeting tracking
        self._aoa_active = False
        self._aoa_intensity = 0

        # Landing roll tracking (acceleration-based for carrier compatibility)
        self.landing_roll_active = False
        self.last_g_x = 0.0  # Forward/backward acceleration in Gs
        self.last_wow_left = False
        self.last_wow_right = False

        # Gear transit tracking
        self.gear_transit_active = False
        self.gear_pos = 1.0            # default: gear down
        self.last_gear_pos = 1.0

        # Landing impact tracking (strut compression gradient)
        self.landing_impact_active = False
        self.landing_impact_time = 0
        self.landing_impact_intensity = 0
        self._rod_airborne = True   # Were struts unloaded (airborne)?

        # Weapon release tracking
        self.weapon_release_active = False
        self.weapon_release_time = 0
        self.weapon_release_intensity = 0
        self.last_station_counts = {}  # Track counts for all stations
        self.last_station_clsids = {}  # Track CLSIDs for weight-based intensity

        self._build_mappings()

    def _build_mappings(self):
        """Create telemetry → haptic mappings"""

        # Gun fire detection (via ammo change)
        self.rules.append(TelemetryMappingRule(
            "payload.cannon_ammo",
            lambda v: int(v) if v is not None else 0,
            self._on_cannon_ammo_change,
            "Gun Fire → Haptic Vibration"
        ))

        # Weight-on-wheels for touchdown and landing roll
        self.rules.append(TelemetryMappingRule(
            "leds.WOW_NOSE",
            lambda v: bool(v),
            lambda v: self._on_wow_change('nose', v),
            "Nose WOW → Haptic Pulse"
        ))
        self.rules.append(TelemetryMappingRule(
            "leds.WOW_LEFT",
            lambda v: bool(v),
            lambda v: self._on_wow_change('left', v),
            "Left WOW → Landing Roll"
        ))
        self.rules.append(TelemetryMappingRule(
            "leds.WOW_RIGHT",
            lambda v: bool(v),
            lambda v: self._on_wow_change('right', v),
            "Right WOW → Landing Roll"
        ))

        # Forward acceleration for landing roll wobble (works on runways AND carriers!)
        self.rules.append(TelemetryMappingRule(
            "flight.g_x",
            lambda v: float(v) if v is not None else 0.0,
            self._on_acceleration_change,
            "G-Force → Landing Roll Wobble"
        ))

        # Gear lock clunks (detect when gear finishes moving and locks)
        # Gear light ON = transit, OFF = locked
        self.rules.append(TelemetryMappingRule(
            "leds.NOSE_GEAR",
            lambda v: bool(v),
            self._on_gear_light_change,
            "Gear Lock → Haptic Clunk"
        ))

        # Gear transit haptic (universal — uses LoGetMechInfo gear.value)
        self.rules.append(TelemetryMappingRule(
            "leds.GEAR_POS",
            lambda v: float(v) if v is not None else 1.0,
            self._on_gear_pos_change,
            "Gear Transit → Haptic Vibration"
        ))

        # Landing impact detection (strut compression gradient — only tracked when gear is down)
        self.rules.append(TelemetryMappingRule(
            "leds.ROD_LEFT",
            lambda v: float(v) if v is not None else 0.0,
            self._on_rod_change_left,
            "Left Strut → Landing Impact"
        ))
        self.rules.append(TelemetryMappingRule(
            "leds.ROD_RIGHT",
            lambda v: float(v) if v is not None else 0.0,
            self._on_rod_change_right,
            "Right Strut → Landing Impact"
        ))

        # Note: Weapon release detection is handled in update() loop, not via subscription
        # (station counts change independently, not via a single subscription path)

        # AOA buffeting — joystick only (stick shaker feel)
        # Onset ~15°, scales up to ~35° (based on F/A-18C pilot reports)
        self.rules.append(TelemetryMappingRule(
            "flight.aoa",
            lambda v: float(v) if v is not None else 0.0,
            self._on_aoa_change,
            "High AOA → Stick Buffet"
        ))

    def _on_cannon_ammo_change(self, ammo: int):
        """Detect gun fire from ammo decrease - 100% accurate!"""
        import time

        if self.last_cannon_ammo is not None and ammo < self.last_cannon_ammo:
            # Gun is firing!
            self.gun_fire_active = True
            self.gun_fire_time = time.time()
        else:
            self.gun_fire_active = False

        self.last_cannon_ammo = ammo

    def update(self):
        """Called every frame to handle time-based effects and update motors"""
        import time

        now = time.time()
        throttle_intensity = 0
        joystick_intensity = 0

        # --- Poll for weapon releases (not subscription-based) ---
        self._check_weapon_release()

        # --- Check watchdogs and deactivate expired one-shot effects ---
        if self.gun_fire_active and now - self.gun_fire_time > 0.1:
            self.gun_fire_active = False

        if self.weapon_release_active and now - self.weapon_release_time > 0.10:
            self.weapon_release_active = False

        if self.landing_impact_active and now - self.landing_impact_time > 0.15:
            self.landing_impact_active = False

        if self.gear_clunk_active and now - self.gear_clunk_time > 0.1:
            self.gear_clunk_active = False

        # --- Calculate intensity for each active effect ---

        # AOA Buffeting (stick shaker + throttle)
        if self._aoa_active:
            throttle_intensity = max(throttle_intensity, self._aoa_intensity)
            joystick_intensity = max(joystick_intensity, self._aoa_intensity)

        # Gun Fire
        if self.gun_fire_active:
            throttle_intensity = max(throttle_intensity, 255)
            joystick_intensity = max(joystick_intensity, 255)

        # Weapon Release (bomb/missile drop)
        if self.weapon_release_active:
            throttle_intensity = max(throttle_intensity, self.weapon_release_intensity)
            joystick_intensity = max(joystick_intensity, self.weapon_release_intensity)

        # Landing Impact (strut compression spike)
        if self.landing_impact_active:
            throttle_intensity = max(throttle_intensity, self.landing_impact_intensity)
            joystick_intensity = max(joystick_intensity, self.landing_impact_intensity)

        # Gear Clunk
        if self.gear_clunk_active:
            throttle_intensity = max(throttle_intensity, 150)
            joystick_intensity = max(joystick_intensity, 150)

        # Gear Transit Vibration (hydraulic pump hum while gear is moving)
        if self.gear_transit_active:
            transit_intensity = 65  # Subtle hum
            throttle_intensity = max(throttle_intensity, transit_intensity)
            joystick_intensity = max(joystick_intensity, transit_intensity)

        # Landing Roll Wobble (acceleration-based - works on runways AND carriers!)
        # Active when: main wheels on ground AND accelerating/braking
        # Intensity: scales with G-force magnitude (absolute value for both accel and decel)
        if (self.last_wow_left or self.last_wow_right):
            g_forward = abs(self.last_g_x)  # abs() handles both positive (accel) and negative (braking) G

            # Threshold: only wobble if accelerating/braking > 0.05 G
            # (filters noise while still feeling taxi acceleration)
            if g_forward > 0.05:
                self.landing_roll_active = True

                # Scale from 0.05G (gentle taxi accel) to 0.8G (hard braking/accel) → 0-255 intensity
                # Cap at 0.8G (typical cat launch ~2-3G, but we want wobble before that)
                g_clamped = min(g_forward, 0.8)
                g_range = 0.75  # 0.8 - 0.05
                g_in_range = g_clamped - 0.05
                intensity_fraction = g_in_range / g_range

                # Scale from 45 to 255 (minimum 45 for noticeable wobble)
                roll_intensity = round(45 + (intensity_fraction * 210.0))

                throttle_intensity = max(throttle_intensity, roll_intensity)
                joystick_intensity = max(joystick_intensity, roll_intensity)

                if self.debug and now - getattr(self, '_last_wobble_debug', 0) > 2.0:
                    print(f"[DEBUG WOBBLE] G: {g_forward:.2f} | Intensity: {roll_intensity}")
                    self._last_wobble_debug = now
            else:
                self.landing_roll_active = False
        else:
            self.landing_roll_active = False

        # --- Set final motor values ---
        # Both motors get same base intensity, but joystick can be boosted with multiplier
        self.throttle.set_motor(throttle_intensity)

        # Apply joystick multiplier (increase if motor feels too weak)
        joystick_boosted = min(255, int(joystick_intensity * self.JOYSTICK_MULTIPLIER))
        self.joystick.set_motor(joystick_boosted)

    def _on_wow_change(self, gear: str, state: bool):
        """Detect touchdown from WOW state change"""
        import time
        
        # Update state for the specific gear
        if gear == 'left':
            self.last_wow_left = state
        elif gear == 'right':
            self.last_wow_right = state
        
        # Check for touchdown event (transition from airborne to ground)
        on_ground = self.last_wow_left or self.last_wow_right
        
        if on_ground and self.was_airborne:
            # Touchdown detected!
            self.touchdown_intensity = 180  # Fixed intensity for now
            self.touchdown_active = True
            self.touchdown_time = time.time()
        
        self.was_airborne = not on_ground


    def _on_acceleration_change(self, g_x: float):
        """Handle changes in forward/backward acceleration (for landing roll wobble)"""
        self.last_g_x = g_x

    def _on_gear_light_change(self, gear_light: bool):
        """Detect gear lock from light OFF (locked position)"""
        import time

        # Gear lights ON = transit
        # Gear lights OFF = locked
        # Clunk when transition from ON→OFF (gear just locked)
        locked = not gear_light

        if locked and not self.last_gear_locked and not self.gear_clunk_active:
            # Gear just locked - brief clunk
            self.gear_clunk_active = True
            self.gear_clunk_time = time.time()

        self.last_gear_locked = locked

    def _on_rod_change_left(self, rod: float):
        """Track strut compression for landing impact (left main gear)"""
        if self.gear_pos > 0.99:  # Only track when gear is down
            self._track_impact(rod)

    def _on_rod_change_right(self, rod: float):
        """Track strut compression for landing impact (right main gear)"""
        if self.gear_pos > 0.99:  # Only track when gear is down
            self._track_impact(rod)

    def _track_impact(self, rod: float):
        """
        Detect landing impact — full 255 impulse on touchdown.
        Tracks airborne→compressed transition (rod < 0.05 → rod > 0.3).
        """
        import time
        if rod < 0.05:
            # Strut unloaded — airborne
            self._rod_airborne = True
        elif self._rod_airborne and rod > 0.3:
            # Touchdown — full impulse
            self.landing_impact_intensity = 255
            self.landing_impact_active = True
            self.landing_impact_time = time.time()
            self._rod_airborne = False  # One trigger per landing
            if self.debug:
                print(f"[DEBUG IMPACT] Touchdown! rod={rod:.2f}")

    def _on_gear_pos_change(self, pos: float):
        """Detect gear transit from continuous position value"""
        self.last_gear_pos = self.gear_pos
        self.gear_pos = pos
        # In transit = value not at either extreme
        self.gear_transit_active = (0.01 < pos < 0.99)

    def _on_aoa_change(self, aoa: float):
        """AOA buffeting on joystick + throttle (stick shaker)"""
        # F/A-18C buffet onset ~15° AOA, scales up to ~35°
        AOA_ONSET = 15.0
        AOA_MAX = 35.0
        on_ground = self.last_wow_left or self.last_wow_right
        if aoa > AOA_ONSET and not on_ground:
            # Scale 15°→35° to intensity 45→255
            aoa_clamped = min(aoa, AOA_MAX)
            fraction = (aoa_clamped - AOA_ONSET) / (AOA_MAX - AOA_ONSET)
            self._aoa_intensity = round(45 + (fraction * 210))
            self._aoa_active = True
            if self.debug:
                import time
                if time.time() - getattr(self, '_last_aoa_debug', 0) > 2.0:
                    print(f"[DEBUG AOA] {aoa:.1f}° | Intensity: {self._aoa_intensity}")
                    self._last_aoa_debug = time.time()
        else:
            self._aoa_active = False
            self._aoa_intensity = 0

    def _check_weapon_release(self):
        """
        Check all weapon stations for releases
        Called from update() loop to poll for weapon count changes

        Handles two cases:
        1. Station count decreases (e.g., rack drops one bomb)
        2. Station disappears entirely from payload (DCS removes station after launch)
        """
        import time

        # Get current packet to access all station counts
        if not self.parser or not hasattr(self.parser, 'last_packet'):
            return

        packet = self.parser.last_packet
        if not packet or 'payload' not in packet:
            return

        payload = packet['payload']

        # Build current station counts and CLSIDs from this packet
        current_stations = {}
        current_clsids = {}
        for key, value in payload.items():
            if key.endswith('_count'):
                current_stations[key] = value
            elif key.endswith('_clsid'):
                current_clsids[key] = value

        # Skip weapon release detection while on the ground (rearm/loadout changes)
        on_ground = self.last_wow_left or self.last_wow_right
        if on_ground:
            # Still track so we have correct baseline when airborne
            self.last_station_counts = current_stations
            self.last_station_clsids = current_clsids
            return

        # Check for releases: count decreased OR station disappeared
        for station_id, last_count in self.last_station_counts.items():
            current_count = current_stations.get(station_id, 0)

            if last_count > 0 and current_count < last_count:
                # Weapon released! Look up CLSID from last known state
                clsid_key = station_id.replace('_count', '_clsid')
                clsid = self.last_station_clsids.get(clsid_key, "")
                weight = FA18C_WEAPON_WEIGHTS.get(clsid)

                if weight is not None:
                    self.weapon_release_intensity = weapon_weight_to_intensity(weight)
                else:
                    self.weapon_release_intensity = WEAPON_RELEASE_INTENSITY_UNKNOWN

                self.weapon_release_active = True
                self.weapon_release_time = time.time()

                if self.debug:
                    station_num = station_id.replace('station_', '').replace('_count', '')
                    weight_str = f"{weight} kg" if weight else "unknown"
                    if station_id not in current_stations:
                        print(f"[DEBUG WEAPON] Station {station_num}: {last_count} → removed | "
                              f"CLSID: {clsid or 'N/A'} ({weight_str}) | Intensity: {self.weapon_release_intensity}")
                    else:
                        print(f"[DEBUG WEAPON] Station {station_num}: {last_count} → {current_count} | "
                              f"CLSID: {clsid or 'N/A'} ({weight_str}) | Intensity: {self.weapon_release_intensity}")
                break  # Only trigger once per update

        # Update tracking with current state
        self.last_station_counts = current_stations
        self.last_station_clsids = current_clsids


# ============================================================================
# Mapping Manager
# ============================================================================

class TelemetryMappingManager:
    """
    Manages telemetry subscriptions and routing to hardware

    Routes telemetry data to hardware outputs
    """

    def __init__(self, parser, debug: bool = False):
        self.parser = parser
        self.debug = debug
        self.mappings = []
        self.haptic_mapping = None  # Store haptic mapping for updates

    def clear_mappings(self):
        """Remove all mappings — used before reloading after hot-plug"""
        self.mappings = []
        self.haptic_mapping = None

    def load_mappings(self, throttle=None, pto2=None, joystick=None):
        """Load universal telemetry mappings for all WinWing hardware"""
        print("=== Loading Telemetry Mappings (Universal) ===")

        # LED Mappings
        if throttle:
            throttle_mapping = OrionThrottle_TelemetryMapping(throttle)
            self.mappings.append(throttle_mapping)
            print(f"[Throttle] Loaded {len(throttle_mapping.rules)} LED rules")

        if pto2:
            pto2_mapping = OrionPTO2_TelemetryMapping(pto2)
            self.mappings.append(pto2_mapping)
            print(f"[PTO2] Loaded {len(pto2_mapping.rules)} LED rules")

        # Haptic Mappings
        if throttle and joystick:
            self.haptic_mapping = FA18C_HapticFeedback_TelemetryMapping(throttle, joystick, self.parser, debug=self.debug)
            self.mappings.append(self.haptic_mapping)
            print(f"[Haptics] Loaded {len(self.haptic_mapping.rules)} rules")

        # Subscribe all rules to parser
        self._subscribe_all()

        print("=== Telemetry Mappings Active ===\n")

    def _subscribe_all(self):
        """Subscribe all mapping rules to telemetry parser"""
        for mapping in self.mappings:
            for rule in mapping.rules:
                # Create callback that applies transform then action
                def callback(value, r=rule):
                    transformed = r.transform(value)
                    r.action(transformed)

                self.parser.subscribe(rule.data_path, callback)

        # Apply current state to newly loaded mappings
        self._apply_current_state()

    def _apply_current_state(self):
        """Apply current telemetry state to all mappings"""
        # Get all current values and trigger callbacks
        for mapping in self.mappings:
            for rule in mapping.rules:
                current_value = self.parser.get_value(rule.data_path)
                if current_value is not None:
                    transformed = rule.transform(current_value)
                    rule.action(transformed)

    def update(self):
        """Called every frame for time-based effects"""
        if self.haptic_mapping and hasattr(self.haptic_mapping, 'update'):
            self.haptic_mapping.update()


# ============================================================================
# Test / Demo
# ============================================================================

def main():
    """Test telemetry mappings with simulated data"""
    print("=== Telemetry Mappings Test ===")
    print("This would require actual hardware controllers")
    print("See telemetry_bridge.py for full implementation")


if __name__ == "__main__":
    main()
