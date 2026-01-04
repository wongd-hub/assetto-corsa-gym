"""
Cloud control server: receives control commands and applies to local vJoy.

This server accepts control commands from a remote source (e.g., RL training
on EC2) and applies them to the local vJoy device. Use with control_from_cloud
command or integrate into your training loop.

Usage:
    python control_server.py --host 0.0.0.0 --port 8766
"""

import sys
import os
# Add parent directory to path so we can import ac_bridge
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
import json
import argparse
import websockets
from websockets.server import WebSocketServerProtocol


class ControlServer:
    """WebSocket server that applies received controls to vJoy."""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8766, device_id: int = 1):
        self.host = host
        self.port = port
        self.device_id = device_id
        self.controller = None
        self.packet_count = 0
    
    async def handler(self, websocket: WebSocketServerProtocol):
        """Handle incoming control commands."""
        from ac_bridge.control import VJoyController
        
        remote = websocket.remote_address
        print(f"[{remote[0]}:{remote[1]}] Client connected")
        
        # Initialize vJoy controller for this connection
        if self.controller is None:
            try:
                self.controller = VJoyController(device_id=self.device_id)
                print(f"vJoy device {self.device_id} initialized")
            except Exception as e:
                print(f"Error initializing vJoy: {e}")
                await websocket.close()
                return
        
        try:
            async for message in websocket:
                self.packet_count += 1
                
                try:
                    # Parse control command
                    controls = json.loads(message)
                    
                    # Apply to vJoy
                    self.controller.set_controls(
                        throttle=controls.get('throttle', 0.0),
                        brake=controls.get('brake', 0.0),
                        steering=controls.get('steering', 0.0),
                        clutch=controls.get('clutch', 0.0)
                    )
                    
                    # Optional gear
                    if 'gear' in controls:
                        self.controller.set_gear(controls['gear'])
                    
                    # Log periodically
                    if self.packet_count % 60 == 0:
                        print(f"[#{self.packet_count}] "
                              f"T:{controls.get('throttle', 0):.2f} "
                              f"B:{controls.get('brake', 0):.2f} "
                              f"S:{controls.get('steering', 0):+.2f}")
                    
                except json.JSONDecodeError:
                    print(f"Invalid JSON: {message[:50]}")
                except Exception as e:
                    print(f"Error applying control: {e}")
        
        except websockets.exceptions.ConnectionClosed:
            print(f"[{remote[0]}:{remote[1]}] Client disconnected")
        finally:
            if self.controller:
                stats = self.controller.get_stats()
                print(f"\nSession stats:")
                print(f"  Packets: {self.packet_count}")
                print(f"  Rate: {stats['update_rate_hz']:.1f} Hz")
    
    async def start(self):
        """Start the control server."""
        print("="*70)
        print("CONTROL SERVER")
        print("="*70)
        print(f"\nListening on {self.host}:{self.port}")
        print(f"vJoy device: {self.device_id}")
        print("\nWaiting for control commands...\n")
        
        async with websockets.serve(self.handler, self.host, self.port):
            await asyncio.Future()  # Run forever


def main():
    parser = argparse.ArgumentParser(description="vJoy control server")
    parser.add_argument('--host', default='0.0.0.0', help='Server host')
    parser.add_argument('--port', type=int, default=8766, help='Server port')
    parser.add_argument('--device-id', type=int, default=1, help='vJoy device ID')
    args = parser.parse_args()
    
    server = ControlServer(host=args.host, port=args.port, device_id=args.device_id)
    
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        print("\n\nServer stopped")


if __name__ == "__main__":
    main()

