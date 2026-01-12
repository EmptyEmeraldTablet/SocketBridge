-- ============================================================================
-- SocketBridge 房间数据采集脚本 (Room Data Collector)
-- ============================================================================
-- 使用方法:
-- 1. 在游戏中按 F7 开启/关闭采集模式
-- 2. 飞行到房间角落（内角），按 F8 记录该角落坐标
-- 3. 完成 4 个角落（L型 5 个）后，按 F9 导出数据
-- 4. 数据会自动发送到 Python 端并保存到文件
-- ============================================================================

local ROOM_COLLECTOR = {
    -- 状态
    enabled = false,
    recording_mode = false,
    corners = {},
    current_room = nil,
    recorded_data = {},
    
    -- 配置
    corner_threshold = 5.0,  -- 停留时间阈值（秒）
    corner_timer = 0,
    last_position = nil,
    corner_names = {
        "top_left", "top_right", "bottom_left", "bottom_right"
    },
    
    -- 玩家碰撞箱半径 (Isaac 标准约 20-35)
    player_radius = 25,
}

-- ============================================================================
-- 核心功能函数
-- ============================================================================

function ROOM_COLLECTOR:init()
    -- 注册按键回调
    mod:AddCallback(ModCallbacks.MC_INPUT_ACTION, function(_, inputAction, hook)
        if inputAction == InputAction.IS_DEBUG_MENU and self.enabled then
            -- F7: 开关采集模式
            self:toggleMode()
            return true
        end
        if inputAction == InputAction.MENU_ACCEPT and self.enabled then
            -- F8: 记录角落
            self:recordCorner()
            return true
        end
        if inputAction == InputAction.REORDER_CARDS and self.enabled then
            -- F9: 导出数据
            self:exportData()
            return true
        end
    end)
    
    -- 注册帧更新回调
    mod:AddCallback(ModCallbacks.MC_POST_UPDATE, function()
        if not self.enabled then return end
        self:update()
    end)
    
    print("[RoomCollector] Initialized - F7: Toggle | F8: Record Corner | F9: Export")
end

function ROOM_COLLECTOR:toggleMode()
    self.recording_mode = not self.recording_mode
    if self.recording_mode then
        self:startRecording()
    else
        self:stopRecording()
    end
    print("[RoomCollector] Recording mode: " .. tostring(self.recording_mode))
end

function ROOM_COLLECTOR:startRecording()
    self.corners = {}
    self.corner_timer = 0
    self.last_position = nil
    self:scanCurrentRoom()
    print("[RoomCollector] Started recording - Fly to corners and press F8")
end

function ROOM_COLLECTOR:stopRecording()
    self.corner_timer = 0
    self.last_position = nil
    print("[RoomCollector] Stopped recording")
end

