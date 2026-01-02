"""
WebSocket server for streaming AC telemetry.

Simple implementation for local development. The server:
1. Reads telemetry from AC at configured rate
2. Broadcasts JSON to all connected clients
3. Handles client connections/disconnections gracefully
"""

import asyncio
import json
import structlog
from typing import Set
import websockets
from websockets.server import WebSocketServerProtocol

logger = structlog.get_logger()


class TelemetryServer:
    """
    WebSocket server that broadcasts AC telemetry to connected clients.
    
    Usage:
        server = TelemetryServer(host="localhost", port=8765)
        await server.start()
    """
    
    def __init__(self, host: str = "localhost", port: int = 8765, rate_hz: int = 10):
        self.host = host
        self.port = port
        self.rate_hz = rate_hz
        self.clients: Set[WebSocketServerProtocol] = set()
        self.running = False
        
    async def register(self, websocket: WebSocketServerProtocol):
        """Register a new client connection."""
        self.clients.add(websocket)
        logger.info("client_connected", 
                   remote=websocket.remote_address,
                   total_clients=len(self.clients))
        
    async def unregister(self, websocket: WebSocketServerProtocol):
        """Unregister a client that disconnected."""
        self.clients.discard(websocket)
        logger.info("client_disconnected",
                   remote=websocket.remote_address,
                   total_clients=len(self.clients))
    
    async def broadcast(self, message: str):
        """Send message to all connected clients."""
        if not self.clients:
            return
            
        # Send to all clients, remove any that fail
        disconnected = set()
        for client in self.clients:
            try:
                await client.send(message)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(client)
        
        # Clean up disconnected clients
        for client in disconnected:
            await self.unregister(client)
    
    async def handler(self, websocket: WebSocketServerProtocol):
        """
        Handle a client connection.
        
        This registers the client and keeps the connection alive.
        The actual telemetry broadcasting happens in read_telemetry_loop().
        """
        await self.register(websocket)
        try:
            # Keep connection alive by waiting for messages
            # (clients don't need to send anything, but this keeps the connection open)
            async for message in websocket:
                # Could handle client requests here in the future
                pass
        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            await self.unregister(websocket)
    
    async def read_telemetry_loop(self):
        """
        Read telemetry from AC and broadcast to all clients.
        
        This runs in parallel with the WebSocket server.
        """
        from ac_bridge.telemetry.ac_native_memory import ACSharedMemory
        
        asm = ACSharedMemory()
        sleep_time = 1.0 / self.rate_hz
        packet_count = 0
        prev_lap = 0
        lap_invalidated = False
        
        logger.info("telemetry_loop_started", rate_hz=self.rate_hz)
        
        try:
            while self.running:
                # Check if AC is connected
                if not asm.is_connected():
                    await asyncio.sleep(2)
                    continue
                
                packet_count += 1
                p = asm.physics
                g = asm.graphics
                
                # Detect lap completion
                lap_complete = g.completedLaps > prev_lap
                if lap_complete:
                    prev_lap = g.completedLaps
                    lap_invalidated = False
                
                # Track lap invalidity
                if p.numberOfTyresOut > 2 and not lap_invalidated:
                    lap_invalidated = True
                
                is_lap_valid = not lap_invalidated
                
                # Calculate derived metrics
                avg_wheel_slip = sum(p.wheelSlip) / 4
                wheel_lock_detected = p.brake > 0.5 and avg_wheel_slip > 0.5
                locked_wheels_mask = [slip > 0.5 for slip in p.wheelSlip]
                
                # Damage detection
                bodywork_damaged = any(dmg > 0.05 for dmg in p.carDamage)
                bodywork_critical = any(dmg > 0.50 for dmg in p.carDamage)
                tyre_damaged = any(wear > 0.80 for wear in p.tyreWear)
                tyre_critical = any(wear > 0.95 for wear in p.tyreWear)
                
                # Build telemetry packet
                telemetry = {
                    'timestamp': packet_count,
                    'packet_id': p.packetId,
                    
                    # Basic car state
                    'speed_kmh': p.speedKmh,
                    'rpm': p.rpms,
                    'gear': p.gear,
                    
                    # Control inputs
                    'gas': p.gas,
                    'brake': p.brake,
                    'clutch': p.clutch,
                    'steer_angle': p.steerAngle,
                    
                    # Velocity (world and local)
                    'velocity_x': p.velocity[0],
                    'velocity_y': p.velocity[1],
                    'velocity_z': p.velocity[2],
                    'local_velocity_x': p.localVelocity[0],
                    'local_velocity_y': p.localVelocity[1],
                    'local_velocity_z': p.localVelocity[2],
                    
                    # Angular velocity (rotation rates)
                    'angular_velocity_x': p.localAngularVel[0],
                    'angular_velocity_y': p.localAngularVel[1],
                    'angular_velocity_z': p.localAngularVel[2],
                    
                    # Orientation
                    'yaw': p.heading,
                    'pitch': p.pitch,
                    'roll': p.roll,
                    
                    # G-forces
                    'acc_g_x': p.accG[0],
                    'acc_g_y': p.accG[1],
                    'acc_g_z': p.accG[2],
                    
                    # World position
                    'world_position_x': g.carCoordinates[0],
                    'world_position_y': g.carCoordinates[1],
                    'world_position_z': g.carCoordinates[2],
                    
                    # Wheel dynamics
                    'wheel_slip': list(p.wheelSlip),
                    'wheel_angular_speed': list(p.wheelAngularSpeed),
                    'wheel_load': list(p.wheelLoad),
                    'wheel_pressure': list(p.wheelsPressure),
                    'suspension_travel': list(p.suspensionTravel),
                    'avg_wheel_slip': avg_wheel_slip,
                    'wheel_lock_detected': wheel_lock_detected,
                    'locked_wheels': locked_wheels_mask,
                    
                    # Damage
                    'car_damage': list(p.carDamage),
                    'bodywork_damaged': bodywork_damaged,
                    'bodywork_critical': bodywork_critical,
                    'tyre_wear': list(p.tyreWear),
                    'tyre_damaged': tyre_damaged,
                    'tyre_critical': tyre_critical,
                    
                    # Temperature
                    'brake_temp': list(p.brakeTemp),
                    'tyre_core_temp': list(p.tyreCoreTemperature),
                    'air_temp': p.airTemp,
                    'road_temp': p.roadTemp,
                    
                    # Track limits and lap
                    'number_of_tyres_out': p.numberOfTyresOut,
                    'is_lap_valid': is_lap_valid,
                    'completed_laps': g.completedLaps,
                    'current_time': g.iCurrentTime,
                    'last_time': g.iLastTime,
                    'best_time': g.iBestTime,
                    'distance_traveled': g.distanceTraveled,
                    'normalized_position': g.normalizedCarPosition,
                    'current_sector_index': g.currentSectorIndex,
                    
                    # Track conditions
                    'surface_grip': g.surfaceGrip,
                    
                    # Assists
                    'tc': p.tc,
                    
                    # Pit status
                    'is_in_pit': bool(g.isInPit),
                    'is_in_pit_lane': bool(g.isInPitLane),
                    
                    # Fuel
                    'fuel': p.fuel,
                }
                
                # Broadcast to all connected clients
                await self.broadcast(json.dumps(telemetry))
                
                await asyncio.sleep(sleep_time)
                
        except Exception as e:
            logger.error("telemetry_loop_error", error=str(e))
        finally:
            asm.close()
            logger.info("telemetry_loop_stopped")
    
    async def start(self):
        """
        Start the WebSocket server and telemetry loop.
        
        This runs both tasks concurrently:
        - WebSocket server (handles connections)
        - Telemetry loop (reads AC and broadcasts)
        """
        self.running = True
        
        logger.info("starting_server", host=self.host, port=self.port, rate_hz=self.rate_hz)
        
        # Start WebSocket server
        async with websockets.serve(self.handler, self.host, self.port):
            logger.info("server_listening", url=f"ws://{self.host}:{self.port}")
            
            # Start telemetry broadcasting loop
            await self.read_telemetry_loop()
    
    def stop(self):
        """Stop the server gracefully."""
        self.running = False
        logger.info("server_stopping")

