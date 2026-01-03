# Examples

## WebSocket Telemetry Streaming

### Local Development Mode

Start a WebSocket server on your local machine:

```bash
uv run main.py stream --host localhost --port 8765 --rate 10
```

Then connect with the example client:

```bash
uv run examples/websocket_client.py
```

This is useful for:
- Local testing and development
- Running Gymnasium environments on same machine
- Quick prototyping

### Cloud Training Mode

Stream telemetry to a remote server (EC2, VPS, etc.):

```bash
# On EC2: Start receiver
python examples/cloud_server.py --host 0.0.0.0 --port 8765

# On Windows: Connect and stream
uv run main.py cloud --uri ws://your-ec2-ip:8765 --rate 10
```

This enables:
- Cloud-based RL training with home AC setup
- Training on GPU instances while playing at home
- No port forwarding or VPN needed

See [Cloud Setup Guide](../docs/cloud_setup.md) for detailed instructions.

### Custom Client

You can create your own client in any language. Here's the basic structure:

**Python:**
```python
import asyncio
import json
import websockets

async def receive():
    async with websockets.connect("ws://localhost:8765") as ws:
        async for message in ws:
            data = json.loads(message)
            print(data['speed_kmh'], data['rpm'])

asyncio.run(receive())
```

**JavaScript/Node.js:**
```javascript
const WebSocket = require('ws');
const ws = new WebSocket('ws://localhost:8765');

ws.on('message', (data) => {
    const telemetry = JSON.parse(data);
    console.log(telemetry.speed_kmh, telemetry.rpm);
});
```

**Python (Gymnasium Environment):**
```python
import asyncio
import json
import websockets
import gymnasium as gym

class ACEnv(gym.Env):
    async def connect(self):
        self.ws = await websockets.connect("ws://localhost:8765")
    
    async def get_obs(self):
        message = await self.ws.recv()
        return json.loads(message)
```

## Data Format

Each message is a JSON object with the following structure:

```json
{
  "timestamp": 123,
  "packet_id": 456789,
  "speed_kmh": 145.3,
  "rpm": 5420,
  "gear": 3,
  "gas": 0.85,
  "brake": 0.00,
  "steer_angle": -12.5,
  
  "velocity_x": 35.2,
  "velocity_y": 0.1,
  "velocity_z": 15.8,
  
  "angular_velocity_x": 0.05,
  "angular_velocity_y": 0.12,
  "angular_velocity_z": 0.02,
  
  "world_position_x": 123.45,
  "world_position_y": 10.2,
  "world_position_z": 456.78,
  
  "yaw": 1.57,
  "pitch": 0.02,
  "roll": 0.01,
  
  "wheel_slip": [0.12, 0.15, 0.10, 0.13],
  "wheel_angular_speed": [145.2, 147.1, 143.8, 146.5],
  "wheel_load": [2500, 2450, 2300, 2350],
  
  "number_of_tyres_out": 0,
  "is_lap_valid": true,
  "bodywork_damaged": false,
  "completed_laps": 5,
  "distance_traveled": 12543.2,
  "normalized_position": 0.75,
  ...
}
```

See `docs/telemetry.md` for complete field descriptions.

