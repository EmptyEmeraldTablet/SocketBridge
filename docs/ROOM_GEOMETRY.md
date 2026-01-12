# Room Geometry Analysis - Wall and Grid Dimensions

> Created: 2026-01-12  
> Updated: 2026-01-12

## Key Discovery

**Documented room size (13×7) = API grid dimensions (15×9) - 2**

```
API returns: 15 × 9 (including 1-tile walls on all sides)
Documented:  13 × 7 (internal playable area, excluding walls)

Formula:
  internal_width  = grid_width  - 2  # Remove left + right walls
  internal_height = grid_height - 2  # Remove top + bottom walls

Example:
  15 - 2 = 13  ✓
  9 - 2 = 7    ✓
```

## Room Shape Dimensions

| Shape | Name | API Grid | Internal | grid_size | Internal Tiles |
|-------|------|----------|----------|-----------|----------------|
| 0 | normal | 13×7 | 11×5 | 40 | 55 |
| 1 | closet_h | 15×9 | 13×7 | 135 | 91 |
| 2 | closet_v | 15×9 | 13×7 | 135 | 91 |
| 3 | tall | 15×16 | 13×14 | 40 | 182 |
| 4 | tall_tight | 15×16 | 13×14 | 40 | 182 |
| 5 | wide | 28×9 | 26×7 | 40 | 182 |
| 6 | wide_tight | 28×9 | 26×7 | 252 | 182 |
| 7 | large | 28×16 | 26×14 | 40 | 364 |
| 8-11 | L1-L4 | 28×16 | 26×14 | 40 | 364 |

**Note**: All room shapes maintain consistent **physical dimensions** (in pixels) regardless of grid resolution.

## Physical Room Dimensions

### Standard Room (Shape 0, 13×7)
```
Internal tiles: 11 × 5 = 55 tiles
Grid size: 40 px
Physical size: 440 × 200 px

API grid: 13 × 7 = 91 tiles
With walls: 520 × 280 px
```

### Closet Room (Shape 1-2, 13×3 internal)
```
Internal tiles: 11 × 1 = 11 tiles
Grid size: 135 px
Physical size: 1485 × 135 px

API grid: 15 × 9 = 135 tiles
With walls: 2025 × 1215 px

Observation: Closet uses larger grid_size (135 vs 40) to maintain
same physical room size while having fewer internal tiles.
```

### Wide Room (Shape 5-6, 26×7 internal)
```
Internal tiles: 24 × 5 = 120 tiles
Grid size: 40/252 px
Physical size: 960 × 200 px

API grid: 28 × 9 = 252 tiles
With walls: 1120 × 280 px
```

## grid_size Calculation Formula

```
grid_size = total_pixel_width / grid_width

Where:
  total_pixel_width = documented_width × internal_tile_size (40)
                    = 13 × 40 = 520 (for normal room)

Examples:
  Normal (13×7):     grid_size = 520 / 13 = 40
  Closet (13×7):     grid_size = 520 / 13 = 40 (internal)
                     But API returns 15×9 with grid_size = 135
                     Because: 2025 / 15 = 135
  
  Wide Tight (26×7): grid_size = 1040 / 28 = 37.14 ≈ 40 (approx)
                     Actual: 252 (as observed)

Key Insight: grid_size scales to maintain consistent physical room size
```

## Wall Detection

### Boundary Walls
```
Position: gx ∈ {0, grid_width-1} OR gy ∈ {0, grid_height-1}

For 15×9 grid:
  Left wall:   gx = 0,  gy = 0..8
  Right wall:  gx = 14, gy = 0..8
  Top wall:    gy = 0,  gx = 0..14
  Bottom wall: gy = 8,  gx = 0..14
```

### Collision Values (from ROOM_LAYOUT.grid)
```
collision = 4 → GridType 16 (方块/Block)
collision = 5 → GridType 16 (Block, different state)
collision = 0 → No collision (web, pit, etc.)
```

### Observed Wall Patterns

**Frame 1799 (Shape 1, Closet)**:
```
Grid: 15×9, grid_size=135
Walls found at: (2,0), (2,3), (4,2)
Type: 16, Collision: 4

Note: Wall positions don't match expected edge pattern.
This may be due to:
1. Internal obstacles (not boundary walls)
2. Different wall layout for closet rooms
3. Data recording artifact
```

## Coordinate System

### Pixel to Grid Conversion
```
gx = floor(pixel_x / grid_size)
gy = floor(pixel_y / grid_size)

Example (grid_size=135):
  pixel (320, 380) → grid (2, 2)
  pixel (840, 164) → grid (6, 1)
```

