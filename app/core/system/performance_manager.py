"""Scheduler adaptativo para tarefas CPU-bound do projeto.

A regra principal é simples: leitura física de ROM continua conservadora; tarefas
que já possuem todos os dados em memória podem usar processos/interpretadores
independentes. Nenhum worker recebe uma conexão SQLite compartilhada.
"""
from __future__ import annotations

import logging
import multiprocessing
import os
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from typing import Callable, Iterable, TypeVar

from .hardware_detector import HardwareDetector, HardwareProfile

logger = logging.getLogger(__name__)
T = TypeVar("T")
R = TypeVar("R")


def _run_one(function: Callable[[T], R], value: T) -> R:
    """Executa uma tarefa top-level no processo filho."""
    return function(value)


class PerformanceManager:
    """Seleciona paralelismo com base no hardware disponível."""

    def __init__(self, profile: HardwareProfile | None = None) -> None:
        self.profile = profile or HardwareDetector.detect()

    @classmethod
    def detect(cls) -> "PerformanceManager":
        """Cria um scheduler usando o hardware detectado no momento."""
        return cls(HardwareDetector.detect())

    def describe(self) -> str:
        """Retorna um resumo apropriado para o log da aplicação."""
        ram_gb = self.profile.ram_total_bytes / 1024**3 if self.profile.ram_total_bytes else 0
        return (
            f"CPU={self.profile.cpu}; cores={self.profile.physical_cores}/{self.profile.logical_cores}; "
            f"RAM={ram_gb:.1f}GB; SIMD=[{self.profile.simd_summary}]; "
            f"cpu_workers={self.profile.recommended_cpu_workers}; "
            f"io_workers={self.profile.recommended_io_workers}; batch={self.profile.recommended_batch_size}"
        )

    def cpu_workers(self, requested: int | None = None) -> int:
        """Calcula workers CPU sem ultrapassar o limite recomendado."""
        if requested is None or requested <= 0:
            return self.profile.recommended_cpu_workers
        return max(1, min(int(requested), self.profile.logical_cores))

    def map_cpu(self, function: Callable[[T], R], values: Iterable[T], *, workers: int | None = None, chunksize: int = 32) -> list[R]:
        """Executa tarefas independentes em processos, preservando a ordem.

        A função e seus argumentos precisam ser serializáveis por pickle. A
        implementação usa ``spawn`` explicitamente, importante no Windows e
        seguro para uma aplicação Qt que já possui threads.
        """
        items = list(values)
        if not items:
            return []
        count = self.cpu_workers(workers)
        if count <= 1 or len(items) < 2:
            return [function(item) for item in items]
        logger.info("CPU parallel stage: %d tarefas, %d processos, chunksize=%d", len(items), count, chunksize)
        context = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(max_workers=count, mp_context=context) as executor:
            return list(executor.map(function, items, chunksize=max(1, chunksize)))

    def map_io(self, function: Callable[[T], R], values: Iterable[T], *, workers: int | None = None) -> list[R]:
        """Executa tarefas predominantemente de I/O com threads limitadas."""
        items = list(values)
        if not items:
            return []
        count = max(1, min(workers or self.profile.recommended_io_workers, self.profile.recommended_io_workers))
        if count <= 1 or len(items) < 2:
            return [function(item) for item in items]
        with ThreadPoolExecutor(max_workers=count, thread_name_prefix="mame-io") as executor:
            return list(executor.map(function, items))

    def choose_cpu_executor(self) -> str:
        """Retorna a estratégia CPU escolhida para diagnóstico."""
        return "process_pool_spawn" if self.profile.recommended_cpu_workers > 1 else "serial"
