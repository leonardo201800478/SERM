# SERM V2 — MAME DAT / ListXML Scraper

## Objetivo

O SERM V2 deve obter os dados do MAME diretamente do executável instalado pelo usuário. A fonte primária é o próprio MAME, por meio de:

```text
mame.exe -listxml
```

O resultado é o XML oficial produzido pela versão instalada do MAME. No SERM, ele é tratado como a representação DAT/ListXML da fonte MAME.

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

A versão do MAME deve ser obtida posteriormente por uma camada própria de identificação do executável. O scraper não deve inferir versão pelo nome do arquivo.

O XML obtido deve permanecer associado à versão/fonte correspondente quando entrar na Data Foundation.

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

## Próxima etapa

Depois do primeiro teste real com o executável MAME do ambiente do usuário, a saída será usada para implementar o parser de máquinas e a persistência na Data Foundation, incluindo resolução, refresh, orientação, pixel aspect, physical aspect e informações de tela disponíveis no ListXML.
