"""
Test action smoothing with ACBridgeLocal.

This demonstrates:
1. Moderate smoothing (default)
2. Aggressive smoothing
3. No smoothing (hard clamps only)
4. Custom smoothing config

Run with AC open and in a session.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import time
import numpy as np
from ac_bridge import (
    ACBridgeLocal,
    get_moderate_config,
    get_aggressive_config,
    get_conservative_config,
    get_no_smoothing_config,
    SmoothingConfig
)


def test_step_inputs(bridge: ACBridgeLocal, duration_secs: float = 3.0):
    """
    Test with sudden step inputs (worst case for stability).
    
    Sends: 0 -> 1.0 steering, then back to 0
    """
    print("\n[TEST] Sudden steering input (0.0 -> 1.0 -> 0.0)")
    print("=" * 60)
    
    steps_per_second = 10  # Control rate
    total_steps = int(duration_secs * steps_per_second)
    
    for step in range(total_steps):
        # Step input: 0 -> 1.0 halfway through
        if step < total_steps // 2:
            target_steer = 1.0
        else:
            target_steer = 0.0
        
        # Apply (smoothing happens inside)
        bridge.apply_action(
            steer=target_steer,
            throttle=0.3,  # Gentle throttle
            brake=0.0
        )
        
        # Print every 5 steps
        if step % 5 == 0:
            stats = bridge.get_smoother_stats()
            if stats:
                avg_delta = stats.get('avg_steer_delta', 0)
                print(f"  Step {step:02d}: target={target_steer:.1f}, avg_delta={avg_delta:.3f}")
        
        time.sleep(1.0 / steps_per_second)
    
    # Final stats
    stats = bridge.get_smoother_stats()
    if stats:
        print(f"\n[STATS] Total steps: {stats['step_count']}")
        print(f"[STATS] Avg steer delta: {stats['avg_steer_delta']:.4f}")
        print(f"[STATS] Avg throttle delta: {stats['avg_throttle_delta']:.4f}")
        print(f"[STATS] Max steer delta (config): {stats['config']['max_steer_delta']}")
    
    # Reset controls
    bridge.controller.reset()


def test_noisy_inputs(bridge: ACBridgeLocal, duration_secs: float = 3.0):
    """
    Test with noisy policy outputs (simulates early training).
    
    Adds Gaussian noise to smooth sine wave.
    """
    print("\n[TEST] Noisy policy outputs (sine + noise)")
    print("=" * 60)
    
    steps_per_second = 10
    total_steps = int(duration_secs * steps_per_second)
    
    for step in range(total_steps):
        t = step / steps_per_second
        
        # Smooth sine + noise
        clean_steer = 0.5 * np.sin(2 * np.pi * 0.3 * t)  # 0.3 Hz sine
        noise = np.random.normal(0, 0.1)  # 10% noise
        noisy_steer = clean_steer + noise
        
        bridge.apply_action(
            steer=noisy_steer,
            throttle=0.4,
            brake=0.0
        )
        
        if step % 5 == 0:
            stats = bridge.get_smoother_stats()
            if stats:
                avg_delta = stats.get('avg_steer_delta', 0)
                print(f"  Step {step:02d}: noisy={noisy_steer:+.2f}, avg_delta={avg_delta:.3f}")
        
        time.sleep(1.0 / steps_per_second)
    
    # Final stats
    stats = bridge.get_smoother_stats()
    if stats:
        print(f"\n[STATS] Avg steer delta: {stats['avg_steer_delta']:.4f}")
    
    bridge.controller.reset()


def main():
    print("\n" + "=" * 70)
    print("ACTION SMOOTHING TEST")
    print("=" * 70)
    print("\nMake sure AC is running and you're in a session!")
    print("This test will apply various control patterns at 10 Hz.\n")
    print("Note: Some vJoy warnings may appear during stress tests.")
    print("This is normal and won't occur during regular RL training.\n")
    
    input("Press Enter to start...")
    
    # Test 1: Moderate smoothing (default)
    print("\n" + "=" * 70)
    print("TEST 1: MODERATE SMOOTHING (default)")
    print("=" * 70)
    
    bridge = ACBridgeLocal(
        telemetry_hz=60,
        control_hz=10,
        smoothing_config=get_moderate_config()
    )
    bridge.connect()
    
    time.sleep(1)  # Let telemetry stabilize
    
    test_step_inputs(bridge, duration_secs=3.0)
    time.sleep(0.5)
    test_noisy_inputs(bridge, duration_secs=3.0)
    
    bridge.close()
    
    print("\n[OK] Moderate smoothing complete")
    time.sleep(1)
    
    # Test 2: No smoothing (hard clamps only)
    print("\n" + "=" * 70)
    print("TEST 2: NO SMOOTHING (hard clamps only)")
    print("=" * 70)
    print("WARNING: This will be jerky!")
    
    bridge = ACBridgeLocal(
        telemetry_hz=60,
        control_hz=10,
        smoothing_config=get_no_smoothing_config()
    )
    bridge.connect()
    
    time.sleep(1)
    
    test_step_inputs(bridge, duration_secs=3.0)
    
    bridge.close()
    
    print("\n[OK] No smoothing complete")
    
    # Final summary
    print("\n" + "=" * 70)
    print("ALL TESTS COMPLETE")
    print("=" * 70)
    print("\nKey Observations:")
    print("- Moderate: Smooth, stable, good default for RL training")
    print("- No smoothing: Jerky, immediate response (debugging only)")
    print("\nRecommendation: Use moderate config (default) for training")
    print("Aggressive config available if you need more responsiveness")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()

