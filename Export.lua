-- DCS Native Telemetry Export
-- Replaces DCS-BIOS for WinWing LED + Haptic Control
--
-- Provides:
-- - All cockpit LED states (via GetDevice) — per-aircraft arg tables
-- - Weapon telemetry (via LoGetPayloadInfo)
-- - Flight data for haptics (via LoGetSelfData, LoGetEngineInfo)
-- - Weight-on-wheels (via LoGetMechInfo) — universal
--
-- Installation:
-- Copy to: Saved Games/DCS/Scripts/Export.lua

-- ============================================================================
-- Configuration
-- ============================================================================

local BRIDGE_HOST = "127.0.0.1"
local BRIDGE_PORT = 7780
local UPDATE_RATE = 30  -- Hz

-- ============================================================================
-- Socket Setup
-- ============================================================================

package.path = package.path .. ";.\\LuaSocket\\?.lua"
package.cpath = package.cpath .. ";.\\LuaSocket\\?.dll"

local socket = require("socket")
local udp = socket.udp()
udp:settimeout(0)

-- ============================================================================
-- Per-Aircraft LED Argument Tables
-- ============================================================================
-- Each aircraft has its own arg numbers. Only the args for the detected
-- aircraft are read — no cross-contamination between modules.
--
-- To add a new aircraft:
--   1. Use ArgDiscover.lua to find the arg numbers
--   2. Add a new table below keyed by the aircraft name from LoGetSelfData()
-- ============================================================================

local AIRCRAFT_ARGS = {

    -- F/A-18C Hornet
    ["FA-18C_hornet"] = {
        leds = {
            MASTER_CAUTION   = 13,
            NOSE_GEAR        = 166,
            LEFT_GEAR        = 165,
            RIGHT_GEAR       = 167,
            GEAR_HANDLE      = 227,
            HALF_FLAPS       = 163,
            FULL_FLAPS       = 164,
            FLAPS_YELLOW     = 162,
            HOOK             = 294,
            MASTER_MODE_AA   = 47,
            MASTER_MODE_AG   = 48,
            STATION_CTR      = 152,
            STATION_LI       = 154,
            STATION_LO       = 156,
            STATION_RI       = 158,
            STATION_RO       = 160,
        },
        brightness = {
            CONSOLES_BRIGHTNESS = 413,
        },
        gear_lever = 226,
    },

    -- F-16C Viper
    ["F-16C_50"] = {
        leds = {
            MASTER_CAUTION   = 117,
            NOSE_GEAR        = 350,
            LEFT_GEAR        = 351,
            RIGHT_GEAR       = 352,
            GEAR_HANDLE      = 369,
            MASTER_MODE_AA   = 106,
        },
        brightness = {
            CONSOLES_BRIGHTNESS = 685,
        },
        gear_lever = 362,
    },
}

-- ============================================================================
-- State Tracking
-- ============================================================================

local frame_count = 0
local last_update = 0
local aircraft_name = nil
local current_args = nil  -- resolved arg table for current aircraft

-- ============================================================================
-- Helper Functions
-- ============================================================================

local function encode_json(t)
    local result = "{"
    local first = true

    for k, v in pairs(t) do
        if not first then
            result = result .. ","
        end
        first = false

        result = result .. '"' .. tostring(k) .. '":'

        if type(v) == "number" then
            result = result .. tostring(v)
        elseif type(v) == "boolean" then
            result = result .. (v and "true" or "false")
        elseif type(v) == "string" then
            -- Escape backslashes and quotes to prevent malformed JSON
            result = result .. '"' .. v:gsub('\\', '\\\\'):gsub('"', '\\"') .. '"'
        elseif type(v) == "table" then
            result = result .. encode_json(v)
        else
            result = result .. "null"
        end
    end

    result = result .. "}"
    return result
end

local function get_aircraft_name()
    local self_data = LoGetSelfData()
    if self_data and self_data.Name then
        return self_data.Name
    end
    return nil
end

