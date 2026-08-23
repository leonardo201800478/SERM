# Arquitetura do ARCADE MANAGER

**Referência:** 23/08/2026

## 1. Princípio arquitetural

O ARCADE MANAGER é dividido em um núcleo de preservação/construção de sets e camadas de gerenciamento de execução.

```text
┌────────────────────────────────────────────────────────────┐
│                        GUI / Qt                             │
├────────────────────────────────────────────────────────────┤
│ Library │ Scan │ Reconstruction │ Emulators │ Controls     │
│ FFB     │ RetroArch │ Downloads │ Settings                │
├────────────────────────────────────────────────────────────┤
│                     Application Services                   │
├──────────────────────┬──────────────────────┬──────────────┤
│ ROM/Set Domain       │ Emulator Domain      │ Hardware     │
│ Dataset              │ Runtime/Backend      │ Controls     │
│ Scan                 │ Core                 │ Profiles     │
│ Reconstruction       │ Plugin               │ FFB         │
│ Dependencies         │ Configuration        │ Devices     │
├──────────────────────┴──────────────────────┴──────────────┤
│ SQLite │ Filesystem │ Emulator executables │ External APIs │
└────────────────────────────────────────────────────────────┘
```

A GUI nunca deve duplicar regras de negócio. Operações de I/O pesado devem ocorrer em services/workers.

## 2. Núcleo de ROMs

```text
MAME listxml
   ↓
parser / dataset
   ↓
SQLite + modelos
   ↓
filtros
   ↓
Scan físico
   ↓
current_scan.jsonl
   ↓
Dependency Resolver
   ↓
Reconstrução
   ↓
Meu Set
   ↓
residual
```

Esse núcleo permanece independente de controles, FFB, RetroArch e downloads.

### Regras

1. FULLSET/origens são somente leitura.
2. Machine é entidade lógica; arquivo é artefato físico.
3. Scan registra a origem encontrada.
4. Reconstrução não faz nova varredura global quando a origem já está no manifesto.
5. Uma machine por vez e uma ROM por vez.
6. Processamento em streaming.
7. Staging temporário no destino.
8. Publicação somente depois de validação.

## 3. Dependency Resolver

O resolvedor será responsável por relações de:

- ROM;
- parent/clone;
- BIOS;
- device;
- sample;
- disk;
- CHD;
- arquivos compartilhados.

A resolução deve produzir dependências lógicas antes da operação física de reconstrução.

## 4. Domínio de emuladores

O projeto adota três conceitos distintos:

### Emulator

Um runtime standalone, como MAME, Flycast, FBNeo ou Supermodel.

### Backend

Implementação capaz de preparar e executar conteúdo em um runtime específico.

### Core

Um módulo Libretro executado pelo RetroArch.

```text
RetroArch
 ├── mame core
 ├── fbneo core
 └── flycast core
```

RetroArch não deve duplicar as entidades standalone. Um mesmo jogo pode ter mais de um backend de execução.

## 5. Plugin Manager

Plugins são componentes auxiliares que ampliam emuladores/backends.

```text
Emulator Backend
       ↓
Plugin Manager
       ↓
Plugin
```

O primeiro plugin integrado será o FFBArcadePlugin.

O plugin deve possuir metadados de compatibilidade, instalação, configuração e jogos suportados.

## 6. Domínio de controles

Controles serão modelados em camadas:

```text
Physical Device
      ↓
Hardware Profile
      ↓
Control Profile
      ↓
Control Family / Game Group
      ↓
Machine Override
      ↓
Backend Mapping
```

Isso permite configurar uma vez e aplicar a múltiplas máquinas.

### Exemplos

```text
Street Fighter Family
Neo Geo Family
Beat'em Up 2P
Lightgun
Driving
Motorcycle
Flight Stick
Spinner
Trackball
```

Uma máquina pode pertencer a uma família de controle e ainda possuir override individual.

## 7. Hardware profiles

Um hardware profile representa o equipamento físico, por exemplo:

```text
Logitech G27
 ├── Steering axis
 ├── Accelerator
 ├── Brake
 ├── Clutch
 └── H-pattern shifter
```

O perfil não deve conter diretamente a configuração de um único emulador. O backend converte o perfil para o formato necessário.

## 8. Arcade hardware profiles

Para preservar características do gabinete original, jogos podem possuir dados como:

- tipo de controle;
- rotação do volante;
- número de pedais;
- transmissão;
- tipo de câmbio;
- eixos analógicos;
- botões;
- FFB;
- particularidades do hardware.

Esses dados são independentes do dispositivo físico utilizado pelo usuário.

Exemplo:

```text
Arcade Game: Daytona USA
Original Steering: 270°
User Device: G27
Generated mapping: G27 → 270° profile
```

## 9. Force Feedback

FFB é uma camada transversal:

```text
Game
 ↓
Arcade FFB Profile
 ↓
FFB Plugin
 ↓
Physical Wheel
```

O perfil FFB pode ser individual ou herdado de uma família.

## 10. RetroArch

RetroArch possui configuração própria, mas os cores são entidades independentes:

```text
RetroArch Runtime
 ├── Core installation
 ├── Core configuration
 ├── System directory
 ├── Save directory
 └── State directory
```

Um core terá:

- nome;
- arquivo;
- versão;
- arquitetura;
- sistema suportado;
- origem de download;
- hash quando disponível;
- compatibilidade conhecida.

## 11. Downloads

Downloads devem ser separados do runtime.

```text
Package
 ↓
Provider
 ↓
Download Manager
 ↓
Validation
 ↓
Staging
 ↓
Install
 ↓
Backup / rollback
```

A arquitetura do StellarUpdater/Stellar é referência conceitual para o gerenciador RetroArch, mas o ARCADE MANAGER terá implementação própria.

## 12. Configuração de emuladores

Arquivos nativos continuam sendo a fonte de verdade da configuração específica do emulador quando existentes.

O `EmulatorConfigService` deve:

1. ler configuração existente;
2. validar;
3. importar sem destruir informação;
4. alterar somente propriedades suportadas;
5. preservar configurações desconhecidas;
6. criar backup antes de substituir configuração inválida.

## 13. Fluxo de execução

A execução futura seguirá:

```text
Selecionar jogo
      ↓
Resolver machine
      ↓
Selecionar backend
      ↓
Selecionar core se RetroArch
      ↓
Resolver Control Profile
      ↓
Resolver Hardware Profile
      ↓
Resolver FFB Profile / plugins
      ↓
Preparar configuração
      ↓
Iniciar runtime
```

A preparação deve ser reversível e não deve alterar o FULLSET.

## 14. Banco

SQLite permanece como autoridade persistente. A expansão deverá acrescentar entidades de emuladores, cores, plugins, controles e downloads sem acoplar essas entidades ao registro físico de ROM.

## 15. Estado da arquitetura

### Implementado

- camadas GUI/services/models;
- dataset/listxml;
- SQLite/migrations;
- Scan;
- manifesto JSONL;
- Reconstrução estruturada;
- capabilities/runtime de emuladores;
- política central de configuração.

### Em evolução

- Dependency Resolver;
- integração completa de configuração/discovery;
- protocolo transacional de reconstrução.

### Planejado

- RetroArch backend/core manager;
- Plugin Manager;
- FFBArcadePlugin;
- Control Profiles;
- Control Families;
- Hardware Profiles;
- Arcade Hardware Profiles;
- FFB Profiles;
- Download Manager;
- torrent/qBittorrent.
