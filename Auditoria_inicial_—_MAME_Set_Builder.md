# Auditoria inicial — MAME Set Builder

## Estado observado

- Repositório Python/PySide6 com SQLite, parser streaming de `-listxml` e abas de diretórios, filtros e scan.
- O parser `app/mame/listxml_parser.py` preserva apenas `Machine`, `Rom` e `Disk` parcialmente. Ele lê atributos principais da máquina, ROMs e discos, mas descarta `device_ref`, `sample`, `chip`, `display`, `sound`, `input`, `dipswitch`, `configuration`, `port`, `adjuster`, `feature`, `device`, `slot`, `softwarelist` e `ramoption`.
- `ListxmlExportService` usa `ET.fromstring` para materializar o XML, tem referência a `ET` sem import explícito no arquivo auditado, e reconstrói apenas os nós `<machine>` selecionados. Para fidelidade plena, deve filtrar/reemitir os subtrees originais de um XML validado, sem normalizar ou perder elementos.
- O importador `DatabaseService` persiste apenas máquinas, ROMs e discos. Apesar do esquema prever tabelas para entidades adicionais, elas não são preenchidas. Há divergência potencial entre `disk.idx` no importador e `disk.index` no schema citado pela documentação.
- `RomScanner` é serial, percorre máquina por máquina e ROM por ROM, usa `read()` do conteúdo inteiro em memória, só implementa ZIP e arquivo avulso, não implementa 7Z nem CHD, não calcula SHA-1 e aceita a primeira ocorrência mesmo quando ela está corrompida, sem continuar procurando outra fonte válida.
- `RomScanService` usa `ET.parse`/DOM e materializa todas as máquinas; não é streaming e não inclui discos no resultado do scanner.
- `DirectoriesTab` e rotinas de CHD dependem diretamente de `mame.ini`/`rompath`; não há configuração persistente de até três origens independentes, destino da reconstrução, modo de pasta única ou subpastas, nem cache controlada.
- O schema e os modelos indicam intenção de suportar mais entidades, mas a implementação atual ainda não entrega reconstrução fiel do set.

## Referências técnicas consultadas

1. A documentação oficial do MAME descreve `-listxml` como saída XML abrangente de sistemas e dispositivos, destinada a front-ends e scripts, e mostra que cada `<machine>` pode conter, entre outros, `rom`, `disk`, `device_ref`, `sample`, `chip`, `display`, `sound`, `input`, `dipswitch`, `configuration`, `port`, `adjuster`, `driver`, `feature`, `device`, `slot`, `softwarelist` e `ramoption`: https://docs.mamedev.org/commandline/commandline-all.html
2. A documentação Python informa que `hashlib` fornece SHA-1 e hashes modernos; o GIL é liberado em atualizações maiores que 2047 bytes, permitindo paralelismo em partes do cálculo, embora o gargalo prático seja frequentemente I/O: https://docs.python.org/3/library/hashlib.html
3. A documentação Python de `zipfile` confirma suporte a ZIP64, leitura de ZIP e exceção `BadZipFile`; a implementação atual deve usar leitura em blocos, `testzip()`/CRC do membro e validação MAME separada: https://docs.python.org/3/library/zipfile.html

## Direção preliminar

- Fonte estrutural preferencial: XML oficial gerado pela mesma versão do executável MAME. Um `.db` é mais rápido para filtros e consultas repetidas, mas não deve ser a única fonte de verdade enquanto não guardar todos os elementos e o fingerprint do dataset.
- Verificação em camadas: tamanho e CRC para triagem; SHA-1 quando presente no XML para confirmação final; CHD por SHA-1 de dados/validação compatível com `chdman`, sem tratar o tamanho físico do arquivo como hash do conteúdo.
- Reconstrução segura: nunca alterar o FULLSET; copiar para arquivo temporário no mesmo volume, `fsync`, renomear atomicamente, validar o destino e gravar manifest/log transacional. Um arquivo corrompido em uma fonte deve ser marcado e não impedir procura nas demais fontes.
- Concorrência deve ser limitada por I/O e por dispositivo, com filas de tarefas, cache de metadados por `(path, size, mtime_ns)` e número de workers configurável; evitar alegar ou depender de AVX2 diretamente em Python.
- Não implementar evasão de antivírus. Em vez disso, reduzir falsos positivos com diretórios de trabalho explícitos, operações temporárias seguras, exclusões configuradas pelo usuário/administrador e assinatura/whitelist legítima quando aplicável.
