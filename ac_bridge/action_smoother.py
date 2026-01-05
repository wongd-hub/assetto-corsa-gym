"""
Action smoothing and rate limiting for stable RL training.

Implements:
1. Rate limiting (max delta per step)
2. Low-pass filtering (EMA smoothing)
3. Asymmetric pedal dynamics
4. Action squashing (hard clamps)

The golden rule: Policy chooses targets, controller decides how fast to reach them.
"""

import numpy as np
from dataclasses import dataclass
import structlog

logger = structlog.get_logger()


@dataclass
class SmoothingConfig:
    """
    Configuration for action smoothing.
    
    All features can be enabled/disabled independently.
    """
    
    # Rate limiting (max delta per step)
    enable_rate_limiting: bool = True
    max_steer_delta: float = 0.15      # Full lock in ~0.7s at 10 Hz
    max_throttle_up: float = 0.10      # Smooth application
    max_throttle_down: float = 0.25    # Faster lift
    max_brake_up: float = 0.30         # Quick braking
    max_brake_down: float = 0.10       # Slow release
    max_clutch_delta: float = 0.50     # Clutch can move fast
    
    # Low-pass filtering (EMA smoothing)
    enable_ema_smoothing: bool = True
    steer_alpha: float = 0.6           # 0.5-0.7 for steering
    throttle_alpha: float = 0.7        # 0.6-0.8 for throttle
    brake_alpha: float = 0.7           # Can be asymmetric
    clutch_alpha: float = 0.8          # Less smoothing for clutch
    
    # Hard clamps (always enabled)
    clamp_steer_min: float = -1.0
    clamp_steer_max: float = 1.0
    clamp_pedals_min: float = 0.0
    clamp_pedals_max: float = 1.0


