# Suíte de testes

Esta pasta contém somente testes relacionados à arquitetura atualmente suportada pelo projeto.

## Estrutura oficial

- `tests/` — testes unitários/funcionais ainda organizados por componente.
- `tests/unit/` — testes unitários isolados.
- `tests/integration/` — testes que exercitam mais de uma camada ou persistência.

A localização não define se um teste é atual ou legado. A regra é a implementação efetivamente utilizada pela aplicação.

## Política de legado

Um teste deve ser **removido** quando:

- cobre uma classe/API substituída;
- cobre apenas um shim de compatibilidade que não representa a arquitetura atual;
- está vazio ou não contém asserções executáveis;
- duplica uma cobertura que já existe na implementação atual sem acrescentar uma decisão arquitetural relevante.

Um teste deve ser **atualizado**, e não removido, quando a implementação continua sendo utilizada e apenas sua API mudou.

Não manter testes apenas para preservar compatibilidade com código abandonado.

## Estado consolidado

Removidos da suíte oficial:

- `tests/unit/test_listxml_parser.py` — antigo `ListXmlParser`, substituído pelo parser atual;
- `tests/unit/test_ini_parser.py` — arquivo vazio;
- `tests/integration/test_mame_integration.py` — arquivo vazio.

`tests/manual_merge_modes.py` não é uma suíte pytest; deve ser tratado como ferramenta manual/temporária e não como critério de aprovação da suíte automatizada.

## Comando oficial

```powershell
python -m pytest -v
```

O resultado desse comando deve ser interpretado somente em conjunto com esta política: testes novos devem proteger comportamento da arquitetura atual, e testes legados não devem ser reintroduzidos para fazer código novo obedecer APIs antigas.
