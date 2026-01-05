"""
Real-time stepper for consistent RL step timing.

Provides "stable step" abstraction that ensures actions are held for a
consistent duration before observations are sampled.

This is the recommended way to use ACBridgeLocal in a Gym environment.
"""

import time
from typing import Optional, Tuple
import numpy as np
import structlog

from ac_bridge.timing import Ticker
from ac_bridge.client import ACBridgeLocal

logger = structlog.get_logger()


class RealTimeStepper:
    """
    Enforces consistent step timing for RL training.
    
    Ensures that:
    1. Action is applied
    2. System waits for exactly one control tick
    3. Observation is sampled after action has taken effect
    
    This decouples the "apply action" timing from the "sample observation" timing,
    which is critical for RL where we want: a_t → s_{t+1}.
    
    Usage in apex-seeker Gym env:
        stepper = RealTimeStepper(bridge, control_hz=10)
        
        # In reset():
        obs, info = stepper.reset()
        
        # In step():
        obs, info = stepper.step(action)
    
    The stepper handles all timing internally using the drift-correcting Ticker.
    """
    
    def __init__(
        self,
        bridge: ACBridgeLocal,
        control_hz: int = 10,
        verify_action_applied: bool = False
    ):
        """
        Initialize stepper.
        
        Args:
            bridge: ACBridgeLocal instance (must be connected)
            control_hz: Control rate in Hz (default: 10 Hz = 0.1s steps)
            verify_action_applied: If True, verify action was applied by comparing
                                   with telemetry (adds latency, for debugging only)
        """
        self.bridge = bridge
        self.control_hz = control_hz
        self.verify_action_applied = verify_action_applied
        
        # Ticker for step timing
        self.ticker = Ticker(hz=control_hz)
        
        # Track last action for debugging
        self.last_action: Optional[np.ndarray] = None
        self.step_count = 0
        
        logger.info(
            "stepper_initialized",
            control_hz=control_hz,
            dt=1.0/control_hz
        )
    
    def step(self, action: np.ndarray) -> Tuple[np.ndarray, dict]:
        """
        Execute one RL step with consistent timing.
        
        This is the main method apex-seeker will call in env.step().
        
        Steps:
        1. Apply action to bridge
        2. Wait for next control tick (drift-corrected)
        3. Sample observation from bridge
        4. Return obs + enriched info
        
        Args:
            action: Action array [steer, throttle, brake] or [steer, throttle, brake, clutch]
                   Each component should be in appropriate range:
                   - steer: -1.0 (left) to 1.0 (right)
                   - throttle: 0.0 to 1.0
                   - brake: 0.0 to 1.0
                   - clutch: 0.0 to 1.0 (optional)
        
        Returns:
            (obs, info) tuple where:
                obs: Observation array from bridge
                info: Dict with telemetry + step timing metadata
        """
        # Parse action
        if len(action) < 3:
            raise ValueError(f"Action must have at least 3 components, got {len(action)}")
        
        steer = float(action[0])
        throttle = float(action[1])
        brake = float(action[2])
        clutch = float(action[3]) if len(action) > 3 else 0.0
        
        # Validate action ranges
        if not (-1.0 <= steer <= 1.0):
            logger.warning("action_out_of_range", component="steer", value=steer)
            steer = np.clip(steer, -1.0, 1.0)
        if not (0.0 <= throttle <= 1.0):
            logger.warning("action_out_of_range", component="throttle", value=throttle)
            throttle = np.clip(throttle, 0.0, 1.0)
        if not (0.0 <= brake <= 1.0):
            logger.warning("action_out_of_range", component="brake", value=brake)
            brake = np.clip(brake, 0.0, 1.0)
        
        # Apply action immediately
        self.bridge.apply_action(steer, throttle, brake, clutch)
        self.last_action = action
        
        # Wait for next control tick (drift-corrected)
        seq, t_wall, dt, dt_actual = self.ticker.tick()
        
        # Sample observation AFTER action has been applied
        obs, info = self.bridge.latest_obs()
        
        # Enrich info with step metadata
        info.update({
            'step_seq': seq,
            'step_t_wall': t_wall,
            'step_dt': dt,
            'step_dt_actual': dt_actual,
            'step_count': self.step_count,
            'action': action.tolist() if isinstance(action, np.ndarray) else list(action)
        })
        
        # Optional: verify action was applied (debugging only)
        if self.verify_action_applied:
            self._verify_action(steer, throttle, brake, info)
        
        self.step_count += 1
        
        return obs, info
    
    def reset(self) -> Tuple[np.ndarray, dict]:
        """
        Reset stepper and return initial observation.
        
        This should be called by apex-seeker env.reset().
        
        Returns:
            (obs, info) tuple for initial state
        """
        logger.info("stepper_reset")
        
        # Trigger bridge reset (restarts AC session)
        self.bridge.reset()
        
        # Reset ticker for new episode
        self.ticker.reset()
        self.step_count = 0
        self.last_action = None
        
        # Get initial observation
        obs, info = self.bridge.latest_obs()
        
        # Add reset metadata
        info.update({
            'step_seq': 0,
            'step_count': 0,
            'episode_reset': True
        })
        
        return obs, info
    
    def _verify_action(self, steer: float, throttle: float, brake: float, info: dict):
        """
        Verify that action was applied by comparing with telemetry.
        
        This is for debugging only and adds latency.
        
        Args:
            steer, throttle, brake: Commanded values
            info: Telemetry dict to check against
        """
        # Allow small tolerance for rounding/quantization
        tolerance = 0.05
        
        actual_throttle = info.get('throttle', 0.0)
        actual_brake = info.get('brake', 0.0)
        
        if abs(actual_throttle - throttle) > tolerance:
            logger.warning(
                "action_mismatch",
                component="throttle",
                commanded=throttle,
                actual=actual_throttle,
                diff=abs(actual_throttle - throttle)
            )
        
        if abs(actual_brake - brake) > tolerance:
            logger.warning(
                "action_mismatch",
                component="brake",
                commanded=brake,
                actual=actual_brake,
                diff=abs(actual_brake - brake)
            )
        
        # Note: Steering angle is harder to verify because it's in degrees
        # and may have steering ratio applied. Skip for now.
    
    def get_stats(self) -> dict:
        """
        Get stepper statistics.
        
        Returns:
            Dict with timing stats and step counts
        """
        ticker_stats = self.ticker.get_stats()
        
        return {
            'step_count': self.step_count,
            'control_hz': self.control_hz,
            'ticker_stats': ticker_stats,
            'last_action': self.last_action.tolist() if self.last_action is not None else None
        }


