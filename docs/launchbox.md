# ARCADE MANAGER — Integração com LaunchBox

## Objetivo

O LaunchBox é tratado como **frontend de apresentação e execução**, não como banco de dados primário do ARCADE MANAGER.

A integração será unidirecional:

```text
ARCADE MANAGER
      ↓
LaunchBox Exporter
      ↓
XML
      ↓
LaunchBox\Data
```

O ARCADE MANAGER não deve instalar o LaunchBox, copiar ROMs/emuladores ou alterar a configuração de emuladores já existente no frontend.

## Fonte de verdade

A fonte de verdade permanece no ARCADE MANAGER:

- machine;
- ROMs e dependências;
- catálogo;
- emulador/backend;
- RetroArch/core;
- perfil de controles;
- hardware arcade;
- perfil de volante;
- FFB;
- classificação e grupos.

Os XML do LaunchBox são artefatos derivados e podem ser regenerados.

## Categorias personalizadas

A exportação deverá permitir organizar a biblioteca em categorias e playlists coerentes com a arquitetura do ARCADE MANAGER.

Exemplos:

- Arcade — MAME;
- Arcade — FBNeo;
- Arcade — Flycast;
- Arcade — Supermodel;
- Arcade — RetroArch MAME;
- Arcade — RetroArch FBNeo;
- Arcade — RetroArch Flycast;
- Driving — G27;
- Driving — G27 — 270°;
- Driving — G27 — 360°;
- Driving — G27 — 540°;
- Driving — G27 — 900°;
- Fighting — Street Fighter;
- Fighting — Mortal Kombat;
- Fighting — The King of Fighters;
- Neo Geo;
- Lightgun;
- Trackball;
- Spinner.

A categorização deve ser baseada nos metadados internos, e não em heurísticas frágeis aplicadas diretamente ao XML do LaunchBox.

## Rotação de volante

Jogos de direção poderão ser classificados pelo perfil físico de volante arcade:

```text
Machine
  ↓
Arcade Hardware Profile
  ↓
Wheel Profile
  ↓
Rotation Degrees
  ↓
LaunchBox Category
```

Exemplo:

```text
Daytona USA
    → Driving
    → G27
    → 270°
```

O valor representa o perfil recomendado pelo hardware arcade emulado, e não necessariamente a capacidade máxima do volante físico.

## Exportação incremental

O exportador deverá:

1. validar o diretório `LaunchBox\Data`;
2. validar os XML existentes;
3. preservar dados externos não gerados pelo ARCADE MANAGER;
4. atualizar somente os registros sob responsabilidade do exportador;
5. criar backup antes de alterações destrutivas;
6. validar o XML resultante;
7. registrar data, versão e origem do export.

Nunca sobrescrever indiscriminadamente XML do usuário.

## Execução

O LaunchBox já poderá possuir os emuladores e suas configurações. O ARCADE MANAGER apenas referencia a configuração/associação definida para o jogo.

Não duplicar no LaunchBox a lógica de backend existente no ARCADE MANAGER.

## Estado

### Planejado

- Exportador XML;
- categorias por backend;
- categorias por família de jogo;
- categorias por hardware;
- categorias por rotação de volante;
- geração incremental;
- validação XML;
- backup e recuperação.

Nenhuma dessas funcionalidades deve ser considerada implementada até existir código funcional e teste com uma instalação real do LaunchBox.
