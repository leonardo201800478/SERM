# Processamento adaptativo

## Objetivo

O MAME Set Builder continua 100% em Python e não cria extensões C/C++ próprias. O aplicativo detecta o hardware no início e escolhe parâmetros conservadores para tarefas CPU-bound e I/O-bound.

## Hardware detectado

`app/core/system/hardware_detector.py` coleta:

- CPU e arquitetura;
- CPUs lógicos e estimativa de núcleos físicos;
- RAM total/disponível;
- AVX, AVX2, FMA3, SHA e AVX-512 quando as flags forem fornecidas pelo `py-cpuinfo`;
- versão do Python.

`py-cpuinfo` é uma dependência Python pura: a implementação não exige compilação C/C++/assembly para consultar as flags de CPU.

## Scheduler

`app/core/system/performance_manager.py` fornece duas políticas:

- `map_io()`: threads limitadas para operações predominantemente de I/O;
- `map_cpu()`: `ProcessPoolExecutor` com contexto `spawn` para tarefas independentes e CPU-bound.

O contexto `spawn` é deliberado porque o aplicativo é Qt e roda principalmente no Windows. Nenhum processo filho recebe uma conexão SQLite aberta pelo processo principal.

## Política do scanner físico

O acesso a `I:\ROMS\MAME` permanece conservador. Não devemos transformar o scan físico em um `ProcessPool` que abre centenas de ZIPs simultaneamente: em HDD isso pode piorar o throughput, aumentar seeks e pressionar a RAM.

O paralelismo de processos deve ser usado depois que os dados físicos já foram coletados, por exemplo para:

- consolidação de candidatos;
- classificação de resultados;
- preparação de registros do manifesto;
- reconstrução de máquinas;
- validações independentes que não alteram a origem.

A escrita SQLite permanece centralizada/serializada.

## SIMD e AVX2

Detectar AVX2 não faz um loop Python executar AVX2 automaticamente. O projeto não implementa intrinsics ou código compilado próprio. Para hashes, CRC e descompressão usamos os módulos/bibliotecas nativos já fornecidos pelo Python quando apropriado. A detecção SIMD serve para escolher backends e perfis no futuro, não para executar instruções de CPU diretamente em Python.

## Segurança

- Origem de ROMs: somente leitura.
- Processos CPU: recebem dados serializáveis, nunca conexões SQLite compartilhadas.
- `current_scan.jsonl`: continua sendo gerado em arquivo temporário e promovido atomicamente pelo fluxo existente.
- Cancelamento e encerramento de workers devem sempre usar `shutdown()`/context managers.

## Benchmark

O próximo passo é medir separadamente:

1. scan físico/HDD;
2. consolidação SQLite;
3. geração do JSONL;
4. reconstrução.

Os números do scan físico observado recentemente — aproximadamente 359 GB e 3.493 s — devem ser usados como baseline. A quantidade de workers somente deve aumentar quando o benchmark demonstrar ganho real.
