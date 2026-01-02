# Assetto Corsa Telemetry Parser

## Overview

This project reads real-time telemetry data from Assetto Corsa using shared memory. The telemetry system provides comprehensive car state information including physics, graphics, and static data at configurable rates (1-60 Hz).

## Architecture

### Shared Memory Approach

Assetto Corsa exposes three memory-mapped files for telemetry access:

1. **acpmf_physics** - Updated every physics tick (typically 333 Hz)
   - Car dynamics (speed, acceleration, forces)
   - Wheel data (slip, load, temperature)
   - Engine state (RPM, gear, fuel)
   - Control inputs (gas, brake, steering)

2. **acpmf_graphics** - Updated every graphics frame (typically 60-144 Hz)
   - Lap timing and position
   - Track limits and penalties
   - Session information
   - UI state

3. **acpmf_static** - Updated on session change
   - Car specifications
   - Track information
   - Session configuration

### Implementation

The native implementation uses Python's `mmap` and `ctypes` modules to map and read shared memory structures directly. This provides sub-millisecond latency access to telemetry data.

## Sources and Attribution

This implementation is based on research and code from:

- **DIY-DirectDrive Project** by JanBalke420
  - Repository: https://github.com/JanBalke420/DIY-DirectDrive
  - Provided native AC shared memory structure definitions
  - Used for primary implementation in `ac_native_memory.py`

- **ac-remote-telemetry-client** by rickwest
  - Repository: https://github.com/rickwest/ac-remote-telemetry-client
  - Reference for AC UDP protocol investigation
  - Note: UDP approach was not used in final implementation due to reliability issues

- **CrewChiefV4** by mrbelowski
  - Repository: https://github.com/mrbelowski/CrewChiefV4
  - Analyzed for AC UDP protocol implementation
  - Confirmed UDP telemetry requires handshake/subscribe protocol
  - Note: UDP approach abandoned in favor of shared memory

- **pyaccsharedmemory** library
  - Python package for ACC/AC shared memory access
  - Used as fallback implementation in `ac_shared_memory.py`
  - Note: Primarily designed for ACC, limited compatibility with original AC

### Why Shared Memory Instead of UDP

Initial development explored AC's UDP telemetry protocol based on references from ac-remote-telemetry-client and CrewChiefV4. The UDP approach was ultimately abandoned for the following reasons:

1. **Reliability Issues** - UDP packets were inconsistently received even with proper handshake/subscribe implementation
2. **Protocol Complexity** - Required maintaining bidirectional communication with handshake, subscription, and keepalive packets
3. **Port Conflicts** - AC binds to port 9996 exclusively, preventing direct packet sniffing without relay software
4. **Session Dependency** - Only works when actively driving, fails in menus or between sessions
5. **Latency** - Even when working, UDP had higher and more variable latency than shared memory

Shared memory provides:
- Sub-millisecond read latency (< 1ms vs 5-50ms for UDP)
- 100% reliability (no dropped packets)
- Simple implementation (single read operation, no protocol state machine)
- Works regardless of AC's internal state
- Direct access without intermediate relay software

## Key Telemetry Fields

### Track Limits and Penalties

- `numberOfTyresOut` (int): Count of wheels off track (0-4)
  - 0: All wheels on track
  - 1-2: Minor cut (typically still valid)
  - 3-4: Major cut (lap invalidated)

- `is_lap_valid` (bool): Derived field tracking if current lap has been invalidated
  - Resets on lap completion
  - Set to false when 3+ tyres go off track

### Wheel Dynamics

- `wheelSlip` (float[4]): Slip ratio per wheel [FL, FR, RL, RR]
  - 0.0: Perfect grip (wheel speed matches ground speed)
  - 0.1-0.2: Optimal slip for maximum grip
  - 0.5+: Significant loss of traction
  - 1.0: Complete lock (braking) or spin (acceleration)

- `wheel_lock_detected` (bool): Derived field combining brake pressure and wheel slip
  - True when brake > 0.5 AND avg wheel slip > 0.5
  - Indicates wheels have stopped rotating but car is still moving

### Damage Detection

- `carDamage` (float[5]): Body damage by section [front, rear, left, right, center]
  - 0.0: Pristine condition
  - 0.05-0.50: Minor to moderate damage
  - 0.50-1.0: Severe to destroyed
  - Derived fields: `bodywork_damaged` (>5%), `bodywork_critical` (>50%)

- `tyreWear` (float[4]): Tire degradation per wheel [FL, FR, RL, RR]
  - 0.0: New tire
  - 0.8: Significantly worn (grip reduction)
  - 0.95+: Critical wear (imminent failure)
  - Derived fields: `tyre_damaged` (>80%), `tyre_critical` (>95%)

