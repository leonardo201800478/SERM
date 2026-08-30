# SERM V2 — Especificação do Catálogo Base MAME

## Objetivo

O banco base do SERM V2 representa o catálogo completo capturado do `mame.exe -listxml`, complementado por fontes auxiliares (`catlist.ini`, `resolution.ini` e `Vsync.ini`). Esta camada deve permanecer como catálogo de referência e não deve ser reduzida pelos filtros nem conter profiles de sets.

## Estado validado

Auditoria realizada sobre o banco real em 30/08/2026:

- 31 tabelas MAME identificadas.
- `mame_machine`: 50.368 máquinas.
- `mame_rom`: 371.752 ROM entries.
- `mame_disk`: 1.402 discos/CHDs.
- `mame_biosset`: 40.611 BIOS entries.
- `mame_display`: 24.365 displays.
- `mame_classification`: 37.995 classificações CATLIST.
- `mame_resolution`: 23.598 resoluções.
- `mame_vsync`: 18.376 entradas, sendo 18.374 resolvidas e 2 não resolvidas.
- `mame_listxml_document`: 1 documento lossless de 319.966.164 bytes.
- `mame_listxml_import`: 1 importação concluída, MAME 0.289.

A auditoria detalhada e suas amostras reais ficam registradas no arquivo gerado `mame_database_audit.md`.

## Fonte de verdade

A fonte primária é o documento ListXML lossless. O registro em `mame_listxml_import` identifica build, hash, caminho e estado da importação; `mame_listxml_document` preserva o XML completo.

As tabelas relacionais são uma representação consultável e indexável do XML. Fontes INI são dados auxiliares e devem preservar sua proveniência em `mame_source_document`.

## Entidade central: mame_machine

`mame_machine` é a raiz relacional para consultas do catálogo. Campos relevantes:

- identidade: `id`, `name`;
- origem: `import_id`, `sourcefile`, `ingested_at`;
- natureza: `isbios`, `isdevice`, `ismechanical`, `runnable`;
- relações: `cloneof`, `romof`, `sampleof`;
- descrição: `description`, `year`, `manufacturer`.

As relações parent/clone devem ser consultadas através de `cloneof` e `romof`; não devem ser reconstruídas por heurística de nomes.

## ROMs e reconstrução

`mame_rom` contém 371.752 registros e é a fonte relacional principal para futura construção/reconstrução de sets. Campos essenciais: `machine_id`, `name`, `bios`, `size`, `crc`, `sha1`, `md5`, `merge`, `region`, `offset`, `status`, `optional`, `dispose`.

O campo `merge` deve ser preservado porque será necessário para estratégias merged, split e non-merged. `crc`/`sha1` devem ser tratados como identidade de conteúdo para as futuras funções de reconstrução.

`mame_disk` mantém os componentes de disco/CHD separadamente, com `md5`, `sha1`, `merge`, `region`, `status` e demais atributos.

## Hardware e dependências

O catálogo contém dados detalhados de hardware e dependências:

- `mame_chip`: 198.113;
- `mame_device`: 12.482;
- `mame_device_ref`: 781.216;
- `mame_slot`: 26.111;
- `mame_slot_option`: 544.952;
- `mame_ramoption`: 6.649.

Essas tabelas não devem ser descartadas durante filtros: podem ser relevantes para análise de compatibilidade e dependências.

## Vídeo

Há duas fontes distintas:

1. `mame_display`: dados de display provenientes do ListXML, com resolução, refresh, rotação, timings e proporção.
2. `mame_resolution`: dados auxiliares de `resolution.ini`.

As duas fontes devem permanecer separadas para permitir comparação e auditoria. Dados autoritativos do ListXML não devem ser sobrescritos por INI em caso de conflito.

## Classificação

`mame_classification` contém os dados resolvidos do `catlist.ini`, incluindo `category`, `subcategory`, `section_raw`, `flags_raw`, `machine_id`, `machine_name`, `source_document_id` e `resolved_status`.

CATLIST é uma fonte de classificação, não substitui os dados estruturais do ListXML.

## Vsync

`mame_vsync` contém dados de `Vsync.ini` e mantém a proveniência através de `source_document_id`. A auditoria encontrou 18.376 entradas, 18.374 resolvidas e duas entradas não correspondentes a máquinas (`RootFolderIcon mame` e `SubFolderIcon folder`). Essas duas entradas devem permanecer como `unresolved`; não devem gerar máquinas artificiais.

## Configuração e controles

O catálogo também contém:

- `mame_input`: 43.656;
- `mame_control`: 57.793;
- `mame_port`: 349.028;
- `mame_dipswitch`: 572.398;
- `mame_dipvalue`: 1.439.502;
- `mame_configuration`: 36.808;
- `mame_confsetting`: 343.901;
- `mame_adjuster`: 2.050.

Esses dados serão utilizados posteriormente para funções de análise e seleção, sem modificar o catálogo base.

## Driver, features e software

- `mame_driver`: 43.050;
- `mame_feature`: 24.143;
- `mame_biosset`: 40.611;
- `mame_sample`: 28.735;
- `mame_softwarelist`: 7.924.

Essas informações podem alimentar filtros posteriores por estado de emulação, som, vídeo, proteção, BIOS, software lists e outros critérios.

## Política de preservação

O banco base deve ser tratado como catálogo de referência:

```text
ListXML lossless
      ↓
catálogo relacional completo
      ↓
fontes auxiliares INI
      ↓
CONSULTAS / VIEWS / ÍNDICES
      ↓
filtros
      ↓
set reduzido
      ↓
novo banco de trabalho
      ↓
profiles
```

Não criar profiles nesta camada. Não modificar ou remover máquinas/ROMs como consequência de filtros. Profiles e artefatos de sets customizados serão responsabilidade de uma etapa posterior, utilizando um banco de trabalho separado.

## Camada de consultas futura

Antes da implementação dos filtros, deve existir uma camada somente-leitura para centralizar acesso ao catálogo. A API pretendida inclui, no mínimo:

```text
get_machine()
get_machine_roms()
get_machine_disks()
get_machine_bios()
get_machine_clones()
get_machine_parent()
get_machine_display()
get_machine_classification()
get_machine_resolution()
get_machine_vsync()
list_runnable_machines()
list_parents()
list_clones()
list_mechanical()
list_bios()
list_devices()
```

Essa camada deve evitar SQL duplicado espalhado pela GUI e pelos filtros e deve permitir que futuras funções sejam construídas sobre relações explícitas do catálogo.

## Regra de proveniência

Todo dado derivado de fonte externa ao ListXML deve manter `source_document_id` e o hash da fonte. Reimportações com o mesmo SHA devem ser idempotentes (`REUSE`). Um novo SHA representa uma nova versão da fonte.

## Auditoria

A auditoria automática deve continuar sendo executável para detectar perda de registros, tabelas inesperadas, inconsistências de cardinalidade e alterações acidentais no catálogo base.