class ActionSmoother:
    """
    Smooths and rate-limits actions for stable RL training.
    
    Prevents jerky inputs that destabilize training:
    - Limits how fast inputs can change
    - Smooths noisy policy outputs
    - Models realistic pedal dynamics
    - Always clamps to safe ranges
    
    Usage:
        smoother = ActionSmoother(config=SmoothingConfig())
        smooth_action = smoother.smooth(target_action)
    """
    
    def __init__(self, config: SmoothingConfig = None):
        """
        Initialize action smoother.
        
        Args:
            config: Smoothing configuration (defaults to moderate settings)
        """
        self.config = config or SmoothingConfig()
        
        # State tracking
        self._prev_steer = 0.0
        self._prev_throttle = 0.0
        self._prev_brake = 0.0
        self._prev_clutch = 0.0
        
        # Statistics
        self._step_count = 0
        self._total_steer_delta = 0.0
        self._total_throttle_delta = 0.0
        self._total_brake_delta = 0.0
        
        logger.info(
            "action_smoother_initialized",
            rate_limiting=self.config.enable_rate_limiting,
            ema_smoothing=self.config.enable_ema_smoothing,
            max_steer_delta=self.config.max_steer_delta
        )
    
    def smooth(
        self,
        steer: float,
        throttle: float,
        brake: float,
        clutch: float = 0.0
    ) -> tuple[float, float, float, float]:
        """
        Apply smoothing to target action.
        
        Args:
            steer: Target steering (-1 to 1)
            throttle: Target throttle (0 to 1)
            brake: Target brake (0 to 1)
            clutch: Target clutch (0 to 1)
        
        Returns:
            (smooth_steer, smooth_throttle, smooth_brake, smooth_clutch)
        """
        # Phase 0: Hard clamps on inputs (always applied)
        steer = np.clip(steer, self.config.clamp_steer_min, self.config.clamp_steer_max)
        throttle = np.clip(throttle, self.config.clamp_pedals_min, self.config.clamp_pedals_max)
        brake = np.clip(brake, self.config.clamp_pedals_min, self.config.clamp_pedals_max)
        clutch = np.clip(clutch, self.config.clamp_pedals_min, self.config.clamp_pedals_max)
        
        # Phase 1: Rate limiting (if enabled)
        if self.config.enable_rate_limiting:
            steer = self._apply_rate_limit(
                steer, self._prev_steer,
                self.config.max_steer_delta,
                self.config.max_steer_delta
            )
            
            # Asymmetric pedal dynamics
            throttle = self._apply_rate_limit(
                throttle, self._prev_throttle,
                self.config.max_throttle_up,
                self.config.max_throttle_down
            )
            
            brake = self._apply_rate_limit(
                brake, self._prev_brake,
                self.config.max_brake_up,
                self.config.max_brake_down
            )
            
            clutch = self._apply_rate_limit(
                clutch, self._prev_clutch,
                self.config.max_clutch_delta,
                self.config.max_clutch_delta
            )
        
        # Phase 2: EMA smoothing (if enabled)
        if self.config.enable_ema_smoothing:
            steer = self._apply_ema(steer, self._prev_steer, self.config.steer_alpha)
            throttle = self._apply_ema(throttle, self._prev_throttle, self.config.throttle_alpha)
            brake = self._apply_ema(brake, self._prev_brake, self.config.brake_alpha)
            clutch = self._apply_ema(clutch, self._prev_clutch, self.config.clutch_alpha)
        
        # Final clamps (safety)
        steer = np.clip(steer, self.config.clamp_steer_min, self.config.clamp_steer_max)
        throttle = np.clip(throttle, self.config.clamp_pedals_min, self.config.clamp_pedals_max)
        brake = np.clip(brake, self.config.clamp_pedals_min, self.config.clamp_pedals_max)
        clutch = np.clip(clutch, self.config.clamp_pedals_min, self.config.clamp_pedals_max)
        
        # Track statistics
        self._total_steer_delta += abs(steer - self._prev_steer)
        self._total_throttle_delta += abs(throttle - self._prev_throttle)
        self._total_brake_delta += abs(brake - self._prev_brake)
        
        # Update previous values
        self._prev_steer = steer
        self._prev_throttle = throttle
        self._prev_brake = brake
        self._prev_clutch = clutch
        
        self._step_count += 1
        
        return steer, throttle, brake, clutch
    
    def _apply_rate_limit(
        self,
        target: float,
        prev: float,
        max_up_rate: float,
        max_down_rate: float
    ) -> float:
        """
        Apply asymmetric rate limiting.
        
        Args:
            target: Target value
            prev: Previous value
            max_up_rate: Max increase per step
            max_down_rate: Max decrease per step
        
        Returns:
            Rate-limited value
        """
        delta = target - prev
        
        if delta > 0:
            # Increasing
            delta = min(delta, max_up_rate)
        else:
            # Decreasing
            delta = max(delta, -max_down_rate)
        
        return prev + delta
    
    def _apply_ema(self, target: float, prev: float, alpha: float) -> float:
        """
        Apply exponential moving average smoothing.
        
        Args:
            target: Target value
            prev: Previous smoothed value
            alpha: Smoothing factor (0=full smoothing, 1=no smoothing)
        
        Returns:
            Smoothed value
        """
        return alpha * target + (1.0 - alpha) * prev
    
    def reset(self):
        """
        Reset smoother state.
        
        Call this when starting a new episode.
        """
        self._prev_steer = 0.0
        self._prev_throttle = 0.0
        self._prev_brake = 0.0
        self._prev_clutch = 0.0
        
        logger.info("action_smoother_reset")
    
    def get_stats(self) -> dict:
        """
        Get smoothing statistics.
        
        Returns:
            Dict with average deltas and step count
        """
        if self._step_count == 0:
            return {'step_count': 0}
        
        return {
            'step_count': self._step_count,
            'avg_steer_delta': self._total_steer_delta / self._step_count,
            'avg_throttle_delta': self._total_throttle_delta / self._step_count,
            'avg_brake_delta': self._total_brake_delta / self._step_count,
            'config': {
                'rate_limiting': self.config.enable_rate_limiting,
                'ema_smoothing': self.config.enable_ema_smoothing,
                'max_steer_delta': self.config.max_steer_delta
            }
        }


