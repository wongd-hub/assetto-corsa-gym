# RealTimeStepper API

`RealTimeStepper` enforces consistent timing for RL training by aligning actions with observations.

## The Problem

Without a stepper:

```python
bridge.apply_action(action)  # Applied immediately
obs = bridge.latest_obs()     # Read immediately (0ms later!)
# Problem: Observation doesn't reflect action's effect yet
```

With a stepper:

```python
obs, info = stepper.step(action)
# 1. Applies action
# 2. Waits until next 10 Hz tick
# 3. Reads observation *after* action took effect
# Result: Consistent action→observation causality
```

## Usage

```python
from ac_bridge import ACBridgeLocal, RealTimeStepper

bridge = ACBridgeLocal(telemetry_hz=60, control_hz=10)
stepper = RealTimeStepper(bridge, control_hz=10)

bridge.connect()

# Reset (triggers session restart)
obs, info = stepper.reset()

# Training loop
for episode in range(100):
    action = policy(obs)
    obs, info = stepper.step(action)
    reward = compute_reward(obs, info)
    
    if done:
        obs, info = stepper.reset()

bridge.close()
```

## Methods

### `__init__(bridge, control_hz=10)`

**Args:**
- `bridge`: ACBridgeLocal instance
- `control_hz`: Control rate in Hz (default: 10)

### `step(action) -> tuple[obs, info]`

Apply action and return next observation.

**Args:**
- `action`: np.ndarray of shape (3,) with [steer, throttle, brake]
  - Or dict: `{'steer': float, 'throttle': float, 'brake': float}`

**Returns:**
- `obs`: 15-dim observation vector
- `info`: Telemetry dict with timing metadata

**Timing guarantee:**
- Action is applied for exactly `dt = 1/control_hz` seconds
- Drift correction maintains <1ms accuracy

### `reset() -> tuple[obs, info]`

Restart session and return initial observation.

Calls `bridge.reset()` which:
1. Presses button 7 (restart race)
2. Waits 2s, presses button 9 (start race)
3. Resets controls and shifts to 1st gear

### `get_stats() -> dict`

Returns timing statistics:

```python
{
    'total_steps': 10000,
    'avg_step_duration': 0.1001,  # Close to target 0.1s
    'avg_drift': 0.0003,           # <1ms drift
    'max_drift': 0.0012,
    'drift_corrections': 42        # Times drift was corrected
}
```

## Timing Details

The stepper uses a drift-correcting ticker:

```python
target_dt = 1 / control_hz  # e.g., 0.1s for 10 Hz

for tick in ticker:
    # Apply action
    bridge.apply_action(action)
    
    # Wait until next tick boundary
    ticker.sleep_until_next()  # Corrects for drift
    
    # Read observation
    obs, info = bridge.latest_obs()
```

**Drift correction:**
- Measures actual elapsed time each step
- Adjusts next sleep duration to compensate
- Maintains long-term frequency accuracy

## Action Formats

The stepper accepts multiple action formats:

```python
# NumPy array (recommended)
action = np.array([steer, throttle, brake])
obs, info = stepper.step(action)

# Dict
action = {'steer': 0.5, 'throttle': 0.8, 'brake': 0.0}
obs, info = stepper.step(action)

# Tuple/list
action = (0.5, 0.8, 0.0)
obs, info = stepper.step(action)
```

## Integration with Gym

```python
class ACEnv(gym.Env):
    def __init__(self):
        self.bridge = ACBridgeLocal(control_hz=10)
        self.stepper = RealTimeStepper(self.bridge, control_hz=10)
        # ...
    
    def step(self, action):
        obs, info = self.stepper.step(action)
        reward = self._compute_reward(obs, info)
        done = self._check_done(info)
        return obs, reward, done, False, info
    
    def reset(self):
        obs, info = self.stepper.reset()
        return obs, info
```

## Performance

Typical step timing @ 10 Hz:

- Target: 100.0ms
- Actual: 100.0-100.3ms (includes drift correction)
- Overhead: ~0.1ms for timing logic

Long-term accuracy:
- 10,000 steps should take 1000.0s ± 10ms

## See Also

- [ACBridgeLocal](bridge-local.md) - Core bridge API
- [Timing System](../systems/timing-protocol.md) - Clock and ticker details

