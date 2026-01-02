"""
AC Shared Memory Reader - Simpler and more reliable than UDP.

This reads telemetry directly from AC's shared memory mapped files.
No handshakes, no subscriptions - just read what AC exposes.
"""

import time
from pyaccsharedmemory import accSharedMemory
import structlog

logger = structlog.get_logger()


def extract_telemetry_dict(sm):
    """
    Extract all useful telemetry into a dictionary for emission.
    
    This creates a complete observation that can be consumed by your
    other project for reward calculation, state observation, etc.
    
    Returns:
        dict: Comprehensive telemetry dictionary
    """
    return {
        # Motion
        'speed_kmh': sm.Physics.speed_kmh,
        'velocity': {
            'x': sm.Physics.velocity.x,
            'y': sm.Physics.velocity.y,
            'z': sm.Physics.velocity.z,
        },
        'local_velocity': {
            'x': sm.Physics.local_velocity.x,
            'y': sm.Physics.local_velocity.y,
            'z': sm.Physics.local_velocity.z,
        },
        
        # Orientation
        'heading': sm.Physics.heading,
        'pitch': sm.Physics.pitch,
        'roll': sm.Physics.roll,
        
        # Controls
        'gas': sm.Physics.gas,
        'brake': sm.Physics.brake,
        'clutch': sm.Physics.clutch,
        'steer_angle': sm.Physics.steer_angle,
        'gear': sm.Physics.gear,
        'rpm': sm.Physics.rpm,
        
        # G-forces
        'g_force': {
            'x': sm.Physics.g_force.x,
            'y': sm.Physics.g_force.y,
            'z': sm.Physics.g_force.z,
        },
        
        # Wheel slip (critical for incident detection)
        'wheel_slip': {
            'front_left': sm.Physics.wheel_slip.front_left,
            'front_right': sm.Physics.wheel_slip.front_right,
            'rear_left': sm.Physics.wheel_slip.rear_left,
            'rear_right': sm.Physics.wheel_slip.rear_right,
        },
        
        # Tire data
        'tyre_core_temp': {
            'front_left': sm.Physics.tyre_core_temp.front_left,
            'front_right': sm.Physics.tyre_core_temp.front_right,
            'rear_left': sm.Physics.tyre_core_temp.rear_left,
            'rear_right': sm.Physics.tyre_core_temp.rear_right,
        },
        'wheel_pressure': {
            'front_left': sm.Physics.wheel_pressure.front_left,
            'front_right': sm.Physics.wheel_pressure.front_right,
            'rear_left': sm.Physics.wheel_pressure.rear_left,
            'rear_right': sm.Physics.wheel_pressure.rear_right,
        },
        
        # Brake data
        'brake_temp': {
            'front_left': sm.Physics.brake_temp.front_left,
            'front_right': sm.Physics.brake_temp.front_right,
            'rear_left': sm.Physics.brake_temp.rear_left,
            'rear_right': sm.Physics.brake_temp.rear_right,
        },
        
        # Damage (for collision detection)
        'car_damage': {
            'front': sm.Physics.car_damage.front,
            'rear': sm.Physics.car_damage.rear,
            'left': sm.Physics.car_damage.left,
            'right': sm.Physics.car_damage.right,
            'center': sm.Physics.car_damage.center,
        },
        'suspension_damage': {
            'front_left': sm.Physics.suspension_damage.front_left,
            'front_right': sm.Physics.suspension_damage.front_right,
            'rear_left': sm.Physics.suspension_damage.rear_left,
            'rear_right': sm.Physics.suspension_damage.rear_right,
        },
        
        # Position on track
        'normalized_car_position': sm.Graphics.normalized_car_position,
        'car_coordinates': {
            'x': sm.Graphics.car_coordinates[0].x,
            'y': sm.Graphics.car_coordinates[0].y,
            'z': sm.Graphics.car_coordinates[0].z,
        },
        
        # Lap timing
        'current_time': sm.Graphics.current_time,
        'last_time': sm.Graphics.last_time,
        'best_time': sm.Graphics.best_time,
        'last_sector_time': sm.Graphics.last_sector_time,
        'completed_lap': sm.Graphics.completed_lap,
        'current_sector_index': sm.Graphics.current_sector_index,
        'delta_lap_time': sm.Graphics.delta_lap_time,
        'is_delta_positive': sm.Graphics.is_delta_positive,
        
        # Race/session info
        'position': sm.Graphics.position,
        'session_time_left': sm.Graphics.session_time_left,
        'distance_traveled': sm.Graphics.distance_traveled,
        
        # Penalties and validity
        'penalty': sm.Graphics.penalty.name if hasattr(sm.Graphics.penalty, 'name') else int(sm.Graphics.penalty),
        'is_valid_lap': sm.Graphics.is_valid_lap,
        'is_in_pit': sm.Graphics.is_in_pit,
        'is_in_pit_lane': sm.Graphics.is_in_pit_lane,
        
        # Flags
        'flag': sm.Graphics.flag.name if hasattr(sm.Graphics.flag, 'name') else int(sm.Graphics.flag),
        
        # Driver aids activation
        'abs': sm.Physics.abs,
        'tc': sm.Physics.tc,
        
        # Engine/fuel
        'fuel': sm.Physics.fuel,
        'water_temp': sm.Physics.water_temp,
        'air_temp': sm.Physics.air_temp,
        'road_temp': sm.Physics.road_temp,
        
        # FFB (for anomaly detection)
        'final_ff': sm.Physics.final_ff,
        'kerb_vibration': sm.Physics.kerb_vibration,
        'slip_vibration': sm.Physics.slip_vibration,
    }


