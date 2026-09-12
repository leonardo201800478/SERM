"""Leitura estruturada dos requisitos de entrada do MAME ``-listxml``."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from xml.etree import ElementTree


@dataclass(frozen=True, slots=True)
class MameControlRequirement:
    """Controle declarado pelo driver MAME para uma máquina."""

    control_type: str
    player: int | None = None
    buttons: int | None = None
    ways: int | None = None
    minimum: int | None = None
    maximum: int | None = None
    sensitivity: int | None = None
    keydelta: int | None = None
    reverse: bool = False
    attributes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class MameInputRequirements:
    """Conjunto de controles de uma máquina, sem qualquer mapeamento físico."""

    machine_name: str
    players: int | None
    coins: int | None
    service: bool
    controls: tuple[MameControlRequirement, ...]

    @property
    def max_buttons(self) -> int | None:
        values = [control.buttons for control in self.controls if control.buttons is not None]
        return max(values) if values else None


class MameControlService:
    """Extrai os controles do ListXML sem carregar o documento inteiro em memória."""

    def read_machine(self, xml_path: str | Path, machine_name: str) -> MameInputRequirements | None:
        path = Path(xml_path)
        for _event, element in ElementTree.iterparse(path, events=("end",)):
            if element.tag != "machine":
                continue
            if element.attrib.get("name") == machine_name:
                result = self._parse_machine(element)
                element.clear()
                return result
            element.clear()
        return None

    def iter_machines(self, xml_path: str | Path):
        """Itera requisitos de entrada, adequado ao ListXML grande do MAME."""
        path = Path(xml_path)
        for _event, element in ElementTree.iterparse(path, events=("end",)):
            if element.tag != "machine":
                continue
            yield self._parse_machine(element)
            element.clear()

    @classmethod
    def _parse_machine(cls, machine: ElementTree.Element) -> MameInputRequirements:
        input_node = machine.find("input")
        if input_node is None:
            return MameInputRequirements(
                machine_name=machine.attrib.get("name", ""),
                players=cls._int(machine.attrib.get("players")),
                coins=None,
                service=False,
                controls=(),
            )

        controls = tuple(
            cls._parse_control(control)
            for control in input_node.findall("control")
        )
        return MameInputRequirements(
            machine_name=machine.attrib.get("name", ""),
            players=cls._int(input_node.attrib.get("players")),
            coins=cls._int(input_node.attrib.get("coins")),
            service=cls._bool(input_node.attrib.get("service")),
            controls=controls,
        )

    @classmethod
    def _parse_control(cls, node: ElementTree.Element) -> MameControlRequirement:
        attributes = dict(node.attrib)
        return MameControlRequirement(
            control_type=attributes.get("type", "unknown").casefold(),
            player=cls._int(attributes.get("player")),
            buttons=cls._int(attributes.get("buttons")),
            ways=cls._int(attributes.get("ways")),
            minimum=cls._int(attributes.get("minimum")),
            maximum=cls._int(attributes.get("maximum")),
            sensitivity=cls._int(attributes.get("sensitivity")),
            keydelta=cls._int(attributes.get("keydelta")),
            reverse=cls._bool(attributes.get("reverse")),
            attributes=attributes,
        )

    @staticmethod
    def _int(value: str | None) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    @staticmethod
    def _bool(value: str | None) -> bool:
        return str(value).casefold() in {"yes", "true", "1"}


__all__ = ["MameControlRequirement", "MameControlService", "MameInputRequirements"]
