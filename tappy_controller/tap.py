"""
Tappy - Smart Water Tap Controller
Main controller implementing the water-saving learning algorithm.

Based on pseudocode from Tap.py - converts object detection into
adaptive water flow control that learns user habits.
"""

import time
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

from huskylens_interface import HuskyLensController, SimulatedHuskyLens, ObjectID
from arduino_interface import ArduinoValveController, SimulatedArduinoController


@dataclass
class WaterVolume:
    """Represents water allocation settings."""
    # How open the valve should be (0-100%)
    percentage: int
    # How long to keep open (seconds)
    duration: int

    def to_tuple(self) -> Tuple[int, int]:
        return (self.percentage, self.duration)

    @classmethod
    def from_tuple(cls, t: Tuple[int, int]) -> 'WaterVolume':
        return cls(percentage=t[0], duration=t[1])


class TappyController:
    """
    Main Tappy controller with adaptive water management.

    This controller:
    1. Detects objects via HuskyLens
    2. Allocates appropriate water volume based on object type
    3. Learns from user behavior to reduce water waste
    4. Controls valve via Arduino
    """

    # Object name mapping (from pseudocode)
    OBJECT_NAMES: Dict[int, str] = {
        0: "NONE",
        1: "Toothbrush",
        2: "Apple",
        3: "Carrot",
        4: "Hand"
    }

    def __init__(
        self,
        huskylens: Optional[HuskyLensController] = None,
        arduino: Optional[ArduinoValveController] = None,
        simulation_mode: bool = False
    ):
        """
        Initialize Tappy controller.

        Args:
            huskylens: HuskyLens controller instance
            arduino: Arduino controller instance
            simulation_mode: If True, use simulated hardware
        """
        if simulation_mode:
            self.huskylens = SimulatedHuskyLens()
            self.arduino = SimulatedArduinoController()
        else:
            self.huskylens = huskylens or HuskyLensController()
            self.arduino = arduino or ArduinoValveController()

        # Current learned water volume for each object
        # Format: [percentage_open, time_open]
        # Index corresponds to ObjectID
        self.current_water_volume: List[WaterVolume] = [
            WaterVolume(0, 0),    # NONE
            WaterVolume(20, 5),   # Toothbrush - low flow, short duration
            WaterVolume(70, 7),   # Apple - higher flow for washing
            WaterVolume(60, 7),   # Carrot - similar to apple
            WaterVolume(80, 15),  # Hand - highest flow, longest duration
        ]

        # Minimum water volume thresholds (floor values)
        # The learning algorithm won't reduce below these
        self.min_water_volume: List[WaterVolume] = [
            WaterVolume(0, 0),    # NONE
            WaterVolume(10, 2),   # Toothbrush
            WaterVolume(40, 5),   # Apple
            WaterVolume(40, 5),   # Carrot
            WaterVolume(70, 15),  # Hand
        ]

        # State tracking
        self.current_object_id = 0
        self.valve_state = 0
        self.is_running = False
        self.last_object_id = 0
        self.water_delivered = 0.0

    def connect(self) -> bool:
        """Connect to all hardware."""
        huskylens_ok = self.huskylens.connect()
        arduino_ok = self.arduino.connect()
        return huskylens_ok and arduino_ok

    def disconnect(self):
        """Disconnect from all hardware."""
        self.huskylens.disconnect()
        self.arduino.disconnect()

    def get_object_name(self, object_id: int) -> str:
        """Get human-readable name for object ID."""
        return self.OBJECT_NAMES.get(object_id, "Unknown")

    def update_water_volume(self, object_id: int, actual_volume_used: float) -> WaterVolume:
        """
        Update water volume allocation based on actual usage.

        Implements the learning algorithm:
        - If user doesn't use full allocated volume, reduce future allocation
        - Uses exponential moving average (0.2 new + 0.8 old)
        - Never reduces below minimum threshold

        Args:
            object_id: The object that was detected
            actual_volume_used: How much water was actually used

        Returns:
            Updated WaterVolume for this object
        """
        if object_id == 0 or object_id >= len(self.current_water_volume):
            return WaterVolume(0, 0)

        current = self.current_water_volume[object_id]
        minimum = self.min_water_volume[object_id]

        # Calculate expected volume
        expected_volume = (current.percentage / 100.0) * current.duration * 0.5

        # If user used less than allocated, learn from it
        if actual_volume_used < expected_volume and expected_volume > 0:
            usage_ratio = actual_volume_used / expected_volume

            # Exponential moving average: 20% new behavior, 80% learned behavior
            new_percentage = int(0.2 * (current.percentage * usage_ratio) + 0.8 * current.percentage)
            new_duration = int(0.2 * (current.duration * usage_ratio) + 0.8 * current.duration)

            # Enforce minimums
            new_percentage = max(new_percentage, minimum.percentage)
            new_duration = max(new_duration, minimum.duration)

            self.current_water_volume[object_id] = WaterVolume(new_percentage, new_duration)

            print(f"Learning: {self.get_object_name(object_id)} adjusted to "
                  f"{new_percentage}% for {new_duration}s (was {current.percentage}% for {current.duration}s)")

        return self.current_water_volume[object_id]

    def run_cycle(self) -> bool:
        """
        Run one detection and response cycle.

        Returns:
            True if an object was detected and water was dispensed
        """
        # Get current detection
        self.current_object_id = self.huskylens.get_object_id()

        if self.current_object_id != 0:
            # Object detected - dispense water
            self.last_object_id = self.current_object_id
            volume_settings = self.current_water_volume[self.current_object_id]

            print(f"Detected: {self.get_object_name(self.current_object_id)} - "
                  f"Dispensing at {volume_settings.percentage}% for {volume_settings.duration}s")

            # Open valve and track volume
            self.valve_state, self.water_delivered = self.arduino.rotate_valve(
                volume_settings.percentage,
                volume_settings.duration
            )
            self.arduino.last_object_id = self.last_object_id

            return True

        else:
            # No object - check if we need to close valve and learn
            if self.valve_state != 0:
                print("Object removed - closing valve")
                self.arduino.close_valve()

                # Learn from the interaction
                self.update_water_volume(
                    self.arduino.last_object_id,
                    self.arduino.last_object_volume
                )

                self.valve_state = 0

            return False

    def run(self, poll_interval: float = 0.1):
        """
        Main loop - continuously monitor and respond to objects.

        Args:
            poll_interval: Time between detection checks (seconds)
        """
        self.is_running = True
        print("Tappy started - monitoring for objects...")
        print("Press Ctrl+C to stop")

        try:
            while self.is_running:
                self.run_cycle()
                time.sleep(poll_interval)

        except KeyboardInterrupt:
            print("\nStopping Tappy...")
            self.arduino.close_valve()
            self.is_running = False

    def stop(self):
        """Stop the main loop."""
        self.is_running = False
        self.arduino.close_valve()

    def get_stats(self) -> Dict:
        """Get current water volume settings for all objects."""
        return {
            self.get_object_name(i): {
                "percentage": vol.percentage,
                "duration": vol.duration,
                "estimated_volume_L": (vol.percentage / 100.0) * vol.duration * 0.5
            }
            for i, vol in enumerate(self.current_water_volume)
            # Skip NONE
            if i > 0
        }


