"""
HuskyLens Interface Module for Tappy
Handles communication with the HuskyLens AI camera for object detection.
"""

import serial
import time
from typing import Optional, Dict, List
from dataclasses import dataclass
from enum import IntEnum


class ObjectID(IntEnum):
    """Enumeration of recognized objects."""
    NONE = 0
    TOOTHBRUSH = 1
    APPLE = 2
    CARROT = 3
    HAND = 4


@dataclass
class DetectionResult:
    """Represents a detection result from HuskyLens."""
    object_id: int
    x_center: int
    y_center: int
    width: int
    height: int
    confidence: float = 1.0

    @property
    def object_name(self) -> str:
        """Get human-readable object name."""
        names = {
            0: "None",
            1: "Toothbrush",
            2: "Apple",
            3: "Carrot",
            4: "Hand"
        }
        return names.get(self.object_id, "Unknown")


class HuskyLensController:
    """
    Interface for HuskyLens AI camera.

    The HuskyLens communicates via serial and can detect/recognize
    objects that have been trained on the device.
    """

    # HuskyLens protocol constants
    HEADER = bytes([0x55, 0xAA, 0x11])
    COMMAND_REQUEST = 0x20
    COMMAND_REQUEST_BLOCKS = 0x21
    COMMAND_REQUEST_LEARNED = 0x2D

    def __init__(self, port: str = 'COM4', baud_rate: int = 9600):
        """
        Initialize HuskyLens connection.

        Args:
            port: Serial port for HuskyLens
            baud_rate: Communication speed (9600 as per Arduino sketches)
        """
        self.port = port
        self.baud_rate = baud_rate
        self.serial_conn: Optional[serial.Serial] = None
        self.learned_ids: List[int] = []

    def connect(self) -> bool:
        """Establish serial connection to HuskyLens."""
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=0.5
            )
            time.sleep(0.5)
            print(f"Connected to HuskyLens on {self.port}")
            return True
        except serial.SerialException as e:
            print(f"Failed to connect to HuskyLens: {e}")
            return False

    def disconnect(self):
        """Close serial connection."""
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            print("Disconnected from HuskyLens")

    def _calculate_checksum(self, data: bytes) -> int:
        """Calculate checksum for HuskyLens protocol."""
        return sum(data) & 0xFF

    def _send_command(self, command: int, data: bytes = b'') -> bool:
        """Send a command to HuskyLens."""
        if not self.serial_conn:
            return False

        # Build packet: header + length + command + data + checksum
        length = len(data) + 1  # +1 for command byte
        packet = self.HEADER + bytes([length, command]) + data
        checksum = self._calculate_checksum(packet[2:])  # Checksum excludes header
        packet += bytes([checksum])

        self.serial_conn.write(packet)
        return True

    def _read_response(self) -> Optional[bytes]:
        """Read response from HuskyLens."""
        if not self.serial_conn:
            return None

        # Look for header
        header = self.serial_conn.read(3)
        if header != self.HEADER:
            return None

        # Read length
        length_byte = self.serial_conn.read(1)
        if not length_byte:
            return None
        length = length_byte[0]

        # Read rest of packet
        data = self.serial_conn.read(length + 1)  # +1 for checksum
        return data

    def request(self) -> bool:
        """Request data from HuskyLens."""
        return self._send_command(self.COMMAND_REQUEST)

    def get_object_id(self) -> int:
        """
        Get the ID of the currently detected object.

        Returns:
            Object ID (0 if nothing detected)
        """
        if not self.serial_conn:
            return 0

        self._send_command(self.COMMAND_REQUEST_BLOCKS)
        response = self._read_response()

        if response and len(response) >= 6:
            # Parse block data - ID is typically in the response
            # Format varies by HuskyLens firmware version
            object_id = response[5] if len(response) > 5 else 0
            return object_id

        return 0

    def get_detection(self) -> Optional[DetectionResult]:
        """
        Get full detection result including position and size.

        Returns:
            DetectionResult or None if nothing detected
        """
        if not self.serial_conn:
            return None

        self._send_command(self.COMMAND_REQUEST_BLOCKS)
        response = self._read_response()

        if response and len(response) >= 11:
            # Parse block: x_center, y_center, width, height, ID
            x_center = (response[1] << 8) | response[0]
            y_center = (response[3] << 8) | response[2]
            width = (response[5] << 8) | response[4]
            height = (response[7] << 8) | response[6]
            object_id = (response[9] << 8) | response[8]

            return DetectionResult(
                object_id=object_id,
                x_center=x_center,
                y_center=y_center,
                width=width,
                height=height
            )

        return None

    def is_learned(self) -> bool:
        """Check if HuskyLens has learned objects."""
        return len(self.learned_ids) > 0


# Simulation mode for testing without hardware
class SimulatedHuskyLens(HuskyLensController):
    """Simulated HuskyLens for testing without hardware."""

    def __init__(self):
        super().__init__()
        self.simulated_object_id = 0
        self.connected = False

    def connect(self) -> bool:
        print("[SIMULATION] HuskyLens connected")
        self.connected = True
        self.learned_ids = [1, 2, 3, 4]  # Pretend we've learned all objects
        return True

    def disconnect(self):
        print("[SIMULATION] HuskyLens disconnected")
        self.connected = False

    def set_detected_object(self, object_id: int):
        """Set the simulated detected object (for testing)."""
        self.simulated_object_id = object_id
        print(f"[SIMULATION] Now detecting: {ObjectID(object_id).name if object_id in ObjectID._value2member_map_ else 'Unknown'}")

    def get_object_id(self) -> int:
        return self.simulated_object_id

    def get_detection(self) -> Optional[DetectionResult]:
        if self.simulated_object_id == 0:
            return None
        return DetectionResult(
            object_id=self.simulated_object_id,
            x_center=160,
            y_center=120,
            width=50,
            height=50
        )

    def is_learned(self) -> bool:
        return True
