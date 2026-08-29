# SERM V2 — Ambiente de desenvolvimento

## Escopo

A V2 é o projeto Python ativo dentro do diretório `v2/`.

O **workspace recomendado do VS Code é a raiz `SERM/`**. A configuração do workspace aponta automaticamente para `v2/.venv`, inicia novos terminais em `v2/` e direciona o pytest para `v2/tests`. Isso permite manter a V1 visível para pesquisa sem permitir que ela seja tratada como o projeto Python ativo.

O arquivo `SERM.code-workspace` pode ser aberto diretamente no VS Code.

## Windows + VS Code

### 1. Criar o ambiente virtual

No terminal PowerShell aberto em `v2/`:

```powershell
cd .\v2
py -3.14 -m venv .venv
```

Se outra versão suportada de Python estiver sendo usada, o comando deve apontar explicitamente para ela.

### 2. Ativar o ambiente

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Instalar a V2 em modo editável

```powershell
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

A instalação editável faz com que `serm_v2` seja importável pelo mesmo ambiente usado pelo VS Code.

### 4. Selecionar o interpretador

O workspace já aponta para:

```text
v2\.venv\Scripts\python.exe
```

O interpretador selecionado pelo VS Code é usado para IntelliSense, lint, testes, execução e depuração.

## Comandos oficiais de desenvolvimento

Todos os comandos abaixo devem ser executados a partir de `v2/`.

### Executar a aplicação

```powershell
python -m serm_v2
```

ou:

```powershell
python -m serm_v2.main
```

Depois da instalação editável, o entry point também estará disponível:

```powershell
serm
```

### Testes

```powershell
python -m pytest
```

Teste específico:

```powershell
python -m pytest tests/test_bootstrap.py
```

### Lint

```powershell
ruff check .
```

### Formatação

```powershell
ruff format .
```

### Verificação de formatação sem modificar arquivos

```powershell
ruff format --check .
```

### Cobertura

```powershell
python -m pytest --cov=serm_v2 --cov-report=term-missing
```

## Regras de ambiente

- `.venv/` nunca é versionado;
- banco SQLite de desenvolvimento nunca é versionado;
- logs e caches nunca são versionados;
- configurações locais e segredos nunca são versionados;
- arquivos JSON/XML/CFG/INI que sejam **fontes reais do projeto** podem ser versionados;
- dados operacionais locais ficam em `v2/data/` e são ignorados pelo Git;
- V1 não deve ser adicionada ao `PYTHONPATH` da V2;
- testes V2 devem importar exclusivamente `serm_v2`.

## Organização de dependências

`v2/pyproject.toml` é a fonte de declaração das dependências da V2.

- `[project].dependencies`: dependências necessárias para executar a aplicação;
- `[project.optional-dependencies].dev`: ferramentas de desenvolvimento e testes;
- não criar `requirements.txt` paralelo sem uma necessidade concreta de distribuição/deploy.

## Fluxo recomendado no VS Code

```text
Abrir SERM.code-workspace
      ↓
VS Code seleciona v2/.venv
      ↓
Terminal inicia em v2/
      ↓
Instalar .[dev]
      ↓
Testes
      ↓
Ruff check
      ↓
Ruff format --check
      ↓
Executar/debugar SERM V2
```
