# Estrutura do projeto V2

A estrutura abaixo descreve a responsabilidade arquitetural dos diretórios principais. O código deve permanecer organizado por responsabilidade, evitando colocar regras de negócio na GUI.

```text
v2/
├── pyproject.toml
├── README.md
├── LICENSE
├── ui.ini
├── docs/
├── images/
├── serm_v2/
│   ├── main.py
│   ├── __main__.py
│   ├── assets/
│   ├── catalog/
│   ├── config/
│   ├── database/
│   │   ├── bootstrap.py
│   │   ├── engine.py
│   │   ├── migrations/
│   │   └── models/
│   ├── domain/
│   ├── emulation/
│   ├── gui/
│   ├── integrations/
│   ├── library/
│   ├── reconstruction/
│   ├── runtime/
│   ├── services/
│   ├── sources/
│   └── tools/
└── tests/
```

## Pontos de entrada

- `serm_v2/main.py` — inicialização da aplicação.
- `serm_v2/__main__.py` — execução com `python -m serm_v2`.
- `pyproject.toml` — empacotamento, dependências, console scripts, pytest e Ruff.

## GUI

`serm_v2/gui/` contém páginas e diálogos. Entre as superfícies atuais estão Home, gerenciamento de emuladores, diretórios, filtros MAME/No-Intro, scan, reconstrução e apresentação.

A GUI pode solicitar operações a services, atualizar progresso e apresentar resultados. Não deve assumir a responsabilidade por indexação física, cálculo de hashes, persistência de catálogo ou regras de reconstrução.

## Services

`serm_v2/services/` contém os workflows de aplicação e componentes especializados. O diretório inclui serviços para:

- gerenciamento de emuladores;
- catálogos MAME e classificação;
- display, resolução e VSync;
- scan e persistência de scan;
- filtros;
- No-Intro;
- WHDLoad/C64;
- reconstrução e arquivos;
- integração com RetroArch.

## Sources

`serm_v2/sources/` define contratos, routing e aquisição. O objetivo é manter formatos externos fora do núcleo canônico.

## Database

`serm_v2/database/` contém engine, bootstrap, modelos e migrations. Alterações estruturais devem ser acompanhadas por migration compatível e testes.

## Tests

`tests/` contém testes unitários e de integração organizados por domínio. Novos serviços devem receber testes que cubram caminhos normais e falhas relevantes.

## Regra de dependência

Dependências preferenciais:

```text
GUI → Services → Domain / Sources / Database / Runtime
```

Evitar:

```text
GUI → SQL direto
GUI → varredura física
GUI → parser específico de fonte
Service → código V1
```

## V1

A implementação V1 permanece separada e não deve ser adicionada como pacote importável pela V2.
