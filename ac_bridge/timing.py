"""
Timing primitives for consistent step timing in RL training.

Provides drift-correcting ticker that maintains stable frequencies
for telemetry polling and control loops.
"""

import time
from typing import Iterator, Tuple
import structlog

logger = structlog.get_logger()


class MonotonicClock:
    """
    Monotonic clock using perf_counter with wall-time correlation.
    
    perf_counter() is monotonic and high-resolution, but arbitrary origin.
    This class correlates it with wall time for logging/debugging.
    """
    
    def __init__(self):
        self.t_perf_start = time.perf_counter()
        self.t_wall_start = time.time()
    
    def now(self) -> float:
        """Get current time in seconds since epoch (perf_counter based)."""
        return time.perf_counter()
    
    def to_wall_time(self, t_perf: float) -> float:
        """Convert perf_counter time to approximate wall time."""
        elapsed = t_perf - self.t_perf_start
        return self.t_wall_start + elapsed
    
    def elapsed(self) -> float:
        """Time elapsed since clock creation."""
        return time.perf_counter() - self.t_perf_start


class Ticker:
    """
    Drift-correcting ticker that yields at precise intervals.
    
    Unlike naive time.sleep(1/hz), this corrects for accumulated drift
    and maintains long-term frequency accuracy.
    
    Usage:
        ticker = Ticker(hz=10)
        for seq, t_wall, dt, dt_actual in ticker:
            # Execute at 10 Hz with <1ms drift
            process_step()
    
    Returns:
        seq (int): Sequence number (0, 1, 2, ...)
        t_wall (float): Wall clock time (perf_counter)
        dt (float): Target time step (1/hz)
        dt_actual (float): Actual time since last tick
    """
    
    def __init__(self, hz: int, start_seq: int = 0):
        """
        Initialize ticker.
        
        Args:
            hz: Target frequency in Hz (e.g., 10 for 10 Hz)
            start_seq: Starting sequence number (default: 0)
        """
        if hz <= 0:
            raise ValueError(f"hz must be positive, got {hz}")
        
        self.hz = hz
        self.dt_target = 1.0 / hz
        self.seq = start_seq
        
        self.clock = MonotonicClock()
        self.t_start = self.clock.now()
        self.t_last = self.t_start
        self.t_next = self.t_start + self.dt_target
        
        # Statistics
        self.total_drift = 0.0
        self.max_jitter = 0.0
        
        logger.info(
            "ticker_initialized",
            hz=hz,
            dt_target=self.dt_target,
            start_seq=start_seq
        )
    
    def __iter__(self) -> Iterator[Tuple[int, float, float, float]]:
        """Make ticker iterable."""
        return self
    
    def __next__(self) -> Tuple[int, float, float, float]:
        """
        Yield next tick with drift correction.
        
        Returns:
            (seq, t_wall, dt_target, dt_actual)
        """
        # Calculate how long to sleep
        t_now = self.clock.now()
        sleep_time = self.t_next - t_now
        
        # Sleep if we're ahead of schedule
        if sleep_time > 0:
            time.sleep(sleep_time)
        
        # Update times
        t_now = self.clock.now()
        dt_actual = t_now - self.t_last
        
        # Track statistics
        jitter = abs(dt_actual - self.dt_target)
        self.max_jitter = max(self.max_jitter, jitter)
        self.total_drift += (dt_actual - self.dt_target)
        
        # Prepare return values
        seq = self.seq
        t_wall = t_now
        
        # Update state for next tick
        self.t_last = t_now
        self.t_next = self.t_start + (self.seq + 1) * self.dt_target
        self.seq += 1
        
        # Log drift warning if getting too large
        if abs(self.total_drift) > 0.1:  # 100ms total drift
            logger.warning(
                "ticker_drift_warning",
                total_drift_ms=self.total_drift * 1000,
                max_jitter_ms=self.max_jitter * 1000,
                seq=seq
            )
        
        return seq, t_wall, self.dt_target, dt_actual
    
    def tick(self) -> Tuple[int, float, float, float]:
        """
        Alternative method name for explicit tick.
        Same as calling next() or iterating.
        """
        return self.__next__()
    
    def reset(self, start_seq: int = 0) -> None:
        """
        Reset ticker to new starting point.
        
        Useful when resetting episodes in RL training.
        
        Args:
            start_seq: New starting sequence number
        """
        self.seq = start_seq
        self.t_start = self.clock.now()
        self.t_last = self.t_start
        self.t_next = self.t_start + self.dt_target
        self.total_drift = 0.0
        self.max_jitter = 0.0
        
        logger.info("ticker_reset", start_seq=start_seq)
    
    def get_stats(self) -> dict:
        """
        Get timing statistics.
        
        Returns:
            dict with drift and jitter metrics
        """
        elapsed = self.clock.now() - self.t_start
        expected_ticks = int(elapsed * self.hz)
        actual_ticks = self.seq
        
        return {
            'hz_target': self.hz,
            'dt_target': self.dt_target,
            'elapsed_seconds': elapsed,
            'expected_ticks': expected_ticks,
            'actual_ticks': actual_ticks,
            'tick_deficit': expected_ticks - actual_ticks,
            'total_drift_ms': self.total_drift * 1000,
            'max_jitter_ms': self.max_jitter * 1000,
            'avg_drift_per_tick_ms': (self.total_drift / max(1, actual_ticks)) * 1000
        }


def run_ticker_demo(hz: int = 10, duration: float = 5.0):
    """
    Demo function to visualize ticker performance.
    
    Args:
        hz: Frequency in Hz
        duration: How long to run in seconds
    """
    print(f"\n{'='*70}")
    print(f"Ticker Demo: {hz} Hz for {duration}s")
    print(f"{'='*70}\n")
    
    ticker = Ticker(hz=hz)
    start_time = time.perf_counter()
    
    try:
        while True:
            seq, t_wall, dt, dt_actual = ticker.tick()
            
            elapsed = time.perf_counter() - start_time
            if elapsed > duration:
                break
            
            # Print every 10th tick
            if seq % 10 == 0:
                drift_ms = (dt_actual - dt) * 1000
                print(
                    f"[{seq:04d}] "
                    f"t={elapsed:6.3f}s | "
                    f"dt={dt_actual*1000:6.2f}ms | "
                    f"drift={drift_ms:+6.2f}ms"
                )
    
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    
    # Print final statistics
    stats = ticker.get_stats()
    print(f"\n{'='*70}")
    print("Final Statistics:")
    print(f"{'='*70}")
    print(f"Target frequency:     {stats['hz_target']} Hz")
    print(f"Target dt:            {stats['dt_target']*1000:.2f} ms")
    print(f"Elapsed time:         {stats['elapsed_seconds']:.3f} s")
    print(f"Expected ticks:       {stats['expected_ticks']}")
    print(f"Actual ticks:         {stats['actual_ticks']}")
    print(f"Tick deficit:         {stats['tick_deficit']}")
    print(f"Total drift:          {stats['total_drift_ms']:+.2f} ms")
    print(f"Max jitter:           {stats['max_jitter_ms']:.2f} ms")
    print(f"Avg drift per tick:   {stats['avg_drift_per_tick_ms']:+.3f} ms")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    # Run demo if executed directly
    import sys
    
    if len(sys.argv) > 1:
        hz = int(sys.argv[1])
    else:
        hz = 10
    
    run_ticker_demo(hz=hz, duration=10.0)

