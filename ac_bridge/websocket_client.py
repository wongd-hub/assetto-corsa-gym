"""
WebSocket client for streaming AC telemetry to remote server.

This mode connects TO a remote WebSocket server (e.g., on EC2)
and streams telemetry data. Use this when your Windows machine is
behind NAT/firewall and can't accept incoming connections.
"""

import asyncio
import json
import structlog
import websockets
from websockets.client import WebSocketClientProtocol

logger = structlog.get_logger()


class TelemetryClient:
    """
    WebSocket client that streams AC telemetry to a remote server.
    
    Usage:
        client = TelemetryClient(uri="wss://your-ec2-instance.com:8765", rate_hz=10)
        await client.start()
    """
    
    def __init__(self, uri: str, rate_hz: int = 10, reconnect_delay: int = 5):
        self.uri = uri
        self.rate_hz = rate_hz
        self.reconnect_delay = reconnect_delay
        self.running = False
        
    async def stream_telemetry(self, websocket: WebSocketClientProtocol):
        """
        Read telemetry from AC and stream to remote server.
        """
        from ac_bridge.telemetry.ac_native_memory import ACSharedMemory
        
        asm = ACSharedMemory()
        sleep_time = 1.0 / self.rate_hz
        packet_count = 0
        prev_lap = 0
        lap_invalidated = False
        
        logger.info("telemetry_stream_started", rate_hz=self.rate_hz)
        
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
                
                # Send to remote server
                await websocket.send(json.dumps(telemetry))
                
                await asyncio.sleep(sleep_time)
                
        except Exception as e:
            logger.error("telemetry_stream_error", error=str(e))
            raise
        finally:
            asm.close()
            logger.info("telemetry_stream_stopped")
    
    async def start(self):
        """
        Connect to remote server and stream telemetry.
        
        Automatically reconnects if connection is lost.
        """
        self.running = True
        
        while self.running:
            try:
                logger.info("connecting_to_server", uri=self.uri)
                
                async with websockets.connect(self.uri) as websocket:
                    logger.info("connected_to_server", uri=self.uri)
                    await self.stream_telemetry(websocket)
                    
            except websockets.exceptions.ConnectionClosed:
                logger.warning("connection_closed", reconnect_delay=self.reconnect_delay)
                if self.running:
                    await asyncio.sleep(self.reconnect_delay)
                    
            except Exception as e:
                logger.error("connection_error", error=str(e), reconnect_delay=self.reconnect_delay)
                if self.running:
                    await asyncio.sleep(self.reconnect_delay)
    
    def stop(self):
        """Stop the client gracefully."""
        self.running = False
        logger.info("client_stopping")

