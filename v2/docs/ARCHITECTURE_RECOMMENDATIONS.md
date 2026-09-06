# Recomendações arquiteturais consolidadas

**Referência:** 17/08/2026

> Este documento é normativo para decisões futuras, mas não declara como implementado aquilo que ainda está no roadmap. Para o estado efetivo, consultar o código e `docs/phases.md`.

## 1. Fonte de verdade

O código atual do GitHub é a fonte de verdade da implementação. O `listxml` do mesmo MAME é a fonte estrutural primária do dataset. SQLite é índice/persistência derivada.

Datasets de versões diferentes não devem ser misturados.

## 2. Scan versus reconstrução

O Scan tem responsabilidade de descobrir e registrar o estado físico. A reconstrução tem responsabilidade de usar esse resultado.

**Não repetir uma varredura global das fontes durante reconstrução.**

```text
Scan
 ↓
current_scan.jsonl
 ↓
Reconstruction
```

O manifesto deve preservar, quando conhecido, `source.kind`, `source.archive`, `source.member`, machine, nome esperado, tamanho, CRC, SHA-1 e estado.

## 3. Reconstrução segura

A estratégia aprovada é:

```text
Machine
 ↓
ROM individual
 ↓
source registrada
 ↓
streaming limitado
 ↓
CRC + tamanho + SHA-1 quando disponível
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

### Regras

- uma machine por vez;
- uma ROM por vez;
- origem somente leitura;
- não carregar ROM inteira em RAM;
- não manter cache permanente de ROMs;
- staging temporário apenas no destino;
- nunca publicar arquivo parcial;
- retry controlado em caso de falha;
- validar antes da publicação.

## 4. Correção de nome

Quando o conteúdo encontrado possui identidade correta mas nome diferente, o destino recebe o nome esperado pelo MAME. Não alterar o nome físico na origem.

## 5. ROM compartilhada

Quando uma machine necessita de uma ROM presente em outra machine, usar a origem já registrada pelo Scan. Copiar o conteúdo individualmente durante a reconstrução da machine que precisa dele.

Não copiar uma coleção intermediária inteira nem criar cache permanente.

## 6. Integridade

CRC32 é excelente para triagem e compatibilidade com MAME. Quando SHA-1 estiver disponível no dataset, ele deve participar da confirmação final. O tamanho também deve ser conferido.

O hash deve ser calculado no mesmo streaming da transferência sempre que possível, evitando uma leitura integral adicional.

## 7. Set types

- **Split:** respeitar parent/clone e os membros próprios de cada conjunto.
- **Non-Merged:** cada machine deve resultar em um conjunto autossuficiente.
- **Merged:** parent e clones relacionados devem seguir a composição física do MAME.

A semântica deve ser validada com fixtures reais antes de declarar a implementação concluída.

## 8. Residual

Depois da reconstrução, o manifesto residual deve conter somente os arquivos que continuam sem fonte válida ou não puderam ser reconstruídos.

```text
current_scan.jsonl
       ↓
Reconstrução
       ↓
concluído ─────────→ destino
       ↓
faltante ─────────→ current_reconstruction.jsonl
       ↓
Torrent futuro
```

O manifesto original não deve ser destruído, porque ele continua sendo a referência completa do diagnóstico.

## 9. Banco e parser

Não reconstruir o XML a partir de um modelo reduzido se isso eliminar elementos do `listxml`. O parser deve preservar a estrutura que o produto realmente utiliza. O schema atual é autoridade para alterações no banco.

## 10. Performance

Prioridade:

1. reduzir trabalho;
2. streaming;
3. evitar leituras duplicadas;
4. SQLite/indexação;
5. batch onde apropriado;
6. concorrência somente quando comprovadamente benéfica.

Na reconstrução, concorrência agressiva é contraindicada por padrão porque aumenta contenção de I/O e complexidade de recuperação.

## 11. Torrent

A integração qBittorrent é futura e deve consumir o residual. O primeiro objetivo é utilizar torrents existentes; criação de novos torrents/subsets é posterior.

## 12. Estado real

Implementado: dataset/modelos/banco/filtros, Scan ROMs, manifesto JSONL, geração XML filtrado e estrutura de Reconstrução.

Em validação: protocolo transacional completo da reconstrução, três layouts de set, residual e recuperação.

Pendente: torrent/qBittorrent, resolução completa de dependências e cobertura integral de CHD/disk/outros `source.kind`.
