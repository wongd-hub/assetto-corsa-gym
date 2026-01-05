# AC Bridge API Reference

Comprehensive but concise reference for the ac-bridge Python API.

---

## Core Classes

### ACBridgeLocal

Main bridge for same-machine RL training. Polls AC telemetry in background thread, exposes latest frame via thread-safe cache.

```python
from ac_bridge import ACBridgeLocal

bridge = ACBridgeLocal(
    telemetry_hz=60,   # Background polling rate
    control_hz=10,     # Target step rate (for stepper)
    controller="vjoy", # Controller type
    device_id=1,       # vJoy device ID
    obs_dim=15         # Observation vector dimension
)
```

**Methods:**

- `connect()` - Start telemetry thread, wait for first frame
- `close()` - Stop threads, cleanup resources
- `is_connected()` - Check if telemetry available
- `latest_obs() -> (obs, info)` - Get cached latest frame (instant, non-blocking)
- `apply_action(steer, throttle, brake, clutch=0.0)` - Send control to vJoy
- `reset(wait_time=5.0)` - Restart session (buttons 7+9), reset controls, shift to 1st

**Observation Format:**

15-dim normalized float32 array:
```
[0] speed (0-300 km/h → 0-1)
[1-3] velocity x/y/z
[4-6] throttle/brake/steerAngle
[7-8] rpm/gear
[9-11] g-forces (lateral/longitudinal/vertical)
[12] avg wheel slip
[13] tyres out (0-4 → 0-1)
[14] damage indicator (binary)
```

**Info Dict Fields:**

Timing: `seq`, `t_wall`, `dt`, `dt_actual`  
Driving: `speed_kmh`, `rpm`, `gear`, `throttle`, `brake`, `steer_angle`  
Position: `position`, `velocity`, `local_velocity`, `angular_velocity`  
Track: `tyres_out`, `is_valid_lap`, `completed_laps`, `current_time`, `distance_traveled`  
Damage: `car_damage`, `bodywork_damaged`, `bodywork_critical`, `tyre_wear`, `tyre_damaged`  
Environment: `surface_grip`, `air_temp`, `road_temp`, `is_in_pit_lane`

---

### RealTimeStepper

Enforces consistent step timing for RL. Wraps ACBridgeLocal with drift-correcting ticker.

```python
from ac_bridge import ACBridgeLocal, RealTimeStepper

bridge = ACBridgeLocal(telemetry_hz=60, control_hz=10)
stepper = RealTimeStepper(bridge, control_hz=10)
bridge.connect()
```

**Methods:**

- `step(action) -> (obs, info)` - Apply action, wait for tick, return observation
- `reset() -> (obs, info)` - Trigger session reset, return initial observation
- `get_stats()` - Get timing statistics

**Action Format:**

numpy array: `[steer, throttle, brake]` or `[steer, throttle, brake, clutch]`
- steer: -1.0 (left) to 1.0 (right)
- throttle/brake/clutch: 0.0 to 1.0

---

### Ticker

Drift-correcting frequency generator. Maintains precise timing over long runs.

```python
from ac_bridge import Ticker

ticker = Ticker(hz=10)  # 10 Hz = 0.1s steps
for seq, t_wall, dt, dt_actual in ticker:
    # Execute at precise 10 Hz
    process_step()
```

**Methods:**

- `tick() -> (seq, t_wall, dt, dt_actual)` - Yield next tick
- `reset(start_seq=0)` - Reset ticker for new episode
- `get_stats()` - Get drift and jitter statistics

---

## Protocol Types

### TelemetryFrame

```python
from ac_bridge.protocol import TelemetryFrame

frame = TelemetryFrame(
    seq=42,
    t_wall=123.456,
    dt=0.1,
    dt_actual=0.0987,
    obs=np.array([...]),
    info={...}
)
```

### ControlCommand

```python
from ac_bridge.protocol import ControlCommand

cmd = ControlCommand(
    seq=42,
    steer=0.2,
    throttle=0.8,
    brake=0.0,
    clutch=0.0
)
```

### Codec

Encode/decode messages (JSON or MessagePack):

```python
from ac_bridge.protocol import Message, Codec

msg = Message(type=MessageType.TELEMETRY, payload={...})
bytes_data = Codec.encode(msg, format='json')  # or 'msgpack'
decoded = Codec.decode(bytes_data, format='json')
```

---

## Usage Patterns

### Pattern 1: Basic Training Loop

