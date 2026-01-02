# Assetto Corsa Gym Bridge

A telemetry bridge for connecting Assetto Corsa to Gymnasium reinforcement learning environments.

## Features

- Real-time telemetry reading via shared memory (sub-millisecond latency)
- WebSocket streaming for local development and integration
- Comprehensive car state data (physics, damage, lap timing, track limits)
- Derived metrics for RL training (wheel lock detection, lap validity, damage levels)
- JSON export for training pipelines
- Multiple client support (broadcast to many consumers simultaneously)
- Configurable polling rates (1-60 Hz)

## Quick Start

```bash
# Install dependencies
uv sync

# Start AC and begin driving

# Option 1: Stream over WebSocket (recommended for integration)
uv run main.py stream --rate 10

# Option 2: Read and display in console
uv run main.py read --rate 10

# Option 3: Export to JSON file
uv run main.py read --rate 10 --json-output telemetry.jsonl
```

See [examples/](examples/) for client connection examples.

## Documentation

See [docs/](docs/) for detailed documentation:

- [Telemetry System](docs/telemetry.md) - Implementation details, field descriptions, integration guide
- [Quick Start Guide](docs/README.md) - Installation and usage

## Key Telemetry Metrics

- Track limits: `numberOfTyresOut`, `is_lap_valid`
- Wheel dynamics: `wheelSlip`, `wheel_lock_detected`
- Damage: `bodywork_damaged`, `tyre_wear`
- Lap timing: `completedLaps`, `iCurrentTime`, `iBestTime`
- Physics: `velocity`, `accG`, control inputs

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

