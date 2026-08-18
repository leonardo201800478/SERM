# Torrent / aquisição de ROMs

**Referência:** 17/08/2026

## Estado

A integração de download via torrent/qBittorrent é **pendente**. Não considerar esta aba ou fluxo como implementado apenas por existirem modelos ou documentação histórica.

## Objetivo

O Torrent deve receber o manifesto residual da reconstrução e adquirir somente os artefatos realmente ausentes.

```text
Reconstrução
    ↓
current_reconstruction.jsonl
    ↓
Torrent/qBittorrent
    ↓
arquivos faltantes
    ↓
Scan/revalidação ou reconstrução
```

## Regras

- Não baixar ROMs que já foram validadas localmente.
- Não alterar o FULLSET/origens.
- Identificar torrents por infohash ou outro identificador confiável.
- Obter metadata antes de consultar a lista de arquivos.
- Fazer matching por caminho/nome e, quando possível, tamanho/hash.
- Permitir seleção apenas dos arquivos necessários.
- Validar os arquivos obtidos antes de disponibilizá-los para reconstrução.

## Futuro

A primeira integração deve consumir torrents existentes. A criação de novos `.torrent` para subsets é uma etapa posterior e exige geração correta de piece hashes.
