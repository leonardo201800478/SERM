---
name: python-workspace-setup
description: 'Create or initialize a complete Python workspace in VS Code. Use when starting a Python-only project, scaffolding a distributable package, setting up src/tests layout, configuring a virtual environment, or validating an initial Python workspace.'
argument-hint: 'Describe the project name, target folder, and whether it should be a package or script.'
user-invocable: true
disable-model-invocation: false
---

# Python Workspace Setup

Create a small, usable Python package workspace with predictable structure, local project instructions, and an executable validation check.

## When to Use

- Starting a new Python-only project in VS Code.
- Creating a package intended to grow or be installed in editable mode.
- Setting up a `src/<package>` and `tests` layout.
- Recovering when a project template command completes without creating files.

Do not use this workflow for a one-off Python file; use a script-oriented setup instead.

## Procedure

1. Confirm the requested project name, destination folder, and whether the user wants a package or a single script. For an unspecified project type, choose a package only when the project is expected to grow or be distributed.
2. Read the workspace's local instructions before creating files. Preserve existing user changes and use the project's virtual environment for Python commands.
3. Create or open the workspace at the requested destination. Keep application code under `src/<package_name>` and tests under `tests`.
4. Install only the Python-related VS Code extensions required by the local setup guidance: `ms-python.python` and `ms-python.vscode-python-envs`.
5. Use the VS Code Python package template when available. Pass the explicit destination path if `.` produces an empty workspace.
6. Verify that scaffolding created files before proceeding. Check for `pyproject.toml`, `README.md`, the package module, and a test. A successful command with an empty directory is a failed scaffold.
7. If the template still produces no files, create the minimal package manually:
   - `pyproject.toml` with a PEP 621 project definition and setuptools build backend.
   - `src/<package_name>/__init__.py` with a version.
   - `tests/test_package.py` with a basic import/version check.
   - `README.md` with virtual-environment, editable-install, and test commands.
   - `.gitignore` for Python caches, virtual environments, test caches, and build metadata.
   - `.github/copilot-instructions.md` stating that the project is Python-only and defining `src` and `tests` locations.
8. Validate in the project virtual environment. First run compilation, then install the package with `python -m pip install -e .`, then run `python -m pytest -q`. If collection cannot import the package before installation, treat that as an environment/setup issue and rerun after the editable install.
9. Confirm the final files exist and report the validation result. Do not launch an application unless the user explicitly requests it.

## Completion Criteria

- The workspace folder is the requested destination and is open in VS Code.
- The project contains a valid Python package layout under `src` and tests under `tests`.
- `pyproject.toml` and `README.md` exist.
- `.github/copilot-instructions.md` exists with current project conventions.
- The package installs in editable mode and the initial test suite passes.
- Any fallback from template scaffolding is documented briefly in the completion report.
