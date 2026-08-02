from dataclasses import dataclass, field


@dataclass
class Machine:

    name: str

    description: str = ""

    cloneof: str | None = None

    romof: str | None = None

    manufacturer: str = ""

    year: str = ""

    sourcefile: str = ""

    runnable: bool = True

    isbios: bool = False

    isdevice: bool = False

    ismechanical: bool = False

    categories: set = field(default_factory=set)

    genres: set = field(default_factory=set)

    machine_types: set = field(default_factory=set)

    drivers: set = field(default_factory=set)

    languages: set = field(default_factory=set)

    controls: set = field(default_factory=set)

    players: int = 0

    working: bool = True