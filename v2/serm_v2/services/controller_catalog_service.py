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
            vendor_match = entry.vendor_id is not None and device.vendor_id == entry.vendor_id
            product_match = bool(entry.product_ids) and device.product_id in entry.product_ids

            # VID sozinho identifica apenas o fabricante, não o modelo.
            if vendor_match and product_match:
                score += 85
                reasons.append("VID+PID")
            elif vendor_match:
                score += 20
                reasons.append("VID")

            model_name = entry.model_name.casefold()
            if model_name and model_name in device_text:
                score += 60
                reasons.append("nome/modelo exato")
            elif any(alias.casefold() in device_text for alias in entry.aliases if alias):
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
        # M30 identificado no inventário real do Windows e confirmado pelo
        # backend SDL3 como "8BitDo M30 Gamepad" (VID 0x2DC8 / PID 0x5006).
        # O M30 Bluetooth/D-Input usa também VID 0x2DC8 / PID 0x0651.
        # O layout de seis botões é uma propriedade documentada do modelo e
        # será usado somente como layout esperado quando o backend físico ainda
        # não tiver exposto os elementos individuais.
        #
        # Ultimate 2C Wireless (81HD): VID 0x2DC8 / PID 0x310A. A documentação
        # e os testes externos consultados mostram o mesmo PID para USB-C direto
        # e para o adaptador 2.4G; não tratamos o PID XInput genérico 0x045E:0x028E
        # como identidade do modelo, evitando confundir o 2C com um Xbox real.
        return ControllerCatalogService(
            (
                ControllerCatalogEntry(
                    model_id="8bitdo-m30",
                    manufacturer="8BitDo",
                    model_name="M30",
                    aliases=("8BitDo M30 Gamepad", "M30 Gamepad"),
                    device_type=InputDeviceType.GAMEPAD,
                    vendor_id=0x2DC8,
                    product_ids=(0x5006, 0x0651),
                    expected_face_buttons=6,
                    expected_axes=2,
                ),
                ControllerCatalogEntry(
                    model_id="8bitdo-ultimate-2c",
                    manufacturer="8BitDo",
                    model_name="Ultimate 2C",
                    aliases=(
                        "8BitDo Ultimate 2C Wireless Controller",
                        "8BitDo Ultimate 2C Wireless",
                        "Ultimate 2C Wireless Controller",
                    ),
                    device_type=InputDeviceType.GAMEPAD,
                    vendor_id=0x2DC8,
                    product_ids=(0x310A,),
                    expected_face_buttons=4,
                    expected_axes=4,
                ),
            )
        )


__all__ = [
    "ControllerCatalogEntry",
    "ControllerCatalogService",
    "ControllerIdentification",
]
