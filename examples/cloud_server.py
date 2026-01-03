"""
Example WebSocket server for receiving AC telemetry on cloud (EC2, etc).

This server accepts connections from the Windows bridge running at home
and receives telemetry data. Run this on your cloud instance.

Usage:
    python cloud_server.py --host 0.0.0.0 --port 8765
"""

import asyncio
import json
import argparse
import websockets
from websockets.server import WebSocketServerProtocol


class TelemetryReceiver:
    """Simple telemetry receiving server."""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8765):
        self.host = host
        self.port = port
        self.packet_count = 0
        
    async def handler(self, websocket: WebSocketServerProtocol):
        """Handle incoming telemetry stream from Windows bridge."""
        remote = websocket.remote_address
        print(f"[{remote[0]}:{remote[1]}] Client connected")
        
        try:
            async for message in websocket:
                self.packet_count += 1
                
                # Parse telemetry
                data = json.loads(message)
                
                # Example: Print key metrics every 10 packets
                if self.packet_count % 10 == 0:
                    print(f"[#{self.packet_count}] "
                          f"Speed: {data['speed_kmh']:.1f} km/h | "
                          f"Lap: {data['completed_laps']} | "
                          f"Valid: {data['is_lap_valid']}")
                
                # TODO: Process telemetry for RL training
                # - Store in buffer
                # - Feed to policy network
                # - Calculate rewards
                # - etc.
                
        except websockets.exceptions.ConnectionClosed:
            print(f"[{remote[0]}:{remote[1]}] Client disconnected")
        except Exception as e:
            print(f"[{remote[0]}:{remote[1]}] Error: {e}")
    
    async def start(self):
        """Start the receiving server."""
        print("="*70)
        print("TELEMETRY RECEIVER (Cloud Server)")
        print("="*70)
        print(f"\nListening on {self.host}:{self.port}")
        print("Waiting for Windows bridge to connect...\n")
        
        async with websockets.serve(self.handler, self.host, self.port):
            await asyncio.Future()  # Run forever


def main():
    parser = argparse.ArgumentParser(description="Cloud telemetry receiver")
    parser.add_argument('--host', default='0.0.0.0', help='Server host (default: 0.0.0.0)')
    parser.add_argument('--port', type=int, default=8765, help='Server port (default: 8765)')
    args = parser.parse_args()
    
    receiver = TelemetryReceiver(host=args.host, port=args.port)
    
    try:
        asyncio.run(receiver.start())
    except KeyboardInterrupt:
        print("\n\nServer stopped")


if __name__ == "__main__":
    main()

