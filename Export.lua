-- DCS Native Telemetry Export
-- WinWing LED + Haptic Control via UDP
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

local function get_log_path()
    local ok, dir = pcall(function() return lfs.writedir() end)
    if ok and type(dir) == "string" then
        return dir .. "Logs/WinWing_Export.log"
    end
    return "Logs/WinWing_Export.log"
end

local log_file = io.open(get_log_path(), "w")

local function log(msg)
    if log_file == nil then return end
    local ok, err = pcall(function()
        log_file:write(string.format("%s %s\n", os.date("%Y-%m-%d %H:%M:%S"), msg))
        log_file:flush()
    end)
    if not ok then
        log_file = nil
    end
end

local log_once_table = {}
local function log_once(key, msg)
    if not log_once_table[key] then
        log_once_table[key] = true
        log(msg)
    end
end

local socket
local socket_load_error
do
    local ok, mod = pcall(require, "socket")
    if ok then
        socket = mod
    else
        socket_load_error = tostring(mod)
    end
end

local udp = nil
if socket ~= nil then
    local ok, obj = pcall(function()
        return socket.udp()
    end)
    if ok then
        udp = obj
    end
end

if udp ~= nil then
    pcall(function()
        udp:settimeout(0)
    end)
end

log("log_file type: " .. type(log_file))
log("socket type: " .. type(socket))
log("udp type: " .. type(udp))

log("WinWing DCS Native Telemetry Export loaded")
log("Time: " .. os.date("%Y-%m-%d %H:%M:%S"))
log("Target: " .. BRIDGE_HOST .. ":" .. BRIDGE_PORT)
log("Update Rate: " .. UPDATE_RATE .. " Hz")
log("LuaSocket: " .. (socket ~= nil and ("loaded (type=" .. type(socket) .. ")") or ("failed: " .. tostring(socket_load_error))))
log("Per-aircraft LED args — no cross-contamination")
log("Supported: FA-18C_hornet, F-16C_50")

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

local function cannon_field_to_number(value)
    local number_value = tonumber(value)
    if number_value ~= nil then
        return math.floor(number_value)
    end
    return nil
end

local function get_cannon_ammo_value(payload)
    local cannon = payload.Cannon
    if type(cannon) ~= "table" then
        return nil
    end

    for _, key in ipairs({ "shells", "ammo", "count", "remaining" }) do
        local value = cannon_field_to_number(cannon[key])
        if value ~= nil then
            return value
        end
    end

    return nil
end

