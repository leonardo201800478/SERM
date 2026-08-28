# Suíte de testes

A suíte `tests/` valida somente componentes que fazem parte da arquitetura atual do projeto.

## Regra

Um teste deve permanecer aqui somente se testar uma implementação atualmente utilizada pela aplicação. Testes de APIs, classes ou fluxos substituídos devem ser removidos ou migrados para a implementação atual.

Compatibilidade retroativa (`shim`) não é motivo suficiente para manter um teste legado na suíte oficial.

## Organização

- `tests/`: testes unitários e de integração dos componentes atuais.
- `tests/integration/`: testes de integração que exercitam componentes atuais em conjunto.
- `tests/unit/`: testes unitários dos componentes atuais.

Não existe uma categoria especial de teste que seja considerada oficial apenas pelo diretório. A referência é a arquitetura atual do código.

## Comando oficial

```powershell
python -m pytest -v
```

Antes de remover um teste, verificar se a implementação coberta ainda é usada pela aplicação. Se for, atualizar o teste para a API atual em vez de removê-lo.
