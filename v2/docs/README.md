# Documentação SERM V2

Esta é a entrada rápida para a documentação técnica da V2.

## Arcade Studio

- [Validação semântica MAME](mame-semantic-validation.md) — contrato de fontes, cardinalidade, facets, relações, identidade física e reconstrução.
- [Arquitetura de ROMs MAME](arcade-mame-rom-architecture.md) — artigo aprofundado sobre machine sets, ROMs, `merge`, `romof`, parent/clone, identidade física, CHD, layouts e manifesto.
- [ADR-0003 — Arquitetura de reconstrução de ROMs MAME](decisions/0003-mame-rom-reconstruction-architecture.md) — decisão arquitetural e invariantes do pipeline.

## Ordem de autoridade

Quando houver divergência entre documentos, use esta ordem:

1. código V2;
2. testes automatizados;
3. decisões arquiteturais (ADRs);
4. documentação operacional;
5. documentação histórica.

A documentação explica os contratos implementados; não substitui os testes executáveis.

## Validação recente

A arquitetura de reconstrução de ROMs foi validada no catálogo MAME real disponível no SERM:

```text
179.667 relações merge verificadas
SELF       167.637
MERGED      12.030
PARENT           0
ROMOF            0
MISSING          0
DIVERGÊNCIAS     0
```

Também foram executados os testes de reconstrução, manifesto, Set Builder e CHD:

```text
31 passed
```

E os testes semânticos específicos de `merge`:

```text
10 passed
```

A validação de amostra real também foi concluída sem alteração no banco:

```text
15 casos dirigidos
5 SELF
5 ROMOF
5 AMBIGUOUS
0 UNRELATED
0 UNRESOLVED
```

Esses números são resultados de validação do estado atual da branch e devem ser atualizados quando o contrato ou a implementação forem alterados.
