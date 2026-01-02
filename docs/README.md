# Assetto Corsa Gym Bridge Documentation

## Quick Start

### Installation

```bash
# Clone repository
git clone <repository-url>
cd assetto-corsa-gym

# Install dependencies (using uv)
uv sync
```

### Basic Usage

1. Start Assetto Corsa and begin driving

2. Run telemetry reader:
```bash
uv run main.py read --rate 10
```

3. Export to JSON for training:
```bash
uv run main.py read --rate 10 --json-output data/telemetry.jsonl
```

## Documentation

- [Telemetry System](telemetry.md) - Detailed documentation on telemetry implementation, data fields, and integration

## Project Structure

```
assetto-corsa-gym/
├── ac_bridge/
│   ├── telemetry/
│   │   ├── ac_native_memory.py    # Primary: Native AC shared memory
│   │   ├── ac_shared_memory.py    # Fallback: pyaccsharedmemory wrapper
│   │   └── __init__.py
│   ├── control/                   # (Future) vJoy/ViGEm control output
│   └── client.py
├── docs/
│   ├── README.md                  # This file
│   └── telemetry.md               # Telemetry documentation
├── main.py                        # CLI entry point
└── pyproject.toml                 # Dependencies
```

## Commands

### read

Read and display telemetry from AC's shared memory.

```bash
uv run main.py read [OPTIONS]
```

Options:
- `--rate N` - Polling rate in Hz (default: 10)
- `--json-output PATH` - Export telemetry to JSONL file
- `--native` - Use native AC shared memory (default)
- `--acc-lib` - Use pyaccsharedmemory library (fallback)

## Requirements

- Windows (shared memory implementation is Windows-specific)
- Python 3.11+
- Assetto Corsa (original, not Competizione)
- Running AC game with active driving session

## Attribution

See [telemetry.md](telemetry.md) for detailed source attribution.

Key references:
- DIY-DirectDrive by JanBalke420 - Native shared memory structures
- ac-remote-telemetry-client by rickwest - UDP protocol reference
- pyaccsharedmemory library - Fallback implementation

