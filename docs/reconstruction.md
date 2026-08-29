# Reconstrução no SERM

**Produto:** Strife Emulator and Roms Manager (SERM)
**Referência:** 29/08/2026

A reconstrução é dividida por domínio de origem. MAME já possui suas regras definidas; consoles utilizarão catálogos próprios e não devem ser tratados como uma extensão do LISTXML.

```text
Reconstrução
├── MAME
├── Consoles
│   ├── No-Intro
│   ├── Redump
│   └── Amiga / WHDLoad / Retroplay
└── RetroArch BIOS
```

## 1. Regras comuns

A unidade de validade é o artefato físico esperado pelo catálogo/fonte. Nome sozinho nunca é identidade suficiente quando hashes estiverem disponíveis.

Fluxo comum:

```text
catálogo / dataset
 ↓
item lógico
 ↓
evidência física
 ↓
hash matching
 ↓
Reconstruction Planner
 ↓
staging
 ↓
ArchiveService / CHDService
 ↓
validação
 ↓
publicação atômica
```

Origens são somente leitura. Nenhuma reconstrução pode modificar, mover, apagar ou renomear conteúdo de origem.

Não manter cache permanente de ROMs. Staging é temporário e deve ser limpo ao final.

## 2. MAME

O fluxo MAME continua baseado em LISTXML, Scan e `current_scan.jsonl`:

```text
MAME listxml
 ↓
Dataset
 ↓
Scan
 ↓
current_scan.jsonl
 ↓
Dependency Resolver
 ↓
ROM / BIOS / device / sample / disk / CHD
 ↓
Reconstrução
```

A reconstrução utiliza a origem registrada pelo Scan e não deve fazer nova varredura global quando a evidência já estiver disponível.

### ZIP

ROMs são transferidas individualmente em streaming, renomeadas conforme o set e validadas antes da publicação.

### CHD MAME

CHDs existentes são validados pelo mecanismo próprio do MAME e tratados como artefatos de disco, não como ZIPs.

### Parent / Clone

A resolução utiliza as relações do LISTXML. Split, Merged e Non-Merged permanecem conforme o modelo MAME já definido e devem ser validados com fixtures reais antes de serem considerados finais.

## 3. Consoles — No-Intro

No-Intro é a fonte de referência para conjuntos de cartuchos/mídias digitais suportados.

O DAT Manager baixará e manterá localmente as versões mais recentes disponíveis, sem baixar ROMs automaticamente.

### Modelo lógico

```text
NoIntroGame
├── name
├── cloneof / parent
├── metadata
└── roms[]
    ├── name
    ├── size
    ├── crc32
    ├── md5
    └── sha1
```

O parser deve preservar os campos relevantes do DAT e não reduzir um jogo a um único arquivo quando existirem múltiplas ROMs.

### Matching

Prioridade conceitual:

```text
SHA1
 ↓
MD5
 ↓
CRC32 + tamanho
```

O nome físico pode estar errado e ainda assim o conteúdo ser reconhecido.

### Reconstrução

Exemplo:

```text
arquivo existente: Sonic.bin
        ↓
SHA1 corresponde ao DAT
        ↓
nome esperado: Sonic The Hedgehog (USA).md
        ↓
renomear no destino
        ↓
criar ZIP
        ↓
validar contra DAT
```

A operação deve evitar reprocessamento quando o conteúdo já estiver correto.

## 4. Consoles — Redump

Redump é tratado como domínio orientado a discos, não como No-Intro para CDs.

O modelo deverá preservar, conforme os dados disponíveis:

- sistema;
- título;
- edição;
- versão;
- serial;
- região;
- idiomas;
- hashes e demais metadados de identificação do disco.

### Fluxo

```text
Redump catalog
 ↓
Disc
 ↓
matching
 ↓
Disc Image
 ↓
CHD Builder
 ↓
CHD validation
 ↓
CHD final
```

**CHD é o formato preferencial de saída para discos** quando o sistema e a mídia forem compatíveis.

ISO/BIN-CUE podem ser usados como fontes/intermediários quando necessários. O projeto não deve converter cegamente uma imagem sem preservar faixas, áudio e demais características relevantes da mídia.

O `CHDService` permanece separado do `ArchiveService`.

## 5. Amiga — WHDLoad / Retroplay

Amiga possui semântica própria. O catálogo planejado utilizará o ecossistema WHDLoad/Retroplay e sua distribuição/índice, incluindo a fonte de download usada pelo GamesNostalgia quando aplicável.

O modelo deverá representar:

```text
AmigaPackage
├── title
├── version
├── variant
├── platform / chipset
├── language
├── media type
└── archive file
```

Formatos como LHA/LZX não devem ser tratados como ZIP apenas por conveniência. O suporte a esses formatos deve ser explicitamente implementado quando entrar em escopo.

## 6. RetroArch BIOS

BIOS de RetroArch é um domínio separado. O catálogo deve ser derivado dos metadados `.info`/fontes confiáveis do ecossistema.

Objetivo:

```text
catalogar
 ↓
scan/hash
 ↓
classificar
├── OK
├── renomeável
├── movível
├── reconstruível
└── MISSING
 ↓
operar somente o necessário
```

A validação deve ser rápida e não fazer nova varredura global desnecessária.

## 7. ArchiveService

Todos os domínios que precisarem manipular arquivos compactados devem utilizar a infraestrutura comum:

```text
ArchiveService
├── ZIP → zipfile
├── 7Z → 7z.exe / py7zr
└── RAR → backend externo quando necessário
```

Para reconstrução, o serviço deve suportar criação de ZIP, inclusão/substituição/renomeação quando necessário, teste de integridade, staging e publicação atômica.

## 8. Residual

O residual representa somente requisitos que não puderam ser satisfeitos. Um artefato validado e publicado não deve permanecer como pendência.

No MAME, `current_reconstruction.jsonl` continua sendo o mecanismo atual. Para consoles, o formato de manifesto deve ser definido junto com o Console Reconstruction Service.

## 9. Segurança

- nunca modificar origem;
- rejeitar path traversal;
- não publicar arquivo parcial;
- validar conteúdo antes da publicação;
- utilizar temporários no destino;
- limpar temporários após sucesso/falha;
- não baixar ROMs apenas para atualizar catálogo;
- não executar arquivos de conteúdo durante validação.

## 10. Próximas etapas

1. Catalog Manager;
2. No-Intro DAT Manager/Parser;
3. fixtures reais com Mega Drive/Genesis;
4. Console Game/ROM/Parent-Clone model;
5. hash matcher;
6. ZIP Builder;
7. validador DAT;
8. Redump provider/parser;
9. Disc model;
10. CHD Builder;
11. Amiga/Retroplay catalog;
12. RetroArch BIOS reconstruction;
13. migração gradual da reconstrução MAME para o ArchiveService.
