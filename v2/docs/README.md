# Documentação SERM V2

Esta é a entrada rápida para a documentação técnica da V2.

## Estado atual

A fundação e a semântica de reconstrução de ROMs MAME estão validadas. O próximo objetivo é fechar o ciclo físico de materialização e só então levar o fluxo completo para a GUI.

**Próxima meta oficial: fechar o contrato do scan MAME.**

Consulte o [Roadmap da V2](phases.md) para metas, critérios de saída e ordem obrigatória.

## Arcade Studio

- [Validação semântica MAME](mame-semantic-validation.md) — contrato de fontes, cardinalidade, facets, relações, identidade física e reconstrução.
- [Arquitetura de ROMs MAME](arcade-mame-rom-architecture.md) — artigo aprofundado sobre machine sets, ROMs, `merge`, `romof`, parent/clone, identidade física, CHD, layouts e manifesto.
- [ADR-0003 — Arquitetura de reconstrução de ROMs MAME](decisions/0003-mame-rom-reconstruction-architecture.md) — decisão arquitetural e invariantes do pipeline.
- [Reconstrução](reconstruction.md) — ciclo lógico → físico → manifesto → materialização.
- [Dependências MAME](reconstruction-dependencies.md) — parent/clone, `romof`, `merge`, BIOS, devices, samples e CHD.

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
50.368 máquinas
179.667 relações merge verificadas
SELF       167.637
MERGED      12.030
PARENT           0
ROMOF            0
MISSING          0
DIVERGÊNCIAS     0
```

Foram executados os testes de reconstrução, manifesto, Set Builder e CHD:

```text
31 passed
```

Testes semânticos específicos de `merge`:

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

O planner real também foi confrontado diretamente com a evidência do catálogo e apresentou **0 divergências**.

## O que ainda não está concluído

- contrato completo do scan MAME;
- grafo completo de BIOS/devices/samples;
- validação de delta CHD em famílias reais;
- prova end-to-end da materialização física dos três layouts;
- re-scan do destino reconstruído;
- integração completa do pipeline na GUI;
- execução por perfis de emulador;
- otimizações de performance posteriores à estabilização dos contratos.

Esses itens estão ordenados no [Roadmap da V2](phases.md).