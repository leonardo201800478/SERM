import subprocess
import re
import logging
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

# Configuração básica de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("mame_executable.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("MameExecutable")

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
        """Detecta a versão do MAME usando --version, -version, ou fallback."""
        path_exists = self.path.exists()
        if path_exists and not self.path.is_file():
            logger.error(f"Caminho não é um arquivo: {self.path}")
            raise ValueError(f"Path is not a file: {self.path}")

        # Tenta diferentes argumentos para obter versão
        args_list = [
            ["--version"],
            ["-version"],
            ["-help"],
            ["--help"]
        ]

        for args in args_list:
            cmd = [str(self.path)] + args
            logger.info(f"Tentando: {' '.join(cmd)}")
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10,
                    encoding='utf-8',
                    errors='ignore',
                    shell=False
                )
                logger.debug(f"Return code: {result.returncode}")
                logger.debug(f"STDOUT: {result.stdout[:200] if result.stdout else ''}...")
                logger.debug(f"STDERR: {result.stderr[:200] if result.stderr else ''}...")

                # Primeiro tenta extrair com padrão "MAME X.Y"
                match = re.search(r'MAME\s+([\d.]+)', result.stdout, re.IGNORECASE)
                if match:
                    self._version = match.group(1)
                    logger.info(f"Versão detectada via MAME X.Y: {self._version}")
                    return

                # Tenta padrão mais genérico: número com dois ou mais dígitos e pontos
                match = re.search(r'(\d+\.\d+(?:\.\d+)?)', result.stdout)
                if match:
                    self._version = match.group(1)
                    logger.info(f"Versão detectada via padrão genérico: {self._version}")
                    return

                # Se chegou aqui, pode ser que a saída contenha a versão de outra forma
                lines = result.stdout.splitlines()
                for line in lines:
                    if 'version' in line.lower() or 'mame' in line.lower():
                        # Tenta extrair números
                        nums = re.findall(r'\d+\.\d+(?:\.\d+)?', line)
                        if nums:
                            self._version = nums[0]
                            logger.info(f"Versão detectada via linha contendo 'version': {self._version}")
                            return

            except subprocess.TimeoutExpired:
                logger.warning(f"Timeout ao executar {' '.join(cmd)}")
                continue
            except Exception as e:
                logger.warning(f"Erro ao executar {' '.join(cmd)}: {e}")
                continue

        # Se nenhum método funcionou, tenta ler propriedades do arquivo (Windows)
        try:
            import win32api
            info = win32api.GetFileVersionInfo(str(self.path), "\\")
            ms = info['FileVersionMS']
            ls = info['FileVersionLS']
            version = f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"
            self._version = version
            logger.info(f"Versão obtida via GetFileVersionInfo: {self._version}")
            return
        except ImportError:
            logger.warning("win32api não disponível, pulando leitura de versão de arquivo.")
        except Exception as e:
            logger.warning(f"Erro ao ler versão do arquivo via win32api: {e}")

        # Fallback final: executa e vê se há alguma saída
        try:
            result = subprocess.run(
                [str(self.path)],
                capture_output=True,
                text=True,
                timeout=10,
                encoding='utf-8',
                errors='ignore',
                shell=False
            )
            # Verifica se a saída contém algo que pareça versão
            for line in result.stdout.splitlines() + result.stderr.splitlines():
                if 'mame' in line.lower() or 'version' in line.lower():
                    nums = re.findall(r'\d+\.\d+(?:\.\d+)?', line)
                    if nums:
                        self._version = nums[0]
                        logger.info(f"Versão detectada via saída geral: {self._version}")
                        return
        except Exception as e:
            logger.warning(f"Erro ao executar MAME sem argumentos: {e}")

        # Ausência do executável ou saída sem versão não impede o restante da
        # aplicação de tratar a instalação como desconhecida; operações que
        # realmente precisam do binário continuam validando o caminho.
        self._version = "unknown"
        logger.warning("Não foi possível detectar a versão do MAME. Definido como 'unknown'.")

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