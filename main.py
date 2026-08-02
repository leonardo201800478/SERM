from config import DATABASE
from config import LISTXML

from parsers.xml_parser import XMLParser


def main():

    print("=" * 60)
    print("MAME Set Builder")
    print("=" * 60)

    parser = XMLParser(
        LISTXML,
        DATABASE
    )

    total = parser.parse()

    print()

    print("=" * 60)
    print(f"Total importado: {total:,}")
    print(f"Banco SQLite : {DATABASE}")
    print("=" * 60)


if __name__ == "__main__":
    main()