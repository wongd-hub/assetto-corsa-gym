"""
Test ACBridgeLocal API - shows how apex-seeker will use the bridge.

This demonstrates the full bridge API that apex-seeker Gym env will use.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import time
import numpy as np
from ac_bridge import ACBridgeLocal


def test_basic_api():
    """
    Test basic bridge API: connect, read, control, reset.
    
    This is the minimal integration test for apex-seeker.
    """
    print("\n" + "="*70)
    print("Bridge API Test: Basic Operations")
    print("="*70 + "\n")
    
    # Initialize bridge
    print("1. Initializing bridge...")
    bridge = ACBridgeLocal(
        telemetry_hz=60,  # Poll AC at 60 Hz
        control_hz=10,    # Step at 10 Hz
        obs_dim=15        # Observation dimension
    )
    print("   [OK] Bridge initialized\n")
    
    # Connect (starts background telemetry thread)
    print("2. Connecting to AC...")
    bridge.connect()
    
    if not bridge.is_connected():
        print("   [ERROR] AC not running or no telemetry available")
        print("   Start AC and begin driving, then run this test again.\n")
        bridge.close()
        return False
    
    print("   [OK] Connected!\n")
    
    # Read telemetry
    print("3. Reading telemetry...")
    try:
        obs, info = bridge.latest_obs()
        
        print(f"   Observation shape: {obs.shape}")
        print(f"   Observation dtype: {obs.dtype}")
        print(f"   Sample values: {obs[:5]}")
        print(f"\n   Info keys: {list(info.keys())[:10]}...")
        print(f"   Speed: {info['speed_kmh']:.1f} km/h")
        print(f"   Seq: {info['seq']}, dt_actual: {info['dt_actual']:.4f}s")
        print(f"   Tyres out: {info['tyres_out']}, Valid lap: {info['is_valid_lap']}")
        print("   [OK] Telemetry read successful\n")
    
    except Exception as e:
        print(f"   [ERROR] Error reading telemetry: {e}\n")
        bridge.close()
        return False
    
    # Apply control
    print("4. Testing control output...")
    try:
        # Apply a safe action
        bridge.apply_action(
            steer=0.0,
            throttle=0.3,
            brake=0.0
        )
        print("   [OK] Control command sent\n")
        time.sleep(0.5)
        
        # Reset controls
        bridge.apply_action(steer=0.0, throttle=0.0, brake=0.0)
        print("   [OK] Controls reset\n")
    
    except Exception as e:
        print(f"   [ERROR] Error applying control: {e}\n")
        bridge.close()
        return False
    
    # Cleanup
    print("5. Closing bridge...")
    bridge.close()
    print("   [OK] Bridge closed\n")
    
    print("="*70)
    print("[OK] All tests passed!")
    print("="*70 + "\n")
    
    return True


def test_observation_loop(duration=5.0):
    """
    Test continuous observation reading - simulates apex-seeker Gym env.
    
    This demonstrates:
    - Stable observation updates
    - Timing metadata
    - No dropped frames
    """
    print("\n" + "="*70)
    print(f"Observation Loop Test: {duration}s at 10 Hz")
    print("="*70 + "\n")
    
    bridge = ACBridgeLocal(telemetry_hz=60, control_hz=10)
    bridge.connect()
    
    if not bridge.is_connected():
        print("AC not running. Start AC and try again.\n")
        bridge.close()
        return
    
    print("Reading observations (simulating RL training loop)...\n")
    
    start = time.time()
    samples = []
    prev_seq = None
    drops = 0
    
    try:
        while time.time() - start < duration:
            # This is what apex-seeker Gym env.step() will do
            obs, info = bridge.latest_obs()
            
            # Track sequence for drop detection
            if prev_seq is not None and info['seq'] != prev_seq:
                drops += abs(info['seq'] - prev_seq) - 1
            prev_seq = info['seq']
            
            samples.append(info)
            
            # Sleep for control rate (10 Hz)
            time.sleep(0.1)
    
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    
    finally:
        bridge.close()
    
    # Analyze results
    print("\n" + "="*70)
    print("Results:")
    print("="*70)
    print(f"Samples collected:  {len(samples)}")
    print(f"Expected samples:   ~{int(duration * 10)} (at 10 Hz)")
    print(f"Actual rate:        {len(samples) / duration:.2f} Hz")
    print(f"Dropped frames:     {drops}")
    
    if len(samples) > 1:
        dt_actuals = [s['dt_actual'] for s in samples]
        print(f"dt_actual mean:     {np.mean(dt_actuals)*1000:.2f} ms")
        print(f"dt_actual std:      {np.std(dt_actuals)*1000:.2f} ms")
    
    print("="*70 + "\n")


def test_control_loop(duration=3.0):
    """
    Test control in a loop - simulates apex-seeker taking actions.
    
    Applies a gentle sine wave steering pattern.
    """
    print("\n" + "="*70)
    print(f"Control Loop Test: {duration}s")
    print("="*70 + "\n")
    
    bridge = ACBridgeLocal(telemetry_hz=60, control_hz=10)
    bridge.connect()
    
    if not bridge.is_connected():
        print("AC not running. Start AC and try again.\n")
        bridge.close()
        return
    
    print("Applying sine wave steering (gentle)...\n")
    
    start = time.time()
    step = 0
    
    try:
        while time.time() - start < duration:
            # Read observation
            obs, info = bridge.latest_obs()
            
            # Compute action (sine wave for demo)
            t = time.time() - start
            steer = 0.2 * np.sin(2 * np.pi * 0.5 * t)  # 0.5 Hz sine
            throttle = 0.3  # Gentle throttle
            brake = 0.0
            
            # Apply action
            bridge.apply_action(steer=steer, throttle=throttle, brake=brake)
            
            # Print status
            if step % 10 == 0:
                print(
                    f"[{step:03d}] "
                    f"speed={info['speed_kmh']:6.1f} km/h | "
                    f"steer={steer:+.2f} → AC:{info['steer_angle']:+6.1f}° | "
                    f"throttle={throttle:.2f}"
                )
            
            step += 1
            time.sleep(0.1)  # 10 Hz
    
    except KeyboardInterrupt:
        print("\nInterrupted")
    
    finally:
        # Reset controls
        bridge.apply_action(steer=0.0, throttle=0.0, brake=0.0)
        bridge.close()
    
    print("\n[OK] Control loop complete\n")


def show_apex_seeker_example():
    """
    Show example code for apex-seeker Gym environment.
    
    This is how apex-seeker would integrate the bridge.
    """
    print("\n" + "="*70)
    print("apex-seeker Integration Example")
    print("="*70 + "\n")
    
    example_code = '''
import gymnasium as gym
import numpy as np
from ac_bridge import ACBridgeLocal

class AssettoCorsa_v0(gym.Env):
    """Gym environment for Assetto Corsa using ac-bridge."""
    
    def __init__(self):
        super().__init__()
        
        # Initialize bridge
        self.bridge = ACBridgeLocal(
            telemetry_hz=60,  # Poll AC at 60 Hz
            control_hz=10     # Step at 10 Hz
        )
        self.bridge.connect()
        
        # Define spaces
        self.observation_space = gym.spaces.Box(
            low=-1.0, high=1.0, shape=(15,), dtype=np.float32
        )
        self.action_space = gym.spaces.Box(
            low=np.array([-1.0, 0.0, 0.0]),  # steer, throttle, brake
            high=np.array([1.0, 1.0, 1.0]),
            dtype=np.float32
        )
    
    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        
        # Trigger AC session restart
        self.bridge.reset()
        
        # Get initial observation
        obs, info = self.bridge.latest_obs()
        return obs, info
    
    def step(self, action):
        # Apply action to AC
        steer, throttle, brake = action
        self.bridge.apply_action(steer, throttle, brake)
        
        # Wait for next tick (handled by bridge timing)
        time.sleep(1.0 / 10)  # 10 Hz
        
        # Get new observation
        obs, info = self.bridge.latest_obs()
        
        # Compute reward (YOUR LOGIC)
        reward = self._compute_reward(obs, info)
        
        # Check if done (YOUR LOGIC)
        done = self._is_done(info)
        truncated = False
        
        return obs, reward, done, truncated, info
    
    def _compute_reward(self, obs, info):
        """Define reward function (customize for your task)."""
        reward = 0.0
        
        # Reward for speed
        reward += info['speed_kmh'] / 100.0
        
        # Penalty for going off track
        if info['tyres_out'] > 2:
            reward -= 10.0
        
        # Penalty for damage
        if info['bodywork_damaged']:
            reward -= 5.0
        
        return reward
    
    def _is_done(self, info):
        """Define termination conditions."""
        # End episode if completely off track
        if info['tyres_out'] >= 4:
            return True
        
        # End episode if critical damage
        if info['bodywork_critical']:
            return True
        
        return False
    
    def close(self):
        self.bridge.close()


# Training loop (apex-seeker)
env = AssettoCorsa_v0()
obs, info = env.reset()

for step in range(1000):
    action = env.action_space.sample()  # Replace with your policy
    obs, reward, done, truncated, info = env.step(action)
    
    if done or truncated:
        obs, info = env.reset()

env.close()
'''
    
    print(example_code)
    print("="*70 + "\n")


if __name__ == "__main__":
    print("\n" + "="*70)
    print("AC Bridge API Tests")
    print("="*70)
    print("\nThese tests demonstrate how apex-seeker will use the bridge.")
    print("Make sure AC is running and you're actively driving!\n")
    
    # Run tests
    if test_basic_api():
        test_observation_loop(duration=5.0)
        test_control_loop(duration=3.0)
    
    # Show integration example
    show_apex_seeker_example()

