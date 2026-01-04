# Assetto Corsa Gym Bridge Documentation

## Quick Start

### Installation

```bash
# Clone repository
git clone <repository-url>
cd assetto-corsa-gym

# Install dependencies (using uv)
uv sync

# Install CLI tool
uv pip install -e .
```

### Basic Usage

1. Start Assetto Corsa and begin driving

2. Test telemetry reading:
```bash
uv run ac-bridge test-telemetry --hz 10
```

3. Test control output:
```bash
uv run ac-bridge test-control
```

4. Run full integration test:
```bash
uv run ac-bridge smoke-test
```

5. Run main bridge loop:
```bash
uv run ac-bridge run --hz 60
```

## Documentation

- [Telemetry System](telemetry.md) - Detailed documentation on telemetry implementation, data fields, and integration
- [Control System](control.md) - vJoy control system, API reference, latency optimization
- [Cloud Setup Guide](cloud_setup.md) - Complete guide for streaming telemetry to EC2 or other cloud servers

## Project Structure

```
assetto-corsa-gym/
├── ac_bridge/
│   ├── telemetry/
│   │   ├── ac_native_memory.py    # Native AC shared memory reader
│   │   └── __init__.py
│   ├── control/
│   │   ├── vjoy_controller.py     # vJoy control implementation
│   │   └── __init__.py
│   ├── websocket_server.py        # WebSocket streaming server
│   ├── websocket_client.py        # WebSocket streaming client
│   └── client.py
├── docs/
│   ├── README.md                  # This file
│   ├── telemetry.md               # Telemetry documentation
│   ├── control.md                 # Control documentation
│   └── cloud_setup.md             # Cloud deployment guide
├── examples/
│   ├── websocket_client.py        # Example WebSocket client
│   ├── test_control.py            # vJoy control test
│   ├── control_from_telemetry.py  # Closed-loop demo
│   ├── control_server.py          # Cloud control receiver
│   └── README.md                  # Examples documentation
├── main.py                        # CLI entry point
└── pyproject.toml                 # Dependencies
```

## Commands

All commands are available via the `ac-bridge` CLI tool:

```bash
uv run ac-bridge [COMMAND] [OPTIONS]
```

### run

Run the main bridge loop for RL training. Reads telemetry and accepts control commands.

```bash
uv run ac-bridge run [OPTIONS]
```

Options:
- `--hz N` - Control loop frequency in Hz (default: 10)
- `--telemetry-port PORT` - Telemetry port (default: 9996)
- `--controller vjoy` - Controller type (default: vjoy)
- `--bind ADDR` - RPC bind address (default: 127.0.0.1:50051)
- `--log-dir PATH` - Directory for logs (optional)

### test-telemetry

Test telemetry reading and display parsed fields.

```bash
uv run ac-bridge test-telemetry [OPTIONS]
```

Options:
- `--hz N` - Telemetry read rate in Hz (default: 10)
- `--duration N` - Duration in seconds (default: run until Ctrl+C)

### test-control

Test control output with interactive keyboard or scripted inputs.

```bash
uv run ac-bridge test-control [OPTIONS]
```

Options:
- `--device-id N` - vJoy device ID (default: 1)

### smoke-test

Run full integration smoke test with safe input pattern.

```bash
uv run ac-bridge smoke-test [OPTIONS]
```

Options:
- `--device-id N` - vJoy device ID (default: 1)
- `--duration N` - Test duration in seconds (default: 10)

### reset

Trigger session reset in AC and wait until stable.

```bash
uv run ac-bridge reset [OPTIONS]
```

Options:
- `--device-id N` - vJoy device ID (default: 1)
- `--wait N` - Wait time after reset in seconds (default: 5)

### stream

Stream telemetry over WebSocket for local development.

```bash
uv run ac-bridge stream [OPTIONS]
```

Options:
- `--host HOST` - Server host (default: localhost)
- `--port PORT` - Server port (default: 8765)
- `--rate N` - Broadcast rate in Hz (default: 10)

This starts a WebSocket server that broadcasts telemetry to all connected clients. Multiple clients can connect simultaneously.

Example workflow:
```bash
# Terminal 1: Start stream
uv run ac-bridge stream --rate 10

# Terminal 2: Connect client
uv run examples/websocket_client.py
```

### cloud

Stream telemetry to remote cloud server (EC2, VPS, etc.).

```bash
uv run ac-bridge cloud --uri ws://YOUR_SERVER_IP:8765 [OPTIONS]
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
uv run ac-bridge cloud --uri ws://ec2-ip:8765 --rate 10
```

See [Cloud Setup Guide](cloud_setup.md) for complete instructions.

### test-control

Test vJoy control with keyboard input (interactive).

```bash
uv run main.py test-control [OPTIONS]
```

Options:
- `--device-id N` - vJoy device ID (default: 1)

Interactive keyboard controls (W/A/S/D, Q/E for gears, R to reset).

### control-from-cloud

Receive control commands from remote server and apply to vJoy.

```bash
uv run main.py control-from-cloud --uri ws://SERVER:PORT [OPTIONS]
```

Options:
- `--uri URI` - Remote WebSocket server URI (required)
- `--device-id N` - vJoy device ID (default: 1)
- `--rate N` - Control update rate in Hz (default: 60)

For bidirectional cloud training with telemetry + control.

See [Control System Guide](control.md) for detailed instructions.

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

