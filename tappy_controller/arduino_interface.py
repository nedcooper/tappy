"""
Arduino Interface Module for Tappy
Handles serial communication with the Arduino controlling the stepper motor valve.
"""

import serial
import time
from typing import Optional, Tuple


class ArduinoValveController:
    """Controls the stepper motor valve via Arduino serial communication."""

    def __init__(self, port: str = 'COM3', baud_rate: int = 9600):
        """
        Initialize Arduino connection.

        Args:
            port: Serial port (e.g., 'COM3' on Windows, '/dev/ttyUSB0' on Linux)
            baud_rate: Communication speed (default 9600 to match Arduino sketch)
        """
        self.port = port
        self.baud_rate = baud_rate
        self.serial_conn: Optional[serial.Serial] = None
        self.current_position = 0  # Track valve position (0-100%)
        self.max_steps = 5  # Max revolutions as per tappy_03.ino
        self.steps_per_revolution = 200
        self.last_object_id = 0
        self.last_object_volume = 0.0

    def connect(self) -> bool:
        """Establish serial connection to Arduino."""
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=1
            )
            time.sleep(2)  # Wait for Arduino to reset after connection
            print(f"Connected to Arduino on {self.port}")
            return True
        except serial.SerialException as e:
            print(f"Failed to connect to Arduino: {e}")
            return False

    def disconnect(self):
        """Close serial connection."""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            print("Disconnected from Arduino")

    def rotate_valve(self, percentage: int, duration: int) -> Tuple[int, float]:
        """
        Rotate valve to specified percentage open for given duration.

        Args:
            percentage: How open the valve should be (0-100%)
            duration: How long to keep valve open in seconds

        Returns:
            Tuple of (final_position, volume_delivered)
        """
        if not self.serial_conn or not self.serial_conn.is_open:
            print("Arduino not connected!")
            return (0, 0.0)

        # Calculate target position in steps (percentage of max)
        target_steps = int((percentage / 100.0) * self.max_steps)
        steps_to_move = target_steps - self.current_position

        # Send command to Arduino
        if steps_to_move > 0:
            command = f"OPEN:{steps_to_move}\n"
        elif steps_to_move < 0:
            command = f"CLOSE:{abs(steps_to_move)}\n"
        else:
            command = "HOLD\n"

        self.serial_conn.write(command.encode())
        self.current_position = target_steps

        # Calculate approximate volume (simplified model)
        # Volume = flow_rate * time, where flow_rate depends on percentage
        volume_delivered = (percentage / 100.0) * duration * 0.5  # 0.5 L/s at full flow
        self.last_object_volume = volume_delivered

        print(f"Valve at {percentage}% for {duration}s - Volume: {volume_delivered:.2f}L")
        return (self.current_position, volume_delivered)

    def close_valve(self):
        """Fully close the valve."""
        if self.serial_conn and self.serial_conn.is_open:
            steps_to_close = self.current_position
            if steps_to_close > 0:
                command = f"CLOSE:{steps_to_close}\n"
                self.serial_conn.write(command.encode())
            self.current_position = 0
            print("Valve closed")

    def read_response(self) -> str:
        """Read response from Arduino."""
        if self.serial_conn and self.serial_conn.is_open:
            if self.serial_conn.in_waiting:
                return self.serial_conn.readline().decode().strip()
        return ""


# Simulation mode for testing without hardware
class SimulatedArduinoController(ArduinoValveController):
    """Simulated Arduino controller for testing without hardware."""

    def __init__(self):
        super().__init__()
        self.connected = False

    def connect(self) -> bool:
        print("[SIMULATION] Arduino connected")
        self.connected = True
        return True

    def disconnect(self):
        print("[SIMULATION] Arduino disconnected")
        self.connected = False

    def rotate_valve(self, percentage: int, duration: int) -> Tuple[int, float]:
        if not self.connected:
            return (0, 0.0)

        volume_delivered = (percentage / 100.0) * duration * 0.5
        self.last_object_volume = volume_delivered
        self.current_position = int((percentage / 100.0) * self.max_steps)

        print(f"[SIMULATION] Valve at {percentage}% for {duration}s - Volume: {volume_delivered:.2f}L")
        return (self.current_position, volume_delivered)

    def close_valve(self):
        self.current_position = 0
        print("[SIMULATION] Valve closed")
