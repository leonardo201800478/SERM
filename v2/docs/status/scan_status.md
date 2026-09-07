# Status do scan

## Estado

**Implementação ativa em V2 — setembro de 2026.**

A V2 possui engine e services dedicados a scan, persistência, checkpoints, cache, filtros e páginas de GUI. O scanner ainda está em consolidação para suportar de forma uniforme diferentes famílias de catálogo.

## Pipeline atual

```text
Catalog
  ↓
Scan settings
  ↓
Filter pipeline
  ↓
Filesystem discovery
  ↓
File metadata / hashes
  ↓
Matching
  ↓
Persistent scan result
  ↓
Reconstruction candidates
```

## Invariantes MAME/CHD

1. O catálogo ingerido é a referência das máquinas e dependências.
2. A machine deve ser verificada primeiro nos caminhos diretamente relacionados a ela.
3. Busca alternativa de ROMs pode existir como índice separado, sem bloquear o caminho crítico.
4. CHD deve ser procurado no caminho esperado da machine; não fazer busca global indiscriminada.
5. CHD ausente pode ser classificado imediatamente como ausente, sem calcular SHA-1 de um arquivo inexistente.
6. Verificação profunda de CHD pertence à validação quando o arquivo existe.
7. JSONL e/ou persistência equivalente devem permitir auditoria e recuperação do processamento.
8. Persistência e indexação não devem transformar uma operação de scan em uma varredura redundante do disco.

## Desempenho

O caminho crítico deve privilegiar:

- acesso local à machine;
- cache de metadados quando válido;
- checkpoints para retomada;
- processamento incremental;
- buffering de persistência;
- paralelismo somente onde não comprometer consistência ou I/O.

Índices de fontes alternativas devem ser construídos incrementalmente e reutilizados pela reconstrução.

## Classificação

Os resultados devem distinguir, conforme o modelo do catálogo:

- conteúdo encontrado e compatível;
- conteúdo ausente;
- conteúdo incorreto;
- conteúdo potencialmente reutilizável;
- estado inconclusivo/erro.

A classificação final não deve ser confundida com a heurística utilizada para localizar um candidato.

## Regra de arquitetura

O scanner não depende da GUI. A GUI consome resultados e fornece comandos/configurações; filesystem traversal, hashing, matching, checkpoints e persistência pertencem aos serviços.
