"""Catálogo local de modelos de controladores.

O catálogo não substitui HIDAPI/SDL3. Ele apenas transforma evidências já
coletadas em uma identificação de modelo explicável e em um layout esperado.
Novos modelos podem ser adicionados sem alterar o backend de entrada.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..models.input_control import InputDevice, InputDeviceType


@dataclass(frozen=True, slots=True)
class ControllerCatalogEntry:
    model_id: str
    manufacturer: str
    model_name: str
    device_type: InputDeviceType
    aliases: tuple[str, ...] = ()
    vendor_id: int | None = None
    product_ids: tuple[int, ...] = ()
    expected_face_buttons: int | None = None
    expected_axes: int | None = None


@dataclass(frozen=True, slots=True)
class ControllerIdentification:
    model: ControllerCatalogEntry | None
    confidence: int
    reasons: tuple[str, ...] = ()


class ControllerCatalogService:
    """Identifica modelos somente quando há evidência suficiente."""

    MIN_CONFIDENCE = 60

    def __init__(self, entries: tuple[ControllerCatalogEntry, ...] = ()) -> None:
        self._entries = entries

    def identify(self, device: InputDevice) -> ControllerIdentification:
        candidates: list[tuple[int, ControllerCatalogEntry, list[str]]] = []
        device_text = " ".join(
            value.casefold()
            for value in (device.name, device.product or "", device.manufacturer or "")
            if value
        )
        for entry in self._entries:
            score = 0
            reasons: list[str] = []
            if entry.vendor_id is not None and device.vendor_id == entry.vendor_id:
                score += 50
                reasons.append("VID")
            if entry.product_ids and device.product_id in entry.product_ids:
                score += 35
                reasons.append("PID")
            names = (entry.model_name, entry.manufacturer, *entry.aliases)
            if any(alias.casefold() in device_text for alias in names if alias):
                score += 30
                reasons.append("nome/modelo")
            if score:
                candidates.append((score, entry, reasons))

        if not candidates:
            return ControllerIdentification(None, 0)
        candidates.sort(key=lambda item: item[0], reverse=True)
        score, model, reasons = candidates[0]
        second = candidates[1][0] if len(candidates) > 1 else -1
        if score < self.MIN_CONFIDENCE or (second >= 0 and score - second < 15):
            return ControllerIdentification(None, score, tuple(reasons))
        return ControllerIdentification(model, min(100, score), tuple(reasons))

    @staticmethod
    def default() -> "ControllerCatalogService":
        # VID/PID não verificados não são cadastrados como fato. O inventário
        # real do Windows será a fonte para popular o catálogo posteriormente.
        return ControllerCatalogService(())


__all__ = [
    "ControllerCatalogEntry",
    "ControllerCatalogService",
    "ControllerIdentification",
]
