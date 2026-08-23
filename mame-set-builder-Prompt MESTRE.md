# ARCADE MANAGER — PROMPT MESTRE v5

**Estado de referência:** 23/08/2026

## 1. Identidade do projeto

O produto chama-se **ARCADE MANAGER**.

O repositório continua sendo `leonardo201800478/mame-set-builder` por compatibilidade histórica, mas o nome funcional, arquitetural e documental do produto é ARCADE MANAGER.

O projeto nasceu como MAME Set Builder e agora abrange:

- biblioteca e dataset arcade;
- Scan e auditoria de ROMs;
- reconstrução de sets;
- dependências MAME;
- gerenciamento de emuladores;
- RetroArch e cores;
- plugins;
- controles;
- perfis de hardware arcade;
- Force Feedback;
- downloads e atualizações.

## 2. Fonte de verdade

O código do GitHub é a fonte de verdade da implementação.

Antes de alterar código:

1. consultar o GitHub;
2. consultar modelos e schema afetados;
3. consultar consumidores;
4. verificar commits recentes;
5. preservar funções ativas;
6. implementar;
7. testar o fluxo real;
8. atualizar documentação somente com fatos verificados.

Documentação antiga não supera o código.

## 3. Arquitetura de alto nível

```text
GUI
 ↓
Application Services
 ↓
Domain
 ├── Library / Dataset / ROM
 ├── Reconstruction / Dependencies
 ├── Emulator / Backend / Core
 ├── Controls / Hardware
 ├── FFB / Plugins
 └── Downloads / Packages
 ↓
SQLite + Filesystem + Runtime executables + External APIs
```

A GUI coordena. Regras de negócio permanecem em services e modelos.

## 4. Núcleo de preservação

O núcleo original do MAME Set Builder permanece protegido.

```text
MAME listxml
 ↓
Dataset
 ↓
Filtros
 ↓
Scan
 ↓
current_scan.jsonl
 ↓
Dependency Resolver
 ↓
Reconstrução
 ↓
Meu Set
```

### Regras absolutas

- FULLSET/origens são somente leitura.
- Nunca mover, apagar, renomear ou sobrescrever ROMs de origem.
- Machine é entidade lógica; arquivo é artefato físico.
- Nunca assumir `machine == machine.zip` sem resolver dependências.
- Não criar cache permanente de ROMs.
- Processar ROMs em streaming.
- Staging é temporário e fica no destino.
- Publicar somente depois de validar.

## 5. Scan

O Scan registra o estado físico e a origem de cada ROM quando possível.

O `current_scan.jsonl` é a ponte para reconstrução.

A reconstrução não deve repetir uma varredura global apenas para descobrir origens que já foram registradas.

## 6. Reconstrução

Arquitetura obrigatória:

```text
current_scan.jsonl
 ↓
machine
 ↓
ROM
 ↓
source registrada
 ↓
streaming
 ↓
CRC / tamanho / SHA-1
 ↓
staging
 ↓
ZIP
 ↓
validação
 ↓
os.replace()
```

Uma ROM encontrada com nome físico diferente recebe no destino o nome lógico exigido pelo set. A origem nunca é renomeada.

## 7. Dependency Resolver

O resolvedor deve evoluir para cobrir:

- ROM;
- parent/clone;
- BIOS;
- device;
- sample;
- disk;
- CHD;
- compartilhamentos.

Não implementar uma dependência por heurística quando a estrutura do MAME fornecer informação suficiente.

## 8. Emuladores, backends e cores

Distinguir sempre:

```text
Emulator
Backend
Core
```

MAME, Flycast, FBNeo e Supermodel podem possuir backends standalone.

RetroArch é um runtime. MAME, FBNeo e Flycast são cores executados por ele.

Não duplicar entidades de catálogo só porque existem dois modos de execução.

## 9. RetroArch

O projeto deverá suportar:

- RetroArch runtime;
- core MAME;
- core FBNeo;
- core Flycast;
- diretórios system/assets/shaders/saves/states;
- detecção de versão;
- instalação e atualização de cores;
- execução com seleção explícita do core.

A versão do core deve ser tratada como dado importante para compatibilidade. Nunca declarar que um ROM set é compatível apenas porque o arquivo existe.

## 10. Plugins

Plugins são componentes auxiliares, não emuladores.

Criar arquitetura genérica de Plugin Manager.

O primeiro plugin é o **FFBArcadePlugin**, baseado no fork de referência:

`https://github.com/leonardo201800478/FFBArcadePlugin`

O plugin possui suporte a MAME, Supermodel, Flycast e outros ambientes e conhecimento específico de jogos de Force Feedback. A integração deve aproveitar essa capacidade sem transformar a base do ARCADE MANAGER em uma cópia do plugin.

## 11. Controles

Criar domínio independente de controles:

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

O objetivo é permitir configurar uma máquina e replicar a configuração para um grupo.

Exemplos:

- Street Fighter;
- Mortal Kombat;
- Neo Geo;
- beat'em ups;
- shooters;
- lightgun;
- driving;
- motorcycle;
- flight stick;
- spinner;
- trackball.

## 12. Aplicação em lote

A replicação em lote deve ser uma operação de domínio, não uma simples cópia de arquivo.

A seleção poderá usar:

- família;
- sistema;
- fabricante;
- tipo de controle;
- características do input;
- lista manual.

Sempre permitir override individual.

## 13. Hardware arcade

Separar hardware original do dispositivo físico do usuário.

Exemplo:

```text
Arcade Game
  original wheel = 270°
        ↓
User Hardware Profile
  G27
        ↓
Backend mapping
  G27 limitado a 270°
```

Para jogos de corrida, representar também:

- volante;
- pedais;
- clutch;
- câmbio H-pattern/sequencial;
- botões;
- eixos;
- faixas analógicas;
- rotações;
- peculiaridades do gabinete.

Casos complexos como Hard Drivin' devem ser tratados como perfis de hardware/mapeamento avançado, não como simples teclas.

## 14. Force Feedback

FFB deve possuir:

- dispositivo;
- perfil global;
- perfil por família;
- perfil por jogo;
- plugin/backend;
- parâmetros específicos.

Herança recomendada:

```text
Global
 ↓
Family
 ↓
Game
```

O nível mais específico vence o mais genérico.

## 15. Configuração dos emuladores

Arquivos nativos são preservados.

Política:

```text
arquivo existe
 ↓
validar
 ├── válido → importar/reutilizar
 └── inválido → backup → regenerar somente com mecanismo oficial
```

Nunca sobrescrever configuração válida para alimentar o banco.

Nunca inventar comandos de geração.

No Windows, processos de geração/probe devem ser silenciosos, sem `shell=True`, com stdin apropriado, stdout/stderr capturados e validação posterior.

## 16. Downloads e atualização

Criar um Download Manager genérico com providers.

```text
Provider
 ↓
Package metadata
 ↓
Download
 ↓
Hash/size validation
 ↓
Staging
 ↓
Install
 ↓
Backup
 ↓
Rollback quando possível
```

O gerenciador RetroArch será inspirado conceitualmente no StellarUpdater/Stellar, sem copiar sua implementação.

Provider inicial esperado:

- RetroArch;
- cores;
- assets/system quando houver fonte confiável.

## 17. Banco de dados

SQLite/migrations continuam sendo autoridade.

A expansão deverá criar entidades para:

- emulator;
- backend;
- retroarch_core;
- plugin;
- control_profile;
- control_family;
- control_mapping;
- hardware_profile;
- arcade_hardware_profile;
- ffb_profile;
- package/provider/download.

Não duplicar ROM/machine para representar diferentes backends.

## 18. GUI planejada

A navegação deverá evoluir para algo semelhante a:

```text
Home
Biblioteca
  ├── Dataset
  ├── Filtros
  ├── Scan ROMs
  └── Reconstrução

Emuladores
  ├── MAME
  ├── Flycast
  ├── FBNeo
  ├── Supermodel
  └── RetroArch

Controles
  ├── Dispositivos
  ├── Perfis
  ├── Famílias
  ├── Mapeamentos
  └── Arcade Hardware

Force Feedback
Plugins
Downloads
Configurações
```

A organização final pode mudar durante implementação, mas os domínios devem permanecer separados.

## 19. Estado de referência em 23/08/2026

### Implementado

- dataset/listxml;
- SQLite/migrations;
- filtros/classificação;
- geração de XML;
- Scan ROMs;
- manifesto `current_scan.jsonl`;
- origem física no Scan;
- Reconstrução estrutural;
- Split/Merged/Non-Merged;
- streaming/staging;
- política de configuração de emuladores;
- capabilities/runtime para MAME, Flycast, Supermodel e FBNeo;
- diretórios de ROM do Flycast com até quatro entradas consolidadas no `Dreamcast.ContentPath`.

### Em validação

- protocolo transacional completo;
- residual;
- retry/recuperação;
- semântica final dos layouts;
- todos os source kinds;
- integração completa de discovery/importer.

### Planejado

- RetroArch backend;
- cores MAME/FBNeo/Flycast;
- Plugin Manager;
- FFBArcadePlugin;
- GUI de controles;
- Control Profiles/Families;
- Hardware Profiles;
- Arcade Hardware Profiles;
- G27/volantes/pedais/câmbios;
- FFB Profiles;
- Download Manager;
- Dependency Resolver completo;
- torrent/qBittorrent.

## 20. Regras finais

- Não remover função ativa sem auditoria.
- Não duplicar entidades existentes.
- Não colocar SQL de negócio na GUI.
- Não confundir documentação futura com funcionalidade implementada.
- Não afirmar que algo foi testado sem execução real.
- Sempre verificar o código-fonte atual no GitHub antes de modificar um componente.
- Sempre verificar documentação oficial das bibliotecas/emuladores quando a implementação depender de comportamento externo.
- Preservar compatibilidade com configurações existentes.
