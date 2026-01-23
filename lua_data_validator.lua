--[[
    SocketBridge Lua Data Validation Helpers
    =========================================
    
    Lua-side validation utilities for detecting game-side data issues.
    
    Purpose:
    - Validate data before sending to Python
    - Detect known game API inconsistencies
    - Log suspicious data patterns
    - Help identify game-side vs Python-side issues
    
    Usage:
    1. Load this file AFTER SocketBridge main.lua
    2. Call DataValidator.enable() to activate
    3. Check logs for validation warnings
    
    Example:
        -- Enable validation
        DataValidator.enable()
        
        -- Validation runs automatically when SocketBridge sends data
        -- Check logs for issues
]]

-- Forward declaration
local DataValidator = nil

-- Configuration
local CONFIG = {
    enabled = false,
    log_level = "DEBUG",  -- DEBUG, INFO, WARN, ERROR
    check_player_position = true,
    check_enemies = true,
    check_projectiles = true,
    check_room_layout = true,
    check_pickups = true,
    -- Known game issues to check
    known_issues = {
        GRID_FIREPLACE = true,    -- ID 13 deprecated
        GRID_DOOR_IN_GRID = true, -- ID 16 should be in doors
        AIM_DIR_ZERO = true,      -- aim_dir may be (0,0)
        NEGATIVE_HP = true,       -- Some enemies report negative HP
    }
}

-- Log functions
local function log_debug(msg)
    if CONFIG.log_level == "DEBUG" then
        print(string.format("[LuaValidator-DEBUG] %s", msg))
    end
end

local function log_warn(msg)
    if CONFIG.log_level ~= "ERROR" then
        print(string.format("[LuaValidator-WARN] %s", msg))
    end
end

local function log_error(msg)
    print(string.format("[LuaValidator-ERROR] %s", msg))
end

-- Validate player position data
local function validate_player_position(player_data)
    if not CONFIG.check_player_position then return end
    
    for player_id, data in pairs(player_data) do
        if type(data) ~= "table" then
            log_error(string.format("Player %s data is not a table: %s", player_id, type(data)))
            goto continue
        end
        
        -- Check required fields
        local required_fields = {"pos", "vel", "aim_dir"}
        for _, field_name in ipairs(required_fields) do
            if data[field_name] == nil then
                log_warn(string.format("Player %s missing field: %s", player_id, field_name))
            end
        end
        
        -- Check pos structure
        if data.pos and type(data.pos) == "table" then
            if data.pos.x == nil or data.pos.y == nil then
                log_warn(string.format("Player %s pos missing x or y", player_id))
            end
        end
        
        -- Check aim_dir zero (known game issue)
        if CONFIG.known_issues.AIM_DIR_ZERO and data.aim_dir then
            if data.aim_dir.x == 0 and data.aim_dir.y == 0 then
                log_warn(string.format("Player %s aim_dir is (0,0)", player_id))
            end
        end
        
        -- Check for NaN or infinity
        local function check_numeric(value, field_path)
            if value ~= value then  -- NaN check
                log_warn(string.format("NaN detected at %s", field_path))
            elseif value == math.huge or value == -math.huge then
                log_warn(string.format("Infinity detected at %s", field_path))
            end
        end
        
        if data.pos then
            check_numeric(data.pos.x, string.format("Player %s.pos.x", player_id))
            check_numeric(data.pos.y, string.format("Player %s.pos.y", player_id))
        end
        
        ::continue::
    end
end

-- Validate enemy data
local function validate_enemies(enemies)
    if not CONFIG.check_enemies then return end
    if type(enemies) ~= "table" then return end
    
    local seen_ids = {}
    
    for i, enemy in ipairs(enemies) do
        if type(enemy) ~= "table" then
            log_error(string.format("Enemy %d is not a table", i))
            goto continue
        end
        
        -- Check required fields
        if enemy.id == nil then
            log_warn(string.format("Enemy %d missing id", i))
        end
        
        -- Check duplicate IDs
        if enemy.id then
            if seen_ids[enemy.id] then
                log_warn(string.format("Duplicate enemy id: %d", enemy.id))
            end
            seen_ids[enemy.id] = true
        end
        
        -- Check HP (known game issue: negative HP)
        if CONFIG.known_issues.NEGATIVE_HP and enemy.hp then
            if enemy.hp < 0 then
                log_warn(string.format("Enemy %d has negative HP: %f", enemy.id or i, enemy.hp))
            end
            if enemy.max_hp and enemy.hp > enemy.max_hp then
                log_warn(string.format("Enemy %d HP %f > max_hp %f", 
                    enemy.id or i, enemy.hp, enemy.max_hp or 0))
            end
        end
        
        -- Check position
        if enemy.pos and type(enemy.pos) == "table" then
            if enemy.pos.x == nil or enemy.pos.y == nil then
                log_warn(string.format("Enemy %d pos missing coordinates", enemy.id or i))
            end
        end
        
        ::continue::
    end
end

-- Validate projectile data
local function validate_projectiles(projectiles)
    if not CONFIG.check_projectiles then return end
    if type(projectiles) ~= "table" then return end
    
    for sub_type, proj_list in pairs(projectiles) do
        if type(proj_list) ~= "table" then
            log_warn(string.format("Projectiles[%s] is not a table", sub_type))
            goto continue
        end
        
        for i, proj in ipairs(proj_list) do
            if type(proj) ~= "table" then
                log_error(string.format("Projectiles[%s][%d] is not a table", sub_type, i))
                goto continue
            end
            
            -- Check id
            if proj.id == nil then
                log_warn(string.format("Projectiles[%s][%d] missing id", sub_type, i))
            end
            
            -- Check position
            if proj.pos and (proj.pos.x == nil or proj.pos.y == nil) then
                log_warn(string.format("Projectiles[%s][%d] pos invalid", sub_type, i))
            end
            
            ::continue::
        end
        
        ::continue::
    end
