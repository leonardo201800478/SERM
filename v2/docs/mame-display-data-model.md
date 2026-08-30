# SERM V2 — MAME Display Data Model

## Fonte primária

`mame.exe -listxml` é a fonte primária para identidade e dados nativos do sistema. A documentação MAME 0.289 descreve `-listxml` como saída de detalhes abrangentes de sistemas e devices em XML. O DTD inclui `description`, `year`, `manufacturer`, `biosset`, `rom`, `disk`, `device_ref`, `sample`, `chip`, `display`, `sound`, `input`, `dipswitch`, `configuration`, `port`, `adjuster`, `driver`, `feature`, `device`, `slot`, `softwarelist` e `ramoption`. citeturn0search2

## Estratégia lossless

O SERM mantém duas camadas:

1. **Normalizada** — tabelas `mame_machine`, `mame_rom`, `mame_disk`, `mame_display`, etc., para consultas rápidas.
2. **Lossless** — `mame_xml_node`, que guarda cada elemento, texto e conjunto completo de atributos em JSON.

Portanto, se uma futura versão do MAME acrescentar um atributo que ainda não tenha uma coluna específica, o dado continua armazenado e pode ser normalizado posteriormente.

## Display

O elemento `display` fornece, entre outros, `tag`, `type`, `rotate`, `width`, `height`, `refresh`, `pixclock`, `htotal`, `hbend`, `hbstart`, `vtotal`, `vbend` e `vbstart`. Exemplos reais da saída MAME mostram `refresh` com várias casas decimais e `rotate` em 0/90/180/270. citeturn1search0turn1search9

**Importante:** pixel aspect não deve ser inventado a partir de `width/height`. `width/height` descrevem a área visível em pixels; pixel aspect e physical aspect são conceitos distintos. A documentação técnica do MAME trata explicitamente pixel aspect e physical aspect como propriedades distintas. citeturn0search3

Por isso o SERM mantém pixel aspect como campo separado e permite que venha de uma fonte externa/fallback.

## Fallback

Os arquivos externos são armazenados como fontes independentes:

```text
mame_display_source
        │
        └── mame_external_display_fact
```

A resolução é decidida **por campo**, com a regra:

```text
ListXML
   ↓ se ausente
resolution.ini / Vsync.ini
   ↓ se também ausente
missing
```

Não é permitido substituir silenciosamente um valor existente no ListXML.

A documentação do MAME também estabelece uma hierarquia de configuração entre linha de comando e arquivos INI; essa hierarquia será tratada separadamente do catálogo de fatos de display. citeturn0search11

## Machine Display Profile

O perfil materializado contém:

- machine;
- display;
- resolução efetiva;
- refresh efetivo;
- orientação;
- pixel aspect, quando conhecido;
- fonte de cada campo;
- indicação de fallback;
- status `resolved`, `partial` ou `missing`;
- versão do perfil;
- timestamp de geração.

## Validação planejada

O pipeline deve permitir verificar, nesta ordem:

1. quantidade total de `<machine>` do ListXML;
2. quantidade de sistemas executáveis, separada de devices;
3. quantidade de displays;
4. resolução por display;
5. refresh por display;
6. orientação;
7. pixel aspect quando disponível;
8. máquinas sem display/fato suficiente;
9. comparação ListXML × `resolution.ini`;
10. comparação ListXML × `Vsync.ini`;
11. precedência campo a campo;
12. geração de `Machine Display Profile`.

## Comando

Com o MAME selecionado em **Diretórios**:

```powershell
python -m serm_v2.services.mame_display_audit
```

Com fallbacks explícitos:

```powershell
python -m serm_v2.services.mame_display_audit --resolution "C:\caminho\resolution.ini" --vsync "C:\caminho\Vsync.ini"
```

O relatório JSON é a primeira evidência de integração do Timing Advisor com dados reais do MAME.
