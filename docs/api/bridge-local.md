# ACBridgeLocal API

`ACBridgeLocal` is the main interface for interacting with Assetto Corsa on the same machine.

## Overview

```python
from ac_bridge import ACBridgeLocal

bridge = ACBridgeLocal(
    telemetry_hz=60,       # Background telemetry polling rate
    control_hz=10,          # Target RL step rate
    controller="vjoy",      # Controller type (only "vjoy" currently)
    device_id=1,            # vJoy device ID
    obs_dim=15,             # Observation vector dimension
    smoothing_config=None   # Action smoothing config (None = moderate default)
)
```

## Architecture

```
┌─────────────────────────────────────────┐
│         ACBridgeLocal                    │
│                                          │
│  ┌──────────────────────────────────┐   │
│  │  Background Telemetry Thread     │   │
│  │  - Polls AC shared memory @ 60Hz │   │
│  │  - Enriches with timing metadata │   │
│  │  - Caches latest snapshot        │   │
│  └──────────────────────────────────┘   │
│                                          │
│  ┌──────────────────────────────────┐   │
│  │  Main Thread                      │   │
│  │  - latest_obs() → instant read   │   │
│  │  - apply_action() → smoothed     │   │
│  │  - reset() → session restart     │   │
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

## Methods

### `connect()`

Starts the bridge:

- Spawns background telemetry polling thread
- Initializes vJoy controller
- Verifies AC shared memory is accessible

```python
bridge.connect()
# Raises RuntimeError if AC is not running
```

### `close()`

Cleanly shuts down the bridge:

- Stops telemetry thread
- Resets vJoy controls to neutral
- Releases resources

```python
bridge.close()
# Always call this when done
```

### `latest_obs() -> tuple[np.ndarray, dict]`

Returns the latest cached telemetry observation.

**Returns:**

- `obs` (np.ndarray): Normalized 15-dim observation vector
- `info` (dict): Full telemetry dict with 40+ fields

**Observation Vector (15-dim):**

```python
[
    speed_normalized,      # 0-1 (0-300 km/h)
    rpm_normalized,        # 0-1 (0-8000 RPM)
    gear_normalized,       # 0-1 (0-6)
    steering_angle_norm,   # -1 to 1
    throttle,              # 0-1
    brake,                 # 0-1
    avg_wheel_slip,        # 0-1
    body_damage_norm,      # 0-1
    avg_tyre_wear,         # 0-1
    lateral_accel,         # -1 to 1 (±3g)
    longitudinal_accel,    # -1 to 1 (±3g)
    yaw_rate,              # -1 to 1
    track_position,        # 0-1 (normalized lap distance)
    tyres_out_norm,        # 0-1 (0-4 tyres)
    velocity_y_norm        # -1 to 1 (vertical velocity)
]
```

**Info Dict Fields:**

See [Telemetry System](../systems/telemetry.md) for complete field list.

**Timing Metadata:**

Every observation includes:

```python
info['seq']         # Sequence number
info['t_wall']      # Wall clock time (perf_counter)
info['dt']          # Target dt (e.g., 0.1s for 10 Hz)
info['dt_actual']   # Actual time since last frame
```

**Example:**

```python
obs, info = bridge.latest_obs()

print(f"Speed: {info['speed_kmh']:.1f} km/h")
print(f"Observation shape: {obs.shape}")  # (15,)
print(f"Seq: {info['seq']}, dt: {info['dt_actual']:.3f}s")
```

### `apply_action(steer, throttle, brake, clutch=0.0)`

Applies control action to vJoy with optional smoothing.

**Args:**

- `steer` (float): -1.0 (left) to 1.0 (right)
- `throttle` (float): 0.0 to 1.0
- `brake` (float): 0.0 to 1.0
- `clutch` (float): 0.0 to 1.0 (optional)

**Smoothing (enabled by default):**

1. Rate limiting (max delta per step)
2. EMA filtering (removes noise)
3. Asymmetric pedal dynamics
4. Hard clamps (safety)

See [Action Smoothing](action-smoothing.md) for details.

**Example:**

```python
# Raw policy output (can be noisy/jerky)
raw_action = policy(obs)  # e.g., [0.8, 1.0, 0.0]

