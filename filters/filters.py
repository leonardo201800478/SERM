class Filter:
    def apply(self, machines):
        raise NotImplementedError

class BooleanFilter(Filter):
    def __init__(self, attribute, value):
        self.attribute = attribute
        self.value = value

    def apply(self, machines):
        return [m for m in machines if getattr(m, self.attribute) == self.value]

class ContainsFilter(Filter):
    def __init__(self, attribute, substring):
        self.attribute = attribute
        self.substring = substring.lower()

    def apply(self, machines):
        return [m for m in machines if self.substring in (getattr(m, self.attribute) or '').lower()]

class CompositeFilter(Filter):
    def __init__(self, filters, mode="AND"):
        self.filters = filters
        self.mode = mode.upper()

    def apply(self, machines):
        if self.mode == "AND":
            for f in self.filters:
                machines = f.apply(machines)
            return machines
        elif self.mode == "OR":
            result = []
            for f in self.filters:
                result.extend(f.apply(machines))
            # Remove duplicatas (usando nome como chave)
            seen = set()
            unique = []
            for m in result:
                if m.name not in seen:
                    seen.add(m.name)
                    unique.append(m)
            return unique
        return machines

# Filtros pré-definidos
def working_filter():
    return BooleanFilter('working', 1)

def no_clones_filter():
    # cloneof vazio indica que é um pai
    def apply(machines):
        return [m for m in machines if not m.cloneof]
    return FilterClass(apply)

class FilterClass(Filter):
    def __init__(self, apply_func):
        self.apply_func = apply_func
    def apply(self, machines):
        return self.apply_func(machines)

def no_mechanical_filter():
    return BooleanFilter('ismechanical', 0)

def category_contains(substring):
    return ContainsFilter('category', substring)

def working_arcade_filter():
    return BooleanFilter('working_arcade', 1)

def year_range(start, end):
    def apply(machines):
        return [m for m in machines if m.year and start <= m.year <= end]
    return FilterClass(apply)