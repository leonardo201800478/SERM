# Auditoria do estado atual — MAME Set Builder

**Referência:** 17/08/2026

## Objetivo

Este arquivo deixa de ser uma fotografia antiga do projeto e passa a registrar somente divergências e pendências conhecidas. O código do GitHub é a autoridade.

## Concluído desde a auditoria anterior

- A arquitetura possui uma aba Scan ROMs funcional em evolução.
- O resultado do Scan é representado por modelos e `current_scan.jsonl`.
- O manifesto pode preservar a origem física da ROM quando conhecida.
- A reconstrução foi separada da GUI em serviço próprio.
- A reconstrução não deve reindexar globalmente todas as fontes.
- Foi adotado processamento streaming para limitar RAM.
- Foi definido staging temporário no destino em vez de cache permanente de ROMs.
- A aba Reconstrução possui seleção de tipo de set e execução desacoplada da GUI.
- A documentação agora separa explicitamente implementação de roadmap.

## Pontos ainda em validação

### Reconstrução

- Validar integralmente transferência ROM a ROM, hashes e tamanho após escrita.
- Validar retries e recuperação de falha/interrupção.
- Validar publicação atômica sem deixar ZIP parcial.
- Validar `Split`, `Merged` e `Non-Merged` com parent/clone reais.
- Garantir residual JSONL somente com itens não resolvidos.
- Cobrir todos os `source.kind` realmente emitidos pelo scanner.

### Dataset

O modelo/schema ainda deve ser auditado contra todos os elementos do `listxml` necessários ao produto. Não presumir que tabelas existentes equivalem a importação implementada.

### Dependências

A resolução completa de BIOS, devices, samples, disks, CHDs e compartilhamentos ainda requer integração e testes além do fluxo ROM já desenvolvido.

### Torrent

qBittorrent/download seletivo ainda é futuro. O contrato pretendido é consumir somente o manifesto residual da reconstrução.

## Regras de engenharia

- Não modificar o FULLSET.
- Não duplicar ROMs em cache permanente.
- Não repetir trabalho já registrado pelo Scan sem justificativa técnica.
- Não carregar arquivos grandes integralmente em RAM.
- Não declarar uma funcionalidade como pronta sem teste real.
- Ao corrigir um componente, auditar seus consumidores e modelos relacionados.
