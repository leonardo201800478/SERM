"""Compatibilidade retroativa.

A implementação real do parsing agora é streaming e vive em
``app.mame.listxml_parser`` (função ``iter_machines``). Esta classe é
mantida apenas para não quebrar código/testes existentes que importam
``ListXmlParser`` — ela materializa a lista inteira em memória, então
prefira ``iter_machines`` diretamente em código novo.
"""

from typing import List

from app.core.models.machine import Machine
from app.mame.listxml_parser import iter_machines


class ListXmlParser:
    @staticmethod
    def parse(xml_string: str) -> List[Machine]:
        return list(iter_machines(xml_string))
