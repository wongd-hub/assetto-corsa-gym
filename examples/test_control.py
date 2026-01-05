"""
Simple vJoy control test script.

Tests vJoy installation and demonstrates basic control.
No external dependencies except pyvjoy.
"""

import sys
import os
# Add parent directory to path so we can import ac_bridge
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import time
from ac_bridge.control import VJoyController


def test_throttle(controller):
    """Test throttle sweep."""
    print("\nThrottle sweep (0 -> 100%)...")
    print("Map this axis in AC now!\n")
    for i in range(11):
        throttle = i / 10.0
        controller.set_throttle(throttle)
        print(f"  Throttle: {throttle*100:3.0f}%", end='\r')
        time.sleep(0.15)
    print()
    controller.set_throttle(0.0)
    print("Throttle test complete.\n")
    time.sleep(0.5)


def test_brake(controller):
    """Test brake sweep."""
    print("\nBrake sweep (0 -> 100%)...")
    print("Map this axis in AC now!\n")
    for i in range(11):
        brake = i / 10.0
        controller.set_brake(brake)
        print(f"  Brake: {brake*100:3.0f}%", end='\r')
        time.sleep(0.15)
    print()
    controller.set_brake(0.0)
    print("Brake test complete.\n")
    time.sleep(0.5)


def test_steering(controller):
    """Test steering sweep."""
    print("\nSteering sweep (left -> center -> right)...")
    print("Map this axis in AC now!\n")
    for i in range(21):
        steering = -1.0 + (i / 10.0)
        controller.set_steering(steering)
        print(f"  Steering: {steering:+.2f}", end='\r')
        time.sleep(0.15)
    print()
    controller.set_steering(0.0)
    print("Steering test complete.\n")
    time.sleep(0.5)


def test_clutch(controller):
    """Test clutch sweep."""
    print("\nClutch sweep (0 -> 100%)...")
    print("Map this axis in AC now!\n")
    for i in range(11):
        clutch = i / 10.0
        controller.set_clutch(clutch)
        print(f"  Clutch: {clutch*100:3.0f}%", end='\r')
        time.sleep(0.15)
    print()
    controller.set_clutch(0.0)
    print("Clutch test complete.\n")
    time.sleep(0.5)


def test_all_axes(controller):
    """Test all axes in sequence."""
    print("\nRunning all axis tests in sequence...\n")
    test_throttle(controller)
    test_brake(controller)
    test_steering(controller)
    test_clutch(controller)
    print("All axis tests complete!\n")


def test_combined(controller):
    """Test combined control with circle pattern."""
    import math
    print("\nCombined control test (circle pattern)...")
    print("This demonstrates multiple axes working together.\n")
    for i in range(100):
        angle = i / 100.0 * 6.28318  # 2*pi radians
        throttle = 0.5 + 0.5 * math.cos(angle)
        steering = math.sin(angle)
        
        controller.set_controls(throttle, 0.0, steering)
        print(f"  Throttle: {throttle:.2f} | Steering: {steering:+.2f}", end='\r')
        time.sleep(0.02)
    print()
    controller.reset()
    print("Combined test complete.\n")


def test_gears(controller):
    """Test gear shifting."""
    print("\nGear shift test (buttons 1-2)...")
    print("Map gear up/down buttons in AC now!\n")
    
    gears = [1, 2, 3, 4, 5, 4, 3, 2, 1]  # N, 1st, 2nd, 3rd, 4th, 5th, back down
    gear_names = ['R', 'N', '1st', '2nd', '3rd', '4th', '5th', '6th']
    
    for gear in gears:
        controller.set_gear(gear)
        name = gear_names[gear] if gear < len(gear_names) else str(gear)
        print(f"  Gear: {name}")
        time.sleep(0.5)
    
    controller.set_gear(1)  # Back to neutral
    print("Gear test complete.\n")


