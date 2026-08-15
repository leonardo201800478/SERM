# Arquitetura recomendada para scan e reconstrução de sets MAME

## Conclusão executiva

A fonte estrutural mais confiável é o `-listxml` gerado pelo **mesmo executável e mesma versão do MAME** que será usada para o set. O arquivo SQLite é mais rápido para filtros, consultas repetidas e perfis, mas somente pode substituir o XML depois que o importador persistir todos os nós estruturais necessários. No estado auditado, o projeto ainda não armazenava `device_ref`, `sample`, `chip`, `display`, `sound`, `input`, `dipswitch`, `configuration`, `port`, `adjuster`, `feature`, `device`, `slot`, `softwarelist` e `ramoption`; portanto, um XML reconstruído a partir desse banco não seria plenamente fiel.

O caminho implementado usa o XML como fonte de verdade, filtra em streaming e copia o subtree completo de cada `<machine>`. O SQLite continua sendo o índice de filtros. Cada dataset deve registrar versão, `build`, caminho do executável, SHA-256 do executável e fingerprint do XML; datasets de versões diferentes não devem ser mesclados.

## XML ou banco de dados

| Critério | `listxml` filtrado | SQLite completo |
|---|---|---|
| Fidelidade estrutural | Máxima, se o subtree original for preservado | Máxima somente se todos os elementos/atributos forem armazenados |
| Primeira importação | Mais lenta, pois exige parse XML | Não aplicável sem importação prévia |
| Filtros repetidos | Mais lenta | Mais rápida, com índices |
| Uso de memória | Streaming: proporcional a uma máquina | Baixo durante consultas |
| Risco de incompatibilidade | Baixo quando vinculado à versão do MAME | Alto se o schema estiver incompleto ou misturar versões |
| Recomendação | Fonte de verdade e exportação | Índice derivado, com fingerprint e versionamento |

A documentação oficial descreve `-listxml` como saída abrangente de sistemas e dispositivos e mostra que uma máquina pode conter ROMs, discos, referências de dispositivos, listas de software, slots, opções de RAM e outros elementos [1]. Por isso, o exportador não deve reconstruir nós a partir de um modelo reduzido; deve copiar o subtree original da máquina selecionada.

## CRC32 versus SHA-1

O CRC32 é muito rápido e já é o identificador tradicional das ROMs MAME. Ele é adequado para uma primeira comparação, mas não deve ser a única verificação quando o XML fornece SHA-1. SHA-1 também é legado criptograficamente, porém continua sendo o digest de referência de muitos artefatos MAME; sua finalidade aqui é validação de identidade do arquivo, não autenticação contra um atacante. A implementação consulta tamanho, CRC e SHA-1 quando disponíveis.

| Política | Velocidade | Segurança operacional | Uso indicado |
|---|---:|---:|---|
| Tamanho + CRC32 | Mais alta | Boa contra erro acidental comum, não suficiente como confirmação única | Triagem rápida |
| Tamanho + SHA-1 | Alta | Melhor identificação, mas exige leitura completa | Confirmação quando XML só tem SHA-1 |
| Tamanho + CRC32 + SHA-1 | Menor entre as opções | Mais segura contra corrupção e colisões acidentais | Resultado final e reconstrução |

Como o Python libera o GIL durante atualizações de hash maiores que 2047 bytes, o cálculo pode usar threads, embora o gargalo de sets grandes normalmente seja leitura, descompressão e latência do disco [2]. A implementação lê em blocos de 1 MiB por padrão e nunca carrega uma ROM inteira em RAM. Para ZIP, o scanner usa a leitura do membro e o CRC interno do formato como camada adicional; depois compara com o CRC/SHA-1 do XML [3].

## Paralelismo e AVX2

Não é recomendável tentar “forçar AVX2” diretamente em Python. `hashlib` delega o SHA-1 ao OpenSSL disponível no sistema, e o ganho efetivo depende da biblioteca nativa, do armazenamento e da descompressão. Para ROMs pequenas, aumentar muito o número de workers piora o desempenho por contenção de I/O. O scanner usa `ThreadPoolExecutor`, com limite padrão de até 16 workers e ajuste configurável.

Uma configuração prática é usar 2–4 workers por disco físico, medir throughput e elevar gradualmente. Em NVMe, 4–8 workers costuma ser um ponto de partida razoável; em HDD, 1–3 frequentemente é melhor. O teste correto deve medir MiB/s, IOPS, tempo por arquivo, taxa de cache hit e temperatura/uso do dispositivo, não apenas percentual de CPU.

## Cache e congestionamento de disco

A melhor cache inicial não é uma cópia dos dados das ROMs. Ela é um cache de **metadados**: caminho, tamanho, `mtime_ns`, CRC, SHA-1 e resultado da validação. Quando tamanho e `mtime_ns` não mudaram, o digest pode ser reutilizado. Isso reduz leituras repetidas sem duplicar dezenas ou centenas de gigabytes.

| Local | Benefício | Risco | Recomendação |
|---|---|---|---|
| RAM | Muito rápido | Pode pressionar a memória | Guardar apenas metadados e limitar por quantidade |
| SSD principal | Persistente e rápido | Ocupa espaço e gera escrita | Usar SQLite/JSON de metadados, não cópia integral |
| Disco de origem | Evita duplicação | Congestiona a origem | Não usar como cache de trabalho |
| Destino | Mistura cache com resultado | Pode contaminar o set final | Não usar |

