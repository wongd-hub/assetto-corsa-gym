"""
AC Bridge - Plumbing layer for Assetto Corsa RL training.

Main exports for apex-seeker integration:
    - ACBridgeLocal: Same-machine bridge (direct shared memory + vJoy)
    - ACBridgeWSClient: Cloud bridge (WebSocket to remote server)
    - TelemetryFrame: Typed telemetry data structure
    - ControlCommand: Typed control command structure
    - Ticker: Drift-correcting frequency generator

Usage:
    from ac_bridge import ACBridgeLocal
    
    bridge = ACBridgeLocal(telemetry_hz=60, control_hz=10)
    bridge.connect()
    
    obs, info = bridge.latest_obs()
    bridge.apply_action(steer=0.0, throttle=0.5, brake=0.0)
    bridge.reset()
    
    bridge.close()
"""

from ac_bridge.client import ACBridgeLocal, ACBridgeWSClient, ACBridge
from ac_bridge.protocol import (
    TelemetryFrame,
    ControlCommand,
    Transition,
    Message,
    MessageType,
    Codec,
)
from ac_bridge.timing import Ticker, MonotonicClock

__version__ = "0.2.0"

__all__ = [
    # Main bridge interfaces
    "ACBridgeLocal",
    "ACBridgeWSClient",
    "ACBridge",  # Alias for ACBridgeLocal
    
    # Protocol types
    "TelemetryFrame",
    "ControlCommand",
    "Transition",
    "Message",
    "MessageType",
    "Codec",
    
    # Timing
    "Ticker",
    "MonotonicClock",
]

