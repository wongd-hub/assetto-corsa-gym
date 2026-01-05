"""
Message protocol and schemas for AC Bridge communications.

Defines typed message structures for telemetry, control, and training data
exchange. Supports both JSON (human-readable) and MessagePack (efficient) codecs.
"""

from enum import Enum
from dataclasses import dataclass, asdict, field
from typing import Any, Optional, Union
import json
import numpy as np
import structlog

logger = structlog.get_logger()

# Try to import msgpack, but it's optional
try:
    import msgpack
    MSGPACK_AVAILABLE = True
except ImportError:
    MSGPACK_AVAILABLE = False
    logger.warning("msgpack_not_available", 
                   msg="MessagePack codec unavailable. Install with: uv add msgpack")


class MessageType(Enum):
    """Message types for bridge protocol."""
    
    # Telemetry messages (bridge → consumer)
    TELEMETRY = "telemetry"
    TELEMETRY_BATCH = "telemetry_batch"
    
    # Control messages (controller → bridge)
    CONTROL = "control"
    CONTROL_BATCH = "control_batch"
    
    # Training messages (actor ↔ learner)
    TRANSITION = "transition"
    TRANSITION_BATCH = "transition_batch"
    WEIGHTS_UPDATE = "weights_update"
    
    # Connection management
    PING = "ping"
    PONG = "pong"
    HANDSHAKE = "handshake"
    
    # Errors
    ERROR = "error"


