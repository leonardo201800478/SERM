# Fases do projeto

**Estado:** 17/08/2026

## Fase 1 — Dataset e filtros

**Estado:** implementada em evolução.

- detecção/processamento MAME;
- listxml e modelos;
- SQLite/migrations;
- classificação e filtros;
- geração de XML filtrado.

## Fase 2 — Scan físico

**Estado:** implementada em evolução.

- aba Scan ROMs;
- leitura de fontes;
- diagnóstico de arquivos/membros;
- estados de integridade;
- `current_scan.jsonl`;
- registro de origem física para reconstrução.

## Fase 3 — Reconstrução

**Estado:** implementada estruturalmente, ainda requer validação de integração.

Objetivo:

```text
current_scan.jsonl
 ↓
machine por vez
 ↓
ROM por vez
 ↓
origem registrada
 ↓
streaming
 ↓
validação
 ↓
staging
 ↓
ZIP final atômico
```

Pontos ainda pendentes:

- validar os três tipos de set com fixtures reais;
- fechar residual somente com itens não resolvidos;
- retry e recuperação após interrupção;
- cobertura completa de formatos/source kinds;
- testes de arquivos grandes.

## Fase 4 — Torrent

**Estado:** pendente.

- aba Torrent;
- qBittorrent;
- metadata/infohash;
- matching seletivo;
- download dos resíduos;
- reentrada na reconstrução.

## Fase 5 — Dependências completas

**Estado:** parcial/pendente.

- ROM;
- BIOS;
- devices;
- samples;
- disks;
- CHDs;
- compartilhamentos parent/clone.

## Fase 6 — Qualidade

**Estado:** contínua.

- testes unitários;
- testes de integração;
- fixtures de parent/clone;
- testes de interrupção/cancelamento;
- testes de integridade;
- medição de I/O e memória.

## Regra de avanço

Uma fase só é considerada concluída quando o fluxo real correspondente estiver implementado e testado. Código de preparação, modelos ou documentação não equivalem à funcionalidade concluída.
