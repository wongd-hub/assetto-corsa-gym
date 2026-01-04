"""
Closed-loop demonstration: read telemetry and send simple control commands.

This shows how to integrate telemetry reading with control output.
Implements a simple speed-holding controller as demonstration.
"""

import sys
import os
# Add parent directory to path so we can import ac_bridge
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import time
from ac_bridge.telemetry.ac_native_memory import ACSharedMemory
from ac_bridge.control import VJoyController


def simple_speed_controller(target_speed_kmh: float = 100.0, kp: float = 0.01):
    """
    Simple proportional speed controller.
    
    Args:
        target_speed_kmh: Desired speed in km/h
        kp: Proportional gain
    """
    print("="*70)
    print("CLOSED-LOOP CONTROL DEMO: SPEED HOLD")
    print("="*70)
    print(f"\nTarget speed: {target_speed_kmh} km/h")
    print("Press Ctrl+C to stop\n")
    
    asm = ACSharedMemory()
    controller = VJoyController(device_id=1)
    
    try:
        while True:
            if not asm.is_connected():
                print("Waiting for AC...", end='\r')
                time.sleep(1)
                continue
            
            # Read telemetry
            p = asm.physics
            current_speed = p.speedKmh
            
            # Simple P controller
            error = target_speed_kmh - current_speed
            throttle = max(0.0, min(1.0, kp * error))
            brake = max(0.0, min(1.0, -kp * error)) if error < 0 else 0.0
            
            # Apply control
            controller.set_controls(
                throttle=throttle,
                brake=brake,
                steering=0.0  # Keep straight
            )
            
            # Display status
            print(
                f"Speed: {current_speed:6.1f} km/h | "
                f"Target: {target_speed_kmh:6.1f} | "
                f"Error: {error:+6.1f} | "
                f"Throttle: {throttle:.2f} | "
                f"Brake: {brake:.2f}",
                end='\r'
            )
            
            time.sleep(0.05)  # 20 Hz
            
    except KeyboardInterrupt:
        print("\n\nStopped by user")
    finally:
        controller.close()
        asm.close()
        print("\nClosed-loop demo ended.")


def main():
    print("Available demos:")
    print("  1. Speed holder (maintains 100 km/h)")
    print("  2. Speed holder (maintains 150 km/h)")
    print()
    
    choice = input("Select demo (1-2): ").strip()
    
    if choice == '1':
        simple_speed_controller(target_speed_kmh=100.0)
    elif choice == '2':
        simple_speed_controller(target_speed_kmh=150.0)
    else:
        print("Invalid choice")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

