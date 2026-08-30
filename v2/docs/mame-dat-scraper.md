# SERM V2 — MAME DAT / ListXML Scraper

## Objetivo

O SERM V2 deve obter os dados do MAME diretamente do executável instalado pelo usuário. A fonte primária é o próprio MAME, por meio de:

```text
mame.exe -listxml
```

O resultado é o XML oficial produzido pela versão instalada do MAME. No SERM, ele é tratado como a representação DAT/ListXML da fonte MAME.

## Snapshot e versionamento

Cada execução produz um **snapshot**. O banco não deve sobrescrever snapshots anteriores.

A identidade técnica do conteúdo é o SHA-256 do XML. A versão/build declarada pelo XML é armazenada separadamente como proveniência.

Comportamento:

| Situação | Comportamento |
|---|---|
| mesmo SHA-256 | reutilizar importação existente por padrão |
| mesmo build + SHA diferente | nova importação |
| build futura | nova importação, preservando nós desconhecidos |
| build antiga | nova importação, aceitando atributos ausentes |
| snapshots de builds diferentes | coexistem no mesmo banco |
| `force=True` | nova execução explícita do pipeline |

Assim, o banco pode conter MAME 0.289, 0.290, versões antigas e snapshots adicionais sem transformar um snapshot histórico em outro.

## Por que usar o executável

- evita depender de cópias externas potencialmente desatualizadas;
- garante que a versão dos dados corresponde ao executável usado para emulação;
- permite registrar a proveniência da informação;
- fornece dados reais para os próximos testes de catalogação, identidade e timing.

## API V2

Módulo:

```text
v2/serm_v2/emulation/mame_dat_scraper.py
```

Função principal:

```python
scrape_mame_dat(executable, timeout=120.0)
```

Ela:

1. valida o executável;
2. executa `mame -listxml` no diretório do executável;
3. captura stdout/stderr;
4. valida o XML;
5. conta os elementos `<machine>`;
6. devolve `MameDat` contendo executável, XML bruto e quantidade de máquinas.

O método `MameDat.write()` permite persistir o XML em disco.

## Proveniência

A versão/build do MAME é obtida do atributo `build` do ListXML no pipeline de persistência. O scraper não deve inferir versão pelo nome do arquivo.

A importação também registra o SHA-256 do conteúdo, caminho do snapshot RAW, executável, parser e data da ingestão.

## RAW e normalização

O XML é preservado em formato lossless em:

```text
 data/mame/listxml/listxml-<sha256-prefix>.xml
```

A normalização cria as entidades consultáveis do SERM. Elementos não conhecidos por uma versão do parser permanecem preservados na árvore RAW/XML e não devem bloquear a importação apenas por serem desconhecidos.

## Reimportação

Uma nova execução do mesmo MAME não deve duplicar máquinas se o XML produzido for idêntico.

A comparação é feita pelo conteúdo do XML, não apenas pela versão do MAME. Portanto:

```text
MAME build igual + XML igual    -> reutilização
MAME build igual + XML diferente -> novo snapshot
MAME build diferente            -> novo snapshot
```

## Versões futuras e antigas

O schema do banco e a versão do parser são independentes da versão do MAME.

Um ListXML futuro pode conter atributos ou elementos que o parser ainda não normaliza. Esses dados devem ser preservados pela camada lossless e podem ser promovidos ao modelo relacional posteriormente.

Um ListXML antigo pode não possuir campos introduzidos posteriormente. A ausência deve ser representada como dado ausente/NULL quando semanticamente apropriado, sem inventar valores e sem falhar por `NOT NULL` artificial.

## Fallbacks de configuração

Este scraper não substitui os arquivos legados de configuração de folders. Para os dados de resolução e refresh, a política V2 é:

```text
LISTXML
  ↓ se não houver informação suficiente
folders/resolution.ini
folders/Vsync.ini
  ↓
default do MAME
```

O banco deverá preservar a origem de cada valor relevante.

## Segurança operacional

O scraper não executa ROM, não inicia uma sessão de emulação e não aceita argumentos arbitrários de usuário. O único argumento de negócio desta primeira versão é o caminho do executável MAME.

## Log da GUI

A aba MAME do Scraper deve apresentar um log operacional detalhado, incluindo:

```text
START
executável validado
execução -listxml
versão/build
quantidade de máquinas
quantidade de displays
SHA-256
nova importação / reutilização / forçada
XML lossless
cópia compatível
banco
tempo total
DONE
```

Erros devem indicar claramente a causa e registrar que snapshots anteriores permanecem preservados quando a falha ocorre durante a ingestão.

## Próxima etapa

Depois do primeiro teste real com o executável MAME do ambiente do usuário, a saída será usada para implementar o parser de máquinas e a persistência na Data Foundation, incluindo resolução, refresh, orientação, pixel aspect, physical aspect e informações de tela disponíveis no ListXML.