### Room Offset
```
top_left from API: (60, 140)
bottom_right from API: (580, 420)

For 15×9, grid_size=135:
  Expected: (0,0) to (2025, 1215)
  Actual:   (60, 140) to (580, 420)
  
The API returns grid-relative coordinates, not absolute room coordinates.

To get absolute position:
  absolute_x = top_left.x + grid_x × grid_size
  absolute_y = top_left.y + grid_y × grid_size
```

## Implications for AI

### 1. Boundary Checking
```python
# Current (incorrect):
if position.x < 0 or position.x > grid_width * grid_size:
    return False

# Correct:
if position.x < grid_size or position.x > (grid_width - 1) * grid_size:
    return False  # Account for walls
```

### 2. Playable Area Calculation
```python
def get_playable_bounds(grid_width, grid_height, grid_size):
    """Calculate playable area excluding walls"""
    playable_left = grid_size
    playable_right = (grid_width - 1) * grid_size
    playable_top = grid_size
    playable_bottom = (grid_height - 1) * grid_size
    return (playable_left, playable_right, playable_top, playable_bottom)
```

### 3. Room Shape Handling
```python
def get_internal_area(room_shape, grid_width, grid_height):
    """Get internal playable area based on room shape"""
    if room_shape in [0, 3, 4, 5, 7]:  # Normal shapes
        return (grid_width - 2, grid_height - 2)
    elif room_shape in [8, 9, 10, 11]:  # L-shaped
        # L-shaped rooms have VOID areas
        return calculate_l_shape_internal(grid_width, grid_height, room_shape)
    else:
        # Closet variants - complex layout
        return (grid_width - 2, grid_height - 2)
```

## Test Data Verification

From `test_frames.json`:

| Frame | Shape | Grid | Internal | Playable Tiles |
|-------|-------|------|----------|----------------|
| 1799 | 1 (closet_h) | 15×9 | 13×7 | 91 |
| 2639 | 6 (wide_tight) | 28×9 | 26×7 | 182 |

**Verification**:
- 15 - 2 = 13 ✓
- 9 - 2 = 7 ✓
- 28 - 2 = 26 ✓
- 9 - 2 = 7 ✓

## Issues and Notes

### 1. Wall Position Anomaly
Some test frames show walls at non-edge positions (e.g., (2,0), (2,3), (4,2)).
This needs further investigation to determine if it's:
- Internal obstacles
- Different wall layout for specific room shapes
- Data collection artifact

### 2. Closet Room Complexity
Closet rooms (shape 1-2) use grid_size=135 instead of 40, meaning:
- Fewer internal tiles (13×3 vs 13×7)
- Same physical room size
- Different obstacle density

### 3. L-Shaped Room VOID Detection
For L-shaped rooms (shape 8-11), the VOID area calculation depends on:
- Which quadrant is missing
- The internal area formula

```python
# L1 (bottom-right missing):
internal = (0..12, 0..6) + (13..27, 0..6) + (0..12, 7..13)
VOID = (13..27, 7..13)
```

## Recommendations

### 1. Update Boundary Checking
Modify `is_in_bounds()` to use:
```python
margin = grid_size  # 1-tile margin for walls
```

### 2. Add Internal Area Calculation
Create utility function to calculate playable area:
```python
def calculate_playable_area(room_info, room_layout):
    """Calculate actual playable area excluding walls and VOID"""
    width = room_info.grid_width
    height = room_info.grid_height
    shape = room_info.room_shape
    
    # Base internal area (excluding walls)
    internal_w = width - 2
    internal_h = height - 2
    
    # Adjust for L-shaped rooms
    if shape in [8, 9, 10, 11]:
        void_area = calculate_l_shape_void(shape, width, height)
        internal_w, internal_h = adjust_for_void(internal_w, internal_h, void_area)
    
    return internal_w, internal_h
```

### 3. Collect More L-Shaped Room Data
Current test data lacks L-shaped room samples (shape 8-11).
Need to collect additional test frames for VOID area verification.

## Related Files

- `docs/ROOM_INFO_ANALYSIS.md` - Room info field analysis
- `docs/ROOM_LAYOUT_DEBUG_SUMMARY.md` - Debug issue summary
- `python/test_frames.json` - Extracted test frames
- `main.lua:763-793` - ROOM_INFO collection
- `main.lua:796-1000` - ROOM_LAYOUT collection