```python
from ac_bridge import ACBridgeLocal

bridge = ACBridgeLocal(telemetry_hz=60, control_hz=10)
bridge.connect()

for episode in range(1000):
    bridge.reset()  # Restart session
    
    for step in range(100):
        obs, info = bridge.latest_obs()
        action = policy(obs)  # Your RL policy
        bridge.apply_action(*action)
        time.sleep(0.1)  # 10 Hz

bridge.close()
```

### Pattern 2: Gym Environment (Recommended)

```python
from ac_bridge import ACBridgeLocal, RealTimeStepper
import gymnasium as gym

class AssettoCorsa_v0(gym.Env):
    def __init__(self):
        self.bridge = ACBridgeLocal(telemetry_hz=60, control_hz=10)
        self.stepper = RealTimeStepper(self.bridge, control_hz=10)
        self.bridge.connect()
        
        self.observation_space = gym.spaces.Box(-1, 1, (15,), np.float32)
        self.action_space = gym.spaces.Box(
            np.array([-1, 0, 0]), np.array([1, 1, 1]), np.float32
        )
    
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        obs, info = self.stepper.reset()
        return obs, info
    
    def step(self, action):
        obs, info = self.stepper.step(action)  # Handles timing
        reward = self._compute_reward(obs, info)
        done = self._is_done(info)
        return obs, reward, done, False, info
    
    def _compute_reward(self, obs, info):
        reward = info['speed_kmh'] / 100.0
        if info['tyres_out'] > 2:
            reward -= 10.0
        return reward
    
    def _is_done(self, info):
        return info['tyres_out'] >= 4 or info['bodywork_critical']
    
    def close(self):
        self.bridge.close()
```

### Pattern 3: Cloud Training (Actor-Learner)

```python
# Windows (actor)
from ac_bridge import ACBridgeLocal

bridge = ACBridgeLocal(telemetry_hz=60, control_hz=10)
bridge.connect()

while training:
    obs, info = bridge.latest_obs()
    action = local_policy(obs)  # Inference locally
    bridge.apply_action(*action)
    
    # Batch transitions and send to cloud
    transitions.append((obs, action, reward, next_obs, done))
    if len(transitions) >= 100:
        send_to_cloud(transitions)
        transitions.clear()
```

---

## Performance

- **Telemetry polling:** 60 Hz background thread
- **Control latency:** 3-8ms (vJoy)
- **Step timing accuracy:** <1ms drift over 1000 steps
- **Observation overhead:** ~0.1ms (cached)

---

## Error Handling

```python
bridge = ACBridgeLocal()
bridge.connect()

try:
    obs, info = bridge.latest_obs()
except RuntimeError:
    # AC not connected or no telemetry available
    pass

# Always cleanup
bridge.close()
```

---

## CLI Commands

Quick reference for terminal usage:

```bash
# Main bridge loop (monitoring)
uv run ac-bridge run --hz 10

# Test telemetry reading
uv run ac-bridge test-telemetry --hz 10 --duration 30

# Test control output
uv run ac-bridge test-control

# Full integration test
uv run ac-bridge smoke-test --duration 10

# Reset session
uv run ac-bridge reset

# Stream to cloud
uv run ac-bridge cloud --uri ws://your-server:8765
```

---

## Thread Safety

`ACBridgeLocal` is thread-safe:
- Background thread polls telemetry
- Main thread calls `latest_obs()` (reads from cache with lock)
- Control calls are synchronous (vJoy is not thread-safe)

**Safe:** Multiple `latest_obs()` calls from different threads  
**Unsafe:** Multiple `apply_action()` calls (use single control thread)

---

## Timing Guarantees

- **Ticker:** Maintains target frequency with drift correction
- **dt_actual:** Actual time since last frame (use for physics-based rewards)
- **seq:** Monotonic sequence number (detect dropped frames)

If `seq` jumps (e.g., 42→44), one frame was dropped. This is rare but possible under heavy load.

---

## Customization

### Custom Observation Space

Edit `ACBridgeLocal._read_and_process_telemetry()` to change observation vector:

```python
obs = np.array([
    # Your custom features
    info['speed_kmh'] / 300.0,
    info['distance_traveled'] / 10000.0,
    # ... add more fields
], dtype=np.float32)
```

### Custom Reset Behavior

Modify `ACBridgeLocal.reset()` to change button sequence or wait times.

---

## Attribution

Based on:
- [DIY-DirectDrive](https://github.com/JanBalke420/DIY-DirectDrive) - Shared memory structures
- [assetto_corsa_gym](https://github.com/dasGringuen/assetto_corsa_gym) - vJoy control patterns

---

## Version

ac-bridge v0.2.0

