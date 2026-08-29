# Catalog Manager — SERM

**Estado:** arquitetura definida; implementação da nova fase pendente.
**Referência:** 29/08/2026

## Objetivo

O Catalog Manager mantém localmente as referências necessárias para auditoria e reconstrução sem transformar o catálogo em cache de ROMs.

```text
Fonte externa
 ↓
Provider
 ↓
Download do catálogo
 ↓
Validação
 ↓
Parser específico
 ↓
Catálogo local
 ↓
Reconstruction / Scan
```

## Fontes

### No-Intro

Fonte principal para conjuntos de cartuchos e mídias digitais suportados.

Referência operacional: Dat-o-MATIC e seus downloads diários. O provider deve descobrir os conjuntos disponíveis e manter a versão mais recente conhecida.

O parser deve aceitar as estruturas XML/DAT relevantes sem assumir que todos os sistemas possuem exatamente os mesmos campos.

Campos prioritários:

- game name;
- cloneof/parent;
- ROM name;
- size;
- CRC32;
- MD5;
- SHA1;
- demais metadados presentes.

### Redump

Fonte para discos ópticos.

O provider deve ser implementado somente após validar os endpoints/arquivos de catálogo atualmente disponibilizados pelo Redump. Não assumir URLs de download sem verificação.

O modelo é orientado a `Disc`, com metadados de sistema, título, edição, versão, serial, região, idiomas e hashes quando disponíveis.

### Amiga / WHDLoad / Retroplay

Fonte de catálogo própria para Amiga. O provider deve contemplar o ecossistema WHDLoad/Retroplay e a distribuição/índice utilizada pelo GamesNostalgia quando aplicável.

Não modelar esses pacotes como No-Intro.

### MAME

O catálogo MAME continua derivado do LISTXML e do pipeline já existente. Não criar uma segunda fonte de verdade para máquinas MAME.

## Atualização automática

O Catalog Manager deve verificar atualizações e baixar apenas metadados/catalogação.

```text
catálogo local
 ↓
verificar versão/data
 ↓
┌───────────────┐
│ atualizado?   │
└──────┬────────┘
       │
   não ↓ sim
      baixar  manter
```

Cada catálogo deve registrar:

- provider;
- conjunto;
- versão/data da fonte;
- URL de origem;
- data da sincronização;
- integridade do arquivo, quando possível;
- parser/schema utilizado.

## Cache

Catálogo e conteúdo são coisas diferentes.

```text
Catalog Cache
    ≠
ROM Cache
```

Manter DATs e índices locais é permitido. Não baixar ROMs somente para completar o catálogo.

## Integridade

Um catálogo novo deve ser validado antes de substituir a versão local conhecida.

Se o download falhar ou o parser rejeitar o conteúdo, o catálogo anterior permanece utilizável.

## Modelo comum

O Catalog Manager fornece metadados comuns, mas não força um modelo universal onde a semântica seja diferente.

```text
NoIntroGame
RedumpDisc
AmigaPackage
MameMachine
```

Cada modelo pode possuir campos específicos.

## Relação com reconstrução

```text
Catalog Manager
      ↓
referência lógica
      ↓
Matching Engine
      ↓
Reconstruction Planner
```

O Catalog Manager não cria ZIPs, CHDs ou pacotes finais. Essas responsabilidades pertencem aos serviços de reconstrução/Archive/CHD.

## GUI futura

A interface poderá exibir:

```text
Catálogos
├── No-Intro
│   ├── sistema
│   ├── versão
│   └── status
├── Redump
│   ├── sistema
│   ├── versão/data
│   └── status
└── Amiga / Retroplay
    ├── versão/data
    └── status
```

A atualização manual `Atualizar agora` deve existir mesmo com atualização automática habilitada.

## Próxima implementação

1. infraestrutura `CatalogProvider`;
2. cache e versionamento;
3. No-Intro provider;
4. parser No-Intro XML/DAT;
5. fixture Mega Drive/Genesis fornecida para o projeto;
6. testes de atualização/rollback do catálogo;
7. Redump provider após validação da fonte;
8. Amiga/Retroplay provider.
