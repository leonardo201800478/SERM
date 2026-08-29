# Strife Emulator and Roms Manager — SERM

**Nome do produto:** Strife Emulator and Roms Manager (SERM)
**Repositório:** `mame-set-builder` (nome histórico preservado)
**Estado de referência:** 29/08/2026

O **SERM** é uma aplicação desktop Python/Qt para gerenciamento, auditoria, reconstrução e execução de bibliotecas de emulação. O projeto nasceu como MAME Set Builder e evoluiu para uma plataforma que separa preservação de conteúdo, emuladores, RetroArch, controles, apresentação, downloads e integrações externas.

> **Fonte de verdade:** o código atual do repositório. A documentação distingue explicitamente funcionalidade implementada, validada e planejada.

## Visão do produto

```text
                         SERM
                          │
       ┌──────────────────┼──────────────────┐
       │                  │                  │
   Biblioteca         Emuladores         Apresentação
       │                  │                  │
 MAME / Consoles    MAME/Flycast/FBNeo   CRT / Shaders
 Scan / Rebuild      Supermodel          Overlays
       │             RetroArch
       │                  │
       └──────────────────┼──────────────────┘
                          │
                Perfis / Downloads
                          │
             Catálogos / Integrações
```

## Núcleo de preservação

O núcleo MAME continua protegido e independente das camadas de execução:

```text
MAME listxml
    ↓
Dataset / SQLite
    ↓
Filtros
    ↓
Scan físico
    ↓
current_scan.jsonl
    ↓
Dependency Resolver
    ↓
Reconstrução MAME
    ↓
Set final / residual
```

Regras fundamentais:

- FULLSET e origens são somente leitura;
- Machine é entidade lógica; arquivo é artefato físico;
- o Scan registra evidência física para a reconstrução;
- ROMs são processadas em streaming;
- staging é temporário;
- arquivos finais só são publicados após validação;
- nenhuma camada de emulação altera a verdade física do conteúdo.

## Reconstrução ampla

A reconstrução será dividida em domínios independentes:

```text
Reconstrução
├── MAME
│   ├── ROMs
│   ├── BIOS
│   ├── devices / samples / disks
│   └── CHDs
│
├── Consoles
│   ├── No-Intro
│   │   ├── DATs
│   │   ├── Parent / Clone
│   │   ├── Hash matching
│   │   └── ZIP Builder
│   │
│   ├── Redump
│   │   ├── DAT / catálogo
│   │   ├── Disc metadata
│   │   ├── Hash matching
│   │   └── CHD Builder
│   │
│   └── Amiga / WHDLoad / Retroplay
│       ├── catálogo
│       ├── versões / variantes
│       └── pacotes
│
└── RetroArch BIOS
    ├── catálogo baseado em .info
    ├── validação
    └── reconstrução / instalação
```

MAME e consoles **não compartilham regras de catálogo**. Compartilham apenas infraestrutura genérica quando isso não compromete a semântica da fonte.

## Catálogos externos

O SERM terá um **Catalog Manager** responsável por manter referências locais atualizadas, sem baixar conteúdo de jogos automaticamente.

Fontes planejadas:

- **No-Intro Dat-o-MATIC** — cartuchos e mídias digitais;
- **Redump** — discos ópticos;
- **Retroplay / WHDLoad**, com índice de distribuição utilizado pelo GamesNostalgia — Amiga;
- MAME/listxml — arcade.

O catálogo armazenará origem, conjunto, versão/data, hash do próprio DAT quando possível e data da sincronização. Atualizações serão detectadas sem substituir silenciosamente um catálogo válido.

## Arquivos compactados

A infraestrutura comum é o `ArchiveService`:

```text
ArchiveService
├── ZIP → Python zipfile
├── 7Z  → 7z.exe preferencial / py7zr fallback
└── RAR → backend externo quando necessário
```

O serviço atende leitura, inspeção, teste, extração e criação. ZIP é especialmente importante para a reconstrução de consoles e MAME. CHD permanece em serviço próprio.

## Emuladores

Backends standalone:

- MAME;
- Flycast;
- FBNeo;
- Supermodel.

RetroArch é tratado como runtime, com cores independentes.

A Home de RetroArch está concluída, incluindo instalação/atualização do runtime, atualização de cores por CRC, retry de três tentativas por core, continuidade após falha, detecção de 7-Zip e fallback de extração.

## Apresentação / shaders

A camada de apresentação permanece separada da emulação:

```text
Sistema
├── Core
├── Override
├── Shader
└── Overlay
```

Para RetroArch, priorizar shaders nativos leves e fiéis a CRT. Shaders de terceiros serão baixados diretamente de seus repositórios, sem incorporar seus arquivos ao repositório do SERM. Presets que tragam overlays/reflexos pesados não devem ser escolhidos como padrão.

A proporção de aspecto do shader deve representar o sistema/emulação, nunca ser forçada para 16:9 por causa do monitor do usuário.

## Controles e Force Feedback

Controles, hardware arcade e FFB permanecem domínios separados, com perfis por família/jogo e overrides específicos.

## Estado atual — 29/08/2026

### Concluído / validado

- núcleo MAME/listxml, SQLite, filtros e Scan;
- arquitetura estrutural de reconstrução MAME;
- arquitetura de emuladores e configuração;
- lazy loading das abas;
- consolidação Schema × Adapter dos emuladores;
- Home RetroArch;
- instalação/atualização RetroArch e cores;
- retry de download de cores: 3 tentativas por core e continuidade da fila;
- detecção de 7-Zip no Windows com fallback `py7zr`;
- infraestrutura inicial `ArchiveService`;
- testes consolidados da arquitetura atual;
- instalações reais validadas de MAME, Flycast, FBNeo e Supermodel;
- atualização automática da Home para estado READY após operações.

### Próxima fase

1. Catalog Manager;
2. No-Intro DAT Manager/Parser;
3. modelo Console Game/ROM/Parent-Clone;
4. hash matching de consoles;
5. planner de reconstrução de ZIPs;
6. validador contra DAT;
7. Redump catalog/parser;
8. Disc model e CHD Builder;
9. catálogo Amiga / WHDLoad / Retroplay;
10. integração rápida de BIOS RetroArch;
11. integração gradual do `ArchiveService` na reconstrução MAME.

### Depois

- controles e hardware;
- FFB;
- shaders/overlays por sistema;
- downloads adicionais;
- LaunchBox;
- aquisição/Torrent quando a base estiver madura.

## Regras de desenvolvimento

Antes de alterar código:

1. consultar o código atual no GitHub;
2. verificar modelos, schema e consumidores;
3. identificar funções ativas e legadas;
4. não remover funcionalidade ativa sem auditoria;
5. implementar em blocos pequenos;
6. executar testes da arquitetura atual;
7. validar fluxo real quando aplicável;
8. atualizar documentação somente com fatos verificados.

Documentação antiga não supera o código atual.

## Documentação principal

- `docs/architecture.md` — arquitetura geral do SERM;
- `docs/reconstruction.md` — reconstrução e regras de integridade;
- `docs/reconstruction-consoles.md` — reconstrução de consoles;
- `docs/catalogs.md` — Catalog Manager e fontes externas;
- `docs/archives.md` — ArchiveService;
- `docs/chd-reconstruction.md` — CHDs MAME e CHDs derivados de discos;
- `docs/retroarch.md` — RetroArch;
- `docs/phases.md` — roadmap;
- `mame-set-builder-Prompt MESTRE.md` — regras de evolução do projeto.