end

-- Validate room layout
local function validate_room_layout(room_layout)
    if not CONFIG.check_room_layout then return end
    if type(room_layout) ~= "table" then return end
    
    -- Check grid
    if room_layout.grid then
        for grid_idx, grid_data in pairs(room_layout.grid) do
            if type(grid_data) ~= "table" then
                log_error(string.format("Grid[%s] is not a table", grid_idx))
                goto continue
            end
            
            local grid_type = grid_data.type
            
            -- Check for deprecated GRID_FIREPLACE (ID 13)
            if CONFIG.known_issues.GRID_FIREPLACE and grid_type == 13 then
                log_warn(string.format("Grid[%s] is deprecated GRID_FIREPLACE (ID 13)", grid_idx))
            end
            
            -- Check for GRID_DOOR in grid (should be in doors)
            if CONFIG.known_issues.GRID_DOOR_IN_GRID and grid_type == 16 then
                log_warn(string.format("Grid[%s] is GRID_DOOR (ID 16) - should be in doors", grid_idx))
            end
            
            -- Check valid grid type (0-27)
            if grid_type < 0 or grid_type > 27 then
                log_warn(string.format("Grid[%s] has invalid type: %d", grid_idx, grid_type))
            end
            
            ::continue::
        end
    end
    
    -- Check doors (should not be in grid)
    if room_layout.doors then
        -- Doors are expected here
    end
end

-- Validate pickup data
local function validate_pickups(pickups)
    if not CONFIG.check_pickups then return end
    if type(pickups) ~= "table" then return end
    
    for i, pickup in ipairs(pickups) do
        if type(pickup) ~= "table" then
            log_error(string.format("Pickup %d is not a table", i))
            goto continue
        end
        
        -- Check required fields
        if pickup.id == nil then
            log_warn(string.format("Pickup %d missing id", i))
        end
        
        if pickup.variant == nil then
            log_warn(string.format("Pickup %d missing variant", i))
        end
        
        -- Check position
        if pickup.pos and (pickup.pos.x == nil or pickup.pos.y == nil) then
            log_warn(string.format("Pickup %d pos invalid", i))
        end
        
        ::continue::
    end
end

-- Main validation function - hooks into SocketBridge
local function validate_all(message)
    if not CONFIG.enabled then return message end
    
    log_debug(string.format("Validating message frame %d", message.frame or -1))
    
    local payload = message.payload
    if not payload then return message end
    
    -- Validate each channel
    if payload.PLAYER_POSITION then
        validate_player_position(payload.PLAYER_POSITION)
    end
    
    if payload.ENEMIES then
        validate_enemies(payload.ENEMIES)
    end
    
    if payload.PROJECTILES then
        validate_projectiles(payload.PROJECTILES)
    end
    
    if payload.ROOM_LAYOUT then
        validate_room_layout(payload.ROOM_LAYOUT)
    end
    
    if payload.PICKUPS then
        validate_pickups(payload.PICKUPS)
    end
    
    return message
end

-- Create DataValidator module
DataValidator = {
    -- Enable/disable validation
    enable = function()
        CONFIG.enabled = true
        print("[DataValidator] Enabled")
        
        -- Hook into SocketBridge's send function if available
        if SocketBridge and SocketBridge.Network then
            local original_send = SocketBridge.Network.send
            if original_send then
                SocketBridge.Network.send = function(self, data)
                    validate_all(data)
                    return original_send(self, data)
                end
                print("[DataValidator] Hooked into SocketBridge.Network.send")
            end
        end
    end,
    
    disable = function()
        CONFIG.enabled = false
        print("[DataValidator] Disabled")
    end,
    
    -- Toggle specific checks
    set_check = function(channel, enabled)
        local key = "check_" .. channel:lower()
        if CONFIG[key] ~= nil then
            CONFIG[key] = enabled
            print(string.format("[DataValidator] %s = %s", key, tostring(enabled)))
        else
            print(string.format("[DataValidator] Unknown channel: %s", channel))
        end
    end,
    
    -- Toggle known issue checks
    set_known_issue = function(issue, enabled)
        if CONFIG.known_issues[issue] ~= nil then
            CONFIG.known_issues[issue] = enabled
            print(string.format("[DataValidator] known_issues.%s = %s", issue, tostring(enabled)))
        else
            print(string.format("[DataValidator] Unknown issue: %s", issue))
        end
    end,
    
    -- Get validation status
    status = function()
        print(string.format("[DataValidator] enabled: %s", tostring(CONFIG.enabled)))
        print(string.format("[DataValidator] check_player_position: %s", tostring(CONFIG.check_player_position)))
        print(string.format("[DataValidator] check_enemies: %s", tostring(CONFIG.check_enemies)))
        print(string.format("[DataValidator] check_projectiles: %s", tostring(CONFIG.check_projectiles)))
        print(string.format("[DataValidator] check_room_layout: %s", tostring(CONFIG.check_room_layout)))
    end,
    
    -- Manually validate data
    validate = function(message)
        return validate_all(message or {})
    end,
    
    -- Get configuration
    get_config = function()
        return CONFIG
    end
}

-- Auto-enable if DEBUG mode is detected
if SOCKETBRIDGE_DEBUG then
    print("[DataValidator] Auto-enabling (DEBUG mode detected)")
    DataValidator.enable()
end

return DataValidator