function ROOM_COLLECTOR:scanCurrentRoom()
    -- 自动扫描房间网格，获取墙壁信息
    local room = Isaac.GetRoom()
    if not room then return end
    
    local grid_width = room:GetGridWidth()
    local grid_height = room:GetGridHeight()
    local grid_size = room:GetGridWidth() * 40 / grid_width  -- 估算
    
    local tl = room:GetTopLeftPos()
    local br = room:GetBottomRightPos()
    
    self.current_room = {
        grid_width = grid_width,
        grid_height = grid_height,
        grid_size = grid_size,
        top_left = {x = tl.X, y = tl.Y},
        bottom_right = {x = br.X, y = br.Y},
        shape = room:GetRoomShape(),
        wall_positions = {},
        obstacles = {}
    }
    
    -- 扫描网格实体（墙壁、障碍物）
    for i = 0, room:GetGridSize() - 1 do
        local entity = room:GetGridEntity(i)
        if entity then
            local pos = entity.Position
            local collision = entity.CollisionClass
            local grid_type = entity:GetType()
            
            table.insert(self.current_room.wall_positions, {
                index = i,
                x = pos.X,
                y = pos.Y,
                collision = collision,
                type = grid_type
            })
        end
    end
    
    print("[RoomCollector] Scanned room: " .. grid_width .. "x" .. grid_height .. 
          ", shape=" .. self.current_room.shape ..
          ", walls=" .. #self.current_room.wall_positions)
end

function ROOM_COLLECTOR:update()
    local player = Isaac.GetPlayer(0)
    if not player then return end
    
    local pos = player.Position
    local room = Isaac.GetRoom()
    
    -- 检测房间变化
    if self.current_room and room:GetRoomShape() ~= self.current_room.shape then
        print("[RoomCollector] Room changed, rescan needed")
        self:scanCurrentRoom()
    end
    
    -- 检测玩家是否停止移动（用于自动记录）
    if self.last_position then
        local dist = pos:Distance(self.last_position)
        if dist < 1 then
            self.corner_timer = self.corner_timer + 1/60
        else
            self.corner_timer = 0
        end
    end
    self.last_position = pos
end

function ROOM_COLLECTOR:recordCorner()
    local player = Isaac.GetPlayer(0)
    if not player then return end
    
    local pos = player.Position
    local room = Isaac.GetPlayer(0):GetRoom()
    
    -- 计算玩家中心到房间边界的距离
    local tl = room:GetTopLeftPos()
    local br = room:GetBottomRightPos()
    
    local corner_idx = #self.corners + 1
    if corner_idx > 4 and self.current_room.shape < 8 then
        print("[RoomCollector] Already have 4 corners for normal room!")
        return
    end
    
    -- 根据玩家位置判断是哪个角落
    local corner_type = self:identifyCorner(pos, tl, br)
    
    -- 计算角落坐标（玩家中心 +/- 碰撞箱半径）
    local corner_pos = self:calculateCornerPosition(pos, corner_type, tl, br)
    
    local corner_data = {
        type = corner_type,
        player_pos = {x = pos.X, y = pos.Y},
        corner_pos = corner_pos,
        timestamp = Game():GetFrameCount(),
        room_shape = self.current_room.shape,
        grid_width = self.current_room.grid_width,
        grid_height = self.current_room.grid_height,
        top_left = self.current_room.top_left,
        bottom_right = self.current_room.bottom_right
    }
    
    table.insert(self.corners, corner_data)
    
    print("[RoomCollector] Corner " .. corner_idx .. " recorded: " .. corner_type)
    print("  Player: (" .. string.format("%.1f", pos.X) .. ", " .. string.format("%.1f", pos.Y) .. ")")
    print("  Corner: (" .. string.format("%.1f", corner_pos.x) .. ", " .. string.format("%.1f", corner_pos.y) .. ")")
    
    -- 如果收集完成，自动导出
    local expected = (self.current_room.shape >= 8) and 5 or 4
    if #self.corners >= expected then
        print("[RoomCollector] All corners collected, auto-exporting...")
        self:exportData()
    end
end

function ROOM_COLLECTOR:identifyCorner(player_pos, tl, br)
    -- 根据玩家位置判断角落类型
    local mid_x = (tl.X + br.X) / 2
    local mid_y = (tl.Y + br.Y) / 2
    
    local is_left = player_pos.X < mid_x
    local is_top = player_pos.Y < mid_y
    
    if is_left and is_top then
        return "top_left"
    elseif not is_left and is_top then
        return "top_right"
    elseif is_left and not is_top then
        return "bottom_left"
    else
        return "bottom_right"
    end
end

function ROOM_COLLECTOR:calculateCornerPosition(player_pos, corner_type, tl, br)
    -- 计算实际角落坐标
    -- 玩家站在角落内角时，角落坐标 = 玩家坐标 +/- 碰撞箱半径
    
    local corner = {x = 0, y = 0}
    
    -- 基础角落坐标（从 API 获取）
    if corner_type == "top_left" then
        corner.x = tl.X + self.player_radius
        corner.y = tl.Y + self.player_radius
    elseif corner_type == "top_right" then
        corner.x = br.X - self.player_radius
        corner.y = tl.Y + self.player_radius
    elseif corner_type == "bottom_left" then
        corner.x = tl.X + self.player_radius
        corner.y = br.Y - self.player_radius
    else  -- bottom_right
        corner.x = br.X - self.player_radius
        corner.y = br.Y - self.player_radius
    end
    
    return corner
end

function ROOM_COLLECTOR:exportData()
    if #self.corners == 0 then
        print("[RoomCollector] No corners to export!")
        return
    end
    
    local room = Isaac.GetPlayer(0):GetRoom()
    local tl = room:GetTopLeftPos()
    local br = room:GetBottomRightPos()
    
    -- 构建导出数据
    local export = {
        timestamp = os.date("%Y-%m-%d %H:%M:%S"),
        frame = Game():GetFrameCount(),
        room_info = {
            room_index = Isaac.GetPlayer(0):GetRoom().GetRoomShape and room:GetRoomShape() or 0,
            room_shape = self.current_room.shape,
            grid_width = self.current_room.grid_width,
            grid_height = self.current_room.grid_height,
            grid_size = self.current_room.grid_size,
            stage = Game():GetLevel():GetStage(),
            stage_type = Game():GetLevel():GetStageType(),
            difficulty = Game().Difficulty
        },
        room_bounds = {
            top_left = {x = tl.X, y = tl.Y},
            bottom_right = {x = br.X, y = br.Y}
        },
        player_radius = self.player_radius,
        corners = self.corners,
        calculated_bounds = self:calculateBoundsFromCorners(),
        wall_positions = self.current_room.wall_positions
    }
    
    -- 保存到本地文件
    self:saveToFile(export)
    
    -- 发送到 Python 端
    self:sendToPython(export)
    
    print("[RoomCollector] Data exported!")
    print("  Room: " .. export.room_info.grid_width .. "x" .. export.room_info.grid_height)
    print("  Shape: " .. export.room_info.room_shape)
    print("  Corners: " .. #self.corners)
    
    -- 清空当前数据，准备下一次
    self.corners = {}
end

function ROOM_COLLECTOR:calculateBoundsFromCorners()
    -- 从记录的角落计算房间边界
    if #self.corners < 2 then return nil end
    
    local min_x = math.huge
    local max_x = -math.huge
    local min_y = math.huge
    local max_y = -math.huge
    
    for _, corner in ipairs(self.corners) do
        local pos = corner.corner_pos
        min_x = math.min(min_x, pos.x)
        max_x = math.max(max_x, pos.x)
        min_y = math.min(min_y, pos.y)
        max_y = math.max(max_y, pos.y)
    end
    
    return {
        top_left = {x = min_x, y = min_y},
        bottom_right = {x = max_x, y = max_y},
        width = max_x - min_x,
        height = max_y - min_y
    }
end

function ROOM_COLLECTOR:saveToFile(data)
    local filename = "room_data_" .. os.date("%Y%m%d_%H%M%S") .. ".json"
    
    -- 转换为 JSON
    local json = self:tableToJSON(data)
    
    -- 使用 Isaac 的文件 API 保存
    local success, err = pcall(function()
        local file = io.open(filename, "w")
        if file then
            file:write(json)
            file:close()
            print("[RoomCollector] Saved to: " .. filename)
        else
            print("[RoomCollector] Failed to save file")
        end
    end)
    
    if not success then
        print("[RoomCollector] Error saving: " .. tostring(err))
    end
end

function ROOM_COLLECTOR:sendToPython(data)
    -- 通过 SocketBridge 协议发送数据
    local payload = {
        type = "ROOM_DATA_COLLECTION",
        data = data
    }
    
    -- 使用现有的 Protocol 发送
    if mod.Protocol then
        mod.Protocol:broadcast(payload)
        print("[RoomCollector] Sent to Python")
    else
        print("[RoomCollector] Protocol not available, data saved locally only")
    end
end

function ROOM_COLLECTOR:tableToJSON(t)
    -- 简单的 Lua 表转 JSON
    local function escape(s)
        s = string.gsub(s, '\\', '\\\\')
        s = string.gsub(s, '"', '\\"')
        s = string.gsub(s, '\n', '\\n')
        s = string.gsub(s, '\r', '\\r')
        s = string.gsub(s, '\t', '\\t')
        return s
    end
    
    local function tojson(val, indent, prefix)
        indent = indent or ""
        prefix = prefix or ""
        
        local t = type(val)
        
        if t == "nil" then
            return "null"
        elseif t == "number" then
            return tostring(val)
        elseif t == "string" then
            return '"' .. escape(val) .. '"'
        elseif t == "boolean" then
            return tostring(val)
        elseif t == "table" then
            local items = {}
            local is_array = #val > 0
            
            for k, v in pairs(val) do
                local key
                if is_array then
                    key = ""
                else
                    key = '"' .. escape(tostring(k)) .. '": '
                end
                table.insert(items, indent .. key .. tojson(v, indent .. "  ", ""))
            end
            
            if is_array then
                return "[\n" .. table.concat(items, ",\n") .. "\n" .. indent .. "]"
            else
                return "{\n" .. table.concat(items, ",\n") .. "\n" .. indent .. "}"
            end
        else
            return '"' .. escape(tostring(val)) .. '"'
        end
    end
    
    return tojson(t, "", "")
end

-- ============================================================================
-- 自动扫描模式（替代手动记录）
-- ============================================================================

function ROOM_COLLECTOR:autoScanRoom()
    -- 自动扫描房间并计算边界
    local room = Isaac.GetRoom()
    if not room then return end
    
    local tl = room:GetTopLeftPos()
    local br = room:GetBottomRightPos()
    
    -- 从 API 直接获取边界（更准确）
    local auto_data = {
        method = "api_direct",
        room_info = {
            grid_width = room:GetGridWidth(),
            grid_height = room:GetGridHeight(),
            shape = room:GetRoomShape(),
            top_left = {x = tl.X, y = tl.Y},
            bottom_right = {x = br.X, y = br.Y}
        },
        -- 计算内部可玩区域
        internal = {
            left = tl.X + 40,   -- 1 tile wall
            right = br.X - 40,
            top = tl.Y + 40,
            bottom = br.Y - 40,
            width = br.X - tl.X - 80,
            height = br.Y - tl.Y - 80
        },
        -- 收集墙壁位置
        walls = {},
        obstacles = {}
    }
    
    -- 扫描所有网格实体
    for i = 0, room:GetGridSize() - 1 do
        local entity = room:GetGridEntity(i)
        if entity then
            local pos = entity.Position
            local collision = entity.CollisionClass
            local gtype = entity:GetType()
            
            local is_wall = (collision == GridCollisionClass.COLLISION_WALL or 
                            collision == GridCollisionClass.COLLISION_WALL_EXCEPT_PLAYER)
            
            local entry = {
                index = i,
                x = pos.X,
                y = pos.Y,
                collision = collision,
                type = gtype,
                is_wall = is_wall
            }
            
            if is_wall then
                table.insert(auto_data.walls, entry)
            else
                table.insert(auto_data.obstacles, entry)
            end
        end
    end
    
    print("[RoomCollector] Auto-scan complete:")
    print("  Grid: " .. auto_data.room_info.grid_width .. "x" .. auto_data.room_info.grid_height)
    print("  Walls: " .. #auto_data.walls)
    print("  Obstacles: " .. #auto_data.obstacles)
    
    return auto_data
end

-- ============================================================================
-- 初始化
-- ============================================================================

ROOM_COLLECTOR:init()

-- 公开到全局
mod.RoomCollector = ROOM_COLLECTOR

print("[SocketBridge] Room Data Collector loaded - F7: Toggle | F8: Record Corner | F9: Export")
