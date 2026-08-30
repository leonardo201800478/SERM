# SERM V2 — Banco de configurações dos emuladores

## Objetivo

A aba **Configurações** será orientada por dados. O SERM não deve manter uma lista fixa de widgets e valores como fonte de verdade. Cada emulador deve fornecer as opções reais da versão instalada; o banco acrescenta metadados de apresentação, explicações, dependências, escopo e regras de hardware.

No MAME, a fonte primária é o executável configurado em **Diretórios**. A V2 consulta `-showconfig`, `-noreadconfig -showconfig` e `-showusage`. A documentação oficial 0.289 define `showconfig` como a exibição da configuração corrente e `showusage` como o resumo das opções de linha de comando. O SERM usa ambos para separar estado atual, defaults e catálogo de opções. 

## Camadas do banco

```text
emulator_definition
        │
        ├── config_group
        │       └── config_option
        │               ├── config_option_value
        │               ├── config_option_dependency
        │               └── config_option_capability
        │
        ├── config_file_binding
        ├── config_profile
        │       └── config_profile_value
        └── config_observation

hardware_capability ───────────────┘
```

### `config_option`

Representa a opção real do emulador. Armazena:

- chave nativa;
- descrição curta para tooltip;
- tipo de valor;
- controle de interface recomendado;
- default observado;
- limites/unidade quando conhecidos;
- escopo;
- superfície da interface;
- dependências;
- capacidades de hardware;
- versão que forneceu a definição.

### `config_option_value`

Valores discretos válidos para combos/radio/selectors. Não devemos inventar valores: devem vir do executável, documentação oficial ou uma tabela de conhecimento explicitamente versionada.

### `config_option_dependency`

É a base para o comportamento que diferencia o SERM de frontends comuns. Exemplo:

```text
video = bgfx
    ↓
bgfx_backend passa a ser relevante
    ↓
backend = vulkan
    ↓
opções dependentes de Vulkan tornam-se disponíveis
```

A dependência deve registrar a razão, para que a GUI possa explicar **por que** uma opção foi habilitada, desabilitada ou limitada.

### `config_option_capability`

Relaciona uma opção à capacidade detectada no PC. Isso permitirá que o SERM não apresente como recomendação uma opção incompatível com o hardware/driver disponível.

## Superfícies da interface

`surface` separa a configuração tradicional das camadas que terão abas próprias:

```text
configuration       → Aba Configurações
shaders_artworks    → Aba Shaders / Bezels
```

Assim, opções de artwork, GLSL e outros efeitos podem continuar catalogadas sem poluir a aba Configurações.

## Escopos do MAME

O banco prevê:

```text
global
orientation
monitor
source
bios
parent
system
runtime
```

A ordem de precedência não é inventada pelo SERM. Ela deve refletir a semântica real do MAME. A documentação oficial 0.289 descreve a carga de `mame.ini`, arquivos de orientação/tipo de monitor, source/driver, BIOS, parent e sistema, além de estabelecer que argumentos de linha de comando têm precedência. 

## Perfis

`config_profile` representa uma intenção persistível do SERM. Não é automaticamente um arquivo `.ini`.

Exemplo conceitual:

```text
profile: pacman
scope: system

waitvsync = ...
lowlatency = ...
keepaspect = ...
```

A materialização deve ser feita por um writer específico do emulador, respeitando a hierarquia e o formato nativo.

## Integridade

O banco nunca deve exigir que o SERM reescreva todo o arquivo do emulador. A implementação de escrita deverá:

1. identificar o arquivo correto pela camada/escopo;
2. preservar chaves desconhecidas;
3. preservar comentários e formatação quando tecnicamente possível;
4. criar backup;
5. gravar em temporário;
6. validar;
7. substituir atomicamente.

## MAME — regra especial

A configuração deve distinguir claramente:

- `mame.ini` global;
- INIs de orientação;
- INIs de tipo de monitor;
- INIs de source/driver;
- INI de BIOS;
- INI do parent;
- INI do sistema;
- overrides de runtime.

A documentação oficial do MAME 0.289 explica essa ordem e também informa que múltiplas pastas em `inipath` são pesquisadas na ordem configurada, com o primeiro arquivo encontrado tendo precedência. 

## Primeiro catálogo MAME

A ingestão já foi validada no SERM V2 com o executável configurado:

```text
G:\LaunchBox\emulators\mame\mame.exe
```

Resultado:

```text
50.368 máquinas
```

A próxima etapa da aba Configurações é executar o catálogo de opções do MAME e substituir gradualmente o `SPECS` estático da GUI pelo banco.

## Fontes

- MAME Documentation 0.289 — Command-line Index / Universal Command-line Options.
- MAME Documentation 0.289 — Multiple Configuration Files.
- MAME Documentation 0.289 — Configuring MAME.
- MAME Documentation 0.289 — BGFX Effects.
- Código do executável MAME configurado pelo usuário.
