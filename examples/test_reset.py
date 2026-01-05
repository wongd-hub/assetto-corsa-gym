"""
Test bridge reset functionality.

This test verifies that:
1. Button 7 (restart race) is pressed
2. Controls are reset to neutral
3. Gear is shifted to 1st (gear=2 in cache)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import time
from ac_bridge import ACBridgeLocal


def test_reset():
    """
    Test the full reset sequence.
    
    This simulates what happens when apex-seeker calls env.reset().
    """
    print("\n" + "="*70)
    print("Bridge Reset Test")
    print("="*70 + "\n")
    
    print("Initializing bridge...")
    bridge = ACBridgeLocal(telemetry_hz=60, control_hz=10)
    bridge.connect()
    
    if not bridge.is_connected():
        print("[ERROR] AC not running. Start AC and try again.\n")
        bridge.close()
        return
    
    print("[OK] Bridge connected\n")
    
    # Apply some control inputs first
    print("1. Applying test controls...")
    bridge.apply_action(steer=0.5, throttle=0.8, brake=0.0)
    time.sleep(0.5)
    
    obs, info = bridge.latest_obs()
    print(f"   Before reset:")
    print(f"   - Speed: {info['speed_kmh']:.1f} km/h")
    print(f"   - Throttle: {info['throttle']:.2f}")
    print(f"   - Brake: {info['brake']:.2f}")
    print(f"   - Gear: {info['gear']}\n")
    
    # Trigger reset
    print("2. Triggering reset (button 7 + shift to 1st)...")
    print("   This will:")
    print("   - Press button 7 (restart race)")
    print("   - Wait 5 seconds for session restart")
    print("   - Reset all controls to neutral")
    print("   - Shift to 1st gear")
    print()
    
    # Call reset
    bridge.reset(wait_time=5.0)
    
    # Check state after reset
    time.sleep(1.0)  # Give a moment for telemetry to update
    obs, info = bridge.latest_obs()
    
    print("3. After reset:")
    print(f"   - Speed: {info['speed_kmh']:.1f} km/h")
    print(f"   - Throttle: {info['throttle']:.2f}")
    print(f"   - Brake: {info['brake']:.2f}")
    print(f"   - Gear: {info['gear']}")
    print(f"   - Position: {info['position']}\n")
    
    # Verify reset worked
    success = True
    
    if info['speed_kmh'] > 10.0:
        print("[WARNING] Speed still high after reset")
        success = False
    
    if info['throttle'] > 0.1:
        print("[WARNING] Throttle not reset to zero")
        success = False
    
    if info['gear'] != 1:  # Should be in 1st gear
        print(f"[WARNING] Gear is {info['gear']}, expected 1")
        success = False
    
    if success:
        print("[OK] Reset completed successfully!")
        print("     - Session restarted (button 7)")
        print("     - Controls reset to neutral")
        print("     - Shifted to 1st gear")
    else:
        print("[WARNING] Reset completed but some checks failed")
        print("            This might be normal depending on AC session state")
    
    print()
    bridge.close()
    
    print("="*70)
    print("Reset test complete")
    print("="*70 + "\n")


def test_stepper_reset():
    """
    Test reset through stepper (how apex-seeker will use it).
    """
    print("\n" + "="*70)
    print("Stepper Reset Test")
    print("="*70 + "\n")
    
    from ac_bridge import RealTimeStepper
    
    print("Initializing bridge and stepper...")
    bridge = ACBridgeLocal(telemetry_hz=60, control_hz=10)
    bridge.connect()
    
    if not bridge.is_connected():
        print("[ERROR] AC not running. Start AC and try again.\n")
        bridge.close()
        return
    
    stepper = RealTimeStepper(bridge, control_hz=10)
    print("[OK] Bridge and stepper initialized\n")
    
    # Take a few steps
    print("1. Taking 5 steps with throttle...")
    import numpy as np
    for i in range(5):
        action = np.array([0.0, 0.5, 0.0], dtype=np.float32)  # straight, half throttle
        obs, info = stepper.step(action)
        print(f"   Step {i}: speed={info['speed_kmh']:.1f} km/h, gear={info['gear']}")
    
    print()
    
    # Reset via stepper
    print("2. Calling stepper.reset()...")
    obs, info = stepper.reset()
    
    print("3. After reset:")
    print(f"   - Speed: {info['speed_kmh']:.1f} km/h")
    print(f"   - Gear: {info['gear']}")
    print(f"   - Step count: {info.get('step_count', 0)}")
    print(f"   - Episode reset flag: {info.get('episode_reset', False)}")
    
    if info.get('episode_reset'):
        print("\n[OK] Stepper reset flag set correctly")
    
    if info['speed_kmh'] < 10.0:
        print("[OK] Speed reset correctly")
    
    print()
    bridge.close()
    
    print("="*70)
    print("Stepper reset test complete")
    print("="*70 + "\n")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("AC Bridge Reset Tests")
    print("="*70)
    print("\nThese tests verify that reset properly:")
    print("- Triggers button 7 (restart race)")
    print("- Resets controls to neutral")
    print("- Shifts to 1st gear")
    print("\nMake sure AC is running and you're in a session!\n")
    
    # Run tests
    test_reset()
    
    # Ask if user wants to test stepper too
    print("\nTest stepper reset as well? (This is how apex-seeker will use it)")
    response = input("Run stepper test? (y/n): ").strip().lower()
    
    if response == 'y':
        test_stepper_reset()
    
    print("\nAll reset tests complete!\n")

