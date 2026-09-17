# Preferências de interface — SERM V2

A V2 possui preferências persistentes para:

- **Tema:** modo escuro e modo claro.
- **Idioma:** Português (Brasil), English e Español.

As preferências são armazenadas com `QSettings` em `SERM / SERM V2`, portanto não ficam misturadas aos dados do catálogo, scans ou perfis de filtros.

## Localização

As opções ficam em:

**Configuração → Aparência e Idioma**

O tema é aplicado imediatamente. O idioma possui um catálogo central e tradução runtime reversível, permitindo trocar entre os idiomas sem perder o texto-fonte dos widgets.

## Estratégia de tradução

A infraestrutura está em `serm_v2/gui/ui_preferences.py` e `serm_v2/gui/ui_translation.py`, com aplicação reversível em `serm_v2/gui/ui_translation_runtime.py`.

O catálogo deve ser ampliado à medida que cada superfície da V2 for migrada para o novo design system. Textos técnicos — nomes de arquivos, ROMs, drivers, máquinas, hashes e valores do pipeline — não devem ser traduzidos.