local function debug_cannon_payload(payload)
    local name = tostring(aircraft_name or "unknown")
    local key = "cannon_debug_" .. name
    if log_once_table[key] then
        return
    end

    local cannon = payload.Cannon
    if type(cannon) == "table" then
        local fields = {}
        for field_name, field_value in pairs(cannon) do
            fields[#fields + 1] = tostring(field_name) .. "=" .. tostring(field_value)
        end
        table.sort(fields)
        log_once(key, "payload.Cannon[" .. name .. "] fields: " .. table.concat(fields, ", "))
    else
        log_once(key, "payload.Cannon missing for " .. name .. " (type=" .. type(cannon) .. ")")
    end
end

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

local function get_export_ns()
    if type(_G) ~= "table" then return nil end
    local t = rawget(_G, "Export")
    if type(t) == "table" then return t end
    return nil
end

local export_missing_logged = {}
local export_error_logged = {}

local function safe_export(func_name, ...)
    local ns = get_export_ns()
    local f = nil
    if type(ns) == "table" then
        f = rawget(ns, func_name)
    end
    if type(f) ~= "function" and type(_G) == "table" then
        f = rawget(_G, func_name)
    end
    if type(f) ~= "function" then
        if not export_missing_logged[func_name] then
            export_missing_logged[func_name] = true
            log_once(func_name .. "_missing", "Export API missing: " .. func_name)
        end
        return nil
    end
    local ok, result = pcall(f, ...)
    if not ok then
        if not export_error_logged[func_name] then
            export_error_logged[func_name] = true
            log_once(func_name .. "_error", "Export API error " .. func_name .. ": " .. tostring(result))
        end
        return nil
    end
    return result
end

local function safe_get_device(id)
    local f = nil
    if type(_G) == "table" then
        f = rawget(_G, "GetDevice")
    end
    if type(f) ~= "function" then
        local ns = get_export_ns()
        if type(ns) == "table" then
            f = rawget(ns, "GetDevice")
        end
    end
    if type(f) ~= "function" then
        log_once("getdevice_missing", "GetDevice unavailable; LED readings disabled")
        return nil
    end
    local ok, result = pcall(f, id)
    if not ok then
        log_once("getdevice_error", "GetDevice error: " .. tostring(result))
        return nil
    end
    return result
end

local function table_keys_str(t)
    if type(t) ~= "table" then return tostring(t) end
    local keys = {}
    for k in pairs(t) do
        table.insert(keys, tostring(k))
    end
    table.sort(keys)
    return table.concat(keys, ",")
end

local self_data_dumped = false
local function dump_self_data(sd)
    if self_data_dumped then return end
    self_data_dumped = true
    log("LoGetSelfData type: " .. type(sd))
    if type(sd) ~= "table" then return end
    log("LoGetSelfData keys: " .. table_keys_str(sd))
    local count = 0
    for k, v in pairs(sd) do
        count = count + 1
        if count <= 80 then
            if type(v) == "table" then
                log("self_data[" .. tostring(k) .. "] table keys: " .. table_keys_str(v))
            else
                log("self_data[" .. tostring(k) .. "] = " .. tostring(v))
            end
        end
    end
end

local function name_from_table(t)
    if type(t) ~= "table" then return nil end
    local fields = { "Name", "name", "TypeName", "typeName", "ModelName", "modelName", "Type", "type" }
    for i = 1, #fields do
        local v = t[fields[i]]
        if type(v) == "string" and v ~= "" then
            return v
        end
    end
    return nil
end

local function get_aircraft_name()
    local self_data = safe_export("LoGetSelfData")
    local name = name_from_table(self_data)
    if name then return name end

    if type(self_data) == "table" then
        local object_id = self_data.ObjectID or self_data.objectID or self_data.ID or self_data.id
        if type(object_id) == "number" then
            local obj = safe_export("LoGetObjectById", object_id)
            name = name_from_table(obj)
            if name then return name end
        end

        local type_value = self_data.Type or self_data.type
        if type(type_value) == "number" or type(type_value) == "string" then
            local type_name = safe_export("LoGetNameByType", type_value)
            if type(type_name) == "string" and type_name ~= "" then
                return type_name
            end
        end
    end

    dump_self_data(self_data)
    return nil
end

-- Resolve the arg table for the current aircraft
local function resolve_aircraft_args(name)
    if type(name) ~= "string" or name == "" then return nil end
    if AIRCRAFT_ARGS[name] then
        return AIRCRAFT_ARGS[name]
    end
    local lower = name:lower()
    for key, args in pairs(AIRCRAFT_ARGS) do
        if type(key) == "string" and key:lower() == lower then
            return args
        end
    end
    return nil
end

-- ============================================================================
-- LED reader — uses only the current aircraft's args
-- ============================================================================

local function get_leds()
    local dev0 = safe_get_device(0)
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
    local mech_info = safe_export("LoGetMechInfo")
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
    local payload = safe_export("LoGetPayloadInfo")
    if not payload then
        log_once("payload_nil_" .. tostring(aircraft_name or "unknown"), "LoGetPayloadInfo returned nil for " .. tostring(aircraft_name or "unknown"))
        return nil
    end

    debug_cannon_payload(payload)

    local data = {}
    local cannon_ammo = get_cannon_ammo_value(payload)
    data.cannon_ammo = cannon_ammo or 0

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
    local self_data = safe_export("LoGetSelfData")
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

    data.vertical_velocity = safe_export("LoGetVerticalVelocity") or 0

    local accel = safe_export("LoGetAccelerationUnits")
    if accel then
        data.g_x = accel.x or 0
        data.g_y = accel.y or 0
        data.g_z = accel.z or 0
    else
        data.g_x = 0
        data.g_y = 1
        data.g_z = 0
    end

    local aoa = safe_export("LoGetAngleOfAttack")
    if aoa then
        data.aoa = aoa  -- already in degrees
    else
        data.aoa = 0
    end

    local ias = safe_export("LoGetIndicatedAirSpeed")
    local tas = safe_export("LoGetTrueAirSpeed")

    local vel = safe_export("LoGetVectorVelocity")
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
    local engine = safe_export("LoGetEngineInfo")
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

local call_error_logged = {}
local function safe_call(label, fn, ...)
    local ok, result = pcall(fn, ...)
    if not ok then
        if not call_error_logged[label] then
            call_error_logged[label] = true
            log(label .. " error: " .. tostring(result))
        end
        return nil
    end
    return result
end

local first_send_logged = false
local function safe_udp_send(json)
    if udp == nil then
        log_once("udp_missing", "UDP object unavailable")
        return nil, "udp object unavailable"
    end

    local call_ok, ret_ok, ret_err = pcall(function()
        return udp:sendto(json, BRIDGE_HOST, BRIDGE_PORT)
    end)

    if not call_ok then
        if not first_send_logged then
            first_send_logged = true
            log("UDP sendto exception: " .. tostring(ret_ok))
        end
        return nil, ret_ok
    end

    if not first_send_logged then
        first_send_logged = true
        log("UDP sendto result: ok=" .. tostring(ret_ok) .. " err=" .. tostring(ret_err))
    elseif not ret_ok then
        log_once("udp_send_failed", "UDP sendto failed: " .. tostring(ret_err))
    end

    return ret_ok, ret_err
end

local EXPORT_FUNCTIONS = {
    "LoGetSelfData",
    "LoGetObjectById",
    "LoGetNameByType",
    "LoGetMechInfo",
    "LoGetPayloadInfo",
    "LoGetVerticalVelocity",
    "LoGetAccelerationUnits",
    "LoGetAngleOfAttack",
    "LoGetIndicatedAirSpeed",
    "LoGetTrueAirSpeed",
    "LoGetVectorVelocity",
    "LoGetEngineInfo",
}

local function log_export_availability()
    local ns = get_export_ns()
    log("Export namespace: " .. (type(ns) == "table" and "present" or "absent"))

    local allow_object = safe_export("LoIsObjectExportAllowed")
    local allow_sensor = safe_export("LoIsSensorExportAllowed")
    local allow_ownship = safe_export("LoIsOwnshipExportAllowed")
    log("Export allow object/sensor/ownship: " .. tostring(allow_object) .. " / " .. tostring(allow_sensor) .. " / " .. tostring(allow_ownship))

    for i = 1, #EXPORT_FUNCTIONS do
        local name = EXPORT_FUNCTIONS[i]
        local f = nil
        if type(ns) == "table" then
            f = rawget(ns, name)
        end
        if type(f) ~= "function" and type(_G) == "table" then
            f = rawget(_G, name)
        end
        log("API " .. name .. ": " .. (type(f) == "function" and "present" or "absent"))
    end

    local gd = nil
    if type(_G) == "table" then
        gd = rawget(_G, "GetDevice")
    end
    if type(gd) ~= "function" and type(ns) == "table" then
        gd = rawget(ns, "GetDevice")
    end
    log("API GetDevice: " .. (type(gd) == "function" and "present" or "absent"))
end

-- ============================================================================
-- Main Export Functions
-- ============================================================================

function LuaExportStart()
    self_data_dumped = false
    first_send_logged = false
    log_export_availability()
    aircraft_name = get_aircraft_name()
    current_args = resolve_aircraft_args(aircraft_name)
    frame_count = 0
    last_update = os.clock()
    log("LuaExportStart aircraft=" .. tostring(aircraft_name) .. " supported=" .. tostring(current_args ~= nil))
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
        log("Aircraft changed to " .. tostring(aircraft_name) .. " supported=" .. tostring(current_args ~= nil))
    end

    local packet = {
        aircraft = current_aircraft,
        frame = frame_count,
        time = now,
    }

    -- LED states — only reads args for the current aircraft
    local leds = safe_call("get_leds", get_leds)
    local wow = safe_call("get_wow", get_wow)
    if leds or wow then
        if not leds then
            leds = {}
        end
        if wow then
            for k, v in pairs(wow) do
                leds[k] = v
            end
        end
        packet.leds = leds
    end

    packet.payload = safe_call("get_payload_data", get_payload_data)
    packet.flight = safe_call("get_flight_data", get_flight_data)
    packet.engine = safe_call("get_engine_data", get_engine_data)

    local json = encode_json(packet)
    safe_udp_send(json)
end

function LuaExportStop()
    if udp ~= nil then
        pcall(function()
            udp:close()
        end)
    end
    udp = nil

    if log_file ~= nil then
        pcall(function()
            log_file:close()
        end)
        log_file = nil
    end
end
