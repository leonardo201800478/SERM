# MAME Support Files — fontes complementares

O SERM V2 mantém o Progetto-SNAPS como fonte primária quando o fluxo existente estiver configurado. O repositório `AntoPISA/MAME_SupportFiles` passa a ser uma fonte complementar e um fallback por arquivo.

## Política

1. **ListXML do MAME** continua sendo a fonte authoritative para máquinas, ROMs, discos, `cloneof`, `romof`, BIOS e devices.
2. **Progetto-SNAPS** continua sendo a fonte primária de suporte já integrada ao SERM.
3. **AntoPISA/MAME_SupportFiles** complementa o catálogo e oferece uma alternativa independente para aquisição dos INIs.
4. O SERM deve registrar a proveniência, hash, tamanho e versão/revisão de cada arquivo baixado.
5. Um arquivo obtido do fallback não deve sobrescrever silenciosamente a evidência proveniente da fonte primária; as duas fontes devem permanecer identificáveis.
6. O fallback ocorre por arquivo, não por pacote inteiro. Isso permite que um arquivo atualizado no Progetto-SNAPS continue usando a fonte primária enquanto outro arquivo seja obtido do GitHub.

## Arquivos inicialmente habilitados

- `category.ini`
- `catver.ini`
- `genre.ini`
- `bestgames.ini`
- `Working Arcade.ini`
- `Working Arcade Clean.ini`
- `Not Working Arcade.ini`
- `Parents Arcade.ini`
- `Clones Arcade.ini`
- `Bootlegs.ini`
- `Prototype.ini`
- `Mechanical Arcade.ini`
- `Non Mechanical Arcade.ini`
- `players.ini`
- `resolution.ini`
- `monochrome.ini`
- `driver.ini`
- `mess.ini`
- `CHD Working.ini`
- `CHD (no BIOS).ini`
- `screenless.ini`
- `artwork_necessary.ini`

A lista pode crescer sem alterar o contrato do catálogo.

## Atualização

O repositório de suporte identifica seu ciclo como MAME Support Files v0.289 e informa que diferentes pacotes podem ter ciclos de atualização diferentes. Portanto, o SERM não deve associar automaticamente a revisão do repositório a todos os arquivos.

## Links

- Fonte primária: https://www.progettosnaps.net/index.php
- Repositório alternativo: https://github.com/AntoPISA/MAME_SupportFiles
- Arquivos raw alternativos: https://raw.githubusercontent.com/AntoPISA/MAME_SupportFiles/main/