# Demo showing stepper usage
if __name__ == "__main__":
    import sys
    import os
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
    
    from ac_bridge.client import ACBridgeLocal
    
    print("\n" + "="*70)
    print("RealTimeStepper Demo")
    print("="*70 + "\n")
    
    print("Initializing bridge and stepper...")
    bridge = ACBridgeLocal(telemetry_hz=60, control_hz=10)
    bridge.connect()
    
    if not bridge.is_connected():
        print("AC not running. Start AC and try again.\n")
        bridge.close()
        sys.exit(1)
    
    stepper = RealTimeStepper(bridge, control_hz=10)
    print("   [OK] Bridge and stepper initialized\n")
    
    print("Running 30 steps (3 seconds at 10 Hz)...")
    print("Applying gentle sine wave steering\n")
    
    step_times = []
    
    try:
        for i in range(30):
            # Create action (sine wave steering)
            t = i * 0.1
            steer = 0.2 * np.sin(2 * np.pi * 0.5 * t)
            throttle = 0.3
            brake = 0.0
            action = np.array([steer, throttle, brake], dtype=np.float32)
            
            # Step using stepper (handles timing)
            step_start = time.perf_counter()
            obs, info = stepper.step(action)
            step_elapsed = time.perf_counter() - step_start
            step_times.append(step_elapsed)
            
            # Print status every 5 steps
            if i % 5 == 0:
                print(
                    f"Step {i:02d}: "
                    f"speed={info['speed_kmh']:6.1f} km/h | "
                    f"steer={steer:+.2f} | "
                    f"step_dt={info['step_dt_actual']*1000:.1f}ms | "
                    f"total={step_elapsed*1000:.1f}ms"
                )
    
    except KeyboardInterrupt:
        print("\nInterrupted")
    
    finally:
        bridge.close()
    
    # Show statistics
    print("\n" + "="*70)
    print("Statistics:")
    print("="*70)
    
    stats = stepper.get_stats()
    print(f"Steps completed:     {stats['step_count']}")
    print(f"Control frequency:   {stats['control_hz']} Hz")
    print(f"Ticker drift:        {stats['ticker_stats']['total_drift_ms']:+.2f} ms")
    print(f"Ticker jitter:       {stats['ticker_stats']['max_jitter_ms']:.2f} ms")
    
    if step_times:
        print(f"\nStep timing (wall time):")
        print(f"  Mean:              {np.mean(step_times)*1000:.2f} ms")
        print(f"  Std:               {np.std(step_times)*1000:.2f} ms")
        print(f"  Min:               {np.min(step_times)*1000:.2f} ms")
        print(f"  Max:               {np.max(step_times)*1000:.2f} ms")
    
    print("="*70 + "\n")

