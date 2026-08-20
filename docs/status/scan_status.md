# Status do Scan de ROMs e CHDs

## Estado atual

**FUNCIONAL PARA TESTES** — 2026-08-20

O scanner já é utilizável para testes de reconstrução e foi validado com um
set pequeno contendo ROMs e CHDs. CHDs válidos podem ser utilizados pela
reconstrução e pelo MAME.

## Regras que não podem ser quebradas durante a otimização

1. O LISTXML filtrado continua sendo a fonte de verdade.
2. ROMs devem procurar primeiro o ZIP/diretório da machine.
3. A busca de ROMs reaproveitáveis fora da machine não pode ser eliminada;
   ela deve ser desacoplada do caminho crítico do scan.
4. CHDs só devem ser procurados em:

   `<rom_path>/<machine>/<disk>.chd`

   Não deve existir busca global de `.chd`, nem busca dentro de ZIPs.
5. CHD inexistente deve resultar em `MISSING` imediatamente após o teste de
   existência do caminho esperado.
6. O scan não deve calcular SHA-1 de CHDs ausentes.
7. A validação criptográfica e `chdman verify` pertencem à etapa de validação
   da reconstrução, quando o CHD realmente existe.
8. O JSONL continua sendo o registro de auditoria e recuperação do scan.
9. Persistência e indexação não devem bloquear o processamento físico das
   machines.

## Gargalo identificado

O caminho antigo podia construir um índice global de todos os ZIPs quando uma
ROM não era encontrada localmente. Em fullsets isso transforma uma ausência
simples em uma varredura massiva do HDD.

A otimização deve separar:

- **scan crítico:** verificar somente os arquivos diretamente relacionados à
  machine;
- **indexação de fontes alternativas:** processo secundário, persistente e
  incremental;
- **reconstrução:** consultar o índice de fontes alternativas quando
  necessário.

Também foi identificado que `flush()` por registro no JSONL é inadequado para
um volume muito grande de registros. A persistência deve ser incremental, mas
com buffering, sem exigir flush físico a cada ROM.
