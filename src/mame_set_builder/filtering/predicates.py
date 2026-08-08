"""
Funções auxiliares para construção de condições SQL para filtros.
"""

from typing import List
from ..domain.set_profile import EmulationStatus, SetType

def build_category_condition(categories: List[str]) -> str:
    if not categories:
        return ""
    quoted = [f"'{cat}'" for cat in categories]
    return f"mc.category IN ({', '.join(quoted)})"

def build_emulation_condition(status: EmulationStatus) -> str:
    if status == EmulationStatus.ALL:
        return ""
    allowed = []
    if status == EmulationStatus.GOOD:
        allowed = ['good']
    elif status == EmulationStatus.IMPERFECT:
        allowed = ['good', 'imperfect']
    elif status == EmulationStatus.PRELIMINARY:
        allowed = ['good', 'imperfect', 'preliminary']
    if not allowed:
        return ""
    quoted = [f"'{s}'" for s in allowed]
    return f"d.emulation IN ({', '.join(quoted)})"

def build_clone_condition(include_clones: bool, set_type: SetType) -> str:
    if set_type == SetType.MERGED:
        return ""
    if include_clones:
        return ""
    return "(m.cloneof IS NULL OR m.cloneof = '')"

def build_bios_condition(keep_bios: bool) -> str:
    return "" if keep_bios else "m.isbios = 0"

def build_device_condition(keep_devices: bool) -> str:
    return "" if keep_devices else "m.isdevice = 0"

def build_runnable_condition() -> str:
    return "m.runnable = 1"

def build_conditions(profile) -> List[str]:
    conditions = [build_runnable_condition()]
    
    cat_cond = build_category_condition(profile.categories)
    if cat_cond:
        conditions.append(cat_cond)
    
    emul_cond = build_emulation_condition(profile.emulation_status)
    if emul_cond:
        conditions.append(emul_cond)
    
    clone_cond = build_clone_condition(profile.include_clones, profile.set_type)
    if clone_cond:
        conditions.append(clone_cond)
    
    if not profile.keep_bios:
        conditions.append(build_bios_condition(False))
    if not profile.keep_devices:
        conditions.append(build_device_condition(False))
    
    return conditions