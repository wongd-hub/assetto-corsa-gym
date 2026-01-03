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
- [Cloud Setup Guide](cloud_setup.md) - Complete guide for streaming telemetry to EC2 or other cloud servers

## Project Structure

```
assetto-corsa-gym/
├── ac_bridge/
│   ├── telemetry/
│   │   ├── ac_native_memory.py    # Native AC shared memory reader
│   │   └── __init__.py
│   ├── websocket_server.py        # WebSocket streaming server
│   ├── control/                   # (Future) vJoy/ViGEm control output
│   └── client.py
├── docs/
│   ├── README.md                  # This file
│   └── telemetry.md               # Telemetry documentation
├── examples/
│   ├── websocket_client.py        # Example WebSocket client
│   └── README.md                  # Examples documentation
├── main.py                        # CLI entry point
└── pyproject.toml                 # Dependencies
```

## Commands

### stream

Stream telemetry over WebSocket for local development.

```bash
uv run main.py stream [OPTIONS]
```

Options:
- `--host HOST` - Server host (default: localhost)
- `--port PORT` - Server port (default: 8765)
- `--rate N` - Broadcast rate in Hz (default: 10)

This starts a WebSocket server that broadcasts telemetry to all connected clients. Multiple clients can connect simultaneously.

Example workflow:
```bash
# Terminal 1: Start stream
uv run main.py stream --rate 10

# Terminal 2: Connect client
uv run examples/websocket_client.py
```

### cloud

Stream telemetry to remote cloud server (EC2, VPS, etc.).

```bash
uv run main.py cloud --uri ws://YOUR_SERVER_IP:8765 [OPTIONS]
```

Options:
- `--uri URI` - Remote WebSocket server URI (required)
- `--rate N` - Send rate in Hz (default: 10)
- `--reconnect-delay N` - Seconds between reconnect attempts (default: 5)

This mode is for cloud training. Your Windows machine connects TO the cloud server, bypassing NAT/firewall issues.

Example workflow:
```bash
# On EC2: Start receiver
python examples/cloud_server.py --host 0.0.0.0 --port 8765

# On Windows: Connect and stream
uv run main.py cloud --uri ws://ec2-ip:8765 --rate 10
```

See [Cloud Setup Guide](cloud_setup.md) for complete instructions.

### read

Read and display telemetry from AC's shared memory.

```bash
uv run main.py read [OPTIONS]
```

Options:
- `--rate N` - Polling rate in Hz (default: 10)
- `--json-output PATH` - Export telemetry to JSONL file

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

