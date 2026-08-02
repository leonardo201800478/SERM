# filters/filters.py
from typing import List, Set, Optional
from core.models import Machine

class Filter:
    """Classe base para todos os filtros."""
    def __init__(self, name: str):
        self.name = name

    def apply(self, machines: List[Machine]) -> List[Machine]:
        raise NotImplementedError

# ---------- Filtros básicos ----------

class FieldFilter(Filter):
    """Filtro por igualdade exata de um campo (string ou número)."""
    def __init__(self, field: str, value: str):
        super().__init__(f"{field} == {value}")
        self.field = field
        self.value = value

    def apply(self, machines: List[Machine]) -> List[Machine]:
        return [m for m in machines if getattr(m, self.field, None) == self.value]

class ContainsFilter(Filter):
    """Filtro por substring (case-insensitive)."""
    def __init__(self, field: str, substring: str):
        super().__init__(f"{field} contains '{substring}'")
        self.field = field
        self.substring = substring.lower()

    def apply(self, machines: List[Machine]) -> List[Machine]:
        return [
            m for m in machines
            if self.substring in (getattr(m, self.field, '') or '').lower()
        ]

class BooleanFilter(Filter):
    """Filtro para campos booleanos (True/False)."""
    def __init__(self, field: str, value: bool):
        super().__init__(f"{field} == {value}")
        self.field = field
        self.value = value

    def apply(self, machines: List[Machine]) -> List[Machine]:
        return [m for m in machines if getattr(m, self.field, False) == self.value]

class RangeFilter(Filter):
    """Filtro por intervalo numérico (ex: year >= 1980 e year <= 1990)."""
    def __init__(self, field: str, min_val: Optional[str] = None, max_val: Optional[str] = None):
        name = f"{field} range {min_val or ''} - {max_val or ''}"
        super().__init__(name)
        self.field = field
        self.min_val = min_val
        self.max_val = max_val

    def apply(self, machines: List[Machine]) -> List[Machine]:
        result = machines
        if self.min_val is not None:
            result = [m for m in result if (getattr(m, self.field) or '') >= self.min_val]
        if self.max_val is not None:
            result = [m for m in result if (getattr(m, self.field) or '') <= self.max_val]
        return result

class CompositeFilter(Filter):
    """Combina múltiplos filtros com AND ou OR."""
    def __init__(self, filters: List[Filter], mode: str = "AND"):
        super().__init__(f"Composite({mode})")
        self.filters = filters
        self.mode = mode.upper()

    def apply(self, machines: List[Machine]) -> List[Machine]:
        if self.mode == "AND":
            result = machines
            for f in self.filters:
                result = f.apply(result)
            return result
        elif self.mode == "OR":
            result_set: Set[Machine] = set()
            for f in self.filters:
                result_set.update(f.apply(machines))
            return list(result_set)
        else:
            raise ValueError("Modo deve ser AND ou OR")

# ---------- Filtros pré-definidos (helpers) ----------

def working_filter():
    """Mantém apenas máquinas com working == True (do XML)."""
    return BooleanFilter("working", True)

def no_clones_filter():
    """Mantém apenas máquinas que NÃO são clones (cloneof é None)."""
    class NoClones(Filter):
        def apply(self, machines):
            return [m for m in machines if m.cloneof is None]
    return NoClones("no_clones")

def no_mechanical_filter():
    """Remove máquinas mecânicas (ismechanical == False)."""
    return BooleanFilter("ismechanical", False)

def no_device_filter():
    """Remove dispositivos (isdevice == False)."""
    return BooleanFilter("isdevice", False)

def working_arcade_filter():
    """Usa a coluna working_arcade do arquivo .ini (True/False)."""
    return BooleanFilter("working_arcade", True)

def category_contains(substring: str):
    """Filtra por categoria contendo uma substring."""
    return ContainsFilter("category", substring)

def genre_contains(substring: str):
    """Filtra por gênero contendo uma substring."""
    return ContainsFilter("genre", substring)

def year_range(min_year: Optional[str] = None, max_year: Optional[str] = None):
    """Filtra por intervalo de anos."""
    return RangeFilter("year", min_year, max_year)