# Arquitetura recomendada para Scan e Reconstrução

**Estado de referência:** 17/08/2026

Este documento é mantido como versão em português da arquitetura consolidada. A fonte de verdade da implementação é o código do repositório; o estado operacional e pendências estão em `docs/architecture.md`, `docs/sets.md` e `docs/phases.md`.

## Arquitetura aprovada

```text
MAME/listxml
   ↓
Dataset / SQLite
   ↓
Filtros
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

## Reconstrução

A reconstrução deve usar o diagnóstico do Scan e não reindexar todas as fontes.

```text
machine
 ↓
ROM individual
 ↓
source registrada
 ↓
streaming em blocos
 ↓
CRC + tamanho + SHA-1 quando disponível
 ↓
staging temporário no destino
 ↓
ZIP completo
 ↓
validação
 ↓
os.replace()
```

### Regras

- FULLSET/origens são somente leitura.
- Uma machine é processada por vez.
- Uma ROM é processada por vez.
- ROMs não são carregadas integralmente em RAM.
- Não existe cache permanente de ROMs.
- ROM com nome físico diferente recebe no destino o nome esperado.
- ROM compartilhada por outra machine é obtida pela origem registrada no manifesto.
- Falha de integridade não publica o resultado parcial.
- Retry deve ser limitado e observável.

## Estados

O `current_scan.jsonl` é o diagnóstico completo. O manifesto residual futuro deve conter somente os artefatos ainda não resolvidos. O manifesto original permanece preservado para novas reconstruções.

## Tipos de set

`Split`, `Merged` e `Non-Merged` são suportados como opções da reconstrução, mas sua semântica completa precisa ser validada com fixtures reais antes de declarar a implementação finalizada.

## Pendências

- validação transacional completa;
- residual correto;
- recuperação após interrupção;
- todos os `source.kind`;
- testes grandes;
- dependências completas de BIOS/device/sample/disk/CHD;
- integração qBittorrent.
