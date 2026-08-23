# Roadmap do ARCADE MANAGER

**Estado de referência:** 23/08/2026

A evolução deixa de ser organizada apenas como um construtor de sets. O núcleo de ROMs permanece prioritário, mas passa a coexistir com execução, controles, FFB, apresentação, integração com frontend e gerenciamento de software.

## Fase 1 — Dataset e filtros

**Estado:** implementada em evolução.

- MAME/listxml;
- parser/modelos;
- SQLite/migrations;
- classificação;
- filtros;
- XML filtrado.

## Fase 2 — Scan físico

**Estado:** implementada em evolução.

- Scan ROMs;
- diagnóstico físico;
- estados de integridade;
- `current_scan.jsonl`;
- origem física.

## Fase 3 — Reconstrução

**Estado:** implementada estruturalmente; integração ainda em validação.

- Split;
- Merged;
- Non-Merged;
- streaming;
- staging;
- publicação atômica;
- residual;
- retry/recuperação.

## Fase 4 — Dependency Resolver

**Estado:** parcial/pendente.

- ROM;
- parent/clone;
- BIOS;
- device;
- sample;
- disk;
- CHD;
- compartilhamentos.

## Fase 5 — Plataforma de emuladores

**Estado:** arquitetura iniciada.

Consolidar:

- MAME;
- Flycast;
- FBNeo;
- Supermodel;
- runtime discovery;
- capabilities;
- configuração segura;
- backends de execução.

## Fase 6 — RetroArch

**Estado:** planejada.

- RetroArch runtime;
- core manager;
- MAME core;
- FBNeo core;
- Flycast core;
- detecção de versões;
- seleção de core;
- system/assets/shaders/saves/states;
- execução integrada ao catálogo.

## Fase 7 — Plugin Manager / FFB

**Estado:** planejada.

- arquitetura genérica de plugins;
- instalação/remoção;
- compatibilidade;
- configuração;
- integração FFBArcadePlugin;
- perfis FFB por família/jogo;
- preparação automática do runtime.

## Fase 8 — Controles

**Estado:** planejada.

- descoberta de dispositivos;
- Control Profiles;
- Control Families;
- mappings;
- overrides por jogo;
- aplicação em lote;
- MAME per-game/per-family configuration;
- Flycast/FBNeo/Supermodel/RetroArch.

Objetivo especial:

```text
configurar 1 jogo
      ↓
criar perfil
      ↓
aplicar à família
      ↓
validar conflitos
      ↓
gerar configurações dos backends
```

## Fase 9 — Hardware arcade

**Estado:** planejada.

- Hardware Profiles;
- Arcade Hardware Profiles;
- G27;
- volante;
- pedais;
- clutch;
- câmbio H-pattern;
- rotação original;
- ranges analógicos;
- controles especiais.

Casos de alta complexidade, como Hard Drivin', devem ser suportados por perfis avançados de hardware/mapeamento.

## Fase 10 — Presentation / CRT

**Estado:** planejada.

Criar uma camada independente de apresentação para filtros que não pertencem à emulação.

Prioridades:

- RetroArch shaders;
- Flycast Standalone;
- Supermodel;
- outros runtimes sem filtro CRT satisfatório.

Perfis previstos:

- CRT Light;
- Arcade Scanlines;
- Aperture Grille;
- Shadow Mask;
- Curvature;
- Bloom;
- High Resolution.

A implementação deverá respeitar o renderer, aspect ratio e resolução do runtime. Para RetroArch, o shader nativo do core/runtime será preferido. Para standalone, a solução deverá ser validada tecnicamente antes de ser considerada funcional.

## Fase 11 — Download Manager

**Estado:** planejada.

Criar gerenciador genérico com providers.

Primeiro provider: RetroArch.

Funções:

- catálogo de versões;
- seleção de arquitetura;
- download;
- progresso;
- validação de tamanho/hash;
- staging;
- instalação;
- backup;
- atualização;
- rollback quando possível.

A arquitetura conceitual será estudada a partir do StellarUpdater/Stellar.

## Fase 12 — Aquisição / Torrent

**Estado:** futura.

- qBittorrent;
- metadata/infohash;
- matching;
- download seletivo;
- residual → aquisição → Scan/reconstrução.

## Fase 13 — LaunchBox Export

**Estado:** planejada.

O LaunchBox será tratado exclusivamente como frontend de apresentação/execução já instalado e configurado pelo usuário.

O ARCADE MANAGER deverá gerar XML derivados para `LaunchBox\Data`, preservando o restante da instalação.

Objetivos:

- exportação de jogos;
- plataformas/categorias;
- categorias por backend;
- categorias por RetroArch core;
- categorias por família;
- categorias por hardware;
- categorias por rotação de volante;
- categorias como Street Fighter, Mortal Kombat e Neo Geo;
- validação XML;
- backup antes de alterações;
- exportação incremental.

Exemplos:

```text
Arcade — MAME
Arcade — FBNeo
Arcade — Flycast
Arcade — Supermodel
Driving — G27 — 270°
Driving — G27 — 360°
Driving — G27 — 540°
Driving — G27 — 900°
Fighting — Street Fighter
Fighting — Mortal Kombat
Neo Geo
```

O XML é um artefato derivado. O banco do ARCADE MANAGER continua sendo a fonte de verdade.

## Fase 14 — Qualidade e integração

**Estado:** contínua.

- testes unitários;
- testes de integração;
- fixtures parent/clone;
- testes de interrupção;
- testes de arquivos grandes;
- validação de mappings;
- testes com dispositivos físicos quando possível;
- testes de FFB;
- testes de shaders/apresentação;
- testes de instalação/rollback;
- testes de exportação LaunchBox;
- medição de I/O, CPU e memória.

## Ordem de implementação recomendada

1. Fechar Reconstrução.
2. Fechar Dependency Resolver.
3. Consolidar domínio de emuladores/backends.
4. Adicionar RetroArch.
5. Criar Plugin Manager.
6. Integrar FFBArcadePlugin.
7. Criar domínio de controles.
8. Criar famílias e aplicação em lote.
9. Criar Hardware Profiles/Arcade Hardware Profiles.
10. Integrar volante/G27 e FFB avançado.
11. Criar Presentation/CRT Profiles e avaliar integração por renderer.
12. Criar Download Manager.
13. Implementar Torrent/qBittorrent.
14. Implementar LaunchBox Export.

## Regra de conclusão

Uma fase só é considerada concluída quando o fluxo real correspondente estiver implementado e testado. Modelos, placeholders, telas vazias ou documentação não equivalem à funcionalidade concluída.
