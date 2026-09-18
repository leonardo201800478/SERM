# Architecture recommendations — historical note

Este arquivo registra recomendações que antecederam a consolidação da arquitetura V2.

## Regra atual

A arquitetura normativa está em [`architecture.md`](architecture.md). O estado e o roadmap estão em [`phases.md`](phases.md).

As recomendações deste arquivo não devem ser interpretadas como contrato independente do código atual.

## Decisões preservadas

- GUI separada dos services;
- SQLite como estado persistente V2;
- adapters para fontes externas;
- scan separado de reconstrução;
- staging e publicação atômica;
- V1 sem dependência de runtime na V2.