# Bridge applies smoothing automatically
bridge.apply_action(
    steer=raw_action[0],
    throttle=raw_action[1],
    brake=raw_action[2]
)
```

### `reset(wait_time=5.0) -> None`

Triggers full session restart sequence:

1. Press vJoy button 7 (restart race)
2. Wait 2 seconds
3. Press vJoy button 9 (start race)
4. Wait remaining time
5. Reset all controls to neutral
6. Shift to 1st gear
7. Reset smoother state
8. Reset telemetry ticker

**Args:**

- `wait_time` (float): Total wait time after button 7 press (default: 5s)

**Example:**

```python
bridge.reset(wait_time=3.0)  # Faster reset
# AC will restart race and be ready after 3 seconds
```

**Note:** Button 7 and 9 must be mapped in AC to:
- Button 7 → Restart session
- Button 9 → Start race

### `get_smoother_stats() -> dict`

Returns action smoothing statistics.

**Returns:**

```python
{
    'step_count': 1000,
    'avg_steer_delta': 0.087,
    'avg_throttle_delta': 0.045,
    'avg_brake_delta': 0.032,
    'config': {
        'rate_limiting': True,
        'ema_smoothing': True,
        'max_steer_delta': 0.15
    }
}
```

Empty dict `{}` if smoothing is disabled.

## Usage Patterns

### Pattern 1: Direct Use (Manual Stepping)

```python
bridge = ACBridgeLocal(control_hz=10)
bridge.connect()

for step in range(1000):
    obs, info = bridge.latest_obs()
    action = policy(obs)
    bridge.apply_action(*action)
    time.sleep(0.1)  # Manual 10 Hz timing

bridge.close()
```

### Pattern 2: With RealTimeStepper (Recommended)

```python
from ac_bridge import ACBridgeLocal, RealTimeStepper

bridge = ACBridgeLocal(control_hz=10)
stepper = RealTimeStepper(bridge, control_hz=10)

bridge.connect()

obs, info = stepper.reset()
for step in range(1000):
    action = policy(obs)
    obs, info = stepper.step(action)  # Automatic timing

bridge.close()
```

See [RealTimeStepper](stepper.md) for details.

### Pattern 3: Gymnasium Environment

```python
import gymnasium as gym
from ac_bridge import ACBridgeLocal, RealTimeStepper

class ACEnv(gym.Env):
    def __init__(self):
        super().__init__()
        self.bridge = ACBridgeLocal(control_hz=10)
        self.stepper = RealTimeStepper(self.bridge, control_hz=10)
        
        self.observation_space = gym.spaces.Box(
            low=-1, high=1, shape=(15,), dtype=np.float32
        )
        self.action_space = gym.spaces.Box(
            low=np.array([-1, 0, 0]),
            high=np.array([1, 1, 1]),
            dtype=np.float32
        )
    
    def reset(self, **kwargs):
        if not self.bridge.is_connected:
            self.bridge.connect()
        obs, self.info = self.stepper.reset()
        return obs, self.info
    
    def step(self, action):
        obs, self.info = self.stepper.step(action)
        reward = self._compute_reward(obs, self.info)
        done = self._check_done(self.info)
        truncated = False
        return obs, reward, done, truncated, self.info
    
    def close(self):
        self.bridge.close()
```

## Configuration

### Telemetry Rate

```python
# Higher rate = more responsive, more CPU
bridge = ACBridgeLocal(telemetry_hz=120)  # 120 Hz polling

# Lower rate = less CPU, slightly delayed
bridge = ACBridgeLocal(telemetry_hz=30)   # 30 Hz polling
```

**Recommendation:** 60 Hz is a good balance for 10 Hz RL.

### Control Rate

```python
# Slower RL steps = more exploration
bridge = ACBridgeLocal(control_hz=5)   # 5 Hz (200ms per step)

# Faster RL steps = more reactive
bridge = ACBridgeLocal(control_hz=20)  # 20 Hz (50ms per step)
```

**Recommendation:** 10 Hz is standard for racing RL.

### Action Smoothing

```python
from ac_bridge import get_aggressive_config, get_no_smoothing_config

# More responsive (advanced policies)
bridge = ACBridgeLocal(smoothing_config=get_aggressive_config())

# Disable smoothing (debugging only)
bridge = ACBridgeLocal(smoothing_config=get_no_smoothing_config())
```

See [Action Smoothing](action-smoothing.md) for all options.

## Thread Safety

`ACBridgeLocal` is **thread-safe** for reading telemetry:

- ✅ Multiple threads can call `latest_obs()` simultaneously
- ✅ Telemetry polling runs in background thread
- ❌ Only one thread should call `apply_action()` (control is not thread-safe)

## Performance

Typical latencies on modern hardware:

- `latest_obs()`: <0.1ms (reads cached snapshot)
- `apply_action()`: 3-8ms (vJoy + smoothing)
- Background telemetry: ~0.5ms per poll @ 60 Hz

Total RL step overhead: ~5-10ms

## Error Handling

```python
# AC not running
try:
    bridge.connect()
except RuntimeError as e:
    print(f"AC not running: {e}")

# vJoy error (recovers automatically)
bridge.apply_action(0.5, 1.0, 0.0)
# Logs warning but doesn't crash

# Clean shutdown
try:
    # ... training loop ...
finally:
    bridge.close()  # Always close
```

## See Also

- [RealTimeStepper](stepper.md) - For consistent RL timing
- [Action Smoothing](action-smoothing.md) - Smoothing configuration
- [Telemetry System](../systems/telemetry.md) - Field descriptions

