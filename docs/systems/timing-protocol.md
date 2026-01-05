# Timing & Protocol

## Timing System

AC Bridge includes high-precision timing for stable RL training.

### MonotonicClock

Wraps `time.perf_counter()` for consistent, monotonic time:

```python
from ac_bridge import MonotonicClock

clock = MonotonicClock()
start = clock.now()  # High-resolution timestamp
# ... do work ...
elapsed = clock.now() - start
```

### Ticker

Drift-correcting frequency generator for consistent loop timing:

```python
from ac_bridge import Ticker

ticker = Ticker(hz=10)  # 10 Hz = 100ms per tick

for tick_info in ticker:
    # Do work
    print(f"Tick {tick_info['seq']}: dt={tick_info['dt_actual']:.3f}s")
    
    # Ticker automatically corrects drift
    # Long-term frequency is maintained at exactly 10 Hz
```

**Drift Correction:**

```python
# Without correction (naive sleep):
for i in range(1000):
    do_work()
    time.sleep(0.1)  # Actual: 0.1002s per iteration
# Total: 1000 * 0.1002 = 100.2s (200ms drift!)

# With Ticker (drift correction):
ticker = Ticker(hz=10)
for tick_info in ticker:
    do_work()
# Total: exactly 100.0s (±1ms)
```

### Integration

The stepper and bridge use `Ticker` internally:

```python
# In RealTimeStepper.step():
ticker = Ticker(hz=control_hz)
for tick in ticker:
    bridge.apply_action(action)
    obs, info = bridge.latest_obs()
    # Add timing metadata
    info['seq'] = tick['seq']
    info['t_wall'] = tick['t_wall']
    info['dt'] = tick['dt']
    info['dt_actual'] = tick['dt_actual']
```

## Protocol

### Message Types

AC Bridge defines typed message schemas for communication:

```python
from ac_bridge import TelemetryFrame, ControlCommand, Transition

# Telemetry
frame = TelemetryFrame(
    seq=123,
    t_wall=45.67,
    speed_kmh=145.3,
    rpm=5420,
    # ... 40+ fields
)

# Control
cmd = ControlCommand(
    seq=123,
    steer=0.5,
    throttle=0.8,
    brake=0.0
)

# Transition (for actor-learner)
trans = Transition(
    obs=np.array([...]),
    action=np.array([...]),
    reward=1.0,
    done=False,
    info={'speed': 145.3}
)
```

### Codec

Supports JSON and MessagePack:

```python
from ac_bridge import Codec

codec = Codec(format='json')  # or 'msgpack'

# Encode
data = codec.encode(frame)

# Decode
frame = codec.decode(data, TelemetryFrame)
```

MessagePack is 3-5x faster and more compact than JSON for high-frequency streaming.

## Timing Metadata

Every telemetry frame includes:

- **seq** (int): Sequence number (monotonically increasing)
- **t_wall** (float): Wall clock time in seconds (perf_counter)
- **dt** (float): Target delta time (e.g., 0.1s for 10 Hz)
- **dt_actual** (float): Actual time since last frame

This enables:
- Detecting dropped frames (`seq` gaps)
- Measuring loop latency (`dt_actual` vs `dt`)
- Synchronizing distributed components (`t_wall`)

## See Also

- [Cloud Setup](../advanced/cloud-setup.md) - WebSocket streaming
- [Advanced Protocol](../advanced/protocol.md) - Message batching

