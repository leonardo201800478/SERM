# MAME Set Builder

**Estado de referência:** 17/08/2026

O **MAME Set Builder** é uma aplicação desktop Python/Qt para analisar um dataset MAME, aplicar filtros, auditar um FULLSET e construir um conjunto de destino sem modificar a origem.

> **Fonte de verdade:** o código atual do repositório. Esta documentação distingue explicitamente o que já existe do que continua pendente.

## Fluxo atual

```text
MAME / listxml
      ↓
Dataset / banco
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
residual / ROMs externas
      ↓
Torrent (futuro)
```

## Implementado

- Detecção/processamento do dataset MAME.
- Parser e modelos estruturados.
- SQLite e migrations do projeto.
- Perfis e filtros com atualização da interface.
- Aba **Scan ROMs**.
- Scanner físico com resultados estruturados e manifesto JSONL.
- Registro da origem física das ROMs quando disponível no resultado do Scan.
- Classificação visual de estados.
- Geração de XML filtrado.
- Aba **Reconstrução** integrada.
- Seleção `Split`, `Merged` e `Non-Merged`.
- Reconstrução orientada pelo `current_scan.jsonl`, sem nova varredura global das fontes.
- Princípio de origem/FULLSET somente leitura.
- Staging temporário no destino, sem cache permanente de ROMs.
- Processamento incremental/streaming para evitar carregar ROMs inteiras em RAM.

## Reconstrução

A arquitetura definida é **uma machine por vez e uma ROM por vez**. A origem registrada pelo Scan é a referência inicial; a reconstrução não deve reindexar todas as pastas de ROMs.

```text
current_scan.jsonl
    ↓
machine
    ↓
ROM individual
    ↓
origem registrada
    ↓
streaming
    ↓
CRC / tamanho / SHA-1 quando disponível
    ↓
staging
    ↓
ZIP da machine
    ↓
validação
    ↓
publicação atômica no destino
```

ROMs compartilhadas por outras machines devem ser obtidas pela origem registrada e nunca alteradas na origem. Uma ROM com conteúdo correto, mas nome físico diferente, é escrita no destino com o nome exigido pelo set.

Não há cache permanente de ROMs. O staging temporário é descartável e deve ficar no destino.

## Pendências

### Reconstrução

- Cobertura completa de testes do protocolo ROM → validação → staging → ZIP → validação → publicação.
- Testes reais de `Split`, `Merged` e `Non-Merged` com parent/clone.
- Fechamento do manifesto residual contendo somente ROMs não resolvidas.
- Recuperação após interrupção sem duplicação/perda de estado.
- Cobertura de todos os `source.kind` suportados pelo scanner.
- Testes de integridade pós-escrita e retry com arquivos grandes.

### Torrent / aquisição

- Aba de download via torrent.
- Integração qBittorrent.
- Matching por infohash/lista de arquivos.
- Download seletivo das dependências residuais.
- Reentrada na reconstrução após aquisição.

### Dataset / dependências

- Completar/validar a persistência de todos os nós estruturais relevantes do `listxml` ainda não representados.
- Consolidar Dependency Resolver para ROM, BIOS, device, sample, disk, CHD e compartilhamentos.
- Auditoria completa de CHD/disk e demais artefatos.

### Qualidade

- Ampliar testes de integração Scan → Reconstrução.
- Não considerar funcionalidade futura concluída apenas porque existem modelos ou documentação para ela.

## Regras de segurança

- **Nunca modificar o FULLSET/origens.**
- Nunca renomear, mover ou apagar ROMs na origem.
- Nunca assumir `machine == machine.zip` sem resolver dependências.
- Não criar cache permanente contendo cópias das ROMs.
- Não carregar ROMs inteiras em memória sem necessidade.
- Validar tamanho e hashes antes de publicar artefatos reconstruídos.
- Publicar arquivos finais somente após conclusão e validação.

## Documentação

- `docs/architecture.md` — arquitetura real e limites atuais.
- `docs/archives.md` — auditoria e formatos físicos.
- `docs/database.md` — banco e regras de evolução.
- `docs/filters.md` — filtros e seleção.
- `docs/sets.md` — Scan, manifesto e reconstrução.
- `docs/torrents.md` — integração futura.
- `docs/phases.md` — roadmap real.
- `ARCHITECTURE_RECOMMENDATIONS.md` — decisões técnicas consolidadas.
- `mame-set-builder-Prompt MESTRE.md` — regras para evolução do projeto.

## Desenvolvimento

Antes de alterar qualquer componente: consultar o código atual no GitHub, modelos/schema afetados e consumidores; preservar funções ativas; testar o fluxo real; e atualizar a documentação somente com o que realmente foi implementado.
