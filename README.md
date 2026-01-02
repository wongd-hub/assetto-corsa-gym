# Assetto Corsa Gym Bridge

A telemetry bridge for connecting Assetto Corsa to Gymnasium reinforcement learning environments.

## Features

- Real-time telemetry reading via shared memory (sub-millisecond latency)
- Comprehensive car state data (physics, damage, lap timing, track limits)
- Derived metrics for RL training (wheel lock detection, lap validity, damage levels)
- JSON export for integration with training pipelines
- Configurable polling rates (1-60 Hz)

## Quick Start

```bash
# Install dependencies
uv sync

# Start AC and begin driving

# Read telemetry
uv run main.py read --rate 10

# Export to JSON
uv run main.py read --rate 10 --json-output telemetry.jsonl
```

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

Note: UDP telemetry was explored but abandoned in favor of shared memory due to reliability issues and higher latency.

## License

MIT License - See LICENSE file for details

