"""
Assetto Corsa Gym Bridge - Main CLI Entry Point

This tool bridges Assetto Corsa telemetry to gymnasium environments.
It can operate in local mode (WebSocket server) or cloud mode (WebSocket client).
"""

import click
import structlog

# Configure structlog for readable output
structlog.configure(
    processors=[
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
    ]
)

logger = structlog.get_logger()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """
    Assetto Corsa Gym Bridge
    
    A bridge between Assetto Corsa telemetry and gymnasium environments.
    Use the 'read' command to stream telemetry from AC's shared memory.
    """
    pass


@cli.command()
@click.option(
    '--host',
    default='localhost',
    help='WebSocket server host (default: localhost)',
    type=str
)
@click.option(
    '--port',
    default=8765,
    help='WebSocket server port (default: 8765)',
    type=int
)
@click.option(
    '--rate',
    default=10,
    help='Telemetry broadcast rate in Hz (default: 10)',
    type=int
)
def stream(host: str, port: int, rate: int):
    """
    Stream telemetry over WebSocket (local development mode).
    
    Starts a WebSocket server that broadcasts AC telemetry to all connected clients.
    Clients can connect using any WebSocket library or tool.
    
    Example:
        uv run main.py stream --host localhost --port 8765 --rate 10
    
    Then connect with the example client:
        uv run examples/websocket_client.py
    """
    import asyncio
    from ac_bridge.websocket_server import TelemetryServer
    
    click.echo("\n" + "="*70)
    click.echo("ASSETTO CORSA TELEMETRY STREAM")
    click.echo("="*70)
    click.echo(f"\nWebSocket server: ws://{host}:{port}")
    click.echo(f"Broadcast rate: {rate} Hz")
    click.echo("\nWaiting for clients to connect...")
    click.echo("Press Ctrl+C to stop\n")
    
    server = TelemetryServer(host=host, port=port, rate_hz=rate)
    
    try:
        asyncio.run(server.start())
    except KeyboardInterrupt:
        click.echo("\n\nStopping server...")
        server.stop()


