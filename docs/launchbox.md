# LaunchBox integration

LaunchBox é um **provider opcional de metadata**. O SERM não depende do LaunchBox para sua identidade ou persistência.

## Dados de interesse

A integração pode consultar estruturas como:

- `Metadata.db`;
- `Platforms.xml`;
- `MAME.xml`;
- `Files.xml`;
- outras fontes do ambiente LaunchBox quando suportadas pelo provider.

## Regra de autoridade

LaunchBox pode complementar nomes, IDs, plataformas, imagens e relações. Não substitui fontes authoritative de preservação nem o catálogo canônico do SERM.

## Auditoria

As ferramentas `audit_launchbox` e serviços associados existem para inspecionar conteúdo e compatibilidade. Auditoria não deve alterar o banco canônico sem uma etapa explícita de importação/normalização.

## Identidade

IDs e nomes LaunchBox devem ser tratados como identificadores externos. O SERM mantém sua própria identidade e pode criar mappings entre registros.
