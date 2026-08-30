# Prompt de continuidade — MAME Data Foundation

## Contexto

Estamos reconstruindo a V2 do SERM. A V1 deve ser consultada como referência funcional, mas a V2 deve manter arquitetura própria. O MAME instalado pelo usuário é externo ao armazenamento do SERM.

## Regras

- Usar o executável MAME explicitamente configurado em `Diretórios`.
- O diretório de instalação e o executável são propriedades distintas.
- Nunca assumir que `mame.exe` encontrado na pasta é o executável escolhido.
- Obter dados do próprio executável selecionado usando `-listxml`.
- ListXML é a fonte primária.
- `folders/resolution.ini` e `folders/Vsync.ini` são fallback apenas quando o ListXML não fornecer o dado.
- Preservar refresh com precisão, sem arredondamento para valores convencionais.
- Guardar resolução, orientação, pixel aspect e demais metadados necessários para geometria/artwork.
- Perfis SERM ficam fora da instalação do MAME.
- Não criar perfis NVIDIA/AMD por jogo.
- Não destruir, reformatar ou substituir arquivos nativos do MAME sem necessidade explícita.
- Qualquer escrita nativa futura deve preservar conteúdo não gerenciado, criar backup e usar escrita segura/atômica.
- Não misturar coleta de dados com RomScanner.

## Próximas etapas

1. Executar `mame.exe -listxml` e persistir o resultado como dado bruto/cache versionado.
2. Criar parser de máquinas com resolução, refresh, orientação, pixel aspect e proveniência.
3. Implementar fallback de `resolution.ini` e `Vsync.ini` somente para campos ausentes.
4. Criar Machine Display Profile no banco.
5. Criar Hardware Profile.
6. Criar Timing Advisor.
7. Criar geração de perfil SERM por sistema/máquina somente quando houver decisões persistíveis.

## Critério de qualidade

Toda implementação deve respeitar a semântica real do MAME e ser validada contra o executável configurado pelo usuário. Não substituir comportamento do MAME por heurísticas do SERM quando o próprio MAME já possuir a informação ou mecanismo adequado.
