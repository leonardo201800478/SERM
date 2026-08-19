"""Execução isolada de testes rápidos de HLSL/GLSL no MAME.

O teste nunca altera o mame.ini original. Uma cópia temporária é criada e as
opções atualmente presentes na interface são aplicadas nessa cópia antes de
iniciar o executável do MAME.
"""
from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from app.mame.mame_ini_editor import MameIniEditor


class MameShaderTestRunner:
    """Executa uma instância temporária do MAME para validar shaders."""

    def __init__(self, mame_executable: Path, ini_path: Path):
        self.mame_executable = Path(mame_executable)
        self.ini_path = Path(ini_path)
        self.process: subprocess.Popen | None = None
        self._temp_dir: Path | None = None

    @property
    def running(self) -> bool:
        """Indica se a instância de teste ainda está em execução."""
        return self.process is not None and self.process.poll() is None

    def start(self, machine: str, values: dict[str, str], seconds: int = 30) -> None:
        """Cria um INI temporário e inicia o MAME com as configurações atuais."""
        if self.running:
            raise RuntimeError("Já existe um teste de shader em execução.")
        machine = machine.strip()
        if not machine:
            raise ValueError("Informe o short name de uma machine para testar.")
        if not self.mame_executable.is_file():
            raise FileNotFoundError(f"Executável do MAME não encontrado: {self.mame_executable}")
        if not self.ini_path.is_file():
            raise FileNotFoundError(f"mame.ini não encontrado: {self.ini_path}")

        self._temp_dir = Path(tempfile.mkdtemp(prefix="mame_shader_test_"))
        temp_ini = self._temp_dir / "mame.ini"
        shutil.copy2(self.ini_path, temp_ini)
        editor = MameIniEditor(temp_ini)
        editor.set_many(values)
        editor.save(create_backup=False)

        # O MAME recebe o diretório temporário como inipath, mas os caminhos
        # já existentes no INI continuam sendo preservados sem modificar a
        # instalação original.
        command = [
            str(self.mame_executable),
            machine,
            "-inipath",
            str(self._temp_dir),
            "-seconds_to_run",
            str(max(1, int(seconds))),
        ]
        self.process = subprocess.Popen(
            command,
            cwd=str(self.mame_executable.parent),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def stop(self) -> None:
        """Encerra o teste e remove o diretório temporário."""
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        self.process = None
        self._cleanup()

    def poll(self) -> int | None:
        """Atualiza o estado e retorna o código de saída quando finalizado."""
        if self.process is None:
            return None
        code = self.process.poll()
        if code is not None:
            self.process = None
            self._cleanup()
        return code

    def _cleanup(self) -> None:
        """Remove arquivos temporários depois que o processo termina."""
        if self._temp_dir is not None:
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None