@dataclass
class TelemetryFrame:
    """
    Single telemetry frame with timing metadata.
    
    This is the core data structure returned by bridge.latest_obs().
    """
    
    # Timing metadata (added by Ticker)
    seq: int                    # Sequence number (0, 1, 2, ...)
    t_wall: float              # Wall clock time (perf_counter)
    dt: float                  # Target timestep (1/hz)
    dt_actual: float           # Actual time since last frame
    
    # Observation data (standardized)
    obs: np.ndarray            # Normalized observation vector
    
    # Raw telemetry (from AC shared memory)
    info: dict                 # All raw fields + derived metrics
    
    def to_dict(self) -> dict:
        """Convert to dict for JSON serialization."""
        return {
            'seq': self.seq,
            't_wall': self.t_wall,
            'dt': self.dt,
            'dt_actual': self.dt_actual,
            'obs': self.obs.tolist() if isinstance(self.obs, np.ndarray) else self.obs,
            'info': self.info
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'TelemetryFrame':
        """Reconstruct from dict."""
        return cls(
            seq=data['seq'],
            t_wall=data['t_wall'],
            dt=data['dt'],
            dt_actual=data['dt_actual'],
            obs=np.array(data['obs'], dtype=np.float32) if isinstance(data['obs'], list) else data['obs'],
            info=data['info']
        )


@dataclass
class ControlCommand:
    """
    Single control command.
    
    Sent from controller (or RL agent) to bridge for execution.
    """
    
    seq: int                   # Sequence number (for correlation)
    steer: float              # -1.0 (left) to 1.0 (right)
    throttle: float           # 0.0 to 1.0
    brake: float              # 0.0 to 1.0
    clutch: float = 0.0       # 0.0 to 1.0 (optional)
    gear: Optional[int] = None  # Target gear (optional)
    
    def to_dict(self) -> dict:
        """Convert to dict."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ControlCommand':
        """Reconstruct from dict."""
        return cls(**data)


@dataclass
class Transition:
    """
    Single RL transition (s, a, r, s', done).
    
    Used in actor-learner pattern for sending training data to cloud.
    """
    
    seq: int                   # Step sequence number
    obs: np.ndarray           # Observation at time t
    action: np.ndarray        # Action taken at time t
    reward: float             # Reward received
    next_obs: np.ndarray      # Observation at time t+1
    done: bool                # Episode termination flag
    info: dict                # Additional metadata
    
    def to_dict(self) -> dict:
        """Convert to dict for serialization."""
        return {
            'seq': self.seq,
            'obs': self.obs.tolist() if isinstance(self.obs, np.ndarray) else self.obs,
            'action': self.action.tolist() if isinstance(self.action, np.ndarray) else self.action,
            'reward': self.reward,
            'next_obs': self.next_obs.tolist() if isinstance(self.next_obs, np.ndarray) else self.next_obs,
            'done': self.done,
            'info': self.info
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Transition':
        """Reconstruct from dict."""
        return cls(
            seq=data['seq'],
            obs=np.array(data['obs'], dtype=np.float32),
            action=np.array(data['action'], dtype=np.float32),
            reward=data['reward'],
            next_obs=np.array(data['next_obs'], dtype=np.float32),
            done=data['done'],
            info=data['info']
        )


@dataclass
class Message:
    """
    Generic message wrapper with type and payload.
    
    All messages sent over WebSocket are wrapped in this structure.
    """
    
    type: MessageType
    payload: Union[dict, list]
    timestamp: Optional[float] = None
    
    def to_dict(self) -> dict:
        """Convert to dict for serialization."""
        return {
            'type': self.type.value if isinstance(self.type, MessageType) else self.type,
            'payload': self.payload,
            'timestamp': self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Message':
        """Reconstruct from dict."""
        return cls(
            type=MessageType(data['type']),
            payload=data['payload'],
            timestamp=data.get('timestamp')
        )


class Codec:
    """
    Encoding/decoding for bridge messages.
    
    Supports JSON (default, human-readable) and MessagePack (efficient).
    """
    
    @staticmethod
    def encode(msg: Message, format: str = 'json') -> bytes:
        """
        Encode message to bytes.
        
        Args:
            msg: Message to encode
            format: 'json' or 'msgpack'
        
        Returns:
            Encoded bytes
        """
        if format == 'json':
            return Codec._encode_json(msg)
        elif format == 'msgpack':
            return Codec._encode_msgpack(msg)
        else:
            raise ValueError(f"Unknown format: {format}")
    
    @staticmethod
    def decode(data: bytes, format: str = 'json') -> Message:
        """
        Decode bytes to message.
        
        Args:
            data: Encoded bytes
            format: 'json' or 'msgpack'
        
        Returns:
            Decoded Message
        """
        if format == 'json':
            return Codec._decode_json(data)
        elif format == 'msgpack':
            return Codec._decode_msgpack(data)
        else:
            raise ValueError(f"Unknown format: {format}")
    
    @staticmethod
    def _encode_json(msg: Message) -> bytes:
        """Encode message as JSON."""
        msg_dict = msg.to_dict()
        return json.dumps(msg_dict).encode('utf-8')
    
    @staticmethod
    def _decode_json(data: bytes) -> Message:
        """Decode JSON bytes to message."""
        msg_dict = json.loads(data.decode('utf-8'))
        return Message.from_dict(msg_dict)
    
    @staticmethod
    def _encode_msgpack(msg: Message) -> bytes:
        """Encode message as MessagePack."""
        if not MSGPACK_AVAILABLE:
            raise ImportError("msgpack not installed. Install with: uv add msgpack")
        
        msg_dict = msg.to_dict()
        return msgpack.packb(msg_dict, use_bin_type=True)
    
    @staticmethod
    def _decode_msgpack(data: bytes) -> Message:
        """Decode MessagePack bytes to message."""
        if not MSGPACK_AVAILABLE:
            raise ImportError("msgpack not installed. Install with: uv add msgpack")
        
        msg_dict = msgpack.unpackb(data, raw=False)
        return Message.from_dict(msg_dict)


# Convenience functions for common message types

def create_telemetry_message(frame: TelemetryFrame) -> Message:
    """Create a TELEMETRY message from a frame."""
    return Message(
        type=MessageType.TELEMETRY,
        payload=frame.to_dict(),
        timestamp=frame.t_wall
    )


def create_telemetry_batch_message(frames: list[TelemetryFrame]) -> Message:
    """Create a TELEMETRY_BATCH message from frames."""
    return Message(
        type=MessageType.TELEMETRY_BATCH,
        payload=[f.to_dict() for f in frames],
        timestamp=frames[-1].t_wall if frames else None
    )


def create_control_message(cmd: ControlCommand) -> Message:
    """Create a CONTROL message from a command."""
    return Message(
        type=MessageType.CONTROL,
        payload=cmd.to_dict()
    )


def create_control_batch_message(commands: list[ControlCommand]) -> Message:
    """Create a CONTROL_BATCH message from commands."""
    return Message(
        type=MessageType.CONTROL_BATCH,
        payload=[c.to_dict() for c in commands]
    )


def create_transition_batch_message(transitions: list[Transition]) -> Message:
    """Create a TRANSITION_BATCH message for actor-learner."""
    return Message(
        type=MessageType.TRANSITION_BATCH,
        payload=[t.to_dict() for t in transitions]
    )


def create_ping_message() -> Message:
    """Create a PING message for keepalive."""
    return Message(
        type=MessageType.PING,
        payload={}
    )


def create_pong_message() -> Message:
    """Create a PONG response."""
    return Message(
        type=MessageType.PONG,
        payload={}
    )


def create_error_message(error: str, details: Optional[dict] = None) -> Message:
    """Create an ERROR message."""
    return Message(
        type=MessageType.ERROR,
        payload={
            'error': error,
            'details': details or {}
        }
    )


# Example usage / demo
if __name__ == "__main__":
    import time
    
    print("\n" + "="*70)
    print("Protocol Demo: Message Encoding/Decoding")
    print("="*70 + "\n")
    
    # Create a sample telemetry frame
    frame = TelemetryFrame(
        seq=42,
        t_wall=time.perf_counter(),
        dt=0.1,
        dt_actual=0.0987,
        obs=np.array([0.5, 0.2, 0.8, 0.0], dtype=np.float32),
        info={
            'speed_kmh': 150.3,
            'tyres_out': 0,
            'lap': 2
        }
    )
    
    print("1. TelemetryFrame:")
    print(f"   seq={frame.seq}, dt_actual={frame.dt_actual:.4f}s")
    print(f"   obs shape: {frame.obs.shape}")
    print(f"   info: {frame.info}\n")
    
    # Create a message
    msg = create_telemetry_message(frame)
    print("2. Wrapped in Message:")
    print(f"   type={msg.type.value}")
    print(f"   timestamp={msg.timestamp:.3f}\n")
    
    # Encode as JSON
    json_bytes = Codec.encode(msg, format='json')
    print("3. Encoded as JSON:")
    print(f"   size: {len(json_bytes)} bytes")
    print(f"   preview: {json_bytes[:100]}...\n")
    
    # Decode back
    decoded_msg = Codec.decode(json_bytes, format='json')
    decoded_frame = TelemetryFrame.from_dict(decoded_msg.payload)
    print("4. Decoded back:")
    print(f"   seq={decoded_frame.seq}, dt_actual={decoded_frame.dt_actual:.4f}s")
    print(f"   obs matches: {np.allclose(frame.obs, decoded_frame.obs)}\n")
    
    # Create a control command
    cmd = ControlCommand(
        seq=43,
        steer=0.2,
        throttle=0.8,
        brake=0.0
    )
    
    print("5. ControlCommand:")
    print(f"   seq={cmd.seq}, steer={cmd.steer:+.2f}, throttle={cmd.throttle:.2f}\n")
    
    # Test batch messages
    frames = [frame for _ in range(5)]
    batch_msg = create_telemetry_batch_message(frames)
    batch_bytes = Codec.encode(batch_msg, format='json')
    
    print("6. Batch Message:")
    print(f"   type={batch_msg.type.value}")
    print(f"   frames in batch: {len(batch_msg.payload)}")
    print(f"   encoded size: {len(batch_bytes)} bytes\n")
    
    # Test MessagePack if available
    if MSGPACK_AVAILABLE:
        msgpack_bytes = Codec.encode(msg, format='msgpack')
        print("7. MessagePack encoding:")
        print(f"   JSON size:      {len(json_bytes)} bytes")
        print(f"   MessagePack size: {len(msgpack_bytes)} bytes")
        print(f"   Compression:    {(1 - len(msgpack_bytes)/len(json_bytes))*100:.1f}%\n")
    else:
        print("7. MessagePack not available (install with: uv add msgpack)\n")
    
    print("="*70)
    print("Protocol demo complete!")
    print("="*70 + "\n")

