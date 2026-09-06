# MAME SET BUILDER — Prompt operacional

**Atualizado:** 17/08/2026

## Fonte de verdade

Repositório: `leonardo201800478/mame-set-builder`.

Antes de programar, consultar o código atual, modelos, schema, consumidores e documentação. Nunca assumir que um plano antigo representa a implementação atual.

## Objetivo atual

```text
MAME/listxml
 ↓
dataset
 ↓
filtros
 ↓
Scan ROMs
 ↓
current_scan.jsonl
 ↓
Reconstrução
 ↓
Meu Set
 ↓
residual
 ↓
Torrent futuro
```

## Regras absolutas

1. FULLSET e fontes são somente leitura.
2. Não alterar ROMs de origem.
3. Não assumir `machine == machine.zip`.
4. Não duplicar ROMs em cache permanente.
5. Não carregar ROMs grandes integralmente em RAM.
6. Não repetir uma varredura global quando o manifesto já registra a origem.
7. Não declarar funcionalidade pronta sem teste real.
8. Preservar funções ativas e auditar consumidores quando uma API mudar.

## Scan

O Scan é responsável por descobrir o estado físico e produzir `current_scan.jsonl`. Quando disponível, registrar machine, ROM esperada, tamanho, CRC, SHA-1, `source.kind`, `source.archive` e `source.member`.

## Reconstrução

A reconstrução é sequencial e transacional:

```text
machine
 ↓
ROM
 ↓
source registrada
 ↓
streaming
 ↓
CRC + size + SHA-1 quando disponível
 ↓
staging no destino
 ↓
próxima ROM
 ↓
ZIP completo
 ↓
validação
 ↓
os.replace()
```

ROM com nome incorreto recebe no destino o nome esperado. ROM compartilhada por outra machine é copiada individualmente a partir da origem registrada. A origem nunca é modificada.

O staging é temporário e fica no destino; não é cache permanente.

## Set types

- Split;
- Merged;
- Non-Merged.

A semântica de parent/clone deve seguir o MAME e ser validada com fixtures antes de ser considerada concluída.

## Residual

Após reconstrução, `current_reconstruction.jsonl` deve conter somente itens ainda não resolvidos. O `current_scan.jsonl` original permanece preservado.

## Torrent

Torrent/qBittorrent é futuro. Deve consumir somente o residual, obter metadata antes da lista de arquivos e selecionar apenas os artefatos necessários.

## Banco

SQLite/migrations atuais são autoridade. Antes de modificar schema, consultar modelos, services e consumidores.

## GUI

GUI apresenta e coordena. Regras de negócio ficam em services/modelos. Operações pesadas ficam fora da thread da interface e devem expor logs, progresso e cancelamento cooperativo.

## Estado em 17/08/2026

### Implementado

- dataset/listxml e modelos em evolução;
- SQLite/migrations;
- filtros/classificação;
- XML filtrado;
- Scan ROMs;
- `current_scan.jsonl`;
- origem física no resultado do Scan quando disponível;
- aba e serviço de Reconstrução;
- opções Split/Merged/Non-Merged;
- arquitetura streaming/staging;
- documentação sincronizada.

### Em validação

- integridade pós-escrita;
- retries;
- residual;
- recuperação após interrupção;
- fixtures de parent/clone;
- todos os `source.kind`.

### Pendente

- Torrent/qBittorrent;
- Dependency Resolver completo;
- BIOS/devices/samples/disks/CHDs integrados de ponta a ponta;
- testes abrangentes de integração.
