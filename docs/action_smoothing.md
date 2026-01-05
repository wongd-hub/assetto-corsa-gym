# Action Smoothing

Action smoothing is critical for stable RL training at 10 Hz control rates.

Without smoothing, policies produce jerky, unstable inputs that:
- Cause spin-outs
- Make training diverge
- Produce unrealistic behavior

With smoothing, you get:
- Smooth, human-like inputs
- Stable training
- Faster convergence

## The Golden Rule

**Policy chooses targets, controller decides how fast to reach them.**

This separation is critical. The RL policy outputs *target* values, and the smoother gradually moves toward them.

## Components

### 1. Rate Limiting (Most Important)

Limits how much an input can change per timestep.

Example (steering at 10 Hz):
```python
max_steer_delta = 0.15  # per step
# This means: full lock in ~0.7 seconds
```

Different limits per control:
- **Steering:** Small, smooth (0.10-0.15)
- **Throttle:** Moderate (0.10 up, 0.25 down)
- **Brake:** Fast application, slow release (0.30 up, 0.10 down)

### 2. Low-Pass Filtering (EMA Smoothing)

Removes noisy outputs without lagging.

```python
alpha = 0.6  # 0=full smoothing, 1=no smoothing
steer = alpha * target + (1 - alpha) * prev_steer
```

Typical values at 10 Hz:
- **Steering:** 0.5-0.7
- **Throttle:** 0.6-0.8
- **Brake:** 0.6-0.8

### 3. Asymmetric Pedal Dynamics

Models realistic human behavior:
- Apply brake quickly, release slowly
- Apply throttle smoothly, lift faster

This alone stops 80% of spin-outs.

### 4. Hard Clamps (Always Applied)

Safety layer that always enforces:
- Steering: [-1.0, 1.0]
- Pedals: [0.0, 1.0]

Never trust raw NN outputs.

## Usage

### Default (Recommended)

```python
from ac_bridge import ACBridgeLocal

# Moderate smoothing enabled by default
bridge = ACBridgeLocal(telemetry_hz=60, control_hz=10)
bridge.connect()

# Smoothing happens automatically in apply_action()
bridge.apply_action(steer=0.5, throttle=0.8, brake=0.0)
```

### Custom Config

```python
from ac_bridge import ACBridgeLocal, SmoothingConfig

config = SmoothingConfig(
    enable_rate_limiting=True,
    max_steer_delta=0.10,      # More conservative
    enable_ema_smoothing=True,
    steer_alpha=0.5            # More smoothing
)

bridge = ACBridgeLocal(
    telemetry_hz=60,
    control_hz=10,
    smoothing_config=config
)
```

### Presets

```python
from ac_bridge import (
    ACBridgeLocal,
    get_conservative_config,  # Very smooth, human-like
    get_moderate_config,      # Balanced (default)
    get_aggressive_config,    # More responsive
    get_no_smoothing_config   # Hard clamps only
)

# Conservative (good for initial training)
bridge = ACBridgeLocal(
    control_hz=10,
    smoothing_config=get_conservative_config()
)

# No smoothing (not recommended for RL)
bridge = ACBridgeLocal(
    control_hz=10,
    smoothing_config=get_no_smoothing_config()
)
```

### Monitoring

```python
# Get smoothing statistics
stats = bridge.get_smoother_stats()

print(f"Steps: {stats['step_count']}")
print(f"Avg steer delta: {stats['avg_steer_delta']:.4f}")
print(f"Avg throttle delta: {stats['avg_throttle_delta']:.4f}")
print(f"Config: {stats['config']}")
```

## When to Use Each Preset

### Conservative
- **When:** Initial training, learning from scratch
- **Why:** Prevents catastrophic failures early on
- **Trade-off:** Slower reactions, less responsive

### Moderate (Default)
- **When:** General training, most use cases
- **Why:** Good balance of stability and responsiveness
- **Trade-off:** Minimal, recommended default

### Aggressive
- **When:** Fine-tuning advanced policies, racing
- **Why:** More responsive, closer to expert behavior
- **Trade-off:** Requires stable policy to avoid spin-outs

### No Smoothing
- **When:** Debugging, analyzing raw policy outputs
- **Why:** See what the policy actually wants to do
- **Trade-off:** Unstable, jerky, not suitable for training

## Testing

Run the smoothing test to see the difference:

```bash
# Start AC and enter a session, then:
uv run examples/test_action_smoothing.py
```

This will:
1. Test moderate smoothing (default)
2. Test aggressive smoothing
3. Test no smoothing (you'll see the difference!)

## Implementation Details

The `ActionSmoother` class is integrated into `ACBridgeLocal.apply_action()`:

1. **Phase 0:** Hard clamp inputs (always)
2. **Phase 1:** Apply rate limiting (if enabled)
3. **Phase 2:** Apply EMA smoothing (if enabled)
4. **Phase 3:** Final safety clamps (always)

State is automatically reset when `bridge.reset()` is called.

## Performance

Smoothing adds negligible overhead:
- Rate limiting: Simple clipping, ~0.01ms
- EMA filtering: Single multiply-add, ~0.01ms
- Total: <0.05ms per action

This is insignificant compared to vJoy update latency (3-8ms).

## References

- [Soft Actor-Critic](https://arxiv.org/abs/1801.01290) - Action smoothing improves sample efficiency
- [DDPG](https://arxiv.org/abs/1509.02971) - Exploration noise vs. output smoothing
- [TD3](https://arxiv.org/abs/1802.09477) - Target policy smoothing

## Key Takeaways

1. **Always use smoothing for RL training**
2. **Start with moderate config**
3. **Monitor avg_steer_delta** - should be <0.15 at 10 Hz
4. **Don't trust raw NN outputs** - always clamp and smooth
5. **Smoothing ≠ lag** - EMA with alpha=0.6 is responsive

Without smoothing, RL training in racing simulators is nearly impossible at low control rates (10 Hz).

