# Assetto Corsa Gym Bridge

> [!CAUTION]
> This repo was written primarily using gen-AI (Claude Sonnet 4.5) and serves to enable [apex-seeker](https://github.com/wongd-hub/apex-seeker).

Clean plumbing layer for building Gymnasium RL environments with Assetto Corsa.

**This repo:** Windows integration (telemetry + control + timing)  
**Your repo (e.g., apex-seeker):** RL logic (rewards + done + PPO)

## Features

- **ACBridgeLocal** - Main API with background telemetry (60 Hz) + vJoy control
- **RealTimeStepper** - Drift-correcting step timing for consistent RL training
- **Action Smoothing** - Rate limiting + EMA filtering for stable RL training at 10 Hz
- **Comprehensive telemetry** - 40+ fields including damage, lap timing, track limits
- **Low latency** - 3-8ms control, sub-ms telemetry reads (cached)
- **Actor-learner ready** - WebSocket streaming for cloud training
- **Type-safe** - Protocol with JSON/MessagePack support

## Quick Start

**For apex-seeker (or your Gym env):**

```python
from ac_bridge import ACBridgeLocal, RealTimeStepper

# Initialize
bridge = ACBridgeLocal(telemetry_hz=60, control_hz=10)
stepper = RealTimeStepper(bridge, control_hz=10)
bridge.connect()

# In your Gym env
obs, info = stepper.reset()            # Restarts session
obs, info = stepper.step(action)       # Applies action, waits, returns obs
reward = compute_reward(obs, info)     # Your logic
done = check_done(info)                # Your logic

bridge.close()
```

**CLI Tools (for testing):**

```bash
# Install
uv sync && uv pip install -e .

# Test with AC running
uv run ac-bridge test-telemetry --hz 10
uv run ac-bridge smoke-test
uv run ac-bridge test-control
```

**Action Smoothing (enabled by default):**

```python
from ac_bridge import ACBridgeLocal, get_aggressive_config, get_no_smoothing_config

# Moderate smoothing (default - recommended for training)
bridge = ACBridgeLocal(control_hz=10)

# More responsive (for advanced policies)
bridge = ACBridgeLocal(control_hz=10, smoothing_config=get_aggressive_config())

# Disable smoothing (hard clamps only)
bridge = ACBridgeLocal(control_hz=10, smoothing_config=get_no_smoothing_config())
```

Smoothing includes:
- **Rate limiting** - Limits how fast inputs can change (prevents jerky steering)
- **EMA filtering** - Removes noisy outputs without lag
- **Asymmetric pedals** - Realistic brake/throttle dynamics (fast brake, slow release)
- **Hard clamps** - Always enforces [-1, 1] steering, [0, 1] pedals

This dramatically stabilizes RL training at 10 Hz by preventing spin-outs from sudden control changes.

**See [docs/api_reference.md](docs/api_reference.md) for complete API.**

## Documentation

- **[API Reference](docs/api_reference.md)** - Complete API documentation (start here!)
- [Action Smoothing](docs/action_smoothing.md) - Rate limiting + EMA filtering for stable training
- [Telemetry System](docs/telemetry.md) - Shared memory implementation details
- [Control System](docs/control.md) - vJoy setup and latency optimization
- [Cloud Setup](docs/cloud_setup.md) - Actor-learner pattern for remote training
- [Examples](examples/) - Test scripts and integration demos

## What You Get

**Observation:** 15-dim normalized vector + 40+ field info dict  
**Timing:** Drift-correcting 10 Hz steps, <1ms accuracy  
**Control:** vJoy with 3-8ms latency + action smoothing  
**Smoothing:** Rate limiting + EMA filtering (prevents jerky inputs)  
**Reset:** Automated session restart + 1st gear  
**Cloud:** WebSocket streaming for distributed training

## Requirements

- Windows
- Python 3.11+
- Assetto Corsa (original)

## Attribution

Based on research from:
- [DIY-DirectDrive](https://github.com/JanBalke420/DIY-DirectDrive) - Shared memory structures
- [ac-remote-telemetry-client](https://github.com/rickwest/ac-remote-telemetry-client) - UDP protocol reference
- [CrewChiefV4](https://github.com/mrbelowski/CrewChiefV4) - UDP protocol analysis
- [assetto_corsa_gym](https://github.com/dasGringuen/assetto_corsa_gym) - A fully featured Assetto Corsa Gym Environment

Note: UDP telemetry was explored but abandoned in favor of shared memory due to reliability issues and higher latency.

## License

MIT License - See LICENSE file for details

