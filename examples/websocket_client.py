"""
Example WebSocket client for receiving AC telemetry.

This demonstrates how to connect to the telemetry stream and process data.
"""

import sys
import os
# Add parent directory to path so we can import ac_bridge
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
import json
import websockets


async def receive_telemetry(uri: str = "ws://localhost:8765"):
    """
    Connect to telemetry stream and print data.
    
    Args:
        uri: WebSocket server URI (default: ws://localhost:8765)
    """
    print(f"Connecting to {uri}...")
    
    async with websockets.connect(uri) as websocket:
        print("Connected! Receiving telemetry...\n")
        
        packet_count = 0
        
        try:
            async for message in websocket:
                packet_count += 1
                
                # Parse JSON telemetry
                data = json.loads(message)
                
                # Display key metrics (customize as needed)
                print(f"[#{packet_count}] "
                      f"Speed: {data['speed_kmh']:.1f} km/h | "
                      f"RPM: {data['rpm']} | "
                      f"Gear: {data['gear']} | "
                      f"Lap: {data['completed_laps']} | "
                      f"Valid: {data['is_lap_valid']} | "
                      f"Pos: ({data['world_position_x']:.1f}, {data['world_position_y']:.1f}) | "
                      f"AngVel: ({data['angular_velocity_x']:.2f}, {data['angular_velocity_y']:.2f}, {data['angular_velocity_z']:.2f})")
                
                # Example: Check for wheel lock
                if data['wheel_lock_detected']:
                    locked = [i for i, locked in enumerate(data['locked_wheels']) if locked]
                    wheel_names = ['FL', 'FR', 'RL', 'RR']
                    print(f"  ⚠️  WHEEL LOCK: {[wheel_names[i] for i in locked]}")
                
                # Example: Check for off-track
                if data['number_of_tyres_out'] > 0:
                    print(f"  ⚠️  {data['number_of_tyres_out']} wheels off track!")
                
                # Example: Check for damage
                if data['bodywork_damaged']:
                    print(f"  ⚠️  Bodywork damage detected!")
                
        except websockets.exceptions.ConnectionClosed:
            print("\nConnection closed by server")
        except KeyboardInterrupt:
            print("\nStopped by user")


if __name__ == "__main__":
    # Run the client
    asyncio.run(receive_telemetry())

