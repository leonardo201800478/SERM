"""Camada MAME-aware sobre o motor de reconstrução existente.

Mantém a segurança do ReconstructionEngine e acrescenta semântica de
LISTXML: baddump, nodump, optional, BIOS, devices, clones e samples.
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.mame.reconstruction_engine import (
    ReconstructionEngine,
    ReconstructionMachine,
    ReconstructionResult,
)


@dataclass(frozen=True, slots=True)
class MameBuildOptions:
    """Opções expostas pela interface de reconstrução."""
    include_clones: bool = True
    include_bios: bool = True
    include_devices: bool = True
    include_samples: bool = True
    include_optional: bool = True


class MameAwareReconstructionEngine(ReconstructionEngine):
    """Reconstrutor que aplica a semântica do LISTXML antes do motor físico."""

    def __init__(self, source_paths: Iterable[str | Path], destination_path: str | Path, *, build_options: MameBuildOptions | None = None, xml_path: str | Path | None = None, progress_callback: Callable[[int, int, str], None] | None = None, log_callback: Callable[[str], None] | None = None, max_retries: int = 2) -> None:
        super().__init__(source_paths, destination_path, progress_callback=progress_callback, log_callback=log_callback, max_retries=max_retries)
        self.build_options = build_options or MameBuildOptions()
        self.xml_path = Path(xml_path) if xml_path else None
        self.decisions: list[dict[str, Any]] = []

    def reconstruct(self, machines: list[ReconstructionMachine], *, set_type: str = ReconstructionEngine.SET_SPLIT, copy_perfect: bool = True, repair: bool = True) -> ReconstructionResult:
        """Aplica opções MAME, executa a reconstrução segura e copia samples."""
        self.decisions = []
        catalog = self._load_catalog(self.xml_path)
        prepared = self._prepare_machines(machines, catalog)
        result = super().reconstruct(prepared, set_type=set_type, copy_perfect=copy_perfect, repair=repair)
        sample_artifacts = self._copy_samples(prepared, catalog)
        self._write_decision_report(result, sample_artifacts)
        return result

    def _prepare_machines(self, machines: list[ReconstructionMachine], catalog: dict[str, dict]) -> list[ReconstructionMachine]:
        """Filtra dependências sem alterar os objetos carregados do manifesto."""
        prepared: list[ReconstructionMachine] = []
        options = self.build_options
        for original in machines:
            meta = catalog.get(original.name, {})
            if meta.get("is_device") and not options.include_devices:
                self._decision(original.name, "<machine>", "ignore", "Device desabilitado nas opções de construção.")
                continue
            if meta.get("is_bios") and not options.include_bios:
                self._decision(original.name, "<machine>", "ignore", "Sistema BIOS desabilitado nas opções de construção.")
                continue
            if original.cloneof and not options.include_clones:
                self._decision(original.name, "<machine>", "ignore", "Clone desabilitado nas opções de construção.")
                continue

            machine = copy.deepcopy(original)
            filtered_roms = []
            for rom in machine.roms:
                rom_meta = meta.get("roms", {}).get(rom.rom_name, {})
                mame_status = str(rom_meta.get("status", "good")).lower()
                is_optional = bool(rom.optional or rom_meta.get("optional"))
                is_bios_rom = bool(rom_meta.get("bios"))

                if is_bios_rom and not options.include_bios:
                    self._decision(machine.name, rom.rom_name, "ignore", "ROM marcada como BIOS no LISTXML e a opção de incluir BIOS está desativada.")
                    continue
                if is_optional and not options.include_optional:
                    self._decision(machine.name, rom.rom_name, "ignore", "ROM opcional removida pelas opções de construção.")
                    continue

                if mame_status == "nodump":
                    self._decision(machine.name, rom.rom_name, "ignore", "ROM marcada como NO DUMP KNOWN pelo MAME; não existe conteúdo conhecido para validar e ela não será inventada nem aceita automaticamente.")
                    continue
                if rom.status == "missing" and is_optional:
                    self._decision(machine.name, rom.rom_name, "ignore", "ROM opcional ausente; sua ausência não bloqueia a execução mínima.")
                    continue

                if rom.status == "valid" and mame_status == "baddump":
                    self._decision(machine.name, rom.rom_name, "keep", "ROM corresponde ao dump conhecido pelo MAME. Embora esteja marcada como BAD DUMP, ela é mantida por ser a melhor imagem conhecida.")
                elif rom.status == "valid":
                    self._decision(machine.name, rom.rom_name, "keep", "ROM validada pelo scan físico e mantida na reconstrução.")
                elif rom.status in {"invalid", "sha1_mismatch"}:
                    self._decision(machine.name, rom.rom_name, "search", self._invalid_reason(rom, mame_status))
                elif rom.status == "missing":
                    self._decision(machine.name, rom.rom_name, "block", "ROM obrigatória ausente; o motor tentará reconstrução pela fonte registrada, mas a máquina não pode ser declarada completa enquanto ela faltar.")

                filtered_roms.append(rom)
            machine.roms = filtered_roms
            prepared.append(machine)
        return prepared

    @staticmethod
    def _invalid_reason(rom, mame_status: str) -> str:
        """Monta diagnóstico determinístico para uma ROM inválida."""
        reasons: list[str] = []
        if rom.expected_size > 0 and rom.actual_size != rom.expected_size:
            reasons.append(f"tamanho esperado {rom.expected_size} bytes, encontrado {rom.actual_size}")
        if rom.expected_crc and rom.actual_crc and rom.expected_crc.lower() != rom.actual_crc.lower():
            reasons.append(f"CRC esperado {rom.expected_crc.lower()}, encontrado {rom.actual_crc.lower()}")
        if rom.expected_sha1 and rom.actual_sha1 and rom.expected_sha1.lower() != rom.actual_sha1.lower():
            reasons.append("SHA-1 divergente")
        if not reasons:
            reasons.append("arquivo físico não corresponde aos identificadores conhecidos")
        prefix = "BAD DUMP conhecido; " if mame_status == "baddump" else ""
        return prefix + "ROM invalidada: " + "; ".join(reasons) + "."

    def _copy_samples(self, machines: list[ReconstructionMachine], catalog: dict[str, dict]) -> list[dict]:
        """Copia sample sets ZIP para ``destination/samples`` quando solicitado."""
        if not self.build_options.include_samples:
            return []
        names: set[str] = set()
        for machine in machines:
            names.update(catalog.get(machine.name, {}).get("samples", ()))
        if not names:
            return []
        target_root = self.destination_path / "samples"
        target_root.mkdir(parents=True, exist_ok=True)
        artifacts: list[dict] = []
        for name in sorted(names):
            candidates = [base / "samples" / f"{name}.zip" for base in self.source_paths]
            candidates.extend(base / f"{name}.zip" for base in self.source_paths)
            source = next((path for path in candidates if path.is_file()), None)
            target = target_root / f"{name}.zip"
            if source is None:
                self._decision(f"sample:{name}", "<sample>", "search", f"Sample set {name}.zip não encontrado nas origens configuradas.")
                continue
            if target.exists():
                artifacts.append({"type": "sample", "name": name, "status": "already_exists", "destination": str(target)})
                continue
            partial = target.with_name(target.name + ".partial")
            shutil.copyfile(source, partial)
            os.replace(partial, target)
            artifacts.append({"type": "sample", "name": name, "status": "copied", "source": str(source), "destination": str(target)})
            self._decision(f"sample:{name}", "<sample>", "keep", f"Sample set encontrado em {source} e copiado para o destino.")
        return artifacts

    def _write_decision_report(self, result: ReconstructionResult, sample_artifacts: list[dict]) -> None:
        """Persiste decisões sem misturá-las ao manifesto residual de pendências."""
        output = self.destination_path / "reconstruction-decisions.json"
        payload = {"options": {"include_clones": self.build_options.include_clones, "include_bios": self.build_options.include_bios, "include_devices": self.build_options.include_devices, "include_samples": self.build_options.include_samples, "include_optional": self.build_options.include_optional}, "decisions": self.decisions, "sample_artifacts": sample_artifacts, "unresolved_count": len(result.unresolved)}
        partial = output.with_suffix(".json.partial")
        partial.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(partial, output)

    def _decision(self, machine: str, item: str, action: str, reason: str) -> None:
        """Registra decisão e a envia para o log."""
        record = {"machine": machine, "item": item, "action": action, "reason": reason}
        self.decisions.append(record)
        self._log(f"[DECISÃO] {machine} -> {item} | {action.upper()} | {reason}")

    @staticmethod
    def _load_catalog(xml_path: Path | None) -> dict[str, dict]:
        """Lê somente metadados de ROM, machine, sample, BIOS e device do LISTXML."""
        if xml_path is None or not xml_path.is_file():
            return {}
        try:
            root = ET.parse(xml_path).getroot()
        except (OSError, ET.ParseError):
            return {}
        catalog: dict[str, dict] = {}
        for machine in root.findall("machine"):
            name = machine.get("name", "")
            if not name:
                continue
            roms = {}
            for rom in machine.findall("rom"):
                rom_name = rom.get("name", "")
                if rom_name:
                    roms[rom_name] = {"status": rom.get("status", "good"), "optional": str(rom.get("optional", "")).lower() in {"yes", "true", "1"}, "bios": rom.get("bios", "") or ""}
            samples = tuple(dict.fromkeys(value for value in (machine.get("sampleof", ""), *(node.get("name", "") for node in machine.findall("sample"))) if value))
            catalog[name] = {"is_bios": str(machine.get("isbios", "")).lower() == "yes", "is_device": str(machine.get("isdevice", "")).lower() == "yes", "samples": samples, "roms": roms}
        return catalog
