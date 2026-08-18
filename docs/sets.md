# Sets, Scan e Reconstrução

**Referência:** 17/08/2026

## Conceitos

- **Machine:** entidade lógica do MAME.
- **Arquivo:** artefato físico.
- **FULLSET/origem:** somente leitura.
- **Meu Set/destino:** resultado reconstruível.

Nunca assumir `machine == machine.zip` sem considerar ROMs compartilhadas, parent/clone, BIOS, devices e demais dependências.

## Scan ROMs

A aba Scan ROMs analisa as fontes configuradas e gera o `current_scan.jsonl`. Esse manifesto deve guardar o diagnóstico físico e, quando conhecido, a origem da ROM:

```text
source.archive
source.member
source.kind
machine
rom_name
size / CRC / SHA-1
status
```

O manifesto é a entrada da reconstrução.

## Reconstrução

A reconstrução aprovada é sequencial:

```text
current_scan.jsonl
    ↓
1 machine
    ↓
1 ROM
    ↓
origem já registrada
    ↓
streaming
    ↓
validação
    ↓
staging
    ↓
próxima ROM
    ↓
ZIP completo
    ↓
validação final
    ↓
os.replace()
```

### ROM com nome incorreto

Se o conteúdo físico corresponde à ROM esperada, o destino recebe o nome definido pelo manifesto/set. A origem nunca é renomeada.

### ROM em outra machine

A ROM é lida da origem registrada no manifesto e copiada para o destino durante a reconstrução da machine que necessita dela. Não se deve fazer uma nova varredura global da coleção.

### Integridade

A transferência deve verificar tamanho e CRC e, quando disponível, SHA-1. Falha de validação significa que o artefato não está concluído e pode ser repetido.

### Staging

Staging temporário é permitido no destino. Não existe cache permanente de ROMs. O ZIP final só deve ser publicado após a reconstrução e validação.

## Manifesto residual

Ao terminar, o objetivo é produzir um JSONL residual contendo **somente** as ROMs/dependências que ainda não foram resolvidas. Itens já reconstruídos não devem ser enviados para a etapa de download.

O residual alimentará futuramente a aba Torrent. Depois de obter os arquivos externos, a reconstrução poderá ser executada novamente sem repetir o Scan global.

## Tipos de set

- **Split:** preservar a relação parent/clone.
- **Non-Merged:** cada machine deve ser autossuficiente.
- **Merged:** parent e clones relacionados compartilham o conjunto físico conforme a semântica do MAME.

## Estado real

A aba e o núcleo de reconstrução existem. O desenho transacional/streaming está definido e parte dele já está implementada. A cobertura completa de formatos, residual, retries, recuperação e semântica dos três layouts ainda precisa de testes de integração antes de ser declarada concluída.
