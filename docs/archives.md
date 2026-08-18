# Arquivos, auditoria e integridade

**Referência:** 17/08/2026

## Papel

O scanner físico identifica arquivos e membros disponíveis sem alterar as fontes. O resultado do Scan é persistido no manifesto JSONL e consumido pela reconstrução.

## Identidade física

Sempre que disponível, usar:

- caminho/origem;
- nome do arquivo/membro;
- tamanho;
- CRC;
- SHA-1;
- formato;
- machine associada;
- nome esperado da ROM.

Não assumir que o nome do arquivo físico define a identidade da ROM.

## Origem somente leitura

As pastas configuradas na aba Scan ROMs são fontes. Nenhuma etapa de reconstrução pode renomear, mover, apagar ou sobrescrever arquivos nelas.

## Reconstrução

A reconstrução usa a origem registrada no `current_scan.jsonl`. Não deve executar uma nova indexação global de todos os ZIPs.

Cada ROM deve ser processada individualmente em streaming. O destino recebe o nome esperado pelo set, mesmo quando o membro de origem tem outro nome.

## Integridade

A ordem recomendada é:

```text
origem
 ↓
leitura em blocos
 ↓
CRC/tamanho
 ↓
SHA-1 quando disponível
 ↓
gravação em staging
 ↓
validação do resultado
 ↓
publicação
```

Se a transferência falhar, o artefato parcial não deve ser publicado. O processo pode repetir a operação dentro do limite configurado.

## Cache

Não manter cópias permanentes de ROMs como cache. O único espaço intermediário previsto é um staging temporário no destino.

## Formatos

ZIP é o formato principal da reconstrução atual. O scanner pode reconhecer outros tipos, mas cada `source.kind` deve ser explicitamente suportado pela reconstrução antes de ser considerado concluído.

CHD/disk e demais artefatos devem permanecer conceitualmente separados das ROMs.

## Pendências

- Testes de integridade pós-escrita com arquivos grandes.
- Testes de retry e interrupção.
- Cobertura completa de ZIP/7Z/arquivos soltos conforme os `source.kind` efetivamente emitidos pelo scanner.
- Auditoria completa de CHD/disk.
