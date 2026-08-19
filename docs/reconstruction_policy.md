# Política de reconstrução de ROMs MAME

## Objetivo

A reconstrução deve produzir o máximo possível de um set utilizável sem alterar as fontes. A classificação física do scanner e a classificação documental do MAME são tratadas separadamente.

## Estados documentais

| MAME | Significado | Ausente bloqueia? | Encontrado corretamente |
|---|---|---:|---|
| `good` | Dump considerado correto | Sim, se obrigatório | Mantém |
| `baddump` | Dump conhecido, mas com qualidade/limitações conhecidas | Sim, se obrigatório e ausente | **Mantém** |
| `nodump` | Não existe dump conhecido | Não | Caso excepcional; não inventar substituto |

`baddump` não significa que qualquer arquivo seja aceitável. O arquivo precisa corresponder aos identificadores conhecidos pelo LISTXML. O projeto deve preservar esse dump quando ele for a melhor evidência disponível.

## Optional

ROM marcada como `optional` pode ficar ausente sem tornar a máquina bloqueada. A opção `include_optional=False` permite removê-la deliberadamente da construção.

## Motivo exato

Toda decisão de ROM contém:

- `physical_status`: estado encontrado no filesystem/ZIP;
- `mame_dump_status`: `good`, `baddump` ou `nodump`;
- `action`: `keep`, `search`, `ignore` ou `block`;
- `executable`: se a ausência/condição permite declarar execução mínima;
- `blocking`: se impede a máquina de ser considerada pronta;
- `reason`: explicação textual exata.

Divergências de tamanho, CRC e SHA-1 são discriminadas individualmente quando os dados estão disponíveis.

## Construção

`ReconstructionOptions` possui controles independentes para:

- `include_clones`: incluir clones;
- `include_bios`: incluir sistemas/ROMs BIOS;
- `include_devices`: incluir device sets presentes no resultado do scan;
- `include_samples`: copiar sample sets referenciados pelo LISTXML;
- `include_optional`: incluir ROMs opcionais;
- `mode`: `split`, `merged` ou `non-merged`;
- `layout`: `single` ou `split`.

Samples são assets separados das ROMs e são procurados nas origens configuradas em `source_paths`, sendo gravados em `destination/samples`.

## Execução mínima

A reconstrução não aborta somente porque uma máquina está incompleta. Ela copia as ROMs que podem ser confirmadas, mantém `baddump` conhecidos quando corretos, ignora `nodump` ausente e opcionais ausentes, e registra bloqueadores no `reconstruction-manifest.json`.

Isso permite distinguir:

> "o set não está completo"

de:

> "não há dump conhecido para este requisito"

ou:

> "o dump conhecido é um `baddump`, mas é a melhor imagem disponível e corresponde ao XML".

## Relações MAME

Parent/clone, `merge`, BIOS e devices não são equivalentes. MAME procura recursos de um clone também no parent e em BIOS/device sets. A documentação oficial explica que parent/clone, BIOS e device sets são mecanismos diferentes e que uma máquina pode depender de ROMs de parent, BIOS e dispositivos. urlMAME — How does MAME look for files?https://docs.mamedev.org/usingmame/assetsearch.html

O modo `split` não duplica ROMs com `merge`; o modo `merged` pode concentrar os conteúdos no archive do parent. O modo `non-merged` mantém o objetivo de produzir conjuntos independentes.
