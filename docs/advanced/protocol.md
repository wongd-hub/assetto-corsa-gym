# WebSocket Protocol

Advanced message protocol for cloud training and actor-learner setups.

## Message Types

```python
from ac_bridge.protocol import MessageType

MessageType.TELEMETRY         # Single telemetry frame
MessageType.TELEMETRY_BATCH   # Batch of frames (for compression)
MessageType.CONTROL           # Single control command
MessageType.CONTROL_BATCH     # Batch of commands (reduces RTT)
MessageType.TRANSITION        # RL transition (s, a, r, s', done)
MessageType.TRANSITION_BATCH  # Batch of transitions (actor→learner)
MessageType.WEIGHTS_UPDATE    # Neural network weights (learner→actor)
MessageType.PING / PONG       # Keep-alive heartbeat
```

## Batching

For cloud training, batching reduces network overhead:

### Without Batching (Naive)

```python
# Send every frame individually
for frame in frames:
    ws.send(encode(frame))  # 100 messages = 100 RTTs
```

### With Batching

```python
# Accumulate and send batch
batch = []
for frame in frames:
    batch.append(frame)
    if len(batch) >= 10:
        ws.send(encode_batch(batch))  # 10 messages = 1 RTT
        batch = []
```

**Benefits:**
- 10x fewer network round-trips
- Better compression (repeated field names)
- Lower CPU overhead

## Actor-Learner Pattern

For distributed RL training:

```
┌─────────────────┐         ┌─────────────────┐
│  Windows PC     │         │  Cloud (EC2)    │
│  (Actor)        │         │  (Learner)      │
│                 │         │                 │
│  ┌──────────┐   │         │  ┌──────────┐   │
│  │ AC Bridge│   │  WiFi   │  │ PPO      │   │
│  │ + Policy │   │◄───────►│  │ Trainer  │   │
│  └──────────┘   │         │  └──────────┘   │
│                 │         │                 │
│  - Read AC      │         │  - Train policy │
│  - Run inference│         │  - Send weights │
│  - Collect data │         │  - Store data   │
└─────────────────┘         └─────────────────┘
```

**Actor (Windows):**

```python
from ac_bridge import ACBridgeLocal, RealTimeStepper
import websockets

# Local inference (fast)
bridge = ACBridgeLocal(control_hz=10)
stepper = RealTimeStepper(bridge, control_hz=10)
policy = load_policy()  # ONNX or TorchScript

bridge.connect()

transitions = []

async with websockets.connect('ws://ec2-ip:8000') as ws:
    obs, info = stepper.reset()
    
    for step in range(1000):
        # Local inference (no network delay!)
        action = policy(obs)
        
        # Apply action
        next_obs, next_info = stepper.step(action)
        
        # Collect transition
        transition = Transition(
            obs=obs,
            action=action,
            reward=compute_reward(next_obs, next_info),
            next_obs=next_obs,
            done=check_done(next_info),
            info=next_info
        )
        transitions.append(transition)
        
        # Send batch periodically
        if len(transitions) >= 100:
            await ws.send(encode_batch(transitions))
            transitions = []
        
        # Receive new weights (async)
        if ws.messages:
            weights = await ws.recv()
            policy.load_weights(weights)
        
        obs = next_obs
```

**Learner (Cloud):**

```python
import websockets
from stable_baselines3 import PPO

policy = PPO(...)

async def handle_actor(ws, path):
    while True:
        # Receive transition batch
        data = await ws.recv()
        transitions = decode_batch(data, Transition)
        
        # Add to replay buffer
        for t in transitions:
            replay_buffer.add(t)
        
        # Train periodically
        if len(replay_buffer) >= 1000:
            policy.train()
            
            # Send new weights
            weights = policy.get_weights()
            await ws.send(encode(weights))

# Run server
async with websockets.serve(handle_actor, '0.0.0.0', 8000):
    await asyncio.Future()  # Run forever
```

## Chunked Control

For high-latency connections, send control chunks:

```python
# Cloud sends 10 actions at once
control_batch = [
    ControlCommand(steer=0.5, throttle=0.8, brake=0.0),
    ControlCommand(steer=0.5, throttle=0.9, brake=0.0),
    # ... 8 more
]
ws.send(encode_batch(control_batch))

# Windows executes them locally at 10 Hz
for cmd in control_batch:
    bridge.apply_action(cmd.steer, cmd.throttle, cmd.brake)
    time.sleep(0.1)

# No network delay in control loop!
```

This converts "per-step RTT" into "per-chunk RTT".

## Compression

MessagePack with gzip for large batches:

```python
import msgpack
import gzip

def encode_batch(transitions):
    packed = msgpack.packb(transitions)
    compressed = gzip.compress(packed)
    return compressed

# Typical compression ratios:
# JSON: 1.0x (baseline)
# MessagePack: 0.4x
# MessagePack + gzip: 0.15x
```

For 100-transition batch:
- JSON: ~50KB
- MessagePack: ~20KB
- MessagePack+gzip: ~7KB

## See Also

- [Cloud Setup](cloud-setup.md) - EC2 deployment
- [ACBridgeWSClient](../api/overview.md) - WebSocket client API (TODO)

