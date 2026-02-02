# SocketBridge Project Documentation

> **Version**: 2.1  
> **Last Updated**: February 3, 2026  
> **Status**: Core Features Complete ✅

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Quick Start](#quick-start)
3. [Application Tools Guide](#application-tools-guide)
4. [Developer Guide](#developer-guide)
5. [New Channel Registration Process](#new-channel-registration-process)
6. [FAQ](#faq)
7. [Architecture Reference](#architecture-reference)

---

## Project Overview

**SocketBridge** is a mod for The Binding of Isaac: Repentance that implements real-time data bridging between the game and Python programs. This project provides powerful infrastructure for game AI development, data analysis, and automated testing.

### Core Features

| Feature | Description |
|---------|-------------|
| **Real-time Data Collection** | Efficiently collect various in-game data (player, enemies, projectiles, rooms, etc.) |
| **Multi-frequency Collection** | Support four collection modes: HIGH/MEDIUM/LOW/ON_CHANGE |
| **Bidirectional Communication** | Game data transmitted to Python in real-time, Python can send control commands back to game |
| **Event System** | Complete game event listening and callback mechanism |
| **AI Control Support** | Built-in AI control framework with manual/AI mode switching (F3 key) |
| **Data Recording** | Complete game session recording and playback system |
| **Timing Awareness** | v2.1 protocol supports channel-level timing information, solving data synchronization issues |
| **Quality Monitoring** | Automatic detection of game-side and Python-side issues |

### Directory Structure

```
SocketBridge/
├── main.lua                    # Game mod main file (Lua)
├── metadata.xml                # Mod metadata
├── README.md                   # This document (Chinese)
├── README_EN.md                # English version
├── REFACTORING_PLAN.md         # Refactoring plan document
│
└── python/                     # Python-side code
    ├── isaac_bridge.py         # Core network bridging library
    ├── environment.py          # Game map environment modeling
    ├── models.py               # Compatibility layer (re-export)
    │
    ├── models/                 # Data model layer
    │   ├── base.py             # Base types (Vector2D, EntityType)
    │   ├── entities.py         # Entity data classes
    │   └── state.py            # State management
    │
    ├── channels/               # Data channel layer
    │   ├── base.py             # DataChannel base class, ChannelRegistry
    │   ├── player.py           # Player-related channels
    │   ├── room.py             # Room-related channels
    │   ├── entities.py         # Entity channels
    │   └── hazards.py          # Hazard channels
    │
    ├── services/               # Service layer
    │   ├── facade.py           # Unified API facade
    │   ├── processor.py        # Data processing service
    │   └── monitor.py          # Quality monitoring service
    │
    ├── core/                   # Core layer
    │   ├── connection/         # Connection adapters
    │   ├── protocol/           # Protocol handling
    │   ├── validation/         # Data validation
    │   └── replay/             # Recording and playback system
    │       ├── message.py      # RawMessage v2.1
    │       ├── recorder.py     # Data recorder
    │       ├── replayer.py     # Data playback
    │       └── session.py      # Session management
    │
    ├── apps/                   # Application tools
    │   ├── console.py          # Interactive console
    │   ├── recorder.py         # Game data recorder
    │   ├── replay_test.py      # Playback test tool
    │   ├── room_layout_visualizer.py  # Room layout visualizer
    │   └── terrain_validator.py       # Terrain data validator
    │
    ├── tests/                  # Test cases (111+ tests)
    └── recordings/             # Recording data directory
```

---

## Quick Start

### Requirements

- The Binding of Isaac: Repentance game (Repentance DLC) / Repentance+ IS OK
- Python 3.8+
- Dependencies:

```bash
pip install pydantic
```

### Installation Steps

#### 1. Install Game Mod

Copy the `SocketBridge` folder to the game mods directory:

```
Windows: C:\Users\<Username>\Documents\My Games\Binding of Isaac Repentance\mods\
```

Enable the SocketBridge mod in the game.

#### 2. Start Python Side

```bash
cd python
python isaac_bridge.py
```

Or use application tools:

```bash
# Interactive console
python apps/console.py

# Auto recording mode
python apps/recorder.py --auto
```

#### 3. Start Game

Launch The Binding of Isaac: Repentance, the mod will automatically connect to the Python server (default 127.0.0.1:9527).

### Verify Installation

After starting the game, the Python side should display:

```
✓ Game connected! (127.0.0.1:xxxxx)
```

---

## Application Tools Guide

All tools are located in the `python/apps/` directory.

### 1. Interactive Console (console.py)

Used to send console commands to the game.

```bash
python apps/console.py
```

**Usage:**

```
Isaac Console> giveitem c1      # Give item
Isaac Console> spawn 13         # Spawn enemy
Isaac Console> debug 3          # Enable debug info
Isaac Console> help             # Show help
Isaac Console> status           # Show connection status
Isaac Console> quit             # Exit
```

**Common Commands:**

| Command | Description |
|---------|-------------|
| `giveitem c<ID>` | Give collectible item |
| `giveitem t<ID>` | Give trinket |
| `spawn <ID>` | Spawn entity |
| `goto s.boss.0` | Jump to boss room |
| `debug 3` | Enable debug map |
| `debug 8` | Show damage numbers |

---

### 2. Game Data Recorder (recorder.py)

Record game data for playback and analysis.

```bash
# Start recorder (manual control)
python apps/recorder.py

# Auto recording mode (starts on connect)
python apps/recorder.py --auto

# List all recordings
python apps/recorder.py --list

# Clean up old recordings (keep latest 5)
python apps/recorder.py --cleanup --keep 5
```

**Runtime Hotkeys:**

| Key | Function |
|-----|----------|
| `r` | Start/stop recording |
| `p` | Pause/resume recording |
| `s` | Show current status |
| `l` | List all sessions |
| `q` | Exit |

**Command Line Arguments:**

| Argument | Description | Default |
|----------|-------------|---------|
| `--output, -o` | Output directory | `./recordings` |
| `--host` | Listen address | `127.0.0.1` |
| `--port, -p` | Listen port | `9527` |
| `--auto, -a` | Auto recording mode | off |
| `--list, -l` | List all sessions | - |
| `--cleanup` | Clean up old recordings | - |
| `--keep` | Number to keep | `10` |

**Auto Recording Behavior:**
- Auto start recording when game connects
- Pause (not stop) when game disconnects, wait for reconnection
- Only manual `r` or `q` will actually stop recording

---

### 3. Playback Test Tool (replay_test.py)

Test playback functionality of recorded data.

```bash
# Test latest session
python apps/replay_test.py

# Show first 20 messages
python apps/replay_test.py --count 20

# Test specific session
python apps/replay_test.py --session session_20260202_234038

# Show all messages (use with caution)
python apps/replay_test.py --all
```

**Output Example:**

```
Found 1 session:
  1. session_20260202_234038  Duration: 03:07  Frames: 4989

Session Info:
  Total messages: 9978
  Total frames: 4989

First 5 messages:
----------------------------------------------------------------------
[   1] frame=  684 | type=DATA  | PLAYER_POSITION, PROJECTILES, ENEMIES
[   2] frame=  684 | type=DATA  | PLAYER_POSITION, PROJECTILES, ENEMIES
----------------------------------------------------------------------
✓ Playback test completed!
```

---

### 4. Room Layout Visualizer (room_layout_visualizer.py)

Render room layout as character grid for debugging and validation.

```bash
# Live mode (continuous updates)
python apps/room_layout_visualizer.py live

# Snapshot mode (capture once when entering room)
python apps/room_layout_visualizer.py snapshot

# Compare with game screen
python apps/room_layout_visualizer.py compare
```

**Character Legend:**

| Character | Meaning |
|-----------|---------|
| `.` | Empty space/decoration |
| `#` | Rock/wall |
| `O` | Pit |
| `^` | Spike |
| `T` | Tinted rock |
| `D` | Door |
| `@` | Player position |

---

### 5. Terrain Data Validator (terrain_validator.py)

Validate terrain data correctness, distinguish between Lua-side and Python-side issues.

```bash
# Live validation mode
python apps/terrain_validator.py live

# Print raw data
python apps/terrain_validator.py dump
```

---

## Developer Guide

### Basic Data Reception

```python
import sys
sys.path.insert(0, './python')

from services.facade import SocketBridgeFacade

facade = SocketBridgeFacade()

@facade.on_data
def on_data(frame, room):
    player = facade.get_player()
    if player:
        print(f"Frame {frame}: Player at ({player.x}, {player.y})")

facade.start()
```

### Using IsaacBridge (Low-level API)

```python
from isaac_bridge import IsaacBridge

bridge = IsaacBridge()

@bridge.on("connected")
def on_connected(data):
    print("Game connected!")

@bridge.on("message")
def on_message(msg):
    print(f"Frame {msg.frame}: {msg.channels}")

@bridge.on("event")
def on_event(event):
    print(f"Event: {event.type} - {event.data}")

bridge.start()
```

### AI Control Example

```python
from services.facade import SocketBridgeFacade

facade = SocketBridgeFacade()

@facade.on_data
def ai_update(frame, room):
    player = facade.get_player()
    enemies = facade.get_enemies()

    if enemies and player:
        # Find nearest enemy
        nearest = min(enemies, key=lambda e: 
            (e.x - player.x)**2 + (e.y - player.y)**2)
        
        # Calculate movement direction (away from enemy)
        dx = player.x - nearest.x
        dy = player.y - nearest.y
        
        move_x = 1 if dx > 0 else -1 if dx < 0 else 0
        move_y = 1 if dy > 0 else -1 if dy < 0 else 0
        
        # Shoot at enemy
        shoot_x = -move_x
        shoot_y = -move_y
        
        facade.send_move_and_shoot(move_x, move_y, shoot_x, shoot_y)

facade.start()
```

### Using Recording and Playback System

```python
from core.replay import DataReplayer, ReplayerConfig, list_sessions

# List all sessions
sessions = list_sessions('./recordings')
print(f"Found {len(sessions)} sessions")

# Load and playback
config = ReplayerConfig(recordings_dir='./recordings')
replayer = DataReplayer(config)
session = replayer.load_session(sessions[0].session_id)

# Iterate all messages
for msg in replayer.iter_messages():
    print(f"Frame {msg.frame}: {msg.channels}")
    # Process message...
```

### Entity State Management

SocketBridge provides a two-layer state management mechanism:

#### State Persistence Layers

| Layer | Description | Implementation |
|-------|-------------|----------------|
| **Channel-level State** | Cache latest data for each channel | `DataProcessor._data_cache` |
| **Entity-level State** | Track entities across frames, merge states | `GameEntityState` (new in v2.1) |

#### Problem Background

Since game data collection frequencies differ (e.g., enemies collected every 5 frames), directly accessing data for a specific frame may be empty:

```python
# ❌ Problem: Enemy channel may return empty list (frame not collected)
enemies = facade.get_enemies()  # May be [], even if there are enemies in room
```

#### Solution: Stateful Entity Management

```python
from services.facade import SocketBridgeFacade, BridgeConfig

# Configure entity state management
config = BridgeConfig(
    entity_state_enabled=True,      # Enable entity state management
    enemy_expiry_frames=60,         # Enemies expire after 60 frames
    projectile_expiry_frames=30,    # Projectiles expire after 30 frames
    pickup_expiry_frames=120,       # Pickups expire after 120 frames
)

facade = SocketBridgeFacade(config)

# ✅ Use stateful version to get enemies
enemies = facade.get_enemies_stateful(max_stale_frames=5)
# Returns all enemies seen in last 5 frames, even if not collected this frame

# Get projectiles (stateful)
projectiles = facade.get_projectiles_stateful(max_stale_frames=3)
# Returns {"enemy_projectiles": [...], "player_tears": [...], "lasers": [...]}

# Get pickups (stateful)
pickups = facade.get_pickups_stateful()

# Get bombs (stateful)
bombs = facade.get_bombs_stateful()

# Get threat count
threat_count = facade.get_threat_count()  # Enemy count + enemy projectile count
```

#### How It Works

```
Frame 100: ENEMIES collected → [Enemy A, Enemy B]
Frame 101: ENEMIES not collected
Frame 102: ENEMIES not collected
Frame 103: ENEMIES not collected
Frame 104: ENEMIES not collected
Frame 105: ENEMIES collected → [Enemy A, Enemy C]  (B died, C is new)

# Call get_enemies_stateful(max_stale_frames=5) at frame 102
# Returns [Enemy A, Enemy B] ✓ (uses frame 100 cached data)

# Call get_enemies_stateful(max_stale_frames=5) at frame 105
# Returns [Enemy A, Enemy C] ✓ (latest data)
# Enemy B automatically cleaned up for exceeding 60 frames without update
```

#### Entity Lifecycle

1. **First Appearance** - Entity added to state manager, record `first_seen_frame`
2. **Update** - Update `last_seen_frame` and entity data each time channel collects
3. **Expiry Cleanup** - Entities not updated within `expiry_frames` are automatically removed
4. **Room Switch** - All entity states automatically cleared when switching rooms

#### Using EntityStateManager Directly

```python
from services.entity_state import EntityStateManager, EntityStateConfig

# Create custom entity manager
config = EntityStateConfig(
    expiry_frames=60,      # Expiry frames
    enable_history=True,   # Enable history
    max_history=10,        # Keep last 10 history records
    id_field="id",         # Entity ID field name
)

manager = EntityStateManager[EnemyData](
    name="CUSTOM_ENEMIES",
    config=config,
    id_getter=lambda e: e.id,  # Custom ID getter function
)

# Update (call every frame)
changes = manager.update(enemies_list, current_frame)
# changes = {"added": [1, 2], "updated": [3], "removed": [4]}

# Get active entities
active = manager.get_fresh(max_stale_frames=5)

# Get single entity
enemy = manager.get(entity_id=123)

# Get entity history
history = manager.get_history(entity_id=123)

# Check if entity is active
is_active = manager.is_entity_active(entity_id=123)

# Get statistics
stats = manager.get_stats()
```

#### Configuration Reference

| Entity Type | Type | Collection Frequency | Recommended Expiry Frames | Description |
|-------------|------|---------------------|--------------------------|-------------|
| Enemy | Dynamic | HIGH (every frame) | 10 | Match collection frequency, ~0.17s |
| Projectile | Dynamic | HIGH (every frame) | 5 | Fast moving, short expiry |
| Laser | Dynamic | HIGH (every frame) | 5 | Same as projectiles |
| Pickup | Dynamic | LOW (every 15 frames) | 30 | Collection interval × 2 |
| Bomb | Dynamic | LOW (every 15 frames) | 30 | Collection interval × 2 |
| Grid Entity | Static | ON_CHANGE/LOW | -1 (disabled) | Obstacle destruction is state change, not removal |

> **Design Principles**:
> - **Dynamic Entities**: Expiry frames = Collection interval × 2, ensure cross-frame stability
> - **Static Entities**: Disable auto-expiry (-1), state changes notified by game

---

## New Channel Registration Process

When adding a new data collection channel, follow these steps:

### Step 1: Define Data Schema (Pydantic)

Add data schema in `core/protocol/schema.py`:

```python
class MyNewChannelData(BaseModel):
    """My new channel data"""
    
    model_config = {"extra": "allow"}
    
    value1: float = Field(default=0.0, description="Field 1")
    value2: int = Field(default=0, description="Field 2")
    items: List[str] = Field(default_factory=list, description="List field")
```

### Step 2: Create Channel Class

Create or modify channel file in `channels/` directory:

```python
# channels/my_channel.py

from typing import Dict, Any, Optional, List
from dataclasses import dataclass
import logging

from channels.base import DataChannel, ChannelConfig, ChannelRegistry
from core.protocol.schema import MyNewChannelData
from core.validation.known_issues import ValidationIssue

logger = logging.getLogger(__name__)


@dataclass
class MyChannelData:
    """Channel data wrapper"""
    items: Dict[int, MyNewChannelData]
    
    def get_item(self, idx: int) -> Optional[MyNewChannelData]:
        return self.items.get(idx)


class MyNewChannel(DataChannel[MyChannelData]):
    """My new channel
    
    Collection frequency: MEDIUM
    Priority: 5
    """
    
    name = "MY_NEW_CHANNEL"  # Must match Lua-side channel name
    config = ChannelConfig(
        name="MY_NEW_CHANNEL",
        interval="MEDIUM",
        priority=5,
        enabled=True,
        validation_enabled=True,
    )
    
    def parse(self, raw_data: Dict[str, Any], frame: int) -> Optional[MyChannelData]:
        """Parse raw data"""
        try:
            items = {}
            
            # Handle list format [1]=..., [2]=...
            if isinstance(raw_data, dict):
                for key, value in raw_data.items():
                    try:
                        idx = int(key)
                        items[idx] = MyNewChannelData(**value)
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Failed to parse item {key}: {e}")
            
            return MyChannelData(items=items)
            
        except Exception as e:
            logger.error(f"Failed to parse {self.name}: {e}")
            return None
    
    def validate(self, data: MyChannelData) -> List[ValidationIssue]:
        """Validate data (optional)"""
        issues = []
        # Add custom validation logic
        return issues


# Register channel
ChannelRegistry.register_class(MyNewChannel)
```

### Step 3: Register Collector on Lua Side

Find **Data Collector Definition** section in `main.lua` (around line 580), add new collector:

```lua
-- ============================================================================
-- My New Channel (Custom)
-- ============================================================================
CollectorRegistry:register("MY_NEW_CHANNEL", {
    interval = "MEDIUM",  -- Collection frequency: HIGH/MEDIUM/LOW/RARE/ON_CHANGE
    priority = 5,         -- Priority: 1-10
    collect = function()
        local data = {}
        
        -- Collection data logic example
        data[1] = {
            value1 = 1.5,
            value2 = 10,
            items = {"a", "b", "c"}
        }
        
        return data
    end
})
```

#### Lua Collector Configuration Description

| Field | Type | Description |
|-------|------|-------------|
| `interval` | string | Collection frequency, see table below |
| `priority` | number | Priority 1-10, higher collected first |
| `collect` | function | Collection function, returns data table |
| `enabled` | boolean | Whether enabled (default true) |
| `hash` | function | Optional, custom change detection hash function |

#### Collection Frequency Description

| Frequency | Frame Interval | Description |
|-----------|----------------|-------------|
| `HIGH` | 1 | Collect every frame (positions, projectiles, etc.) |
| `MEDIUM` | 5 | Collect every 5 frames |
| `LOW` | 15 | Collect every 15 frames (stats, health, etc.) |
| `RARE` | 60 | Collect every 60 frames (inventory, etc.) |
| `ON_CHANGE` | -1 | Collect only when data changes |

#### Lua Helper Functions

`main.lua` provides common helper functions:

```lua
-- Vector to table
Helpers.vectorToTable(vector)  -- Returns {x=..., y=...}

-- Get all players
Helpers.getPlayers()  -- Returns player list

-- Get current room
Game():GetRoom()

-- Get room entities
Isaac.GetRoomEntities()

-- Get game time
Isaac.GetTime()
```

#### Complete Lua Collector Example

```lua
-- Collect all pickups
CollectorRegistry:register("PICKUPS", {
    interval = "LOW",
    priority = 4,
    collect = function()
        local pickups = {}
        
        for _, entity in ipairs(Isaac.GetRoomEntities()) do
            if entity.Type == EntityType.ENTITY_PICKUP then
                table.insert(pickups, {
                    id = entity.Index,
                    type = entity.Type,
                    variant = entity.Variant,
                    subtype = entity.SubType,
                    pos = Helpers.vectorToTable(entity.Position),
                    price = entity:ToPickup().Price,
                    shop_item = entity:ToPickup().IsShopItem,
                })
            end
        end
        
        return pickups
    end
})
```

### Step 4: Update Service Layer (Optional)

If you need to access the new channel via `SocketBridgeFacade`, add in `services/facade.py`:

```python
def get_my_channel_data(self) -> Optional[MyChannelData]:
    """Get my channel data"""
    channel = ChannelRegistry.get("MY_NEW_CHANNEL")
    if channel:
        return channel.get_data()
    return None
```

### Step 5: Add Tests

Add tests in `tests/` directory:

```python
# tests/test_my_channel.py

import pytest
from channels.my_channel import MyNewChannel, MyChannelData

def test_parse_valid_data():
    channel = MyNewChannel()
    raw_data = {
        "1": {"value1": 1.5, "value2": 10, "items": ["a", "b"]}
    }
    result = channel.parse(raw_data, frame=100)
    
    assert result is not None
    assert 1 in result.items
    assert result.items[1].value1 == 1.5
```

### Step 6: Integrate Entity State Management (if needed)

If the new channel contains entities that need cross-frame tracking (enemies, projectiles, etc.), integrate them into the entity state management module.

#### 6.1 Add Manager in GameEntityState

Modify `services/entity_state.py`:

```python
class GameEntityState:
    def __init__(
        self,
        # ... existing parameters ...
        my_entity_expiry: int = 30,  # New: set expiry frames based on collection frequency
    ):
        # ... existing managers ...
        
        # New: my entity state manager
        self.my_entities = EntityStateManager(
            name="MY_ENTITIES",
            config=EntityStateConfig(expiry_frames=my_entity_expiry),
            # id_getter: specify ID getter based on entity data structure
            id_getter=lambda x: x.id if hasattr(x, "id") else x.get("id", 0),
        )
    
    # New update method
    def update_my_entities(self, entities: List[Any], frame: int):
        """Update my entity state"""
        self._current_frame = frame
        self.my_entities.update(entities, frame)
    
    # New getter method
    def get_my_entities(self, max_stale_frames: int = 15) -> List[Any]:
        """Get my entities"""
        return self.my_entities.get_fresh(max_stale_frames)
    
    # Update on_room_change to add cleanup
    def on_room_change(self, new_room: int):
        # ... existing code ...
        self.my_entities.clear()  # New
    
    # Update get_stats to add statistics
    def get_stats(self) -> Dict[str, Any]:
        return {
            # ... existing fields ...
            "my_entities": self.my_entities.get_stats(),  # New
        }
```

#### 6.2 Add Configuration in BridgeConfig

Modify `services/facade.py`:

```python
@dataclass
class BridgeConfig:
    # ... existing config ...
    my_entity_expiry_frames: int = 30  # New: set based on collection frequency
```

#### 6.3 Add Update and Get Methods in SocketBridgeFacade

Modify `services/facade.py`:

```python
class SocketBridgeFacade:
    def __init__(self, configConfig] = None: Optional[Bridge):
        # ... existing code ...
        if self.config.entity_state_enabled:
            self.entity_state = GameEntityState(
                # ... existing parameters ...
                my_entity_expiry=self.config.my_entity_expiry_frames,  # New
            )
    
    def _update_entity_state(self, channels: Dict[str, ProcessedChannel], frame: int):
        # ... existing update logic ...
        
        # New: update my entities
        if "MY_NEW_CHANNEL" in channels and channels["MY_NEW_CHANNEL"].data:
            my_data = channels["MY_NEW_CHANNEL"].data
            if isinstance(my_data, list):
                self.entity_state.update_my_entities(my_data, frame)
    
    # New: getter method (stateful version)
    def get_my_entities_stateful(self, max_stale_frames: int = 15) -> List[Any]:
        """Get my entities (stateful version)"""
        if self.entity_state:
            return self.entity_state.get_my_entities(max_stale_frames)
        return []
```

#### 6.4 Expiry Frames Setting Guide

| Entity Type | Collection Frequency | Recommended Expiry Frames | Formula |
|-------------|---------------------|--------------------------|---------|
| Dynamic Entity | HIGH (every frame) | 5-10 | Collection interval × 5~10 |
| Dynamic Entity | LOW (every 15 frames) | 30 | Collection interval × 2 |
| Static Entity | ON_CHANGE | -1 (disabled) | No auto-expiry |

**Selection Basis:**
- **Dynamic Entities** (move, disappear): Enable expiry, expiry frames = Collection interval × 2
- **Static Entities** (obstacles, terrain): Disable expiry (-1), state changes notified by game

### Notes

1. **Channel names must match** - Python side `name = "MY_NEW_CHANNEL"` must be exactly the same as Lua side `CollectorRegistry:register("MY_NEW_CHANNEL", ...)`

2. **Data format conventions** - Lua tables converted to JSON, note:
   - Lua array indices start from 1
   - Use `data[1]` instead of `data[0]`
   - Nested tables converted to nested JSON objects

3. **Error handling** - Lua collector functions should be protected with `pcall`, framework has built-in error handling

4. **Performance considerations** - HIGH frequency channels avoid complex calculations, use appropriate collection frequency

---

## FAQ

### Q1: Game cannot connect to Python server

**Causes:**
- Python server not started
- Port already in use
- Firewall blocking connection
- Connection port not released (common on Windows)

**Solutions:**
```bash
# Check port usage
netstat -ano | findstr 9527

# Use different port
python apps/recorder.py --port 9528

# Ensure port matches in main.lua
local PORT = 9527

# Close previous terminal window

# Wait about 5 minutes for connection to be released, then try again
```

### Q2: ModuleNotFoundError: No module named 'xxx'

**Cause:**
Working directory incorrect or Python path issue.

**Solutions:**
```bash
# Ensure running in python directory
cd python
python apps/xxx.py

# Or run as module
python -m apps.xxx
```

### Q3: Recorded event count is 0

**Cause:**
Old version uses unsupported wildcard `event:*`.

**Solution:**
Update to latest version of `recorder.py`, use `@bridge.on("event")` to listen to all events.

### Q4: Room layout displays incorrectly

**Cause:**
Coordinate conversion formula issue (fixed in v2.1).

**Solution:**
Ensure using correct coordinate formula:
```python
GRID_SIZE = 40  # 40 pixels per cell
adjusted_tl = top_left - 40
grid_x = int((world_x - adjusted_tl.x) / GRID_SIZE)
grid_y = int((world_y - adjusted_tl.y) / GRID_SIZE)
```

### Q5: Pydantic validation error

**Cause:**
Pydantic configuration changes during v2.0 to v2.1 migration.

**Solution:**
Use new configuration method:
```python
# Old way (deprecated)
class Config:
    extra = "allow"

# New way
model_config = {"extra": "allow"}
```

### Q6: How to view raw Lua data?

**Method 1:** Use terrain validator
```bash
python apps/terrain_validator.py dump
```

**Method 2:** Print in code
```python
@bridge.on("message")
def on_message(msg):
    print(json.dumps(msg.payload, indent=2))
```

### Q7: How to switch AI/manual mode in game?

Press **F3** key in game:
- AI mode: Python controls character movement and shooting
- Manual mode: Player controls normally

### Q8: Where are recording files stored?

Stored in `python/recordings/` directory by default:
```
recordings/
├── session_20260202_234038/
│   ├── metadata.json        # Session metadata
│   └── messages_0000.jsonl.gz  # Compressed message data
```

---

## Architecture Reference

### Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│                        Game Side (Lua)                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Collector    │  │  Protocol    │  │   InputExecutor      │   │
│  │ Registry     │──│  v2.1        │──│   (Control Input)    │   │
│  │ (Collection) │  │              │  │                      │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│         │                 │                     ▲                │
│         └─────────────────┼─────────────────────┘                │
│                           │ TCP/IP :9527                         │
└───────────────────────────┼─────────────────────────────────────┘
                            │
┌───────────────────────────┼─────────────────────────────────────┐
│                           ▼                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ IsaacBridge  │──│ DataMessage  │──│   Channels           │   │
│  │ (Network)    │  │ (Protocol)   │  │   (Data Channels)   │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│         │                                      │                 │
│         ▼                                      ▼                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ Recorder     │  │   Services   │  │   Apps               │   │
│  │ (Recording)  │  │ (Facade, etc)│  │   (Applications)     │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│                                                                  │
│                        Python Side                               │
└──────────────────────────────────────────────────────────────────┘
```

### Data Channel List

| Channel Name | Frequency | Priority | Description |
|--------------|-----------|----------|-------------|
| `PLAYER_POSITION` | HIGH | 10 | Player position, velocity, orientation |
| `PLAYER_STATS` | LOW | 5 | Player stats (damage, speed, range, etc.) |
| `PLAYER_HEALTH` | ON_CHANGE | 8 | Player health |
| `PLAYER_INVENTORY` | ON_CHANGE | 3 | Player inventory |
| `ENEMIES` | HIGH | 7 | Enemy information |
| `PROJECTILES` | HIGH | 9 | Projectiles |
| `ROOM_INFO` | LOW | 4 | Room basic information |
| `ROOM_LAYOUT` | ON_CHANGE | 2 | Room layout grid |
| `BOMBS` | LOW | 5 | Bombs |
| `FIRE_HAZARDS` | LOW | 6 | Fire hazards |
| `PICKUPS` | LOW | 4 | Pickups |
| `INTERACTABLES` | LOW | 4 | Interactable entities |

### Protocol Version

Current version: **v2.1**

v2.1 new features:
- `seq` - Message sequence number
- `game_time` - Game timestamp
- `prev_frame` - Previous frame number
- `channel_meta` - Channel-level timing metadata

---

## Related Documents

- [README.md](README.md) - Chinese version
- [REFACTORING_PLAN.md](REFACTORING_PLAN.md) - Refactoring plan and progress
- [MIGRATION_GUIDE.md](MIGRATION_GUIDE.md) - v2.1 migration guide
- [KNOWN_GAME_ISSUES.md](KNOWN_GAME_ISSUES.md) - Known game issues
- [python/DATA_PROTOCOL.md](python/DATA_PROTOCOL.md) - Detailed data protocol documentation

---

## License

This project is for learning and research purposes only.

---

**Last Updated:** February 3, 2026  
**Version:** 2.1
