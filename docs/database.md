# Banco de dados

**Referência:** 17/08/2026

SQLite é o banco principal. O schema e as migrations presentes no repositório são a autoridade para qualquer alteração.

## Regra de alteração

Antes de modificar tabelas:

1. consultar schema/migrations;
2. consultar modelos;
3. consultar repositories/services;
4. localizar consumidores;
5. avaliar compatibilidade;
6. alterar e testar.

Não usar o schema descrito em documentos antigos como autoridade.

## Papel do banco

O banco é usado para dados estruturais, filtros e consultas persistentes. O `current_scan.jsonl` representa o resultado físico de uma execução de Scan e não deve ser substituído por consultas improvisadas na GUI.

## Domínio

O projeto já possui modelos para entidades como machine, ROM, disk, filtros e resultado de scan. A persistência completa de todos os nós do `listxml` continua sendo uma área de evolução.

## Separação

```text
MAME/listxml
   ↓
dataset/modelos
   ↓
SQLite

filesystem
   ↓
ScanResult
   ↓
current_scan.jsonl
```

A reconstrução consome o manifesto físico produzido pelo Scan; não deve criar SQL para pesquisar novamente todas as fontes.

## Pendências

- Completar/validar persistência dos elementos estruturais do `listxml` que ainda não estejam representados.
- Consolidar dependências físicas de ROM, BIOS, device, sample, disk e CHD.
- Ampliar testes de migração e integração entre schema, modelos e services.
