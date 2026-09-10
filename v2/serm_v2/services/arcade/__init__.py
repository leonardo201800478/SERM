"""Servicos do Arcade Studio."""

from .chd_audit import ArcadeChdAuditService, ChdAuditRecord, ChdAuditResult
from .chd_reconstruction import (
    ArcadeChdReconstructionEngine,
    ChdMatchKind,
    ChdReconstruction,
    ChdReconstructionPlan,
    ChdReconstructionResult,
    PhysicalChd,
)
from .download_manager import DestinationAction, DownloadManager
from .materializer import ArcadeSetMaterializer, MaterializationError
from .projeto_snaps_provider import ProgettoSnapsProvider
from .reconstruction_manifest import (
    ArcadeReconstructionManifestBuilder,
    MaterializationEntry,
    MaterializationKind,
    ReconstructionManifest,
)
from .rom_reconstruction import (
    ArcadeRomReconstructionEngine,
    PhysicalRom,
    ReconstructionResult,
    RomMatchKind,
    RomReconstruction,
)
from .rom_reconstruction_plan import (
    ArcadeRomReconstructionPlanner,
    RomReconstructionPlan,
    RomReconstructionPlanResult,
    RomSourceKind,
)
from .resource_catalog import ExternalResourceCatalog
from .set_builder import (
    ArcadeSetBuilder,
    SetBuildDecision,
    SetBuildError,
    SetBuildResult,
    SetBuildTrace,
)
from .set_layout import ArcadeSetLayoutPlanner, SetFileAction, SetLayoutEntry, SetLayoutPlan

__all__ = [
    "ArcadeChdAuditService",
    "ChdAuditRecord",
    "ChdAuditResult",
    "ArcadeChdReconstructionEngine",
    "ChdMatchKind",
    "ChdReconstruction",
    "ChdReconstructionPlan",
    "ChdReconstructionResult",
    "PhysicalChd",
    "DestinationAction",
    "DownloadManager",
    "ProgettoSnapsProvider",
    "ExternalResourceCatalog",
    "ArcadeSetMaterializer",
    "MaterializationError",
    "ArcadeReconstructionManifestBuilder",
    "MaterializationEntry",
    "MaterializationKind",
    "ReconstructionManifest",
    "ArcadeRomReconstructionEngine",
    "PhysicalRom",
    "ReconstructionResult",
    "RomMatchKind",
    "RomReconstruction",
    "ArcadeRomReconstructionPlanner",
    "RomReconstructionPlan",
    "RomReconstructionPlanResult",
    "RomSourceKind",
    "ArcadeSetLayoutPlanner",
    "SetFileAction",
    "SetLayoutEntry",
    "SetLayoutPlan",
    "SetBuildDecision",
    "SetBuildError",
    "SetBuildResult",
    "SetBuildTrace",
]
