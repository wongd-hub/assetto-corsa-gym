"""
Test timing layer with simulated telemetry reading.

This demonstrates how Ticker will be used in the actual bridge.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import time
import numpy as np
from ac_bridge.timing import Ticker


def simulate_telemetry_read():
    """Simulate reading telemetry (takes variable time)."""
    # Simulate variable processing time: 1-3ms
    time.sleep(np.random.uniform(0.001, 0.003))
    
    # Return fake observation
    return np.random.rand(10), {'speed': np.random.uniform(0, 200)}


def test_telemetry_loop(hz=20, duration=5.0):
    """
    Simulate telemetry reading loop with timing discipline.
    
    This is what ACBridgeLocal will do in a background thread.
    """
    print(f"\n{'='*70}")
    print(f"Telemetry Loop Test: {hz} Hz for {duration}s")
    print(f"{'='*70}\n")
    
    ticker = Ticker(hz=hz)
    start = time.perf_counter()
    
    frames = []
    
    try:
        while time.perf_counter() - start < duration:
            seq, t_wall, dt, dt_actual = ticker.tick()
            
            # Simulate telemetry read (this is what _read_telemetry() does)
            obs, info = simulate_telemetry_read()
            
            # Add timing metadata (critical for RL!)
            info.update({
                'seq': seq,
                't_wall': t_wall,
                'dt': dt,
                'dt_actual': dt_actual
            })
            
            frames.append(info)
            
            # Print every 20 frames
            if seq % 20 == 0:
                print(
                    f"[{seq:04d}] "
                    f"speed={info['speed']:6.1f} | "
                    f"dt_actual={dt_actual*1000:5.1f}ms | "
                    f"seq={seq}"
                )
    
    except KeyboardInterrupt:
        print("\nInterrupted")
    
    # Analyze captured frames
    print(f"\n{'='*70}")
    print("Analysis:")
    print(f"{'='*70}")
    print(f"Frames captured:  {len(frames)}")
    print(f"Expected frames:  ~{int(duration * hz)}")
    print(f"Frame rate:       {len(frames) / duration:.2f} Hz")
    
    # Check sequence numbers for drops
    seqs = [f['seq'] for f in frames]
    drops = sum(1 for i in range(1, len(seqs)) if seqs[i] != seqs[i-1] + 1)
    print(f"Dropped frames:   {drops}")
    
    # Timing stats
    dt_actuals = [f['dt_actual'] for f in frames]
    print(f"dt_actual mean:   {np.mean(dt_actuals)*1000:.2f} ms")
    print(f"dt_actual std:    {np.std(dt_actuals)*1000:.2f} ms")
    print(f"dt_actual min:    {np.min(dt_actuals)*1000:.2f} ms")
    print(f"dt_actual max:    {np.max(dt_actuals)*1000:.2f} ms")
    print(f"{'='*70}\n")
    
    return frames


def test_stepped_control(telemetry_hz=60, control_hz=10, duration=3.0):
    """
    Simulate how stepper will work: telemetry at 60 Hz, control at 10 Hz.
    
    This demonstrates the decoupling of telemetry polling and control rate.
    """
    print(f"\n{'='*70}")
    print(f"Stepped Control Test")
    print(f"Telemetry: {telemetry_hz} Hz | Control: {control_hz} Hz | Duration: {duration}s")
    print(f"{'='*70}\n")
    
    telemetry_ticker = Ticker(hz=telemetry_hz)
    control_ticker = Ticker(hz=control_hz)
    
    # Simulate latest frame cache (thread-safe in real implementation)
    latest_frame = None
    
    start = time.perf_counter()
    
    # In real implementation, telemetry runs in background thread
    # For demo, we'll manually interleave
    
    control_steps = []
    telemetry_reads = []
    
    while time.perf_counter() - start < duration:
        # Check if telemetry tick is due
        t_now = time.perf_counter()
        t_next_telem = start + len(telemetry_reads) / telemetry_hz
        t_next_control = start + len(control_steps) / control_hz
        
        if t_next_telem <= t_now:
            # Telemetry tick
            seq, t_wall, dt, dt_actual = telemetry_ticker.tick()
            obs, info = simulate_telemetry_read()
            info.update({'seq': seq, 't_wall': t_wall, 'dt_actual': dt_actual})
            latest_frame = (obs, info)
            telemetry_reads.append(info)
        
        if t_next_control <= t_now and latest_frame is not None:
            # Control tick
            seq, t_wall, dt, dt_actual = control_ticker.tick()
            obs, info = latest_frame
            
            # This is what stepper.step() returns
            control_steps.append({
                'control_seq': seq,
                'telemetry_seq': info['seq'],
                't_wall': t_wall,
                'dt_control': dt_actual,
                'dt_telemetry': info['dt_actual']
            })
            
            print(
                f"Step {seq:03d}: "
                f"action applied | "
                f"read telemetry frame {info['seq']:04d} | "
                f"dt={dt_actual*1000:.1f}ms"
            )
        
        time.sleep(0.001)  # Small sleep to prevent busy loop
    
    print(f"\n{'='*70}")
    print("Results:")
    print(f"{'='*70}")
    print(f"Telemetry frames: {len(telemetry_reads)} ({telemetry_hz} Hz target)")
    print(f"Control steps:    {len(control_steps)} ({control_hz} Hz target)")
    print(f"Ratio:            {len(telemetry_reads) / max(1, len(control_steps)):.1f}:1")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    # Test 1: Basic telemetry loop
    test_telemetry_loop(hz=20, duration=5.0)
    
    # Test 2: Decoupled telemetry/control rates
    test_stepped_control(telemetry_hz=60, control_hz=10, duration=3.0)