def read_telemetry_loop(callback=None, rate_hz=10):
    """
    Read telemetry from AC's shared memory in a loop.
    
    Args:
        callback: Optional function to call with telemetry data
        rate_hz: How many times per second to read (default: 10Hz)
    """
    asm = accSharedMemory()
    sleep_time = 1.0 / rate_hz
    
    print("\n" + "="*70)
    print("ASSETTO CORSA SHARED MEMORY READER")
    print("="*70)
    print(f"\nReading telemetry at {rate_hz} Hz")
    print("Press Ctrl+C to stop\n")
    
    packet_count = 0
    prev_completed_lap = 0
    prev_last_time = 0
    
    try:
        while True:
            # Read physics data
            sm = asm.read_shared_memory()
            
            if sm:
                packet_count += 1
                
                # Basic telemetry
                speed_kmh = sm.Physics.speed_kmh
                rpm = sm.Physics.rpm
                gear = sm.Physics.gear
                gas = sm.Physics.gas
                brake = sm.Physics.brake
                steer = sm.Physics.steer_angle
                
                # Position (from Graphics, not Physics!)
                pos_x = sm.Graphics.car_coordinates[0]
                pos_y = sm.Graphics.car_coordinates[1]
                pos_z = sm.Graphics.car_coordinates[2]
                
                # Lap info
                current_lap = sm.Graphics.current_time_str
                last_lap = sm.Graphics.last_time_str
                best_lap = sm.Graphics.best_time_str
                lap_count = sm.Graphics.completed_lap
                
                # Incident/penalty info
                penalty = sm.Graphics.penalty  # ACC_PENALTY_TYPE enum
                flag = sm.Graphics.flag  # Current flag status
                
                # Check if lap just completed (lap count increased AND last_time updated)
                lap_just_completed = (
                    lap_count > prev_completed_lap and 
                    sm.Graphics.last_time != prev_last_time and
                    sm.Graphics.last_time > 0
                )
                
                # Update tracking variables
                if lap_just_completed:
                    prev_completed_lap = lap_count
                    prev_last_time = sm.Graphics.last_time
                
                # Wheel slip (for lockup/wheelspin detection)
                wheel_slip_fl = sm.Physics.wheel_slip.front_left
                wheel_slip_fr = sm.Physics.wheel_slip.front_right
                avg_front_slip = (wheel_slip_fl + wheel_slip_fr) / 2
                
                # Damage
                damage = sm.Physics.car_damage.center
                
                # Show lap completion indicator
                lap_indicator = "[LAP COMPLETE!]" if lap_just_completed else ""
                
                # Format output
                output = (
                    f"[#{packet_count}] "
                    f"{lap_indicator} "
                    f"Speed: {speed_kmh:.1f} km/h | "
                    f"RPM: {rpm} | "
                    f"Gear: {gear} | "
                    f"Gas: {gas:.2f} | "
                    f"Brake: {brake:.2f} | "
                    f"Steer: {steer:.2f}° | "
                    f"Slip: {avg_front_slip:.2f} | "
                    f"Dmg: {damage:.1f} | "
                    f"Penalty: {penalty.name if hasattr(penalty, 'name') else 'None'} | "
                    f"Laps: {lap_count} | "
                    f"Last: {last_lap}"
                )
                
                print(output)
                
                if callback:
                    # Pass full telemetry dict to callback
                    telemetry_dict = extract_telemetry_dict(sm)
                    callback(telemetry_dict, sm)
            else:
                if packet_count == 0:
                    print("[Waiting for AC... Is it running?]")
                    time.sleep(2)
                    continue
            
            time.sleep(sleep_time)
            
    except KeyboardInterrupt:
        print("\n\nStopped.")
        print(f"Total packets read: {packet_count}")

