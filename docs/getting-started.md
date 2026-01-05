# Quick Start Guide

This guide will get you up and running with AC Bridge in 5 minutes.

## Prerequisites

Before you start, make sure you have:

- ✅ Windows 10/11
- ✅ Python 3.11 or higher
- ✅ Assetto Corsa (original, not Competizione)
- ✅ [vJoy](http://vjoystick.sourceforge.net/) virtual joystick driver installed

## Installation

```bash
# Clone the repository
git clone https://github.com/wongd-hub/assetto-corsa-gym.git
cd assetto-corsa-gym

# Install with uv (recommended)
uv sync
uv pip install -e .

# Or with pip
pip install -e .
```

## Verify Installation

```bash
# Test telemetry reading (AC must be running)
uv run ac-bridge test-telemetry --hz 10

# Test vJoy control
uv run ac-bridge test-control

# Run smoke test (combines telemetry + control)
uv run ac-bridge smoke-test
```

## Your First Integration

Create a file `my_env.py`:

```python
from ac_bridge import ACBridgeLocal, RealTimeStepper
import numpy as np

# Initialize bridge
bridge = ACBridgeLocal(
    telemetry_hz=60,  # Background telemetry polling rate
    control_hz=10      # RL step rate
)

# Create stepper for consistent timing
stepper = RealTimeStepper(bridge, control_hz=10)

# Connect to AC
bridge.connect()
print("Connected to Assetto Corsa!")

try:
    # Reset (restarts race and shifts to 1st gear)
    obs, info = stepper.reset()
    print(f"Initial observation shape: {obs.shape}")
    print(f"Speed: {info['speed_kmh']:.1f} km/h")
    
    # Run for 100 steps
    for step in range(100):
        # Your policy would go here
        # For now, just go straight with some throttle
        action = np.array([0.0, 0.5, 0.0])  # [steer, throttle, brake]
        
        # Apply action and get next observation
        obs, info = stepper.step(action)
        
        # Check what's happening
        print(f"Step {step}: Speed={info['speed_kmh']:.1f} km/h, "
              f"RPM={info['rpm']}, Gear={info['gear']}")
        
        # Your reward/done logic would go here
        if info['number_of_tyres_out'] >= 3:
            print("Off track! Resetting...")
            obs, info = stepper.reset()

finally:
    bridge.close()
    print("Bridge closed")
```

Run it:

```bash
# Start AC, enter a session, then:
python my_env.py
```

## What Just Happened?

1. **`ACBridgeLocal`** - Created a bridge that:
   - Polls AC shared memory at 60 Hz in background thread
   - Caches latest telemetry for instant access
   - Applies control via vJoy with action smoothing

2. **`RealTimeStepper`** - Created a stepper that:
   - Enforces consistent 10 Hz timing (100ms per step)
   - Applies action → waits → reads observation
   - Returns drift-corrected observations with timing metadata

3. **`.reset()`** - Triggered session restart:
   - Pressed vJoy button 7 (restart race)
   - Waited 2s, pressed button 9 (start race)
   - Reset controls, shifted to 1st gear
   - Returned initial observation

4. **`.step(action)`** - Applied action for 100ms:
   - Smoothed action (rate limiting + EMA)
   - Applied to vJoy
   - Waited until next 10 Hz tick
   - Returned observation from that tick

## Next Steps

Now that you have basic integration working:

1. **[Wrap it in a Gym environment](api/overview.md#gymnasium-integration)**
2. **[Understand action smoothing](api/action-smoothing.md)**
3. **[Explore telemetry fields](systems/telemetry.md)**
4. **[Set up cloud training](advanced/cloud-setup.md)**

## Common Issues

### "vJoy device not found"

Make sure vJoy is installed and device 1 is configured:

```bash
# Test vJoy
uv run ac-bridge test-control
```

### "AC not running or no telemetry available"

1. Start Assetto Corsa
2. Enter a practice/race session (not main menu)
3. Run your script

### "Controls not working in AC"

Map vJoy device in AC's controls settings:

1. AC → Options → Controls
2. Select "vJoy Device"
3. Map steering, throttle, brake axes

### "Timing drift / inconsistent step rates"

The `RealTimeStepper` handles this automatically. Check timing stats:

```python
stats = stepper.get_stats()
print(f"Avg step duration: {stats['avg_step_duration']:.3f}s")
print(f"Drift: {stats['avg_drift']:.3f}s")
```

Drift should be <1ms with default settings.

## Example Scripts

Check out the `examples/` directory for more:

- `test_bridge_api.py` - Complete API walkthrough
- `test_action_smoothing.py` - Action smoothing demo
- `test_timing.py` - Timing system validation
- `test_control.py` - Interactive vJoy testing

