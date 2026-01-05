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
from ac_bridge.stepper import RealTimeStepper
from ac_bridge.protocol import (
    TelemetryFrame,
    ControlCommand,
    Transition,
    Message,
    MessageType,
    Codec,
)
from ac_bridge.timing import Ticker, MonotonicClock
from ac_bridge.action_smoother import (
    ActionSmoother,
    SmoothingConfig,
    get_conservative_config,
    get_moderate_config,
    get_aggressive_config,
    get_no_smoothing_config,
)

__version__ = "0.3.0"

__all__ = [
    # Main bridge interfaces
    "ACBridgeLocal",
    "ACBridgeWSClient",
    "ACBridge",  # Alias for ACBridgeLocal
    "RealTimeStepper",  # Stepper for consistent RL stepping
    
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
    
    # Action smoothing
    "ActionSmoother",
    "SmoothingConfig",
    "get_conservative_config",
    "get_moderate_config",
    "get_aggressive_config",
    "get_no_smoothing_config",
]

