# CHD no SERM

**Referência:** 29/08/2026

CHD possui dois contextos distintos no projeto e não deve ser confundido com arquivo compactado genérico.

```text
CHD
├── MAME
│   └── validar/copiar artefatos existentes conforme LISTXML
└── Consoles / Discos
    └── construir CHD a partir de mídia compatível
```

## 1. CHD MAME

No fluxo MAME já definido, um CHD encontrado é:

1. identificado como requisito do Scan/Dependency Resolver;
2. validado pelo `chdman info`;
3. comparado pelo content SHA1 esperado pelo LISTXML;
4. validado com `chdman verify` quando aplicável;
5. copiado para o destino.

Não executar create/extract/merge/recompressão de CHD MAME como parte dessa reconstrução já definida.

Se o content SHA1 divergir, o arquivo não é aceito como o requisito.

## 2. CHD para discos de consoles

Na nova reconstrução de consoles, especialmente com catálogo Redump, **CHD será o formato de saída preferencial** sempre que a mídia e a informação disponível permitirem conversão correta.

Fluxo:

```text
Redump Disc
 ↓
fonte de imagem compatível
 ↓
DiscImage model
 ↓
CHD Builder
 ↓
CHD temporário
 ↓
validação
 ↓
CHD final
```

O builder deve preservar corretamente:

- dados;
- faixas;
- áudio;
- ordem das faixas;
- informações necessárias ao conteúdo;
- metadados relevantes para a conversão.

Não converter cegamente uma ISO/BIN-CUE apenas para produzir um `.chd`.

## 3. Fonte e matching

O Redump será a referência lógica para discos. A identidade deve usar os hashes/metadados fornecidos pela fonte, sem inferir uma correspondência apenas pelo nome.

## 4. Atomicidade

CHD construído deve seguir o mesmo princípio de staging:

```text
CHD temporário
 ↓
verify / validação
 ↓
os.replace()
 ↓
CHD final
```

Nunca publicar uma imagem parcialmente construída.

## 5. Serviço

O `CHDService` permanece separado do `ArchiveService`.

`ArchiveService` trata ZIP/7Z/RAR. `CHDService` trata operações específicas de CHD e ferramentas como `chdman` quando apropriado.

## 6. Próximas etapas

1. validar catálogo/download Redump;
2. modelar `RedumpDisc`;
3. definir fontes de imagem aceitas;
4. implementar detecção de CUE/BIN/ISO e demais formatos necessários;
5. implementar CHD Builder;
6. implementar validação pós-criação;
7. fixtures reais de sistemas ópticos;
8. testes de áudio/múltiplas faixas.