O uso de arquivos temporários deve ser limitado ao necessário. Para 7Z, o backend opcional atual extrai temporariamente somente membros pequenos, com limite de 64 MiB, e remove o temporário automaticamente. Para membros maiores, o resultado é explicitamente não validado até existir um backend de streaming adequado; isso é preferível a estourar a RAM silenciosamente.

## Reconstrução segura

O FULLSET deve ser somente leitura. A reconstrução trabalha em outro destino, copia somente itens validados, grava primeiro em `arquivo.partial`, chama `fsync` e então renomeia atomicamente para o nome final. Ao final, grava `reconstruction-manifest.json` com origem, destino e estado de cada arquivo. Se uma cópia falhar, o parcial é removido e a origem permanece intacta.

A GUI agora permite até três diretórios de origem independentes de `mame.ini`, além de destino e dois layouts: uma pasta única ou a divisão `Roms`, `CHD`, `Devices` e `Bios`. O núcleo já usa a pasta `Roms` para ROMs validadas; a classificação completa de CHD, BIOS e dispositivos depende de o scanner de discos e o importador estrutural passarem a transportar esses tipos até o resultado de reconstrução.

## Relatório de ausentes e corrompidos

O método `generate_missing_xml` seleciona as máquinas cujo resultado contém ROMs ausentes, corrompidas, indisponíveis ou corrigíveis e gera um XML válido com a máquina completa. Esse XML pode alimentar uma etapa posterior de aquisição autorizada. A aplicação não deve baixar nem executar conteúdo de torrent automaticamente sem confirmação explícita, validação de origem e checagem posterior de hashes.

## Antivírus

Não é seguro nem apropriado tentar ocultar o processo de antivírus. A abordagem correta é reduzir falsos positivos sem evasão: usar diretórios de trabalho previsíveis, temporários com extensão `.partial`, operações atômicas, logs claros, permissões mínimas e exclusões configuradas pelo próprio usuário ou administrador quando a política do sistema permitir. Arquivos obtidos de fontes externas devem ser tratados como não confiáveis até passarem por validação de formato, tamanho e hashes.

## Estado da implementação

Foram implementados `app/mame/integrity.py`, scanner concorrente para arquivos soltos/ZIP/7Z opcional, fallback após candidato corrompido, SHA-1 real no resultado, exportação XML em streaming, configuração persistente, controles de três origens/destino/layout na aba de scan e reconstrução atômica com manifesto. A suíte existente foi executada integralmente: **24 testes passaram** e a compilação dos módulos foi concluída sem erro.

## Referências

[1]: https://docs.mamedev.org/commandline/commandline-all.html "MAME — Universal Command-line Options"
[2]: https://docs.python.org/3/library/hashlib.html "Python hashlib documentation"
[3]: https://docs.python.org/3/library/zipfile.html "Python zipfile documentation"

## Classificação visual do Scanner e modos de reconstrução

A classificação da máquina agora segue uma precedência determinística. **Preto (`CORRUPTED`)** significa que foi encontrado um candidato físico, mas seu conteúdo está corrompido, inválido ou não pôde ser identificado com segurança. **Vermelho (`UNAVAILABLE`)** significa que existe pelo menos uma ROM necessária ausente e não há uma rota de reconstrução disponível com as fontes atuais. **Amarelo (`FIXABLE`)** significa que todas as pendências podem ser resolvidas por renomeação, uso de outro nome interno ou compartilhamento de uma ROM válida encontrada em outro set. **Cinza (`MISSING`)** significa que nenhum item físico da máquina foi localizado; não há evidência de arquivo para reconstruir naquele momento. A ordem de prioridade é preto, verde, amarelo, cinza e vermelho para os casos combinados, com vermelho representando ausência parcial não resolvível.

A implementação tenta primeiro o arquivo esperado no ZIP/7Z ou como arquivo solto. Se não encontrar uma cópia válida, faz uma segunda busca nos ZIPs das fontes: o tamanho e o CRC do diretório central fazem a triagem e o SHA-1 confirma o conteúdo quando presente. Quando o mesmo conteúdo é encontrado em outro set ou com outro nome interno, o item recebe estado amarelo e guarda `found_member`, permitindo escrever o nome exigido pelo XML no destino.

| Modo | Resultado |
|---|---|
| **Split** | O arquivo do pai contém seus próprios dados; o clone contém apenas dados específicos. ROMs com atributo `merge` são deixadas para o pai. |
| **Non-merged** | Cada jogo recebe um ZIP autossuficiente, incluindo também ROMs compartilhadas pelo pai quando forem necessárias ao clone. |
| **Merged** | O ZIP do pai recebe os dados do pai e dos clones relacionados, deduplicados pelo nome interno. |

A documentação oficial do MAME define non-merged como um ZIP autossuficiente, split como pai com dados normais e clones apenas com alterações, e merged como pai e clones armazenados juntos [4]. O construtor grava membros em fluxo, com ZIP64 habilitado, sem alterar os arquivos de origem. CHDs continuam sendo tratados separadamente porque não devem ser colocados dentro de ZIP/7Z: a própria documentação do MAME recomenda armazená-los como arquivos CHD independentes [4].

[4]: https://docs.mamedev.org/usingmame/aboutromsets.html "MAME — About ROMs and Sets"
