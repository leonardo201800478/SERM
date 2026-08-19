"""Detecção de recursos de hardware sem extensões nativas próprias.

O projeto permanece integralmente em Python. A detecção é usada apenas para
escolher parâmetros seguros de execução; ela nunca altera a integridade do
scan nem escreve na origem das ROMs.
"""
from __future__ import annotations

import os
import platform
import sys
from dataclasses import dataclass, asdict


@dataclass(frozen=True, slots=True)
class HardwareProfile:
    """Snapshot do hardware relevante para o scheduler."""
    cpu: str
    architecture: str
    physical_cores: int
    logical_cores: int
    ram_total_bytes: int
    ram_available_bytes: int
    avx: bool | None
    avx2: bool | None
    fma3: bool | None
    sha: bool | None
    avx512: bool | None
    python_version: str
    recommended_cpu_workers: int
    recommended_io_workers: int
    recommended_batch_size: int
    memory_budget_bytes: int

    def to_dict(self) -> dict[str, object]:
        """Converte o perfil para uma estrutura serializável."""
        return asdict(self)

    @property
    def simd_summary(self) -> str:
        """Retorna os recursos SIMD conhecidos em formato legível."""
        names = []
        for name, value in (("AVX", self.avx), ("AVX2", self.avx2), ("FMA3", self.fma3), ("SHA", self.sha), ("AVX512", self.avx512)):
            if value is True:
                names.append(name)
            elif value is None:
                names.append(f"{name}?")
        return ", ".join(names) if names else "nenhum recurso SIMD confirmado"


class HardwareDetector:
    """Detecta CPU, RAM e flags de CPU disponíveis sem código compilado."""

    @staticmethod
    def _ram_bytes() -> tuple[int, int]:
        """Obtém RAM total/disponível usando APIs do sistema."""
        try:
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            status = MemoryStatus()
            status.dwLength = ctypes.sizeof(MemoryStatus)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.ullTotalPhys), int(status.ullAvailPhys)
        except Exception:
            pass
        try:
            pages = os.sysconf("SC_PHYS_PAGES")
            page_size = os.sysconf("SC_PAGE_SIZE")
            total = int(pages * page_size)
            return total, total
        except (AttributeError, OSError, ValueError):
            return 0, 0

    @staticmethod
    def _cpu_info() -> tuple[str, set[str], bool]:
        """Obtém nome, flags e indicação de SMT/HT usando py-cpuinfo."""
        try:
            import cpuinfo  # type: ignore
            info = cpuinfo.get_cpu_info()
            flags = {str(flag).lower() for flag in info.get("flags", [])}
            name = str(info.get("brand_raw") or platform.processor() or platform.machine())
            return name, flags, "ht" in flags or "htt" in flags
        except Exception:
            return platform.processor() or platform.machine() or "CPU desconhecida", set(), False

    @classmethod
    def detect(cls) -> HardwareProfile:
        """Detecta hardware e calcula parâmetros conservadores iniciais."""
        logical = max(1, int(os.process_cpu_count() or os.cpu_count() or 1))
        cpu, flags, smt = cls._cpu_info()
        physical = max(1, logical // 2) if smt else logical
        # Não confiamos no campo ``count`` do cpuinfo como núcleos físicos:
        # normalmente ele representa processadores lógicos.
        total_ram, available_ram = cls._ram_bytes()
        cpu_workers = max(1, min(physical, logical - 1 if logical > 2 else 1))
        io_workers = max(1, min(4, physical))
        batch = 2000 if total_ram >= 32 * 1024**3 else 1000 if total_ram >= 16 * 1024**3 else 500
        memory_budget = max(512 * 1024**2, min(total_ram // 4 if total_ram else 1024**3, 8 * 1024**3))
        return HardwareProfile(
            cpu=cpu,
            architecture=platform.machine() or platform.architecture()[0],
            physical_cores=physical,
            logical_cores=logical,
            ram_total_bytes=total_ram,
            ram_available_bytes=available_ram,
            avx="avx" in flags if flags else None,
            avx2="avx2" in flags if flags else None,
            fma3=("fma3" in flags or "fma" in flags) if flags else None,
            sha=("sha" in flags or "sha_ni" in flags) if flags else None,
            avx512=any(flag.startswith("avx512") for flag in flags) if flags else None,
            python_version=sys.version.split()[0],
            recommended_cpu_workers=cpu_workers,
            recommended_io_workers=io_workers,
            recommended_batch_size=batch,
            memory_budget_bytes=memory_budget,
        )
