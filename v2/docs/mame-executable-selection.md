# MAME — Executável e diretório de instalação

## Regra V2

O SERM trata **diretório de instalação** e **executável ativo** como propriedades distintas.

- `mame` / diretório de instalação: base para caminhos relativos dos arquivos de configuração e demais recursos do MAME.
- `mame_executable`: binário exato que o usuário escolheu para execução de comandos do SERM, como detecção de versão e `-listxml`.

Isso é necessário porque um computador pode possuir várias versões do MAME, inclusive múltiplos `mame.exe` dentro de instalações diferentes ou de cópias preservadas.

## Persistência

O caminho do executável é armazenado em:

```text
emulator_paths.json
```

com a chave:

```json
{
  "mame": "G:\\LaunchBox\\emulators\\mame",
  "mame_executable": "G:\\LaunchBox\\emulators\\mame\\mame.exe"
}
```

A seleção do executável não altera `mame.ini` nem qualquer configuração nativa do MAME.

## Uso no DAT/ListXML

A função `scrape_mame_dat()` recebe explicitamente o executável selecionado e executa:

```text
mame.exe -listxml
```

A documentação oficial do MAME 0.289 define `-listxml` como o verbo que produz detalhes abrangentes dos sistemas suportados em XML, sendo apropriado para frontends e ferramentas que precisam processar esses dados. citeturn0search0turn0search12

## Segurança operacional

A troca do executável:

1. não modifica arquivos de configuração do MAME;
2. valida se o caminho aponta para um arquivo `.exe` existente;
3. consulta `-noreadconfig -version` para apresentar uma confirmação ao usuário;
4. mantém o diretório de instalação separado;
5. permite preservar múltiplas versões do MAME sem sobrescrever nenhuma delas.

O comportamento também evita assumir que o primeiro `mame.exe` encontrado no diretório é necessariamente o binário que o usuário deseja utilizar.
