# SERM V2 — Ambiente de desenvolvimento

## Escopo

A V2 deve ser trabalhada como um projeto Python independente dentro do diretório `v2/`.

No VS Code, a recomendação é abrir **`SERM/v2` como a pasta do workspace**, e não a raiz histórica do repositório. Isso reduz descoberta acidental de módulos da V1 e mantém comandos, testes e configurações relativos à V2.

## Windows + VS Code

### 1. Criar o ambiente virtual

No terminal PowerShell aberto em `v2/`:

```powershell
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

### 4. Selecionar o interpretador no VS Code

Selecionar:

```text
v2\.venv\Scripts\python.exe
```

O workspace já contém `settings.json` apontando para esse caminho.

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
- dados de usuário ficam fora do repositório, preferencialmente em `%LOCALAPPDATA%\SERM`;
- V1 não deve ser adicionada ao `PYTHONPATH` da V2;
- testes V2 devem importar exclusivamente `serm_v2`.

## Organização de dependências

`pyproject.toml` é a única fonte de declaração das dependências da V2.

- `[project].dependencies`: dependências necessárias para executar a aplicação;
- `[project.optional-dependencies].dev`: ferramentas de desenvolvimento e testes;
- não criar `requirements.txt` paralelo sem uma necessidade concreta de distribuição/deploy.

## Por que não usar um segundo `requirements.txt` agora?

Manter dependências em `pyproject.toml` evita duas fontes de verdade. O arquivo também concentra configuração do build, pytest e Ruff, seguindo o modelo atual de `pyproject.toml` da comunidade Python.

## Fluxo recomendado no VS Code

```text
Abrir SERM/v2
      ↓
Selecionar .venv/Scripts/python.exe
      ↓
Instalar .[dev]
      ↓
Testes
      ↓
Ruff check
      ↓
Ruff format
      ↓
Executar/debugar SERM V2
```

A configuração do workspace foi criada para que testes e depuração sejam descobertos diretamente pelo VS Code.