-- Resolve the arg table for the current aircraft
local function resolve_aircraft_args(name)
    if not name then return nil end
    -- Direct match
    if AIRCRAFT_ARGS[name] then
        return AIRCRAFT_ARGS[name]
    end
    -- No match — unsupported aircraft (haptics still work, LEDs won't)
    return nil
end

-- ============================================================================
-- LED reader — uses only the current aircraft's args
-- ============================================================================

local function get_leds()
    local dev0 = GetDevice(0)
    if not dev0 then return nil end

    if type(dev0.update_arguments) == "function" then
        dev0:update_arguments()
    end

    local leds = {}

    if current_args then
        -- Boolean LEDs
        if current_args.leds then
            for name, arg_num in pairs(current_args.leds) do
                local value = dev0:get_argument_value(arg_num)
                leds[name] = (value and value > 0.3) and 1 or 0
            end
        end

        -- Brightness dimmers (float 0.0-1.0)
        if current_args.brightness then
            for name, arg_num in pairs(current_args.brightness) do
                local value = dev0:get_argument_value(arg_num)
                leds[name] = value or 0
            end
        end

        -- Gear lever
        if current_args.gear_lever then
            local value = dev0:get_argument_value(current_args.gear_lever)
            leds.GEAR_LEVER = (value and value > 0.5) and 1 or 0
        end
    end

    return leds
end

-- ============================================================================
-- Universal Weight-on-Wheels (via LoGetMechInfo — works on all aircraft)
-- ============================================================================

local function get_wow()
    local mech_info = LoGetMechInfo()
    local wow = {
        WOW_NOSE = 0,
        WOW_LEFT = 0,
        WOW_RIGHT = 0,
    }

    if mech_info and mech_info.gear then
        if mech_info.gear.nose and mech_info.gear.nose.rod then
            wow.WOW_NOSE = (mech_info.gear.nose.rod > 0.01) and 1 or 0
            wow.ROD_NOSE = mech_info.gear.nose.rod
        end

        if mech_info.gear.main and mech_info.gear.main.left and mech_info.gear.main.left.rod then
            wow.WOW_LEFT = (mech_info.gear.main.left.rod > 0.01) and 1 or 0
            wow.ROD_LEFT = mech_info.gear.main.left.rod
        end

        if mech_info.gear.main and mech_info.gear.main.right and mech_info.gear.main.right.rod then
            wow.WOW_RIGHT = (mech_info.gear.main.right.rod > 0.01) and 1 or 0
            wow.ROD_RIGHT = mech_info.gear.main.right.rod
        end

        -- Gear position and transit status (universal — works on all aircraft)
        if mech_info.gear.value then
            wow.GEAR_POS = mech_info.gear.value      -- 0.0=retracted, 1.0=extended
        end
        if mech_info.gear.status then
            wow.GEAR_STATUS = mech_info.gear.status   -- transit state integer
        end
    end

    return wow
end

-- Get payload information (weapons, ammo)
local function get_payload_data()
    local payload = LoGetPayloadInfo()
    if not payload then
        return nil
    end

    local data = {}

    if payload.Cannon and payload.Cannon.shells then
        data.cannon_ammo = payload.Cannon.shells
    else
        data.cannon_ammo = 0
    end

    data.current_station = payload.CurrentStation or 0

    if payload.Stations then
        for station_num, station_data in pairs(payload.Stations) do
            if station_data then
                local key = "station_" .. tostring(station_num)
                data[key .. "_count"] = station_data.count or 0
                if station_data.CLSID then
                    data[key .. "_clsid"] = station_data.CLSID
                end
                if station_data.weapon then
                    data[key .. "_type"] = station_data.weapon.level1 or 0
                end
            end
        end
    end

    return data
end

-- Get flight data (for haptics)
local function get_flight_data()
    local self_data = LoGetSelfData()
    if not self_data then
        return nil
    end

    local data = {}

    if self_data.Position then
        data.altitude = self_data.Position.y
    end

    if self_data.LatLongAlt then
        data.lat = self_data.LatLongAlt.Lat
        data.lon = self_data.LatLongAlt.Long
        data.alt_agl = self_data.LatLongAlt.Alt
    end

    data.vertical_velocity = LoGetVerticalVelocity() or 0

    local accel = LoGetAccelerationUnits()
    if accel then
        data.g_x = accel.x or 0
        data.g_y = accel.y or 0
        data.g_z = accel.z or 0
    else
        data.g_x = 0
        data.g_y = 1
        data.g_z = 0
    end

    local aoa = LoGetAngleOfAttack()
    if aoa then
        data.aoa = aoa  -- already in degrees
    else
        data.aoa = 0
    end

    local ias = LoGetIndicatedAirSpeed()
    local tas = LoGetTrueAirSpeed()

    local vel = LoGetVectorVelocity()
    local speed_from_vel = 0
    local vx, vy, vz = 0, 0, 0

    if vel then
        vx = vel.x or 0
        vy = vel.y or 0
        vz = vel.z or 0
        speed_from_vel = math.sqrt(vx*vx + vz*vz)
    end

    if speed_from_vel > 0 then
        data.ground_speed = speed_from_vel
    elseif tas then
        data.ground_speed = tas
    else
        data.ground_speed = 0
    end

    data.speed_ias = ias or 0
    data.speed_tas = tas or 0
    data.speed_vel = speed_from_vel
    data.vel_x = vx
    data.vel_y = vy
    data.vel_z = vz

    return data
end

-- Get engine data
local function get_engine_data()
    local engine = LoGetEngineInfo()
    if not engine then
        return nil
    end

    local data = {}

    if engine.RPM then
        data.rpm_left = engine.RPM.left or 0
        data.rpm_right = engine.RPM.right or 0
    else
        data.rpm_left = 0
        data.rpm_right = 0
    end

    return data
end

-- ============================================================================
-- Main Export Functions
-- ============================================================================

function LuaExportStart()
    aircraft_name = get_aircraft_name()
    current_args = resolve_aircraft_args(aircraft_name)
    frame_count = 0
    last_update = os.clock()
end

function LuaExportAfterNextFrame()
    frame_count = frame_count + 1

    local now = os.clock()
    local delta = now - last_update
    local min_interval = 1.0 / UPDATE_RATE

    if delta < min_interval then
        return
    end

    last_update = now

    local current_aircraft = get_aircraft_name()
    if not current_aircraft then
        return
    end

    -- Re-resolve args if aircraft changed (respawn, slot change)
    if current_aircraft ~= aircraft_name then
        aircraft_name = current_aircraft
        current_args = resolve_aircraft_args(aircraft_name)
    end

    local packet = {
        aircraft = current_aircraft,
        frame = frame_count,
        time = now,
    }

    -- LED states — only reads args for the current aircraft
    local leds = get_leds()
    if leds then
        local wow = get_wow()
        for k, v in pairs(wow) do
            leds[k] = v
        end
        packet.leds = leds
    end

    packet.payload = get_payload_data()
    packet.flight = get_flight_data()
    packet.engine = get_engine_data()

    local json = encode_json(packet)
    udp:sendto(json, BRIDGE_HOST, BRIDGE_PORT)
end

function LuaExportStop()
    if udp then
        udp:close()
    end
end

-- ============================================================================
-- Initialization
-- ============================================================================

local log_file = io.open(lfs.writedir() .. "Logs/WinWing_Export.log", "w")
if log_file then
    log_file:write("WinWing DCS Native Telemetry Export loaded\n")
    log_file:write("Time: " .. os.date("%Y-%m-%d %H:%M:%S") .. "\n")
    log_file:write("Target: " .. BRIDGE_HOST .. ":" .. BRIDGE_PORT .. "\n")
    log_file:write("Update Rate: " .. UPDATE_RATE .. " Hz\n")
    log_file:write("\n")
    log_file:write("Per-aircraft LED args — no cross-contamination\n")
    log_file:write("Supported: FA-18C_hornet, F-16C_50\n")
    log_file:write("\n")
    log_file:close()
end
