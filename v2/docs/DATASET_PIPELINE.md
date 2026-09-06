# Pipeline de dataset MAME

## Objetivo

A aplicação mantém uma base SQLite derivada do `mame -listxml` da versão ativa do MAME. A atualização da base agora é uma operação única:

1. gerar `mame_<versao>.xml` com `mame -listxml`;
2. importar o XML em streaming;
3. reconstruir as tabelas derivadas do catálogo;
4. importar `catver.ini` (`[Category]` e `[VerAdded]`);
5. localizar CHDs no `rompath`;
6. verificar CHDs com `chdman verify` quando o executável estiver disponível;
7. registrar a execução em `dataset_run`.

A origem de ROMs/CHDs é somente leitura.

## Base de dados

As tabelas derivadas do LISTXML são recriadas juntas. Perfis de filtro não são removidos. Além das entidades tradicionais (`machine`, `rom`, `disk`, `bios`, `device`, `chip`, `display`, `input`, `control`, `feature`, `software_list`, `slot` e `slot_option`), o pipeline mantém:

- `dataset_run`: histórico e estado da construção;
- `catver_entry`: categoria/subcategoria e versão adicionada;
- `chd_scan`: localização, tamanho e resultado de `chdman verify`;
- `rom_source_match`: reservado para o scanner físico de ROMs.

## Por que essa arquitetura

O MAME documenta que `-listxml` é uma fonte apropriada para ferramentas de gerenciamento de ROMs e descreve machines, ROMs e disks. O ClrMamePro separa scanner e rebuilder, usando dados do XML/DAT como catálogo. O scanner pode realizar verificação física por descompressão; o rebuilder trabalha por conteúdo/hash e tamanho. O projeto seguirá essa separação.

## Validação física de ROMs

A próxima etapa é o scanner de origem. O catálogo SQLite define o que é esperado; o scanner físico deverá ler cada membro de ZIP ou arquivo solto, calcular CRC32/SHA1/tamanho e gravar o resultado em `rom_source_match`. O CRC armazenado no diretório do ZIP nunca será tratado sozinho como prova de integridade.

## CHD

`chdman verify` é usado sem `--fix`. Isso é deliberado: o pipeline de catálogo não pode modificar a origem. O `info` também é coletado para registrar SHA1 do CHD quando disponível.

## Reconstrução

A Reconstrução continuará separada do catálogo. O fluxo futuro é:

`catálogo esperado -> índice físico -> matching por CRC+size/SHA1 -> staging -> limpeza/renomeação -> validação -> ZIP temporário -> validação final -> destino`.

O destino nunca deve ser considerado concluído apenas porque um ZIP foi criado; cada conteúdo deve ser validado antes da substituição atômica.
