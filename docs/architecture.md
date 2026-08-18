# Arquitetura atual

**Referência:** 17/08/2026

## Regra

O código do GitHub é a fonte de verdade. Esta página descreve a arquitetura realmente presente e as decisões aprovadas para a próxima evolução.

## Camadas

```text
GUI (Qt)
  ↓
services / workers
  ↓
modelos de domínio
  ↓
MAME / filesystem / SQLite
```

A GUI não deve conter regras de negócio duplicadas.

## Fluxo

```text
MAME
 ↓
listxml
 ↓
parser / dataset
 ↓
SQLite + modelos
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
```

## Scan

O Scan é responsável por analisar o armazenamento físico e registrar a origem encontrada. O resultado JSONL é a ponte entre diagnóstico e reconstrução.

A reconstrução **não deve repetir uma varredura global** das pastas de origem apenas para descobrir novamente o que o Scan já descobriu.

## Reconstrução aprovada

A reconstrução deve ser transacional e sequencial:

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
staging temporário
  ↓
ZIP da machine
  ↓
validação
  ↓
os.replace()
```

Uma ROM compartilhada por outra machine é lida da origem registrada e escrita no destino com o nome exigido pelo set. A origem é sempre somente leitura.

### Staging

Não existe cache permanente de ROMs. O staging é temporário, descartável e deve ficar no destino, permitindo publicação atômica e evitando uma terceira cópia permanente do FULLSET.

### Memória

ROMs não devem ser carregadas integralmente em RAM. O processamento deve ser streaming, com buffer limitado.

### Integridade

Uma transferência não é considerada concluída apenas porque a leitura terminou. O conteúdo deve ser conferido contra tamanho/CRC e SHA-1 quando disponível. Falhas devem permitir retry e nunca publicar um resultado parcial.

## Set types

- **Split:** parent contém os arquivos próprios; clones contêm seus arquivos específicos conforme as relações do MAME.
- **Non-Merged:** cada machine precisa resultar em um conjunto autossuficiente.
- **Merged:** parent e clones relacionados compartilham o arquivo conforme a semântica do formato.

A implementação precisa ser validada com fixtures reais de parent/clone antes de ser considerada concluída.

## Princípios

1. FULLSET/origens somente leitura.
2. Uma machine por vez.
3. Uma ROM por vez.
4. Streaming em vez de cópia integral para RAM.
5. Nenhuma reindexação global durante reconstrução.
6. Publicação somente após validação.
7. Não transformar documentação futura em funcionalidade presumida.

## Pendências

- Fechar protocolo transacional completo com testes.
- Validar todos os `source.kind` usados pelo scanner.
- Fechar residual JSONL e recuperação após interrupção.
- Validar Split/Merged/Non-Merged.
- Completar resolução de BIOS/devices/samples/disks/CHDs onde ainda não estiver integrada.
- Implementar torrent/qBittorrent.
