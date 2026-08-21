# Reconstrução multi-emulador

## Perfis

O seletor da aba Reconstrução possui quatro destinos:

- **MAME** — mantém as machines comuns em `roms/`.
- **Supermodel 3** — envia machines identificadas pelo driver Model 3 para `supermodel3/roms/`.
- **Flycast** — envia NAOMI/NAOMI2 para `flycast/roms/` e mantém cada GD-ROM CHD em `flycast/roms/<machine>/<disk>.chd`.
- **Multi-emulador** — executa os três destinos no mesmo processo.

A classificação usa `machine@sourcefile` do LISTXML, com fallback por nome/descrição. O `sourcefile` é a melhor indicação porque o LISTXML oficial expõe o driver responsável pela machine.

## Layout Multi

```text
<destino>/
├── roms/                       # machines restantes para MAME
├── supermodel3/
│   └── roms/                   # Sega Model 3
├── flycast/
│   └── roms/                   # Sega NAOMI/NAOMI2 + ZIPs
│       └── <machine>/
│           └── <disk>.chd      # GD-ROM
├── bios/                       # BIOS MAME separado
├── devices/                    # devices MAME separado
├── samples/                    # samples comuns
└── systems/
    ├── flycast/
    │   └── dc/                 # BIOS NAOMI para Flycast/RetroArch
    └── mame-set-builder-paths.json
```

O Flycast aceita jogos NAOMI em ZIP MAME e GD-ROM em CHD, com o CHD em um subdiretório nomeado pelo MAME ID. A documentação do Libretro/Flycast dá `ikaruga.zip` + `ikaruga/gdl-0010.chd` como exemplo. O Flycast também espera BIOS NAOMI no diretório de sistema quando usado via RetroArch. citeturn2search7turn2search3

O Supermodel usa ROM sets compatíveis com MAME em ZIP e normalmente mantém esses sets em sua pasta `ROMs`. citeturn1search0

## BIOS e devices

BIOS e devices não são misturados arbitrariamente aos ZIPs dos jogos. O BuildPlanner determina as dependências e o reconstrutor publica os sets externos separadamente.

Isso preserva a semântica do MAME, que procura system ROMs e device ROMs através do `rompath`; portanto a configuração pode apontar `roms`, `bios` e `devices` como caminhos separados. citeturn3search0turn3search2

## CHD

O scan apenas verifica existência em:

```text
<origem>/<machine>/<disk>.chd
```

CHD inexistente é `MISSING` imediatamente. Não há busca global por `.chd`, nem procura dentro de ZIP.

Na reconstrução o CHD é validado pelo content SHA-1 e `chdman verify`; se inválido, é ignorado e permanece faltante. Se válido, é copiado sem reconstrução.

## Scan esperado-driven

O novo scanner de teste está em `app/mame/expected_driven_scan_service.py`.

Ele trabalha em paralelo por machine e possui um writer dedicado para JSONL:

```text
LISTXML
  ↓
requirements
  ↓
worker por machine
  ├── machine.zip / machine/
  └── machine/<disk>.chd
  ↓
result queue
  ├── ScanResult
  └── JSONL writer thread
```

O scan não percorre o HDD para descobrir arquivos. Para ZIP, `ZipInfo` fornece CRC e tamanho no diretório central; o conteúdo é lido somente para o membro que corresponde ao requisito e precisa de SHA-1. citeturn7search0

## Teste recomendado

Use o mesmo LISTXML e as mesmas origens do teste que levou 6479 segundos. O objetivo da comparação é medir:

1. tempo até o primeiro resultado;
2. tempo total do scan;
3. tempo de criação do JSONL;
4. quantidade de I/O do HDD;
5. quantidade de CHDs tratados como `MISSING` sem busca global;
6. reconstrução do mesmo manifesto sem novo scan.

O branch de trabalho é `perf/scan-expected-driven`. Ele contém o scanner esperado-driven, o seletor de perfil e o reconstrutor multi-emulador.
