import subprocess
import re
import logging
from contextlib import contextmanager  # <-- adicione esta linha
from pathlib import Path
from typing import Optional

logger = logging.getLogger("MameExecutable")
logger.setLevel(logging.WARNING)

class MameExecutable:
    def __init__(self, path: Path):
        self.path = path
        self._version = None
        logger.info(f"Inicializando MameExecutable com caminho: {path}")

    @property
    def version(self) -> Optional[str]:
        if self._version is None:
            self._detect_version()
        return self._version

    def _detect_version(self):
        """Detecta a versão do MAME silenciosamente."""
        if not self.path.is_file():
            self._version = "unknown"
            return

        # Tenta apenas o argumento -version (mais rápido e confiável)
        try:
            result = subprocess.run(
                [str(self.path), "-version"],
                capture_output=True,
                text=True,
                timeout=5,
                encoding='utf-8',
                errors='ignore',
                shell=False,
                check=False,
            )
            output = result.stdout.strip() or result.stderr.strip()
            if output:
                # Padrão: "MAME X.Y" ou somente número
                match = re.search(r'(?:MAME\s+)?([\d.]+)', output, re.IGNORECASE)
                if match:
                    self._version = match.group(1)
                    return
        except Exception:
            pass  # silencioso

        # Fallback: define como unknown sem logs
        self._version = "unknown"

    def get_listxml(self) -> str:
        """Executa mame -listxml e retorna o XML como string.

        Aviso: isto materializa o XML inteiro em memória (pode passar de
        100 MB em builds atuais do MAME). Para importar para o banco,
        prefira ``stream_listxml()``, que entrega o stdout do processo
        diretamente para um parser incremental (iterparse), sem nunca
        montar a string completa.
        """
        logger.info("Executando -listxml...")
        try:
            result = subprocess.run(
                [str(self.path), "-listxml"],
                capture_output=True,
                text=True,
                timeout=120,
                encoding='utf-8',
                errors='ignore',
                shell=False
            )
            if result.returncode != 0:
                logger.error(f"Erro ao executar -listxml: código {result.returncode}")
                logger.error(f"STDERR: {result.stderr}")
                raise RuntimeError(f"Error running listxml: {result.stderr}")
            logger.info("listxml obtido com sucesso.")
            return result.stdout
        except subprocess.TimeoutExpired:
            logger.error("Timeout ao executar -listxml.")
            raise RuntimeError("Timeout ao executar -listxml.")
        except Exception as e:
            logger.error(f"Erro ao executar -listxml: {e}")
            raise RuntimeError(f"Failed to get listxml: {e}")

    @contextmanager
    def stream_listxml(self):
        """Executa mame -listxml e expõe o stdout do processo para leitura incremental.

        Uso:
            with mame.stream_listxml() as stdout:
                for machine in iter_machines(stdout):
                    ...

        O XML nunca é materializado como string completa: o subprocesso
        escreve no pipe e o parser (iterparse) consome incrementalmente,
        o que mantém o uso de memória proporcional a UMA máquina por vez,
        não ao dataset inteiro.
        """
        logger.info("Iniciando -listxml em modo streaming...")
        process = subprocess.Popen(
            [str(self.path), "-listxml"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='ignore',
            bufsize=1,
            shell=False,
        )
        try:
            yield process.stdout
        finally:
            process.stdout.close()
            stderr_output = process.stderr.read() if process.stderr else ""
            process.stderr.close()
            returncode = process.wait(timeout=120)
            if returncode != 0:
                logger.error(f"-listxml terminou com código {returncode}: {stderr_output}")
                raise RuntimeError(f"Error running listxml: {stderr_output}")
            logger.info("listxml (streaming) concluído com sucesso.")