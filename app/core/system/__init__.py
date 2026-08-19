"""Detecção de hardware e execução adaptativa do MAME Set Builder."""

from .hardware_detector import HardwareDetector, HardwareProfile
from .performance_manager import PerformanceManager

__all__ = ["HardwareDetector", "HardwareProfile", "PerformanceManager"]
