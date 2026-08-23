# ARCADE MANAGER

**Estado de referência:** 23/08/2026

O **ARCADE MANAGER** é uma aplicação desktop Python/Qt para gerenciamento de bibliotecas arcade. O projeto nasceu como MAME Set Builder, mas evoluiu para uma plataforma capaz de analisar datasets, auditar ROMs, reconstruir sets, administrar emuladores, perfis de controles, Force Feedback, cores RetroArch, plugins e futuras aquisições de conteúdo.

> **Fonte de verdade:** o código atual do repositório. Esta documentação distingue explicitamente o que já existe, o que está em validação e o que está planejado.

## Visão do produto

```text
                    ARCADE MANAGER
                           │
       ┌───────────────────┼───────────────────┐
       │                   │                   │
    Biblioteca          Emuladores          Hardware
       │                   │                   │
   Dataset/ROMs      MAME/Flycast/FBNeo    Controles
   Scan/Rebuild      Supermodel            G27/volantes
   Dependências      RetroArch/cores        FFB
       │                   │                   │
       └───────────────────┼───────────────────┘
                           │
                    Perfis + Execução
                           │
                    Downloads/Updates
```

## Evolução do projeto

O antigo **MAME Set Builder** continua sendo o núcleo de preservação e construção de sets. O novo nome **ARCADE MANAGER** representa o escopo completo do produto.

O núcleo de ROMs permanece independente das novas camadas. Controles, FFB, emuladores, plugins e downloads não devem alterar a verdade física do FULLSET nem contaminar a lógica de integridade das ROMs.

## Núcleo atual

```text
MAME / listxml
      ↓
Dataset / SQLite
      ↓
Filtros / seleção
      ↓
Scan físico
      ↓
current_scan.jsonl
      ↓
Reconstrução
      ↓
Meu Set
      ↓
residual
```

### Princípios do núcleo

- FULLSET e origens são somente leitura.
- Machine é entidade lógica; arquivo é artefato físico.
- O Scan registra a origem física para que a reconstrução não precise revarrer globalmente as fontes.
- Reconstrução trabalha machine por machine e ROM por ROM.
- ROMs são processadas em streaming, sem cache permanente.
- Staging é temporário e fica no destino.
- Arquivos finais só são publicados depois de validação.

## Camada de emuladores

O projeto passa a suportar uma arquitetura de **backends de execução**:

- MAME standalone;
- Flycast standalone;
- FBNeo standalone;
- Supermodel;
- RetroArch como plataforma;
- cores RetroArch MAME, FBNeo e Flycast.

RetroArch não é tratado como três emuladores diferentes. É um runtime que seleciona um core para executar o conteúdo.

## Controles

Será criada uma camada dedicada para gerenciamento de controles:

```text
Dispositivo físico
      ↓
Perfil de hardware
      ↓
Perfil de controles
      ↓
Grupo/família de jogos
      ↓
Configuração específica do backend
```

O objetivo é permitir configurar uma máquina e replicar a configuração para famílias de jogos com controles comuns, por exemplo Street Fighter, Neo Geo, beat'em ups, shooters e jogos de corrida.

## Volantes e controles arcade

O sistema deverá representar o hardware original do gabinete, não apenas teclas. Para jogos de corrida poderão existir perfis com:

- volante e eixo;
- grau de rotação original;
- acelerador;
- freio;
- embreagem;
- câmbio H-pattern/sequencial;
- botões auxiliares;
- faixas analógicas;
- Force Feedback.

Isso permitirá criar perfis específicos para equipamentos como Logitech G27 e aplicá-los a jogos compatíveis.

## Force Feedback

O **FFBArcadePlugin** será integrado como plugin/runtime auxiliar, e não como emulador.

Arquitetura:

```text
MAME / Flycast / Supermodel / outros backends
                    ↓
              Plugin Manager
                    ↓
             FFBArcadePlugin
                    ↓
          perfil FFB por jogo/família
```

A integração deverá preservar a capacidade do plugin de tratar jogos específicos e parâmetros avançados. O fork de referência é `leonardo201800478/FFBArcadePlugin`.

## RetroArch e downloads

O projeto terá um gerenciador de instalação e atualização do ecossistema RetroArch, inspirado na arquitetura observada no projeto StellarUpdater/Stellar, mas com implementação própria.

O futuro gerenciador deverá tratar:

- RetroArch;
- cores;
- system/BIOS;
- assets;
- shaders;
- versões;
- downloads;
- validação;
- instalação;
- backup;
- atualização;
- rollback quando aplicável.

## Status

### Implementado

- dataset/listxml MAME;
- SQLite e migrations;
- filtros e classificação;
- geração de XML filtrado;
- Scan ROMs;
- manifesto `current_scan.jsonl`;
- registro de origem física;
- Reconstrução integrada;
- Split/Merged/Non-Merged em estrutura;
- streaming e staging;
- política segura de configuração de emuladores;
- capabilities/runtime para MAME, Flycast, Supermodel e FBNeo;
- guia de diretórios com configuração específica por emulador, incluindo quatro caminhos de ROM do Flycast.

### Em validação

- protocolo transacional completo da reconstrução;
- residual preciso;
- recuperação após interrupção;
- integração completa do discovery/importer;
- semântica real dos três layouts;
- cobertura completa dos `source.kind`.

### Planejado / nova arquitetura

- consolidação do nome ARCADE MANAGER;
- backend RetroArch;
- cores MAME/FBNeo/Flycast;
- Plugin Manager;
- integração FFBArcadePlugin;
- GUI dedicada de controles;
- perfis e famílias de controles;
- perfis de hardware arcade;
- perfis de volante/pedais/câmbio;
- aplicação em lote de configurações MAME;
- Force Feedback por jogo/família;
- gerenciador de downloads/atualizações RetroArch;
- Dependency Resolver completo;
- aquisição futura via torrent/qBittorrent.

## Segurança

- Nunca modificar o FULLSET/origens.
- Nunca renomear, mover ou apagar ROMs na origem.
- Nunca criar cache permanente de ROMs.
- Nunca publicar arquivo parcial.
- Validar tamanho e hashes antes da publicação.
- Preservar configurações válidas dos emuladores.
- Fazer backup antes de substituir configuração inválida.
- Não inventar formatos ou comandos não verificados na documentação/código do emulador.

## Documentação principal

- `docs/architecture.md` — arquitetura do ARCADE MANAGER.
- `docs/controls.md` — arquitetura planejada de controles e perfis.
- `docs/force-feedback.md` — integração e perfis FFB.
- `docs/retroarch.md` — RetroArch, cores e execução.
- `docs/download-manager.md` — gerenciador de downloads/updates.
- `docs/database.md` — persistência e evolução do banco.
- `docs/emulator-config-policy.md` — política de configuração.
- `docs/sets.md` — Scan, manifesto e reconstrução.
- `docs/phases.md` — roadmap.
- `mame-set-builder-Prompt MESTRE.md` — regras de evolução do projeto.

## Desenvolvimento

Antes de alterar qualquer componente: consultar o código atual no GitHub, modelos/schema afetados e consumidores; preservar funções ativas; testar o fluxo real; e atualizar a documentação somente com fatos verificados.
