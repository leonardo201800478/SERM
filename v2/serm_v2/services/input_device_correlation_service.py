"""Correlação robusta entre inventários HIDAPI e SDL3.

O SDL3 fornece a visão lógica do gamepad e o HIDAPI fornece a identidade
física. A correlação é deliberadamente conservadora: evidência insuficiente
ou ambígua não é convertida silenciosamente em uma associação.
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
    ambiguous: bool = False


class InputDeviceCorrelationService:
    """Relaciona dispositivos HIDAPI e SDL3 por evidências independentes."""

    MIN_SCORE = 50
    MIN_MARGIN = 10

    def correlate(
        self,
        physical_devices: tuple[InputDevice, ...],
        logical_devices: tuple[InputDevice, ...],
    ) -> tuple[DeviceCorrelation, ...]:
        results: list[DeviceCorrelation] = []
        remaining = list(logical_devices)

        # Primeiro resolvemos candidatos com maior evidência. Isso evita que
        # a ordem do HIDAPI/SDL determine qual unidade idêntica será usada.
        pairs: list[tuple[int, int, InputDevice, InputDevice, list[str]]] = []
        for physical in physical_devices:
            for logical in remaining:
                score, candidate, reasons = self._score(physical, logical)
                if score >= self.MIN_SCORE:
                    pairs.append((score, len(reasons), physical, candidate, reasons))
        pairs.sort(key=lambda item: (item[0], item[1]), reverse=True)

        used_physical: set[str] = set()
        used_logical: set[str] = set()
        for score, _, physical, logical, reasons in pairs:
            if physical.device_id in used_physical or logical.device_id in used_logical:
                continue
            result = self._build_result(physical, logical, score, reasons, remaining)
            if result is None:
                continue
            results.append(result)
            used_physical.add(physical.device_id)
            used_logical.add(logical.device_id)

        return tuple(results)

    @classmethod
    def best_match(
        cls,
        physical: InputDevice,
        candidates: tuple[InputDevice, ...] | list[InputDevice],
    ) -> DeviceCorrelation | None:
        scored = [cls._score(physical, candidate) for candidate in candidates]
        scored = [item for item in scored if item[0] >= cls.MIN_SCORE]
        if not scored:
            return None
        scored.sort(key=lambda item: (item[0], len(item[2])), reverse=True)
        score, candidate, reasons = scored[0]
        second = scored[1][0] if len(scored) > 1 else -1
        if second >= 0 and score - second < cls.MIN_MARGIN:
            return DeviceCorrelation(physical, candidate, score, tuple(reasons), True)
        return DeviceCorrelation(physical, candidate, score, tuple(reasons), False)

    @classmethod
    def _build_result(
        cls,
        physical: InputDevice,
        logical: InputDevice,
        score: int,
        reasons: list[str],
        remaining: list[InputDevice],
    ) -> DeviceCorrelation | None:
        alternatives = [
            cls._score(physical, candidate)[0]
            for candidate in remaining
            if candidate.device_id != logical.device_id
        ]
        if alternatives and score - max(alternatives) < cls.MIN_MARGIN:
            return None
        return DeviceCorrelation(physical, logical, score, tuple(reasons), False)

    @staticmethod
    def _score(
        physical: InputDevice, logical: InputDevice
    ) -> tuple[int, InputDevice, list[str]]:
        score = 0
        reasons: list[str] = []
        if physical.vendor_id is not None and physical.vendor_id == logical.vendor_id:
            score += 40
            reasons.append("VID")
        if physical.product_id is not None and physical.product_id == logical.product_id:
            score += 40
            reasons.append("PID")
        if physical.version is not None and physical.version == logical.version:
            score += 10
            reasons.append("version")
        if physical.sdl_guid and physical.sdl_guid == logical.sdl_guid:
            score += 50
            reasons.append("SDL GUID")
        if physical.product and logical.product and InputDeviceCorrelationService._same_text(physical.product, logical.product):
            score += 10
            reasons.append("produto")
        if physical.manufacturer and logical.manufacturer and InputDeviceCorrelationService._same_text(physical.manufacturer, logical.manufacturer):
            score += 5
            reasons.append("fabricante")
        return score, logical, reasons

    @staticmethod
    def _same_text(left: str, right: str) -> bool:
        return " ".join(left.casefold().split()) == " ".join(right.casefold().split())


__all__ = ["DeviceCorrelation", "InputDeviceCorrelationService"]
