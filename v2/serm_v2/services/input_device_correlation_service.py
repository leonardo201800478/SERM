"""Correlação entre inventários HIDAPI e SDL3.

O SDL3 fornece a representação lógica do gamepad e o HIDAPI fornece dados
físicos. Este serviço correlaciona as duas visões sem usar o instance_id do
SDL como identidade persistente.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models.input_control import InputDevice


@dataclass(frozen=True, slots=True)
class DeviceCorrelation:
    """Resultado de uma tentativa de correlação entre dois backends."""

    physical: InputDevice
    logical: InputDevice
    score: int
    reasons: tuple[str, ...] = ()


class InputDeviceCorrelationService:
    """Relaciona dispositivos HIDAPI e SDL3 por evidências independentes."""

    def correlate(
        self,
        physical_devices: tuple[InputDevice, ...],
        logical_devices: tuple[InputDevice, ...],
    ) -> tuple[DeviceCorrelation, ...]:
        results: list[DeviceCorrelation] = []
        used_logical: set[str] = set()

        for physical in physical_devices:
            candidates = [
                candidate
                for candidate in logical_devices
                if candidate.device_id not in used_logical
            ]
            best = self.best_match(physical, candidates)
            if best is not None:
                results.append(best)
                used_logical.add(best.logical.device_id)
        return tuple(results)

    @classmethod
    def best_match(
        cls,
        physical: InputDevice,
        candidates: tuple[InputDevice, ...] | list[InputDevice],
    ) -> DeviceCorrelation | None:
        scored = [cls._score(physical, candidate) for candidate in candidates]
        scored = [item for item in scored if item[0] > 0]
        if not scored:
            return None
        scored.sort(key=lambda item: item[0], reverse=True)
        score, candidate, reasons = scored[0]
        return DeviceCorrelation(physical, candidate, score, tuple(reasons))

    @staticmethod
    def _score(
        physical: InputDevice, logical: InputDevice
    ) -> tuple[int, InputDevice, list[str]]:
        score = 0
        reasons: list[str] = []

        if (
            physical.vendor_id is not None
            and logical.vendor_id is not None
            and physical.vendor_id == logical.vendor_id
        ):
            score += 40
            reasons.append("VID")
        if (
            physical.product_id is not None
            and logical.product_id is not None
            and physical.product_id == logical.product_id
        ):
            score += 40
            reasons.append("PID")
        if physical.version is not None and logical.version is not None and physical.version == logical.version:
            score += 10
            reasons.append("version")
        if physical.sdl_guid and logical.sdl_guid and physical.sdl_guid == logical.sdl_guid:
            score += 50
            reasons.append("SDL GUID")
        if physical.product and logical.product and InputDeviceCorrelationService._same_text(
            physical.product, logical.product
        ):
            score += 10
            reasons.append("produto")
        if physical.manufacturer and logical.manufacturer and InputDeviceCorrelationService._same_text(
            physical.manufacturer, logical.manufacturer
        ):
            score += 5
            reasons.append("fabricante")

        return score, logical, reasons

    @staticmethod
    def _same_text(left: str, right: str) -> bool:
        normalize = lambda value: " ".join(value.casefold().split())
        return normalize(left) == normalize(right)


__all__ = ["DeviceCorrelation", "InputDeviceCorrelationService"]
