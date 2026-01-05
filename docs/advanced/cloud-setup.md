# Cloud Setup Guide

## Problem: NAT and Firewall

Your home Windows PC running AC is behind NAT/firewall, so cloud instances (EC2, etc.) cannot directly connect to it. The solution is to reverse the connection direction.

## Solution: Windows Dials OUT to Cloud

Have your Windows machine connect TO your cloud server. This works because:
- Outbound connections are allowed through NAT
- No port forwarding required on home router
- No public IP needed on Windows machine
- Works from anywhere (home, cafe, etc.)

## Architecture

```
Windows PC (AC + Bridge)  -->  Cloud Server (EC2)  -->  Training
   Behind NAT                   Public IP               GPUs
   
Connection flow:
1. Cloud server starts WebSocket server on port 8765
2. Windows bridge connects TO cloud server
3. Bridge streams telemetry through persistent connection
4. Training code receives telemetry in real-time
```

## Setup Steps

### 1. Cloud Server Setup (EC2)

**Launch EC2 Instance:**
```bash
# Ubuntu 22.04 LTS recommended
# Instance type: t3.medium or better
# Storage: 20GB minimum
```

**Configure Security Group:**
```
Inbound Rules:
- Port 8765 (WebSocket): TCP from YOUR_HOME_IP/32
- Port 22 (SSH): TCP from YOUR_HOME_IP/32
```

**Install Dependencies:**
```bash
# SSH into EC2
ssh -i your-key.pem ubuntu@your-ec2-ip

# Install Python 3.11+
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip -y

# Install websockets
pip3 install websockets
```

**Start Receiver Server:**
```bash
# Copy cloud_server.py to EC2
scp -i your-key.pem examples/cloud_server.py ubuntu@your-ec2-ip:~/

# Run server
python3 cloud_server.py --host 0.0.0.0 --port 8765
```

### 2. Windows Bridge Setup

**Start Streaming to Cloud:**
```bash
# On your Windows PC
uv run main.py cloud --uri ws://YOUR_EC2_IP:8765 --rate 10
```

That's it! The bridge will:
- Connect to your EC2 instance
- Stream telemetry at 10 Hz
- Auto-reconnect if connection drops
- Continue streaming as long as AC is running

### 3. Test Connection

**On EC2 (watch for incoming data):**
```bash
python3 cloud_server.py --host 0.0.0.0 --port 8765

# Should show:
# [YOUR_IP:PORT] Client connected
# [#10] Speed: 145.3 km/h | Lap: 2 | Valid: True
# [#20] Speed: 152.1 km/h | Lap: 2 | Valid: True
```

**On Windows (should show connection success):**
```bash
uv run main.py cloud --uri ws://YOUR_EC2_IP:8765 --rate 10

# Should show:
# connected_to_server uri=ws://YOUR_EC2_IP:8765
# telemetry_stream_started rate_hz=10
```

## Secure Connection (Recommended for Production)

For production use, enable TLS:

### 1. Get SSL Certificate

```bash
# Install certbot on EC2
sudo apt install certbot

# Get certificate (requires domain name)
sudo certbot certonly --standalone -d your-domain.com
```

### 2. Run Server with TLS

Modify `cloud_server.py` to use SSL:

```python
import ssl

ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
ssl_context.load_cert_chain('/etc/letsencrypt/live/your-domain.com/fullchain.pem',
                            '/etc/letsencrypt/live/your-domain.com/privkey.pem')

async with websockets.serve(self.handler, self.host, self.port, ssl=ssl_context):
    await asyncio.Future()
```

### 3. Connect with WSS

```bash
uv run main.py cloud --uri wss://your-domain.com:8765 --rate 10
```

## Firewall Configuration

### EC2 Security Group

```
Inbound:
- Type: Custom TCP
- Port: 8765
- Source: YOUR_HOME_IP/32  # Restrict to your IP for security

Outbound:
- All traffic allowed (default)
```

### Windows Firewall

No configuration needed - outbound connections are allowed by default.

## Troubleshooting

### Connection Refused

```
Error: connection_error error=[Errno 111] Connection refused
```

**Fix:**
- Verify EC2 security group allows port 8765 from your IP
- Verify cloud server is running
- Check EC2 IP address is correct

### Connection Timeout

```
Error: connection_error error=asyncio.exceptions.TimeoutError
```

**Fix:**
- Verify EC2 instance is running
- Check your home network allows outbound connections on port 8765
- Try using a different port (e.g., 443 or 80)

### Auto-Reconnect Not Working

The bridge automatically reconnects every 5 seconds by default. Adjust:

```bash
uv run main.py cloud --uri ws://ec2-ip:8765 --reconnect-delay 10
```

### High Latency

```
Packet delays > 100ms
```

**Fix:**
- Choose EC2 region closer to your location
- Reduce send rate: `--rate 5` instead of `--rate 10`
- Check your home internet connection
- Use wired connection instead of WiFi

## Cost Optimization

### EC2 Instance Sizing

- **Development**: t3.micro ($0.01/hour)
- **Training**: p3.2xlarge ($3.06/hour with GPU)
- **Use Spot Instances**: Save 70% on training costs

### Data Transfer Costs

- Telemetry: ~500 bytes/packet
- At 10 Hz: ~5 KB/s = 18 MB/hour = 432 MB/day
- EC2 data transfer out: First 100 GB/month free
- Cost: Minimal for telemetry alone

### Alternative: Use Existing Server

If you have a VPS or other cloud server:

```bash
# Any Linux server with public IP
# Install websockets: pip install websockets
# Run cloud_server.py
python3 cloud_server.py --host 0.0.0.0 --port 8765

# Connect from Windows
uv run main.py cloud --uri ws://your-vps-ip:8765
```

## Integration with Training Code

The cloud server receives telemetry as JSON. Integrate with your RL training:

```python
import asyncio
import json
import websockets
from collections import deque

class TrainingReceiver:
    def __init__(self):
        self.buffer = deque(maxlen=1000)
        
    async def handler(self, websocket):
        async for message in websocket:
            telemetry = json.loads(message)
            
            # Add to buffer
            self.buffer.append(telemetry)
            
            # Process for training
            if len(self.buffer) >= 10:
                obs = self.extract_observation(telemetry)
                reward = self.calculate_reward(telemetry)
                done = self.check_termination(telemetry)
                
                # Feed to policy...
    
    def extract_observation(self, t):
        return [
            t['speed_kmh'] / 300.0,  # Normalize
            t['rpm'] / 8000.0,
            t['yaw'],
            t['angular_velocity_y'],
            # ... more features
        ]
    
    def calculate_reward(self, t):
        reward = 0.0
        reward += t['speed_kmh'] * 0.01  # Progress reward
        reward -= t['number_of_tyres_out'] * 10  # Off-track penalty
        reward -= int(t['wheel_lock_detected']) * 5  # Lock penalty
        return reward
```

## Next Steps

1. Set up EC2 instance and start cloud_server.py
2. Test connection from Windows with `main.py cloud`
3. Verify data is flowing (check cloud_server.py output)
4. Integrate with your training pipeline
5. Consider adding authentication for production use