@cli.command()
@click.option(
    '--rate',
    default=10,
    help='Telemetry read rate in Hz (default: 10)',
    type=int
)
@click.option(
    '--json-output',
    type=click.Path(),
    help='Path to write JSON telemetry stream (for ingestion by other projects)'
)
def read(rate: int, json_output: str):
    """
    Read telemetry from AC's shared memory and display in console.
    
    This reads directly from AC's memory - no UDP, no handshakes.
    Works every time as long as AC is running.
    
    Examples:
        uv run main.py read --rate 10
        uv run main.py read --rate 60 --json-output telemetry.jsonl
    """
    import json
    import time
    from ac_bridge.telemetry.ac_native_memory import ACSharedMemory
    
    logger.info("reading_shared_memory", rate_hz=rate, json_output=json_output)
    
    click.echo("\n" + "="*70)
    click.echo("ASSETTO CORSA TELEMETRY READER")
    click.echo("="*70)
    click.echo(f"\nReading at {rate} Hz from AC shared memory")
    click.echo("Press Ctrl+C to stop\n")
    
    json_file = None
    if json_output:
        json_file = open(json_output, 'w')
        click.echo(f"Writing telemetry to: {json_output}\n")
    
    try:
        asm = ACSharedMemory()
        packet_count = 0
        prev_lap = 0
        lap_invalidated = False  # Track if CURRENT lap has been cut
        sleep_time = 1.0 / rate
        
        while True:
            if not asm.is_connected():
                click.echo("[Waiting for AC...]")
                time.sleep(2)
                continue
            
            packet_count += 1
            p = asm.physics
            g = asm.graphics
            
            # Detect lap completion - reset lap validity on NEW lap
            lap_complete = g.completedLaps > prev_lap
            if lap_complete:
                prev_lap = g.completedLaps
                lap_invalidated = False  # Reset for new lap
            
            # Track lap invalidity across entire lap
            # Once invalidated, stays invalid until new lap
            if p.numberOfTyresOut > 2 and not lap_invalidated:
                lap_invalidated = True
            
            is_lap_valid = not lap_invalidated
            lap_validity = "VALID" if is_lap_valid else "INVALID"
            
            # Highlight when tires are out
            if p.numberOfTyresOut > 2:
                tyres_status = f"[!{p.numberOfTyresOut} OUT!]"
            elif p.numberOfTyresOut > 0:
                tyres_status = f"[{p.numberOfTyresOut} out]"
            else:
                tyres_status = "On track"
            
            # Detect wheel lock: hard braking + high wheel slip = locking
            # wheelSlip order: FL, FR, RL, RR (Front-Left, Front-Right, Rear-Left, Rear-Right)
            avg_wheel_slip = sum(p.wheelSlip) / 4
            wheel_lock_detected = p.brake > 0.5 and avg_wheel_slip > 0.5
            
            # Show which wheels are locking (slip > 0.5)
            if wheel_lock_detected:
                locked_wheels = []
                wheel_names = ['FL', 'FR', 'RL', 'RR']
                for i, (name, slip) in enumerate(zip(wheel_names, p.wheelSlip)):
                    if slip > 0.5:
                        locked_wheels.append(f"{name}:{slip:.2f}")
                lock_indicator = f" [LOCK: {', '.join(locked_wheels)}]" if locked_wheels else " [LOCK!]"
            else:
                lock_indicator = ""
            
            # Damage detection
            # carDamage: 5 body parts [front, rear, left, right, center]
            # Values: 0.0 = pristine, 1.0 = destroyed
            bodywork_damaged = any(dmg > 0.05 for dmg in p.carDamage)  # 5% threshold
            bodywork_critical = any(dmg > 0.50 for dmg in p.carDamage)  # 50% threshold
            
            # tyreWear: 4 tires [FL, FR, RL, RR]  
            # Values: 0.0 = new, 1.0 = completely worn
            tyre_damaged = any(wear > 0.80 for wear in p.tyreWear)  # 80% worn
            tyre_critical = any(wear > 0.95 for wear in p.tyreWear)  # 95% worn (about to fail)
            
            # Build damage indicator
            damage_parts = []
            if bodywork_critical:
                damage_parts.append("BODY!")
            elif bodywork_damaged:
                damage_parts.append("body")
                
            if tyre_critical:
                damage_parts.append("TYRE!")
            elif tyre_damaged:
                damage_parts.append("tyre")
            
            damage_indicator = f" [DMG: {', '.join(damage_parts)}]" if damage_parts else ""
            
            # TC activation level
            tc_indicator = f"TC:{p.tc:.2f}" if p.tc > 0.01 else ""
            tc_str = f" | {tc_indicator}" if tc_indicator else ""
            
            lap_indicator = " [LAP COMPLETE!]" if lap_complete else ""
            
            # Format individual wheel slip (FL/FR/RL/RR)
            slip_str = f"[{p.wheelSlip[0]:.2f}/{p.wheelSlip[1]:.2f}/{p.wheelSlip[2]:.2f}/{p.wheelSlip[3]:.2f}]"
            
            # Format tire wear (FL/FR/RL/RR as percentages)
            wear_str = f"[{p.tyreWear[0]*100:.0f}/{p.tyreWear[1]*100:.0f}/{p.tyreWear[2]*100:.0f}/{p.tyreWear[3]*100:.0f}%]"
            
            output = (
                f"[#{packet_count}]{lap_indicator}{lock_indicator}{damage_indicator} "
                f"{tyres_status} | "
                f"Lap:{lap_validity} | "
                f"Speed: {p.speedKmh:.1f} km/h | "
                f"RPM: {p.rpms} | "
                f"Gear: {p.gear} | "
                f"Gas: {p.gas:.2f} | "
                f"Brake: {p.brake:.2f}{tc_str} | "
                f"Steer: {p.steerAngle:.1f}° | "
                f"Slip: {slip_str} | "
                f"Wear: {wear_str} | "
                f"Laps: {g.completedLaps} | "
                f"Last: {g.lastTime}"
            )
            
            click.echo(output)
            
            # Write JSON if requested
            if json_file:
                # Identify which specific wheels are locked
                locked_wheels_mask = [slip > 0.5 for slip in p.wheelSlip]
                
                telemetry = {
                        'packet_id': p.packetId,
                        
                        # Basic state
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
                        
                        # Angular velocity
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
                        'flag': g.flag,
                        
                        # Assists
                        'abs_setting': p.abs,
                        'tc': p.tc,
                        
                        # Pit status
                        'is_in_pit': bool(g.isInPit),
                        'is_in_pit_lane': bool(g.isInPitLane),
                        
                        # Fuel
                        'fuel': p.fuel,
                    }
                json_file.write(json.dumps(telemetry) + '\n')
                json_file.flush()
            
            time.sleep(sleep_time)
            
    except KeyboardInterrupt:
        click.echo("\n\nStopped by user")
    except Exception as e:
        click.echo(f"\nError: {e}")
        click.echo("\nMake sure AC is running and you're in a session!")
    finally:
        if json_file:
            json_file.close()
            click.echo(f"\nTelemetry written to: {json_output}")
        asm.close()


if __name__ == "__main__":
    cli()
