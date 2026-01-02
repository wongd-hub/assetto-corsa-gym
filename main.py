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
@click.option(
    '--native/--acc-lib',
    default=True,
    help='Use native AC shared memory (default, more accurate for AC)'
)
def read(rate: int, json_output: str, native: bool):
    """
    Read telemetry from AC's shared memory (simplest method).
    
    This reads directly from AC's memory - no UDP, no handshakes.
    Works every time as long as AC is running!
    
    Examples:
        uv run main.py read --rate 10
        uv run main.py read --rate 60 --json-output telemetry.jsonl
        uv run main.py read --rate 10 --native  # Use native AC (better!)
    """
    import json
    import time
    
    logger.info("reading_shared_memory", rate_hz=rate, json_output=json_output, native=native)
    
    if native:
        # Use native AC shared memory (more accurate)
        from ac_bridge.telemetry.ac_native_memory import ACSharedMemory
        
        click.echo("\n" + "="*70)
        click.echo("ASSETTO CORSA NATIVE TELEMETRY READER")
        click.echo("="*70)
        click.echo(f"\nReading at {rate} Hz using native AC shared memory")
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
                        'speed_kmh': p.speedKmh,
                        'rpm': p.rpms,
                        'gear': p.gear,
                        'gas': p.gas,
                        'brake': p.brake,
                        'clutch': p.clutch,
                        'steer_angle': p.steerAngle,
                        'wheel_slip': list(p.wheelSlip),  # [FL, FR, RL, RR]
                        'avg_wheel_slip': avg_wheel_slip,
                        'wheel_lock_detected': wheel_lock_detected,  # Overall lock
                        'locked_wheels': locked_wheels_mask,  # [FL, FR, RL, RR] booleans
                        
                        # Damage detection
                        'car_damage': list(p.carDamage),  # [front, rear, left, right, center] 0-1
                        'bodywork_damaged': bodywork_damaged,  # Any part > 5% damaged
                        'bodywork_critical': bodywork_critical,  # Any part > 50% damaged
                        'tyre_wear': list(p.tyreWear),  # [FL, FR, RL, RR] 0-1 (0=new, 1=destroyed)
                        'tyre_damaged': tyre_damaged,  # Any tire > 80% worn
                        'tyre_critical': tyre_critical,  # Any tire > 95% worn
                        
                        'number_of_tyres_out': p.numberOfTyresOut,  # KEY: Track limits
                        'is_lap_valid': is_lap_valid,  # Tracked across lap
                        'abs_setting': p.abs,  # ABS config (not activation)
                        'tc': p.tc,  # TC activation level
                        'velocity': list(p.velocity),
                        'local_velocity': list(p.localVelocity),
                        'heading': p.heading,
                        'pitch': p.pitch,
                        'roll': p.roll,
                        'acc_g': list(p.accG),  # G-forces
                        'completed_laps': g.completedLaps,
                        'current_time': g.iCurrentTime,
                        'last_time': g.iLastTime,
                        'best_time': g.iBestTime,
                        'normalized_position': g.normalizedCarPosition,
                        'surface_grip': g.surfaceGrip,
                        'flag': g.flag,
                        'is_in_pit': bool(g.isInPit),
                        'is_in_pit_lane': bool(g.isInPitLane),
                        'brake_temp': list(p.brakeTemp),
                        'tyre_core_temp': list(p.tyreCoreTemperature),
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
    
    else:
        # Use ACC library (fallback)
        from ac_bridge.telemetry.ac_shared_memory import read_telemetry_loop, extract_telemetry_dict
        
        json_file = None
        if json_output:
            json_file = open(json_output, 'w')
            click.echo(f"Writing telemetry to: {json_output}")
        
        def telemetry_callback(telemetry_dict, sm):
            """Write telemetry to JSON file if specified."""
            if json_file:
                json_file.write(json.dumps(telemetry_dict) + '\n')
                json_file.flush()
        
        try:
            callback = telemetry_callback if json_output else None
            read_telemetry_loop(rate_hz=rate, callback=callback)
        except KeyboardInterrupt:
            click.echo("\nStopped by user")
        except Exception as e:
            click.echo(f"\nError: {e}")
            click.echo("\nMake sure AC is running and you're in a session!")
        finally:
            if json_file:
                json_file.close()
                click.echo(f"\nTelemetry written to: {json_output}")


if __name__ == "__main__":
    cli()
