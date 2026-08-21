# Reconstrução multi-emulador

## Perfis

O seletor da aba Reconstrução possui quatro destinos:

- **MAME** — machines comuns em `roms/`.
- **Supermodel 3** — Sega Model 3 em `supermodel3/roms/`.
- **Flycast** — NAOMI/NAOMI2 em `flycast/roms/`, com GD-ROM em `<machine>/<disk>.chd`.
- **Multi-emulador** — publica os três destinos no mesmo processo.

## Layout Multi

```text
<destino>/
├── roms/                       # machines restantes para MAME
├── supermodel3/roms/           # Sega Model 3
├── flycast/roms/               # Sega NAOMI/NAOMI2
│   └── <machine>/<disk>.chd    # GD-ROM
├── bios/                       # BIOS MAME separado
├── devices/                    # devices MAME separado
├── samples/                    # samples
└── systems/                    # caminhos/BIOS de sistemas externos
```

A classificação utiliza `machine@sourcefile` do LISTXML, com fallback por nome/descrição. BIOS e devices não são tratados como jogos: o BuildPlanner determina as dependências necessárias.

## CHD

O scan somente verifica `<origem>/<machine>/<disk>.chd`. Se não existir, o estado é `missing` imediatamente. Não há busca global por `.chd`, procura em outras machines, procura dentro de ZIP ou cálculo de SHA-1 durante o scan.

Na reconstrução, um CHD presente é validado pelo content SHA-1 e `chdman verify`. Se inválido, é ignorado e permanece faltante. Se válido, é copiado diretamente para a estrutura de destino; o arquivo nunca é reconstruído.

## Scan expected-driven

O caminho físico único é `app/mame/physical_rom_scanner.py`.

```text
LISTXML / banco
      ↓
requisitos por machine
      ↓
ThreadPool por machine
      ├── <machine>.zip
      │      └── ZipInfo: nome + CRC + tamanho
      ├── <machine>/<rom>
      │      └── somente ROMs esperadas
      └── <machine>/<disk>.chd
             └── is_file()
      ↓
machine concluída
      ├── SQLite commit
      └── JSONL flush
```

O scanner não faz `rglob('*')`. ROMs de ZIP somente são lidas quando nome, tamanho e CRC já coincidem e o LISTXML possui SHA-1 para confirmação. ROMs soltas seguem nome → tamanho/CRC → SHA-1.

### Persistência

`current_scan.jsonl.tmp` é aberto **antes** dos workers. Cada machine concluída é escrita e `flush()` imediatamente. O SQLite também recebe a machine em uma transação curta. Ao final, o `ScanRomsTab` apenas renomeia o arquivo temporário para `current_scan.jsonl`; não existe uma segunda geração completa do manifesto.

Isso elimina o gargalo observado no teste de 6479 segundos, no qual o scan terminava e somente depois começava a construção do JSONL.

## Progresso e logs

O callback de progresso informa machine concluída/total, ROMs verificadas, válidas, ausentes, CHDs presentes/total e GiB lidos. O logger registra início, cada machine concluída, resumo final e exceções. A reconstrução utiliza callbacks de progresso/log para manter a GUI responsiva e informativa.

## Limpeza de legado

O caminho antigo `app/mame/rom_scanner.py` e os indexadores globais/duplicados foram removidos. Busca de ROMs reaproveitáveis deve permanecer fora do caminho crítico e ser usada pela reconstrução.

## Teste recomendado

Repita o mesmo LISTXML e as mesmas origens do teste que levou 6479 segundos e compare: tempo até o primeiro resultado, tempo total, crescimento do `.jsonl.tmp` durante o scan, I/O do HDD, CHDs ausentes resolvidos por `is_file()` e reconstrução do mesmo manifesto sem novo scan.
