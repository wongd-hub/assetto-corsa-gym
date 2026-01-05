"""
Bridge client API for apex-seeker integration.

Provides clean interface for RL training:
- ACBridgeLocal: Same-machine path (direct shared memory + vJoy)
- ACBridgeWSClient: Cloud path (WebSocket to remote server)

Usage in apex-seeker:
    from ac_bridge import ACBridgeLocal
    
    bridge = ACBridgeLocal(telemetry_hz=60, control_hz=10)
    bridge.connect()
    
    obs, info = bridge.latest_obs()
    bridge.apply_action(steer=0.0, throttle=0.5, brake=0.0)
    bridge.reset()
"""

import time
import threading
from typing import Optional, Tuple
import numpy as np
import structlog

from ac_bridge.timing import Ticker
from ac_bridge.protocol import TelemetryFrame, ControlCommand
from ac_bridge.telemetry.ac_native_memory import ACSharedMemory
from ac_bridge.control.vjoy_controller import VJoyController
from ac_bridge.action_smoother import ActionSmoother, SmoothingConfig, get_moderate_config

logger = structlog.get_logger()


class ACBridgeLocal:
    """
    Local bridge for same-machine RL training.
    
    Fast path: direct shared memory read + vJoy control.
    Background thread continuously polls AC telemetry at specified rate.
    Main thread can call latest_obs() to get most recent cached frame.
    
    This decouples telemetry polling (e.g., 60 Hz) from RL stepping (e.g., 10 Hz).
    
    Example:
        bridge = ACBridgeLocal(telemetry_hz=60, control_hz=10)
        bridge.connect()
        
        # In training loop:
        obs, info = bridge.latest_obs()  # Get cached latest
        bridge.apply_action(steer=0.2, throttle=0.8, brake=0.0)
        
        bridge.close()
    """
    
    def __init__(
        self,
        telemetry_hz: int = 60,
        control_hz: int = 10,
        controller: str = "vjoy",
        device_id: int = 1,
        obs_dim: int = 15,
        smoothing_config: SmoothingConfig = None
    ):
        """
        Initialize bridge.
        
        Args:
            telemetry_hz: Rate to poll AC shared memory (default: 60 Hz)
            control_hz: Target control rate for stepper (default: 10 Hz)
            controller: Controller type, currently only "vjoy"
            device_id: vJoy device ID
            obs_dim: Observation vector dimension (default: 15)
            smoothing_config: Action smoothing configuration (default: moderate)
                             Set to None to disable smoothing
        """
        self.telemetry_hz = telemetry_hz
        self.control_hz = control_hz
        self.obs_dim = obs_dim
        
        # Initialize hardware interfaces
        self.telemetry_reader = ACSharedMemory()
        self.controller = VJoyController(device_id=device_id) if controller == "vjoy" else None
        
        # Action smoothing (use moderate config by default)
        if smoothing_config is None:
            smoothing_config = get_moderate_config()
        self.action_smoother = ActionSmoother(config=smoothing_config) if smoothing_config else None
        
        # Timing
        self.telemetry_ticker = Ticker(hz=telemetry_hz)
        
        # Thread-safe cache for latest telemetry
        self._latest_frame: Optional[TelemetryFrame] = None
        self._frame_lock = threading.Lock()
        
        # Background thread
        self._telemetry_thread: Optional[threading.Thread] = None
        self._running = False
        self._connected = False
        
        logger.info(
            "bridge_initialized",
            telemetry_hz=telemetry_hz,
            control_hz=control_hz,
            controller=controller,
            device_id=device_id
        )
    
    def connect(self) -> None:
        """
        Start telemetry polling thread.
        
        This begins background telemetry collection. Call this before
        using latest_obs() or apply_action().
        """
        if self._running:
            logger.warning("bridge_already_connected")
            return
        
        self._running = True
        self._telemetry_thread = threading.Thread(
            target=self._poll_telemetry_loop,
            daemon=True,
            name="ACBridge-Telemetry"
        )
        self._telemetry_thread.start()
        self._connected = True
        
        # Wait for first frame
        timeout = 5.0
        start = time.time()
        while self._latest_frame is None and (time.time() - start) < timeout:
            time.sleep(0.01)
        
        if self._latest_frame is None:
            logger.warning("no_initial_frame", msg="AC might not be running")
        else:
            logger.info("bridge_connected", first_frame_seq=self._latest_frame.seq)
    
    def close(self) -> None:
        """
        Stop threads and cleanup resources.
        
        Call this when done training to ensure clean shutdown.
        """
        logger.info("bridge_closing")
        
        self._running = False
        self._connected = False
        
        if self._telemetry_thread and self._telemetry_thread.is_alive():
            self._telemetry_thread.join(timeout=2.0)
        
        if self.controller:
            self.controller.reset()
            self.controller.close()
        
        self.telemetry_reader.close()
        
        logger.info("bridge_closed")
    
    def is_connected(self) -> bool:
        """Check if bridge is connected and receiving telemetry."""
        return self._connected and self._latest_frame is not None
    
    def latest_obs(self) -> Tuple[np.ndarray, dict]:
        """
        Get most recent telemetry snapshot.
        
        This is the main method apex-seeker will call in its Gym env step().
        Returns cached latest frame - no blocking, no polling.
        
        Returns:
            (obs, info) tuple where:
                obs: np.ndarray of shape (obs_dim,) - normalized observation
                info: dict with raw telemetry + timing metadata
        
        Raises:
            RuntimeError: If no telemetry available (AC not running or not connected)
        """
        with self._frame_lock:
            if self._latest_frame is None:
                raise RuntimeError(
                    "No telemetry available. Is AC running? Did you call connect()?"
                )
            
            return self._latest_frame.obs.copy(), self._latest_frame.info.copy()
    
    def apply_action(
        self,
        steer: float,
        throttle: float,
        brake: float,
        clutch: float = 0.0
    ) -> None:
        """
        Apply control action via vJoy with optional smoothing.
        
        If smoothing is enabled (default), applies:
        1. Rate limiting (max delta per step)
        2. EMA filtering (removes twitchy outputs)
        3. Asymmetric pedal dynamics (realistic application/release)
        4. Hard clamps (safety)
        
        This dramatically stabilizes RL training at 10 Hz.
        
        Args:
            steer: Target steering, -1.0 (left) to 1.0 (right)
            throttle: Target throttle, 0.0 to 1.0
            brake: Target brake, 0.0 to 1.0
            clutch: Target clutch, 0.0 to 1.0 (optional)
        """
        if not self.controller:
            raise RuntimeError("No controller available")
        
        # Apply smoothing if enabled
        if self.action_smoother:
            steer, throttle, brake, clutch = self.action_smoother.smooth(
                steer, throttle, brake, clutch
            )
        
        # Send smoothed action to vJoy
        self.controller.set_controls(
            throttle=throttle,
            brake=brake,
            steering=steer,
            clutch=clutch
        )
    
    def reset(self, wait_time: float = 5.0) -> None:
        """
        Trigger session restart and wait until ready.
        
        Presses button 7 (restart race), then button 9 (start race) 2s later,
        waits for session to start, then resets controls and shifts to 1st gear.
        
        Args:
            wait_time: Time to wait after reset (default: 5s)
        """
        logger.info("reset_requested")
        
        if not self.controller:
            raise RuntimeError("No controller available")
        
        # Step 1: Trigger restart (button 7)
        self.controller.restart_session()
        logger.info("reset_button_7_pressed", action="restart_race")
        
        # Step 2: Wait 2s, then press button 9 (start race)
        time.sleep(2.0)
        self.controller.press_button(9, duration=0.1)
        logger.info("reset_button_9_pressed", action="start_race")
        
        # Step 3: Wait remaining time for session to fully start
        remaining_wait = wait_time - 2.0
        if remaining_wait > 0:
            time.sleep(remaining_wait)
        
        # Step 4: Reset all controls to neutral
        self.controller.reset()
        
        # Step 5: Shift to 1st gear (gear=2 in cache: 0=R, 1=N, 2=1st)
        time.sleep(0.1)  # Small delay for controls to settle
        self.controller.set_gear(2)
        
        # Reset smoother state for new episode
        if self.action_smoother:
            self.action_smoother.reset()
        
        # Reset ticker for new episode
        self.telemetry_ticker.reset()
        
        logger.info("reset_complete", gear="1st")
    
    def get_smoother_stats(self) -> dict:
        """
        Get action smoother statistics.
        
        Returns:
            Dict with smoothing stats (step count, avg deltas, config)
            Empty dict if smoothing is disabled.
        """
        if not self.action_smoother:
            return {}
        return self.action_smoother.get_stats()
    
    def _poll_telemetry_loop(self):
        """
        Background thread: continuously poll AC telemetry.
        
        This runs at telemetry_hz, independently of RL step rate.
        Each frame is enriched with timing metadata and cached.
        """
        logger.info("telemetry_thread_started", hz=self.telemetry_hz)
        
        try:
            for seq, t_wall, dt, dt_actual in self.telemetry_ticker:
                if not self._running:
                    break
                
                # Check if AC is connected
                if not self.telemetry_reader.is_connected():
                    # No telemetry available, skip this tick
                    time.sleep(dt / 2)  # Sleep a bit to avoid busy loop
                    continue
                
                # Read and process telemetry
                try:
                    obs, info = self._read_and_process_telemetry()
                    
                    # Add timing metadata
                    info.update({
                        'seq': seq,
                        't_wall': t_wall,
                        'dt': dt,
                        'dt_actual': dt_actual
                    })
                    
                    # Create frame
                    frame = TelemetryFrame(
                        seq=seq,
                        t_wall=t_wall,
                        dt=dt,
                        dt_actual=dt_actual,
                        obs=obs,
                        info=info
                    )
                    
                    # Update cache (thread-safe)
                    with self._frame_lock:
                        self._latest_frame = frame
                
                except Exception as e:
                    logger.error("telemetry_read_error", error=str(e))
        
        except Exception as e:
            logger.error("telemetry_thread_error", error=str(e))
        
        finally:
            logger.info("telemetry_thread_stopped")
    
    def _read_and_process_telemetry(self) -> Tuple[np.ndarray, dict]:
        """
        Read AC telemetry and convert to standardized observation.
        
        This defines the observation space that apex-seeker will see.
        Customize this based on your RL task.
        
        Returns:
            (obs, info) tuple where:
                obs: Normalized observation vector
                info: Raw telemetry dict
        """
        p = self.telemetry_reader.physics
        g = self.telemetry_reader.graphics
        s = self.telemetry_reader.static
        
        # Build standardized observation vector (normalized)
        # Customize this for your specific RL task!
        obs = np.array([
            # Velocity (normalized)
            p.speedKmh / 300.0,                    # 0: speed (0-300 km/h → 0-1)
            p.velocity[0] / 100.0,                 # 1: velocity x
            p.velocity[1] / 100.0,                 # 2: velocity y  
            p.velocity[2] / 100.0,                 # 3: velocity z
            
            # Control inputs (already 0-1)
            p.gas,                                  # 4: throttle
            p.brake,                                # 5: brake
            p.steerAngle / 360.0,                  # 6: steering angle
            
            # Engine
            p.rpms / 10000.0,                      # 7: RPM
            p.gear / 6.0,                          # 8: gear
            
            # G-forces
            p.accG[0] / 3.0,                       # 9: lateral g
            p.accG[1] / 3.0,                       # 10: longitudinal g
            p.accG[2] / 3.0,                       # 11: vertical g
            
            # Wheel slip (average)
            np.mean(p.wheelSlip) / 2.0,            # 12: avg wheel slip
            
            # Track position
            float(p.numberOfTyresOut) / 4.0,       # 13: tyres out (0-4 → 0-1)
            
            # Damage indicator
            float(np.any(np.array(p.carDamage) > 0.05)),  # 14: any damage (binary)
        ], dtype=np.float32)
        
        # Ensure correct dimension
        if obs.shape[0] != self.obs_dim:
            logger.warning(
                "obs_dim_mismatch",
                expected=self.obs_dim,
                actual=obs.shape[0]
            )
            # Pad or truncate to match
            if obs.shape[0] < self.obs_dim:
                obs = np.pad(obs, (0, self.obs_dim - obs.shape[0]))
            else:
                obs = obs[:self.obs_dim]
        
        # Build info dict with all raw telemetry
        info = {
            # Core driving
            'speed_kmh': float(p.speedKmh),
            'rpm': int(p.rpms),
            'gear': int(p.gear),
            'throttle': float(p.gas),
            'brake': float(p.brake),
            'steer_angle': float(p.steerAngle),
            
            # Position & velocity
            'position': [float(g.carCoordinates[0]), float(g.carCoordinates[1]), float(g.carCoordinates[2])],
            'velocity': [float(p.velocity[0]), float(p.velocity[1]), float(p.velocity[2])],
            'local_velocity': [float(p.localVelocity[0]), float(p.localVelocity[1]), float(p.localVelocity[2])],
            'angular_velocity': [float(p.localAngularVel[0]), float(p.localAngularVel[1]), float(p.localAngularVel[2])],
            
            # G-forces
            'acc_g': [float(p.accG[0]), float(p.accG[1]), float(p.accG[2])],
            
            # Wheel physics
            'wheel_slip': [float(s) for s in p.wheelSlip],
            'wheel_load': [float(l) for l in p.wheelLoad],
            'wheel_pressure': [float(pr) for pr in p.wheelsPressure],
            'wheel_angular_speed': [float(s) for s in p.wheelAngularSpeed],
            
            # Track limits & penalties
            'tyres_out': int(p.numberOfTyresOut),
            'is_valid_lap': int(p.numberOfTyresOut) <= 2,  # ≤2 tyres out = valid
            
            # Lap & timing
            'completed_laps': int(g.completedLaps),
            'current_time': int(g.iCurrentTime),
            'best_time': int(g.iBestTime),
            'last_time': int(g.iLastTime),
            'current_sector_index': int(g.currentSectorIndex),
            'distance_traveled': float(g.distanceTraveled),
            
            # Damage
            'car_damage': [float(d) for d in p.carDamage],
            'bodywork_damaged': bool(np.any(np.array(p.carDamage) > 0.05)),
            'bodywork_critical': bool(np.any(np.array(p.carDamage) > 0.50)),
            'tyre_wear': [float(w) for w in p.tyreWear],
            'tyre_damaged': bool(np.any(np.array(p.tyreWear) > 0.80)),
            
            # Environment
            'surface_grip': float(g.surfaceGrip),
            'air_temp': float(p.airTemp),
            'road_temp': float(p.roadTemp),
            'is_in_pit_lane': bool(g.isInPitLane),
            
            # Session
            'session_type': int(g.session),
            'status': int(g.status),
            
            # Packet ID (for debugging)
            'packet_id': int(p.packetId),
        }
        
        return obs, info


