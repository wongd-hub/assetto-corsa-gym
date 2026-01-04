# Assetto Corsa Gym Bridge

A telemetry bridge for connecting Assetto Corsa to Gymnasium reinforcement learning environments.

## Features

- Real-time telemetry reading via shared memory (sub-millisecond latency)
- Low-latency control via vJoy (3-8ms total latency)
- WebSocket streaming for local development and integration
- Comprehensive car state data (physics, damage, lap timing, track limits)
- Derived metrics for RL training (wheel lock detection, lap validity, damage levels)
- JSON export for training pipelines
- Multiple client support (broadcast to many consumers simultaneously)
- Configurable polling rates (1-60 Hz for telemetry, up to 100 Hz for control)

## Quick Start

```bash
# Install dependencies
uv sync

# Install the CLI tool
uv pip install -e .

# Start AC and begin driving, then test the connection:
uv run ac-bridge test-telemetry --hz 10

# Test control output (interactive)
uv run ac-bridge test-control

# Run full integration smoke test
uv run ac-bridge smoke-test

# Run main bridge loop (telemetry + control)
uv run ac-bridge run --hz 60 --controller vjoy

# Stream telemetry locally (development/testing)
uv run ac-bridge stream --rate 10

# Stream to cloud (EC2, VPS) for training
uv run ac-bridge cloud --uri ws://your-server:8765 --rate 10

# Reset session in AC
uv run ac-bridge reset
```

See [examples/](examples/) for client connection examples and [docs/cloud_setup.md](docs/cloud_setup.md) for cloud training setup.

## Documentation

See [docs/](docs/) for detailed documentation:

- [Telemetry System](docs/telemetry.md) - Implementation details, field descriptions, integration guide
- [Control System](docs/control.md) - vJoy setup, control API, latency optimization
- [Cloud Setup Guide](docs/cloud_setup.md) - Streaming telemetry and control to/from EC2
- [Quick Start Guide](docs/README.md) - Installation and usage

## Key Features

**Telemetry Metrics:**
- Track limits: `numberOfTyresOut`, `is_lap_valid`
- Wheel dynamics: `wheelSlip`, `wheel_lock_detected`
- Damage: `bodywork_damaged`, `tyre_wear`
- Lap timing: `completedLaps`, `iCurrentTime`, `iBestTime`
- Physics: `velocity`, `accG`, `angular_velocity`

**Control Inputs:**
- Throttle, brake, clutch (0.0-1.0)
- Steering (-1.0 to 1.0)
- Gear shifting (sequential or H-pattern)
- Fast updates: 3-8ms latency, up to 100 Hz

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

