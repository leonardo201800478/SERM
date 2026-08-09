from typing import List
from ..domain.set_profile import EmulationStatus, SetType, RomSetType

def build_category_condition(categories: List[str]) -> str:
    if not categories:
        return ""
    # Mapeamento de categorias amigáveis para categorias reais
    # "System" mapeia para Console, Computer, Portable
    # As outras são diretas
    cat_map = {
        "Arcade": "Arcade",
        "System": ("Console", "Computer", "Portable"),
        "Bios": "BIOS",
        "Device": "Device",
        "Mechanical": "Mechanical",
        "Casino": "Casino",
        "Mahjong": "Mahjong",
        "Mature": None,   # não implementado
        "Screenless": None,
        "Free to play": None,
    }
    conditions = []
    for cat in categories:
        mapped = cat_map.get(cat)
        if mapped is None:
            continue
        if isinstance(mapped, tuple):
            # System
            cond = "mc.category IN ('{}')".format("','".join(mapped))
        else:
            cond = f"mc.category = '{mapped}'"
        conditions.append(cond)
    if not conditions:
        return ""
    return "(" + " OR ".join(conditions) + ")"

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

def build_rom_set_type_condition(rom_set_type: RomSetType) -> str:
    if rom_set_type == RomSetType.ALL:
        return ""
    elif rom_set_type == RomSetType.PARENT:
        return "(m.cloneof IS NULL OR m.cloneof = '')"
    else:  # CLONE
        return "(m.cloneof IS NOT NULL AND m.cloneof != '')"

def build_resource_conditions(use_chd: bool, use_sample: bool, use_bios: bool) -> List[str]:
    conditions = []
    if use_chd:
        conditions.append("EXISTS (SELECT 1 FROM disk d WHERE d.machine_id = m.id)")
    if use_sample:
        conditions.append("(m.sampleof IS NOT NULL AND m.sampleof != '')")
    if use_bios:
        conditions.append("EXISTS (SELECT 1 FROM device_ref dr WHERE dr.machine_id = m.id AND EXISTS (SELECT 1 FROM machine b WHERE b.name = dr.name AND b.isbios = 1))")
    return conditions

def build_conditions(profile) -> List[str]:
    conditions = []
    conditions.append(build_runnable_condition())

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

    rom_type_cond = build_rom_set_type_condition(profile.rom_set_type)
    if rom_type_cond:
        conditions.append(rom_type_cond)

    res_conditions = build_resource_conditions(profile.use_chd, profile.use_sample, profile.use_bios)
    conditions.extend(res_conditions)

    if profile.mamecab_only:
        # Restringe a Arcade e Parent
        conditions.append("mc.category = 'Arcade'")
        conditions.append("(m.cloneof IS NULL OR m.cloneof = '')")

    return conditions