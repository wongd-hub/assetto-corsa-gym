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
    Assetto Corsa Gym Bridge - CLI Tool
    
    A bridge between Assetto Corsa telemetry and control for RL training.
    
    Common commands:
      ac-bridge run              - Main telemetry + control loop
      ac-bridge test-telemetry   - Test telemetry reading
      ac-bridge test-control     - Test control output
      ac-bridge smoke-test       - Full integration test
    """
    pass


@cli.command()
@click.option(
    '--hz',
    default=10,
    help='Control loop frequency in Hz (default: 10)',
    type=int
)
@click.option(
    '--telemetry-port',
    default=9996,
    help='Telemetry port (default: 9996 for AC shared memory)',
    type=int
)
@click.option(
    '--controller',
    default='vjoy',
    type=click.Choice(['vjoy'], case_sensitive=False),
    help='Controller type (default: vjoy)'
)
@click.option(
    '--bind',
    default='127.0.0.1:50051',
    help='RPC bind address (default: 127.0.0.1:50051)',
    type=str
)
@click.option(
    '--log-dir',
    default=None,
    help='Directory for logs (default: none)',
    type=click.Path()
)
def run(hz: int, telemetry_port: int, controller: str, bind: str, log_dir: str):
    """
    Run the main bridge loop: telemetry + control.
    
    This is the primary mode for RL training. Continuously reads telemetry
    from AC and accepts control commands.
    
    Example:
        ac-bridge run --hz 60 --controller vjoy
    """
    import time
    from ac_bridge import ACBridgeLocal
    
    click.echo("\n" + "="*70)
    click.echo("AC BRIDGE - MAIN LOOP")
    click.echo("="*70)
    click.echo(f"\nFrequency: {hz} Hz")
    click.echo(f"Controller: {controller}")
    click.echo(f"Bind: {bind}")
    if log_dir:
        click.echo(f"Logging to: {log_dir}")
    click.echo("\nPress Ctrl+C to stop\n")
    
    # Initialize bridge using new API
    bridge = ACBridgeLocal(telemetry_hz=60, control_hz=hz, controller=controller)
    bridge.connect()
    
    if not bridge.is_connected():
        click.echo("Error: Could not connect to AC. Is it running?")
        bridge.close()
        return
    
    click.echo("Bridge running... Ready for control commands.\n")
    
    packet_count = 0
    
    try:
        while True:
            # Get latest observation
            try:
                obs, info = bridge.latest_obs()
                packet_count += 1
                
                # Display status every second
                if packet_count % hz == 0:
                    click.echo(
                        f"[{info['seq']:06d}] "
                        f"Speed: {info['speed_kmh']:6.1f} km/h | "
                        f"Lap: {info['completed_laps']} | "
                        f"Gear: {info['gear']} | "
                        f"Tyres out: {info['tyres_out']}",
                        nl=False
                    )
                    click.echo("\r", nl=False)
                
                # Control commands would be received here (e.g., via RPC)
                # For now, this is a monitoring loop
                
                time.sleep(1.0 / hz)
            
            except RuntimeError:
                click.echo("Waiting for AC...", end='\r')
                time.sleep(1)
            
    except KeyboardInterrupt:
        click.echo("\n\nStopping bridge...")
    finally:
        bridge.close()
        click.echo("Bridge stopped.")


@cli.command()
@click.option(
    '--hz',
    default=10,
    help='Telemetry read rate in Hz (default: 10)',
    type=int
)
@click.option(
    '--duration',
    default=None,
    help='Duration in seconds (default: run until Ctrl+C)',
    type=int
)
def test_telemetry(hz: int, duration: int):
    """
    Test telemetry reading and display parsed fields.
    
    Continuously reads and displays telemetry at specified rate.
    Useful for validating telemetry connection.
    
    Example:
        ac-bridge test-telemetry --hz 10
        ac-bridge test-telemetry --hz 10 --duration 30
    """
    import time
    from ac_bridge import ACBridgeLocal
    
    click.echo("\n" + "="*70)
    click.echo("TELEMETRY TEST")
    click.echo("="*70)
    click.echo(f"\nReading at {hz} Hz")
    if duration:
        click.echo(f"Duration: {duration}s")
    click.echo("Press Ctrl+C to stop\n")
    
    # Use ACBridgeLocal (without controller for read-only test)
    bridge = ACBridgeLocal(telemetry_hz=hz, control_hz=10)
    bridge.connect()
    
    if not bridge.is_connected():
        click.echo("Error: Could not connect to AC. Is it running?")
        bridge.close()
        return
    
    packet_count = 0
    start_time = time.time()
    
    try:
        while True:
            if duration and (time.time() - start_time) > duration:
                break
            
            try:
                obs, info = bridge.latest_obs()
                packet_count += 1
                
                # Display comprehensive telemetry
                click.echo(
                    f"[{info['seq']:05d}] "
                    f"Speed: {info['speed_kmh']:6.1f} km/h | "
                    f"RPM: {info['rpm']:5d} | "
                    f"Gear: {info['gear']} | "
                    f"Throttle: {info['throttle']:.2f} | "
                    f"Brake: {info['brake']:.2f} | "
                    f"Steer: {info['steer_angle']:+6.1f}° | "
                    f"Lap: {info['completed_laps']} | "
                    f"TyresOut: {info['tyres_out']} | "
                    f"dt: {info['dt_actual']*1000:.1f}ms",
                    nl=False
                )
                click.echo("\r", nl=False)
                
                time.sleep(1.0 / hz)
            
            except RuntimeError:
                click.echo("Waiting for AC...", end='\r')
                time.sleep(1)
        
        if duration:
            click.echo(f"\n\nTest complete: {packet_count} packets in {duration}s")
            click.echo(f"Average rate: {packet_count/duration:.1f} Hz")
        
    except KeyboardInterrupt:
        elapsed = time.time() - start_time
        click.echo(f"\n\nStopped: {packet_count} packets in {elapsed:.1f}s")
        click.echo(f"Average rate: {packet_count/elapsed:.1f} Hz")
    finally:
        bridge.close()


@cli.command()
@click.option(
    '--device-id',
    default=1,
    help='vJoy device ID (default: 1)',
    type=int
)
def test_control(device_id: int):
    """
    Test control output (sends safe scripted input pattern).
    
    Interactive test of vJoy control. Use keyboard or menu to test
    individual axes and buttons.
    
    Example:
        ac-bridge test-control
        ac-bridge test-control --device-id 1
    """
    import time
    from ac_bridge.control import VJoyController
    
    click.echo("\n" + "="*70)
    click.echo("CONTROL TEST - VJOY")
    click.echo("="*70)
    
    controller = VJoyController(device_id=device_id)
    
    click.echo(f"\nvJoy Device {device_id} initialized")
    click.echo("\nTest Menu:")
    click.echo("  1. Test steering")
    click.echo("  2. Test throttle")
    click.echo("  3. Test brake")
    click.echo("  4. Test clutch")
    click.echo("  5. Test all axes")
    click.echo("  6. Test all buttons")
    click.echo("  b1-b8. Test individual buttons")
    click.echo("  q. Quit")
    
    try:
        while True:
            choice = input("\nEnter choice: ").strip().lower()
            
            if choice == 'q':
                break
            elif choice == '1':
                click.echo("Testing steering: -1.0 → 0.0 → 1.0")
                for val in [-1.0, -0.5, 0.0, 0.5, 1.0, 0.0]:
                    controller.set_steering(val)
                    click.echo(f"  Steering: {val:+.1f}")
                    time.sleep(0.5)
            elif choice == '2':
                click.echo("Testing throttle: 0.0 → 1.0")
                for val in [0.0, 0.25, 0.5, 0.75, 1.0, 0.0]:
                    controller.set_throttle(val)
                    click.echo(f"  Throttle: {val:.2f}")
                    time.sleep(0.5)
            elif choice == '3':
                click.echo("Testing brake: 0.0 → 1.0")
                for val in [0.0, 0.25, 0.5, 0.75, 1.0, 0.0]:
                    controller.set_brake(val)
                    click.echo(f"  Brake: {val:.2f}")
                    time.sleep(0.5)
            elif choice == '4':
                click.echo("Testing clutch: 0.0 → 1.0")
                for val in [0.0, 0.25, 0.5, 0.75, 1.0, 0.0]:
                    controller.set_clutch(val)
                    click.echo(f"  Clutch: {val:.2f}")
                    time.sleep(0.5)
            elif choice == '5':
                click.echo("Testing all axes...")
                controller.set_controls(throttle=0.5, brake=0.0, steering=0.0)
                time.sleep(0.5)
                controller.set_controls(throttle=0.0, brake=0.5, steering=0.5)
                time.sleep(0.5)
                controller.set_controls(throttle=0.0, brake=0.0, steering=-0.5)
                time.sleep(0.5)
                controller.reset()
                click.echo("  Done")
            elif choice == '6':
                click.echo("Testing all buttons (1-8)...")
                for btn in range(1, 9):
                    click.echo(f"  Button {btn} pressed")
                    controller.set_button(btn, True)
                    time.sleep(0.3)
                    controller.set_button(btn, False)
                    time.sleep(0.2)
                click.echo("  Done")
            elif choice.startswith('b') and len(choice) == 2:
                try:
                    btn_num = int(choice[1])
                    if 1 <= btn_num <= 8:
                        click.echo(f"Testing button {btn_num}...")
                        controller.set_button(btn_num, True)
                        time.sleep(0.5)
                        controller.set_button(btn_num, False)
                        click.echo("  Done")
                    else:
                        click.echo("Invalid button number (1-8)")
                except ValueError:
                    click.echo("Invalid input")
            else:
                click.echo("Invalid choice")
                
    except KeyboardInterrupt:
        click.echo("\n\nTest interrupted")
    finally:
        controller.reset()
        controller.close()
        click.echo("Controls reset and closed.\n")


@cli.command()
@click.option(
    '--device-id',
    default=1,
    help='vJoy device ID (default: 1)',
    type=int
)
@click.option(
    '--duration',
    default=10,
    help='Test duration in seconds (default: 10)',
    type=int
)
def smoke_test(device_id: int, duration: int):
    """
    Run full integration smoke test: telemetry + control loop.
    
    Tests both telemetry reading and control output in a safe pattern.
    Sends a sine wave steering input while monitoring telemetry.
    
    Example:
        ac-bridge smoke-test
        ac-bridge smoke-test --duration 20
    """
    import time
    import math
    from ac_bridge import ACBridgeLocal
    
    click.echo("\n" + "="*70)
    click.echo("SMOKE TEST - FULL INTEGRATION")
    click.echo("="*70)
    click.echo(f"\nDuration: {duration}s")
    click.echo(f"Pattern: Sine wave steering, safe throttle\n")
    
    click.echo("Initializing...")
    bridge = ACBridgeLocal(telemetry_hz=60, control_hz=20, device_id=device_id)
    bridge.connect()
    
    if not bridge.is_connected():
        click.echo("[ERROR] Could not connect to AC. Is it running?")
        bridge.close()
        return 1
    
    click.echo("[OK] Bridge initialized\n")
    click.echo("Starting smoke test...\n")
    
    start_time = time.time()
    packet_count = 0
    hz = 20  # 20 Hz for smooth control
    
    try:
        while (time.time() - start_time) < duration:
            try:
                obs, info = bridge.latest_obs()
                packet_count += 1
                elapsed = time.time() - start_time
                
                # Safe test pattern: sine wave steering, limited throttle
                steering = 0.3 * math.sin(elapsed * 2)  # Gentle steering
                throttle = 0.3  # Safe 30% throttle
                brake = 0.0
                
                # Apply control via bridge
                bridge.apply_action(steering, throttle, brake)
                
                # Display status
                click.echo(
                    f"[{elapsed:5.1f}s] "
                    f"Speed: {info['speed_kmh']:6.1f} km/h | "
                    f"Steer: {steering:+.2f} → AC:{info['steer_angle']:+6.1f}° | "
                    f"Throttle: {throttle:.2f} → AC:{info['throttle']:.2f}",
                    nl=False
                )
                click.echo("\r", nl=False)
                
                time.sleep(1.0 / hz)
            
            except RuntimeError:
                click.echo("Waiting for AC...", end='\r')
                time.sleep(1)
        
        click.echo(f"\n\n[OK] Smoke test passed!")
        click.echo(f"  Packets: {packet_count}")
        click.echo(f"  Rate: {packet_count/duration:.1f} Hz")
        click.echo("  Controls reset")
        
    except Exception as e:
        click.echo(f"\n\n[ERROR] Smoke test failed: {e}")
        return 1
    except KeyboardInterrupt:
        click.echo("\n\nTest interrupted by user")
        return 1
    finally:
        bridge.close()
    
    return 0


@cli.command()
@click.option(
    '--device-id',
    default=1,
    help='vJoy device ID (default: 1)',
    type=int
)
@click.option(
    '--wait',
    default=5,
    help='Wait time after reset in seconds (default: 5)',
    type=int
)
def reset(device_id: int, wait: int):
    """
    Trigger session reset in AC and wait until stable.
    
    Presses the reset button (button 7) and waits for the car to be
    stable at the starting position.
    
    Example:
        ac-bridge reset
        ac-bridge reset --wait 10
    """
    import time
    from ac_bridge.telemetry.ac_native_memory import ACSharedMemory
    from ac_bridge.control import VJoyController
    
    click.echo("\n" + "="*70)
    click.echo("SESSION RESET")
    click.echo("="*70)
    
    controller = VJoyController(device_id=device_id)
    telemetry = ACSharedMemory()
    
    click.echo("\nTriggering reset...")
    controller.restart_session()
    click.echo("✓ Reset button pressed")
    
    click.echo(f"\nWaiting {wait}s for session to stabilize...")
    time.sleep(wait)
    
    # Check if stable
    if telemetry.is_connected():
        p = telemetry.physics
        if p.speedKmh < 5.0:
            click.echo(f"✓ Car stable (speed: {p.speedKmh:.1f} km/h)")
        else:
            click.echo(f"⚠ Car moving (speed: {p.speedKmh:.1f} km/h)")
    else:
        click.echo("⚠ AC not connected")
    
    controller.close()
    telemetry.close()
    click.echo("\nReset complete.\n")


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
    '--uri',
    required=True,
    help='Remote WebSocket server URI (e.g., ws://ec2-instance.com:8765 or wss://secure.com:8765)',
    type=str
)
@click.option(
    '--rate',
    default=10,
    help='Telemetry send rate in Hz (default: 10)',
    type=int
)
@click.option(
    '--reconnect-delay',
    default=5,
    help='Seconds to wait before reconnecting (default: 5)',
    type=int
)
def cloud(uri: str, rate: int, reconnect_delay: int):
    """
    Stream telemetry to remote cloud server (e.g., EC2).
    
    This mode connects TO a remote WebSocket server, allowing your
    home Windows machine (behind NAT) to stream data to the cloud.
    
    The remote server must be running and accepting WebSocket connections.
    Use wss:// for secure connections (recommended for production).
    
    Examples:
        uv run main.py cloud --uri ws://your-ec2-ip:8765 --rate 10
        uv run main.py cloud --uri wss://secure.example.com:8765 --rate 30
    
    See examples/cloud_server.py for a simple receiving server.
    """
    import asyncio
    from ac_bridge.websocket_client import TelemetryClient
    
    click.echo("\n" + "="*70)
    click.echo("ASSETTO CORSA CLOUD TELEMETRY STREAM")
    click.echo("="*70)
    click.echo(f"\nConnecting to: {uri}")
    click.echo(f"Send rate: {rate} Hz")
    click.echo(f"Auto-reconnect: {reconnect_delay}s delay")
    click.echo("\nPress Ctrl+C to stop\n")
    
    client = TelemetryClient(uri=uri, rate_hz=rate, reconnect_delay=reconnect_delay)
    
    try:
        asyncio.run(client.start())
    except KeyboardInterrupt:
        click.echo("\n\nStopping client...")
        client.stop()


if __name__ == "__main__":
    cli()