def main():
    """Main entry point - run Tappy in simulation mode for demo."""
    print("=" * 50)
    print("TAPPY - Smart Water Tap Controller")
    print("=" * 50)
    print()

    # Create controller in simulation mode
    tappy = TappyController(simulation_mode=True)

    # Connect to (simulated) hardware
    if not tappy.connect():
        print("Failed to connect to hardware!")
        return

    print("\nInitial water volume settings:")
    for name, stats in tappy.get_stats().items():
        print(f"  {name}: {stats['percentage']}% for {stats['duration']}s "
              f"(~{stats['estimated_volume_L']:.2f}L)")

    print("\n--- Running simulation demo ---\n")

    # Simulate some detections
    # type: SimulatedHuskyLens
    sim_huskylens = tappy.huskylens

    # Demo: Detect toothbrush
    print("=== Simulating: Toothbrush detected ===")
    sim_huskylens.set_detected_object(ObjectID.TOOTHBRUSH)
    tappy.run_cycle()
    time.sleep(0.5)

    # Remove toothbrush (simulates user finishing early)
    sim_huskylens.set_detected_object(ObjectID.NONE)
    # Simulate only using 0.3L
    tappy.arduino.last_object_volume = 0.3
    tappy.run_cycle()

    print()

    # Demo: Detect apple
    print("=== Simulating: Apple detected ===")
    sim_huskylens.set_detected_object(ObjectID.APPLE)
    tappy.run_cycle()
    time.sleep(0.5)

    sim_huskylens.set_detected_object(ObjectID.NONE)
    tappy.run_cycle()

    print()

    # Demo: Detect toothbrush again (should show learned values)
    print("=== Simulating: Toothbrush detected again ===")
    sim_huskylens.set_detected_object(ObjectID.TOOTHBRUSH)
    tappy.run_cycle()

    sim_huskylens.set_detected_object(ObjectID.NONE)
    tappy.run_cycle()

    print("\n--- Updated water volume settings after learning ---")
    for name, stats in tappy.get_stats().items():
        print(f"  {name}: {stats['percentage']}% for {stats['duration']}s "
              f"(~{stats['estimated_volume_L']:.2f}L)")

    # Cleanup
    tappy.disconnect()
    print("\nDemo complete! Save water! :)")


if __name__ == "__main__":
    main()