class ACBridgeWSClient:
    """
    Remote bridge for cloud training with actor-learner pattern.
    
    Connects to remote WebSocket server and supports:
    - Local inference (low latency)
    - Transition batching (efficient network usage)
    - Weight updates from cloud learner
    
    TODO: Implement in future PR when cloud training is needed.
    
    Usage:
        bridge = ACBridgeWSClient(uri="ws://your-server:8765")
        await bridge.connect()
        
        # Same API as ACBridgeLocal
        obs, info = bridge.latest_obs()
        bridge.apply_action(...)
    """
    
    def __init__(self, uri: str, telemetry_hz: int = 20, control_hz: int = 10):
        """
        Initialize remote bridge.
        
        Args:
            uri: WebSocket server URI
            telemetry_hz: Telemetry rate
            control_hz: Control rate
        """
        self.uri = uri
        self.local_bridge = ACBridgeLocal(telemetry_hz, control_hz)
        
        logger.warning(
            "ws_client_not_implemented",
            msg="ACBridgeWSClient is a stub. Use ACBridgeLocal for now."
        )
    
    def connect(self):
        """Connect to remote server (not implemented)."""
        raise NotImplementedError("ACBridgeWSClient not yet implemented")
    
    def latest_obs(self):
        """Get latest observation (not implemented)."""
        raise NotImplementedError("ACBridgeWSClient not yet implemented")
    
    def apply_action(self, steer, throttle, brake):
        """Apply action (not implemented)."""
        raise NotImplementedError("ACBridgeWSClient not yet implemented")


# Backwards compatibility
ACBridge = ACBridgeLocal
