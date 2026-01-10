"""
Tappy Controller Package
Smart water tap controller using computer vision for water efficiency.
"""

from .tap import TappyController, WaterVolume
from .huskylens_interface import HuskyLensController, SimulatedHuskyLens, ObjectID, DetectionResult
from .arduino_interface import ArduinoValveController, SimulatedArduinoController

__version__ = "1.0.0"
__all__ = [
    "TappyController",
    "WaterVolume",
    "HuskyLensController",
    "SimulatedHuskyLens",
    "ObjectID",
    "DetectionResult",
    "ArduinoValveController",
    "SimulatedArduinoController",
]
