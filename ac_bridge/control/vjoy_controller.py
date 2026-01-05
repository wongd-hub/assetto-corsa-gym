"""
vJoy-based controller for Assetto Corsa.

Provides low-latency control via virtual joystick with value caching
and batch updates for optimal performance.
"""

import time
import structlog
import pyvjoy
from pyvjoy.exceptions import vJoyException

logger = structlog.get_logger()


class VJoyController:
    """
    Fast vJoy controller for AC with minimal latency.
    
    Features:
    - Value caching (only update changed values)
    - Batch axis updates
    - Direct vJoy API calls (no abstraction overhead)
    - Performance monitoring
    
    Axis mapping:
    - X: Steering (-1.0 to 1.0)
    - Y: Throttle (0.0 to 1.0)
    - Z: Brake (0.0 to 1.0)
    - RZ: Clutch (0.0 to 1.0)
    
    Buttons:
    - 1-7: Gears (sequential up/down via button presses)
    """
    
    # vJoy axis ranges (0x1 to 0x8000)
    AXIS_MIN = 0x1
    AXIS_MAX = 0x8000
    AXIS_CENTER = 0x4000
    
    def __init__(self, device_id: int = 1):
        """
        Initialize vJoy device.
        
        Args:
            device_id: vJoy device ID (default: 1)
        """
        self.device_id = device_id
        
        try:
            self.device = pyvjoy.VJoyDevice(device_id)
            logger.info("vjoy_initialized", device_id=device_id)
        except Exception as e:
            logger.error("vjoy_init_failed", device_id=device_id, error=str(e))
            raise RuntimeError(
                f"Failed to initialize vJoy device {device_id}. "
                "Make sure vJoy is installed and device is configured."
            ) from e
        
        # Value cache to avoid redundant updates
        self._cache = {
            'throttle': None,
            'brake': None,
            'clutch': None,
            'steering': None,
            'gear': None
        }
        
        # Performance tracking
        self._update_count = 0
        self._start_time = time.perf_counter()
        
        # Initialize to neutral position
        self.reset()
    
    def reset(self):
        """Reset all controls to neutral/off position."""
        self.device.set_axis(pyvjoy.HID_USAGE_X, self.AXIS_CENTER)  # Steering center
        self.device.set_axis(pyvjoy.HID_USAGE_Y, self.AXIS_MIN)     # Throttle off
        self.device.set_axis(pyvjoy.HID_USAGE_Z, self.AXIS_MIN)     # Brake off
        self.device.set_axis(pyvjoy.HID_USAGE_RZ, self.AXIS_MIN)    # Clutch off
        
        # Reset cache
        self._cache = {
            'throttle': 0.0,
            'brake': 0.0,
            'clutch': 0.0,
            'steering': 0.0,
            'gear': 1
        }
        
        logger.info("vjoy_reset", device_id=self.device_id)
    
    def _safe_set_axis(self, axis_id: int, value: int, axis_name: str = "unknown") -> bool:
        """
        Safely set axis value with error handling and retry.
        
        Args:
            axis_id: vJoy axis ID (e.g., HID_USAGE_X)
            value: Axis value (0-32767)
            axis_name: Human-readable axis name for logging
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.device.set_axis(axis_id, value)
            return True
        except vJoyException as e:
            logger.warning(
                "vjoy_axis_error",
                axis=axis_name,
                device_id=self.device_id,
                error=str(e),
                attempt="first"
            )
            
            # Try to reset device and retry once
            try:
                time.sleep(0.01)  # Brief pause
                self.device.set_axis(axis_id, value)
                logger.info("vjoy_axis_recovered", axis=axis_name)
                return True
            except vJoyException as retry_err:
                logger.error(
                    "vjoy_axis_failed",
                    axis=axis_name,
                    device_id=self.device_id,
                    error=str(retry_err),
                    msg="vJoy device may be in error state. Try restarting vJoy or AC."
                )
                return False
    
    def _float_to_axis(self, value: float, center_zero: bool = False) -> int:
        """
        Convert float value to vJoy axis value.
        
        Args:
            value: Float value (0.0-1.0 or -1.0 to 1.0)
            center_zero: If True, 0.0 maps to center (for steering)
        
        Returns:
            vJoy axis value (0x1 to 0x8000)
        """
        if center_zero:
            # -1.0 to 1.0 -> AXIS_MIN to AXIS_MAX
            value = max(-1.0, min(1.0, value))
            return int(self.AXIS_MIN + (value + 1.0) * 0.5 * (self.AXIS_MAX - self.AXIS_MIN))
        else:
            # 0.0 to 1.0 -> AXIS_MIN to AXIS_MAX
            value = max(0.0, min(1.0, value))
            return int(self.AXIS_MIN + value * (self.AXIS_MAX - self.AXIS_MIN))
    
    def set_throttle(self, value: float):
        """
        Set throttle position.
        
        Args:
            value: Throttle 0.0 (off) to 1.0 (full)
        """
        if self._cache['throttle'] == value:
            return
        
        axis_value = self._float_to_axis(value)
        if self._safe_set_axis(pyvjoy.HID_USAGE_Y, axis_value, "throttle"):
            self._cache['throttle'] = value
            self._update_count += 1
    
    def set_brake(self, value: float):
        """
        Set brake position.
        
        Args:
            value: Brake 0.0 (off) to 1.0 (full)
        """
        if self._cache['brake'] == value:
            return
        
        axis_value = self._float_to_axis(value)
        if self._safe_set_axis(pyvjoy.HID_USAGE_Z, axis_value, "brake"):
            self._cache['brake'] = value
            self._update_count += 1
    
    def set_clutch(self, value: float):
        """
        Set clutch position.
        
        Args:
            value: Clutch 0.0 (released) to 1.0 (pressed)
        """
        if self._cache['clutch'] == value:
            return
        
        axis_value = self._float_to_axis(value)
        if self._safe_set_axis(pyvjoy.HID_USAGE_RZ, axis_value, "clutch"):
            self._cache['clutch'] = value
            self._update_count += 1
    
    def set_steering(self, value: float):
        """
        Set steering position.
        
        Args:
            value: Steering -1.0 (full left) to 1.0 (full right), 0.0 (center)
        """
        if self._cache['steering'] == value:
            return
        
        axis_value = self._float_to_axis(value, center_zero=True)
        if self._safe_set_axis(pyvjoy.HID_USAGE_X, axis_value, "steering"):
            self._cache['steering'] = value
            self._update_count += 1
    
    def set_gear(self, gear: int):
        """
        Set gear using button presses.
        
        Args:
            gear: Gear number (0=R, 1=N, 2=1st, 3=2nd, etc.)
        
        Note: This uses sequential button presses. In AC, configure
        gear up/down buttons to match. Button mapping:
        - Button 1: Gear up
        - Button 2: Gear down
        """
        if self._cache['gear'] == gear:
            return
        
        current_gear = self._cache['gear'] or 1
        
        if gear > current_gear:
            # Shift up
            for _ in range(gear - current_gear):
                self.device.set_button(1, 1)
                time.sleep(0.001)  # 1ms button press
                self.device.set_button(1, 0)
                time.sleep(0.001)
        elif gear < current_gear:
            # Shift down
            for _ in range(current_gear - gear):
                self.device.set_button(2, 1)
                time.sleep(0.001)
                self.device.set_button(2, 0)
                time.sleep(0.001)
        
        self._cache['gear'] = gear
        self._update_count += 1
    
    def restart_session(self):
        """
        Trigger session restart in AC.
        
        Presses button 7 which should be mapped to "Restart Race" or 
        "Restart Session" in AC's controls.
        """
        self.device.set_button(7, 1)
        time.sleep(0.05)  # 50ms button press
        self.device.set_button(7, 0)
        logger.info("restart_session_triggered")
    
    def press_button(self, button: int, duration: float = 0.05):
        """
        Press a specific button.
        
        Args:
            button: Button number (1-32)
            duration: How long to hold the button in seconds (default: 0.05)
        
        Useful for triggering AC functions like:
        - Button 3/4: Brake balance
        - Button 5/6: TC adjustment
        - Button 7: Restart race
        - Button 8: Restart session
        """
        self.device.set_button(button, 1)
        time.sleep(duration)
        self.device.set_button(button, 0)
        logger.debug("button_pressed", button=button, duration=duration)
    
    def set_controls(self, throttle: float, brake: float, steering: float, clutch: float = 0.0):
        """
        Batch update all controls for minimum latency.
        
        This is the most efficient way to update multiple axes at once.
        Includes error handling for vJoy exceptions with auto-retry.
        
        Args:
            throttle: 0.0 to 1.0
            brake: 0.0 to 1.0
            steering: -1.0 to 1.0
            clutch: 0.0 to 1.0 (default: 0.0)
        """
        # Only update changed values
        if self._cache['throttle'] != throttle:
            if self._safe_set_axis(pyvjoy.HID_USAGE_Y, self._float_to_axis(throttle), "throttle"):
                self._cache['throttle'] = throttle
                self._update_count += 1
        
        if self._cache['brake'] != brake:
            if self._safe_set_axis(pyvjoy.HID_USAGE_Z, self._float_to_axis(brake), "brake"):
                self._cache['brake'] = brake
                self._update_count += 1
        
        if self._cache['steering'] != steering:
            if self._safe_set_axis(pyvjoy.HID_USAGE_X, self._float_to_axis(steering, center_zero=True), "steering"):
                self._cache['steering'] = steering
                self._update_count += 1
        
        if self._cache['clutch'] != clutch:
            if self._safe_set_axis(pyvjoy.HID_USAGE_RZ, self._float_to_axis(clutch), "clutch"):
                self._cache['clutch'] = clutch
                self._update_count += 1
    
    def get_stats(self):
        """
        Get performance statistics.
        
        Returns:
            dict: Statistics including update count, rate, and cache hit rate
        """
        elapsed = time.perf_counter() - self._start_time
        update_rate = self._update_count / elapsed if elapsed > 0 else 0
        
        return {
            'updates': self._update_count,
            'elapsed_seconds': elapsed,
            'update_rate_hz': update_rate,
            'device_id': self.device_id
        }
    
    def close(self):
        """Clean up and reset device."""
        self.reset()
        logger.info("vjoy_closed", device_id=self.device_id, stats=self.get_stats())

