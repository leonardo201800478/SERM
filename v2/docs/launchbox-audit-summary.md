# LaunchBox — Auditoria e decisão de modelagem

**Estado:** procedimento validado; análise quantitativa da instalação do usuário depende do `launchbox-audit.json` gerado localmente.

## Fonte real

A V2 consegue abrir `LaunchBox.Metadata.db` em modo somente leitura e ler `Platforms.xml`. O relatório é gerado em `v2/data/exports/launchbox-audit.json`.

## Decisão

O banco LaunchBox não será usado como banco operacional do SERM. Seus dados serão tratados como provider externo.

```text
LaunchBox
   ↓
Provider
   ↓
modelo intermediário
   ↓
normalização
   ↓
SERM Data Foundation
```

## Dados potencialmente reutilizáveis

As estruturas já conhecidas são úteis para comparação:

- Games;
- Platforms;
- Emulators;
- EmulatorPlatforms;
- GameAlternateTitles;
- GameImages;
- PlatformAlternateNames.

Essas estruturas ajudam a validar o domínio, mas não serão copiadas 1:1.

## Critérios de importação

Cada campo será classificado como:

1. **Canônico** — deve existir no modelo SERM e ter relacionamento próprio;
2. **Normalizável** — entra após transformação;
3. **Provider-only** — permanece apenas no adapter LaunchBox;
4. **Origem** — preservado como payload/proveniência;
5. **Redundante** — não armazenado no SERM.

## Regra de segurança

Nenhuma importação automática para o banco SERM deve ser ativada antes de fechar o modelo, cardinalidades e regras de proveniência.

O arquivo de auditoria local não é versionado e pode conter caminhos da instalação do usuário.

## Próximo passo

Após obter o relatório real, comparar quantitativamente tabelas, preenchimento de colunas, índices, aliases e cardinalidades com `data-model-v2-detailed.md` e produzir a especificação do schema físico V2.