# Preset configurations

def get_conservative_config() -> SmoothingConfig:
    """Conservative: Very smooth, human-like (good for initial training)."""
    return SmoothingConfig(
        max_steer_delta=0.10,
        max_throttle_up=0.08,
        max_throttle_down=0.20,
        max_brake_up=0.25,
        max_brake_down=0.08,
        steer_alpha=0.5,
        throttle_alpha=0.6,
        brake_alpha=0.6
    )


def get_moderate_config() -> SmoothingConfig:
    """Moderate: Balanced (recommended default)."""
    return SmoothingConfig(
        max_steer_delta=0.15,
        max_throttle_up=0.10,
        max_throttle_down=0.25,
        max_brake_up=0.30,
        max_brake_down=0.10,
        steer_alpha=0.6,
        throttle_alpha=0.7,
        brake_alpha=0.7
    )


def get_aggressive_config() -> SmoothingConfig:
    """Aggressive: More responsive (for advanced policies)."""
    return SmoothingConfig(
        max_steer_delta=0.20,
        max_throttle_up=0.15,
        max_throttle_down=0.30,
        max_brake_up=0.40,
        max_brake_down=0.15,
        steer_alpha=0.7,
        throttle_alpha=0.8,
        brake_alpha=0.8
    )


def get_no_smoothing_config() -> SmoothingConfig:
    """Disable all smoothing (hard clamps only)."""
    return SmoothingConfig(
        enable_rate_limiting=False,
        enable_ema_smoothing=False
    )


# Demo
if __name__ == "__main__":
    print("\n" + "="*70)
    print("Action Smoother Demo")
    print("="*70 + "\n")
    
    # Test with step inputs
    smoother = ActionSmoother(config=get_moderate_config())
    
    print("Simulating sudden steering input (0.0 → 1.0):\n")
    
    prev_smooth = 0.0
    for step in range(20):
        # Sudden step input
        target = 1.0 if step >= 5 else 0.0
        
        # Smooth it
        smooth_steer, _, _, _ = smoother.smooth(target, 0.0, 0.0, 0.0)
        
        delta = smooth_steer - prev_smooth
        print(
            f"Step {step:02d}: "
            f"target={target:.2f} → "
            f"smooth={smooth_steer:.3f} "
            f"(Δ={delta:+.3f})"
        )
        
        prev_smooth = smooth_steer
        
        # Stop when converged
        if abs(smooth_steer - target) < 0.01:
            print(f"\n  Converged to target in {step-5} steps")
            break
    
    print("\n" + "="*70)
    print("Key Observations:")
    print("="*70)
    print(f"- Max delta per step: {smoother.config.max_steer_delta}")
    print(f"- Smoothing (alpha): {smoother.config.steer_alpha}")
    print(f"- Time to full lock: ~{1.0/smoother.config.max_steer_delta * 0.1:.1f}s at 10 Hz")
    print("="*70 + "\n")
    
    # Show all presets
    print("Available Presets:\n")
    
    for name, config_fn in [
        ("Conservative", get_conservative_config),
        ("Moderate", get_moderate_config),
        ("Aggressive", get_aggressive_config),
        ("No Smoothing", get_no_smoothing_config)
    ]:
        cfg = config_fn()
        print(f"{name}:")
        print(f"  max_steer_delta: {cfg.max_steer_delta}")
        print(f"  steer_alpha: {cfg.steer_alpha}")
        print(f"  throttle up/down: {cfg.max_throttle_up:.2f}/{cfg.max_throttle_down:.2f}")
        print(f"  brake up/down: {cfg.max_brake_up:.2f}/{cfg.max_brake_down:.2f}")
        print()