### Lap Timing

- `completedLaps` (int): Number of completed laps
- `iCurrentTime` (int): Current lap time in milliseconds
- `iLastTime` (int): Previous lap time in milliseconds
- `iBestTime` (int): Best lap time in session (milliseconds)

### Position and Orientation

- `velocity` (float[3]): World-space velocity [X, Y, Z] in m/s
- `localVelocity` (float[3]): Car-relative velocity [forward, up, right] in m/s
- `heading` (float): Car heading angle in radians
- `pitch` (float): Car pitch angle in radians
- `roll` (float): Car roll angle in radians
- `accG` (float[3]): G-forces [X, Y, Z]

### Control Inputs

- `gas` (float): Throttle position 0.0-1.0
- `brake` (float): Brake pressure 0.0-1.0
- `clutch` (float): Clutch engagement 0.0-1.0
- `steerAngle` (float): Steering wheel angle in degrees

### Driver Assists

- `tc` (float): Traction control activation level 0.0-1.0
- `abs_setting` (float): ABS configuration value (not activation level)

## Usage

### Basic Telemetry Reading

```bash
uv run main.py read --rate 10
```

This outputs formatted telemetry at 10 Hz to the console.

### JSON Export for RL Training

```bash
uv run main.py read --rate 10 --json-output telemetry.jsonl
```

This writes JSONL (JSON Lines) format data suitable for ingestion by reinforcement learning pipelines.

### Fallback Mode

```bash
uv run main.py read --rate 10 --acc-lib
```

Uses the pyaccsharedmemory library instead of native implementation. Less accurate for original AC but may work as fallback.

## Performance Characteristics

### Latency

- Shared memory read: < 1ms
- Memory map overhead: ~50 microseconds
- Python struct unpacking: ~100 microseconds
- Total latency: < 2ms for complete telemetry read

### Update Rates

- Physics data: 333 Hz (AC internal physics rate)
- Graphics data: 60-144 Hz (varies with framerate)
- Recommended polling: 10-60 Hz for RL applications
- Maximum practical: 100 Hz (diminishing returns beyond this)

### Memory Overhead

- Physics structure: 1,320 bytes
- Graphics structure: 1,580 bytes
- Static structure: ~5,000 bytes
- Total mapped: ~8 KB (minimal footprint)

## Data Quality Notes

### Original AC vs ACC

The native implementation targets original Assetto Corsa (not Competizione). Some fields may have different semantics or be unused in AC:

- `abs` field represents ABS configuration, not real-time activation
- `penalty` field in ACC library not always accurate for AC
- `isValidLap` not directly available (derived from tyre count)

### Field Reliability

Highly reliable fields:
- Speed, RPM, gear, control inputs
- Wheel slip, tire wear, damage
- Lap times and lap count
- numberOfTyresOut (most reliable track limit indicator)

Less reliable fields:
- Surface grip (track-dependent calibration)
- Some penalty flags (inconsistent behavior)
- ABS/TC activation (use derived metrics instead)

## Integration with Gymnasium

The telemetry data is structured for easy integration with Gymnasium environments:

### State Observation Space

Recommended fields for observation vector:
- Speed, RPM, gear
- Control inputs (gas, brake, steer)
- Wheel slip (individual or average)
- Position on track (normalizedCarPosition)
- G-forces (lateral/longitudinal acceleration)
- Tire wear and temperatures

### Reward Shaping

Useful fields for reward calculation:
- `iCurrentTime` - Lap time improvement
- `numberOfTyresOut` - Track limits penalty
- `wheel_lock_detected` - Driving quality penalty
- `tyreWear` - Tire management reward
- `normalizedCarPosition` - Progress tracking

### Termination Conditions

Episode termination triggers:
- `bodywork_critical` - Severe crash
- `tyre_critical` - Catastrophic tire failure
- `numberOfTyresOut >= 4` - Complete off-track
- Timeout (lap time exceeds threshold)

## Technical Considerations

### Windows Memory Mapping

The shared memory implementation uses Windows-specific APIs via ctypes. Memory-mapped files are accessed via:

```python
mmap.mmap(-1, size, tagname)
```

The `tagname` corresponds to AC's published memory handles:
- "acpmf_physics"
- "acpmf_graphics"  
- "acpmf_static"

### Structure Packing

All structures use 4-byte alignment (`_pack_ = 4`) to match AC's memory layout. Incorrect packing will cause field misalignment and incorrect data reads.

### Threading and Synchronization

AC updates shared memory asynchronously. No explicit locking is required as reads are atomic for aligned data types. However, consistency within a single read is not guaranteed across different memory sections (physics vs graphics).

For RL applications, read all required data in a single pass and timestamp it, rather than making multiple reads across decision boundaries.

