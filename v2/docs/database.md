# Banco de dados do ARCADE MANAGER

**Referência:** 23/08/2026

SQLite é o banco principal. O schema e as migrations presentes no repositório são a autoridade para qualquer alteração.

## Regra de alteração

Antes de modificar tabelas:

1. consultar schema/migrations;
2. consultar modelos;
3. consultar repositories/services;
4. localizar consumidores;
5. avaliar compatibilidade;
6. alterar migration;
7. executar testes.

Documentação nunca substitui o schema real.

## Papel do banco

O banco persiste dados estruturais, catálogo, configurações de domínio, filtros, perfis e metadados.

O `current_scan.jsonl` continua sendo o manifesto físico de uma execução de Scan e não deve ser substituído por consultas improvisadas da GUI.

## Separação do núcleo de ROM

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

A reconstrução consome o manifesto físico produzido pelo Scan.

## Domínios futuros

A evolução do banco deverá separar claramente:

### Biblioteca

- machine;
- ROM;
- disk;
- CHD;
- BIOS;
- device;
- sample;
- parent/clone;
- dependências.

### Emuladores

- emulator;
- backend;
- installation;
- runtime capability;
- emulator configuration metadata.

### RetroArch

- retroarch installation;
- core;
- core version;
- core installation;
- core source/provider.

### Plugins

- plugin;
- plugin version;
- plugin installation;
- plugin compatibility;
- plugin configuration.

### Controles

- physical device;
- hardware profile;
- control profile;
- control family;
- control mapping;
- machine override.

### Hardware arcade

- arcade hardware profile;
- wheel rotation;
- pedals;
- transmission;
- analog ranges;
- specialized controls.

### Force Feedback

- FFB profile;
- FFB family assignment;
- FFB game override;
- plugin association.

### Downloads

- provider;
- package;
- version;
- download source;
- installed package;
- download job/history quando necessário.

## Regra de normalização

Não duplicar uma machine/ROM para representar diferentes modos de execução.

```text
Machine
 ├── MAME backend
 ├── FBNeo backend
 └── RetroArch + core
```

As relações de execução devem apontar para a mesma entidade lógica.

## Regra de herança

Perfis de controle e FFB devem poder possuir herança:

```text
Global
 ↓
Family
 ↓
Machine
```

O override específico deve vencer o perfil genérico.

## Migrações

A expansão deverá ocorrer em migrations incrementais. Não remodelar o banco inteiro de uma vez apenas por causa da nova arquitetura.

Cada nova entidade deve ser implementada somente após auditar seus consumidores.

## Pendências

- completar persistência estrutural do listxml;
- Dependency Resolver;
- entidades de emuladores/backends;
- RetroArch/core;
- plugins;
- controles/perfis;
- hardware arcade;
- FFB;
- download manager;
- testes de migration e integração.