def test_individual_button(controller, button_num):
    """Test a specific button."""
    print(f"\nTesting Button {button_num}...")
    print(f"Map this button in AC now! (pressing for 2 seconds)\n")
    
    # Press and hold for 2 seconds
    controller.device.set_button(button_num, 1)
    print(f"  Button {button_num}: PRESSED")
    time.sleep(2)
    
    # Release
    controller.device.set_button(button_num, 0)
    print(f"  Button {button_num}: Released")
    print(f"Button {button_num} test complete.\n")
    time.sleep(0.5)


def test_all_buttons(controller):
    """Test all 12 buttons in sequence."""
    print("\nTesting all buttons (1-12) in sequence...")
    print("Map these buttons in AC for various functions!\n")
    
    for btn in range(1, 13):
        controller.device.set_button(btn, 1)
        print(f"  Button {btn}: PRESSED", end='\r')
        time.sleep(0.5)
        controller.device.set_button(btn, 0)
        time.sleep(0.2)
    
    print()
    print("All buttons test complete.\n")


def main():
    print("="*70)
    print("VJOY CONTROL TEST - INTERACTIVE MODE")
    print("="*70)
    print("\nInitializing vJoy device 1...")
    
    try:
        controller = VJoyController(device_id=1)
        print("Success! vJoy is working.\n")
        
        while True:
            print("-" * 70)
            print("Select test to run:")
            print("  1 - Test Throttle (Y axis)")
            print("  2 - Test Brake (Z axis)")
            print("  3 - Test Steering (X axis)")
            print("  4 - Test Clutch (RZ axis)")
            print("  5 - Test All Axes (sequence)")
            print("  6 - Test Combined (circle pattern)")
            print("  7 - Test Gears (buttons 1-2)")
            print("  8 - Test All Buttons (1-12)")
            print("  b1-b12 - Test Individual Button (e.g., 'b9' for button 9)")
            print("  r - Reset all controls")
            print("  s - Show performance stats")
            print("  0 - Exit")
            print("-" * 70)
            
            choice = input("\nEnter choice: ").strip().lower()
            
            if choice == '1':
                test_throttle(controller)
            elif choice == '2':
                test_brake(controller)
            elif choice == '3':
                test_steering(controller)
            elif choice == '4':
                test_clutch(controller)
            elif choice == '5':
                test_all_axes(controller)
            elif choice == '6':
                test_combined(controller)
            elif choice == '7':
                test_gears(controller)
            elif choice == '8':
                test_all_buttons(controller)
            elif choice.startswith('b'):
                try:
                    button_num = int(choice[1:])
                    if 1 <= button_num <= 12:
                        test_individual_button(controller, button_num)
                    else:
                        print("\nButton number must be 1-12.\n")
                except ValueError:
                    print("\nInvalid button number. Use b1-b12.\n")
            elif choice == 'r':
                controller.reset()
                # Also release all buttons (in case any are stuck)
                for btn in range(1, 13):
                    controller.device.set_button(btn, 0)
                print("\nAll controls reset to neutral and all buttons released.\n")
            elif choice == 's':
                stats = controller.get_stats()
                print("\nPerformance Statistics:")
                print(f"  Total updates: {stats['updates']}")
                print(f"  Duration: {stats['elapsed_seconds']:.2f}s")
                print(f"  Average rate: {stats['update_rate_hz']:.1f} Hz\n")
            elif choice == '0':
                break
            else:
                print("\nInvalid choice.\n")
        
        print("\nClosing vJoy controller...")
        controller.close()
        print("Done!\n")
        
    except Exception as e:
        print(f"\nError: {e}")
        print("\nTroubleshooting:")
        print("  1. Is vJoy installed? Download from: https://sourceforge.net/projects/vjoystick/")
        print("  2. Is device 1 configured? Open 'Configure vJoy' and enable device 1")
        print("  3. Are 4 axes enabled? X, Y, Z, RZ must be checked")
        print("  4. Is another app using the device?")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())

