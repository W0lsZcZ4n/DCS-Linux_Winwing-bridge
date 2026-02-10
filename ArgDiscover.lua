-- ============================================================================
-- DCS Cockpit Argument Discovery Script
-- ============================================================================
-- Scans all cockpit arguments (0-1000) and logs any value changes.
-- Use this to reverse-engineer which argument numbers correspond to which
-- cockpit LEDs, indicators, and controls for any aircraft.
--
-- Usage:
--   1. Copy this file to: Saved Games/DCS/Scripts/Export.lua
--      (back up your existing Export.lua first!)
--   2. Start a mission in the aircraft you want to map
--   3. Trigger lights one at a time:
--        - Lower/raise gear → see which args change
--        - Press master caution → see which arg lights up
--        - Toggle master mode AA/AG
--        - Move brightness knobs slowly
--        - Extend/retract hook, flaps, etc.
--   4. Check the log at: Saved Games/DCS/Logs/ArgDiscover.log
--   5. When done, restore your original Export.lua
--
-- The log shows: [timestamp] aircraft | arg_number: old_value -> new_value
-- ============================================================================

-- Configuration
local SCAN_MAX_ARG      = 1000   -- Highest argument number to scan
local SCAN_RATE_HZ      = 10     -- How often to scan (Hz)
local VALUE_THRESHOLD    = 0.005  -- Ignore changes smaller than this (noise)
local LOG_INITIAL_STATE  = true   -- Log all non-zero args on first scan

-- ============================================================================
-- Resolve log path and confirm load IMMEDIATELY (before any mission starts)
-- ============================================================================

local LOG_PATH = lfs.writedir() .. "Logs/ArgDiscover.log"

do
    local f = io.open(LOG_PATH, "a")
    if f then
        f:write("\n")
        f:write("================================================================\n")
        f:write("ArgDiscover.lua LOADED — " .. os.date("%Y-%m-%d %H:%M:%S") .. "\n")
        f:write("Log path: " .. LOG_PATH .. "\n")
        f:write("Waiting for mission start (LuaExportStart)...\n")
        f:write("================================================================\n")
        f:close()
    end
end

-- ============================================================================
-- State
-- ============================================================================

local prev_values = {}
local first_scan = true
local last_scan_time = 0
local aircraft_name = "unknown"

-- ============================================================================
-- Logging
-- ============================================================================

local function log_write(msg)
    local f = io.open(LOG_PATH, "a")
    if f then
        f:write(msg .. "\n")
        f:close()
    end
end

local function log_change(arg_num, old_val, new_val, tag)
    local timestamp = string.format("%.3f", os.clock())
    local line = string.format("[%s] %s | arg %4d: %.4f -> %.4f",
        timestamp, aircraft_name, arg_num, old_val, new_val)
    if tag then
        line = line .. "  (" .. tag .. ")"
    end
    log_write(line)
end

-- ============================================================================
-- Argument Scanner
-- ============================================================================

local function scan_arguments()
    local ok_dev, dev0 = pcall(GetDevice, 0)
    if not ok_dev or not dev0 then return end

    -- update_arguments may not exist on all modules
    pcall(function() dev0:update_arguments() end)

    for arg_num = 0, SCAN_MAX_ARG do
        local ok, value = pcall(function()
            return dev0:get_argument_value(arg_num)
        end)

        if ok and value then
            local prev = prev_values[arg_num]

            if first_scan then
                prev_values[arg_num] = value
                if LOG_INITIAL_STATE and math.abs(value) > VALUE_THRESHOLD then
                    log_change(arg_num, 0, value, "initial")
                end
            else
                if prev and math.abs(value - prev) > VALUE_THRESHOLD then
                    log_change(arg_num, prev, value)
                    prev_values[arg_num] = value
                elseif not prev and math.abs(value) > VALUE_THRESHOLD then
                    log_change(arg_num, 0, value, "new")
                    prev_values[arg_num] = value
                elseif not prev then
                    prev_values[arg_num] = value
                end
            end
        end
    end

    first_scan = false
end

-- ============================================================================
-- DCS Export Hooks
-- ============================================================================

function LuaExportStart()
    -- Get aircraft name
    local ok, self_data = pcall(LoGetSelfData)
    if ok and self_data and self_data.Name then
        aircraft_name = self_data.Name
    end

    -- Reset state
    prev_values = {}
    first_scan = true
    last_scan_time = 0

    log_write("")
    log_write("================================================================")
    log_write("Mission started — " .. os.date("%Y-%m-%d %H:%M:%S"))
    log_write("Aircraft: " .. aircraft_name)
    log_write("Scanning args 0-" .. SCAN_MAX_ARG .. " at " .. SCAN_RATE_HZ .. " Hz")
    log_write("================================================================")
end

function LuaExportAfterNextFrame()
    local now = os.clock()
    if now - last_scan_time < (1.0 / SCAN_RATE_HZ) then
        return
    end
    last_scan_time = now

    -- Re-check aircraft (in case of respawn)
    local ok, self_data = pcall(LoGetSelfData)
    if ok and self_data and self_data.Name then
        if self_data.Name ~= aircraft_name then
            aircraft_name = self_data.Name
            prev_values = {}
            first_scan = true
            log_write("")
            log_write("--- Aircraft changed to: " .. aircraft_name .. " ---")
        end
    end

    -- Wrap entire scan in pcall so one bad frame doesn't kill the script
    local scan_ok, scan_err = pcall(scan_arguments)
    if not scan_ok then
        log_write("[ERROR] scan_arguments: " .. tostring(scan_err))
    end
end

function LuaExportStop()
    log_write("")
    log_write("--- Session ended: " .. os.date("%Y-%m-%d %H:%M:%S") .. " ---")
    log_write("")
end
