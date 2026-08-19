from __future__ import annotations

from app.core.system.hardware_detector import HardwareDetector
from app.core.system.performance_manager import PerformanceManager


def square(value: int) -> int:
    """Função top-level usada para validar serialização do ProcessPool."""
    return value * value


def test_hardware_profile_has_safe_worker_limits() -> None:
    profile = HardwareDetector.detect()
    assert profile.logical_cores >= 1
    assert 1 <= profile.recommended_cpu_workers <= profile.logical_cores
    assert profile.recommended_io_workers >= 1
    assert profile.recommended_batch_size >= 100
    assert profile.memory_budget_bytes >= 512 * 1024**2


def test_cpu_map_preserves_order() -> None:
    manager = PerformanceManager.detect()
    values = [1, 2, 3, 4]
    result = manager.map_cpu(square, values, workers=1)
    assert result == [1, 4, 9, 16]
