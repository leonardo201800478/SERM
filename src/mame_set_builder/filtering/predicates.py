"""
Funções auxiliares para construção de condições SQL para filtros.
"""

from typing import List, Optional, Any
from ..domain.set_profile import EmulationStatus

def build_category_condition(categories: List[str]) -> str:
    """Retorna condição SQL para filtro de categorias."""
    if not categories:
        return ""
    quoted = [f"'{cat}'" for cat in categories]
    return f"mc.category IN ({', '.join(quoted)})"

def build_emulation_condition(status: EmulationStatus) -> str:
    """
    Retorna condição SQL para status de emulação.
    GOOD, IMPERFECT, PRELIMINARY são cumulativos.
    """
    if status == EmulationStatus.ALL:
        return ""
    # GOOD = 'good', IMPERFECT = 'good' OR 'imperfect'
    # PRELIMINARY = 'good' OR 'imperfect' OR 'preliminary'
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

def build_clone_condition(include_clones: bool, set_type: str) -> str:
    """
    Retorna condição para incluir/excluir clones.
    Em merged, clones não podem ser excluídos.
    """
    if set_type == "merged":
        return ""  # não filtrar clones
    if include_clones:
        return ""  # incluir todos
    # Excluir clones: apenas máquinas com cloneof IS NULL ou ''
    return "(m.cloneof IS NULL OR m.cloneof = '')"

def build_bios_condition(keep_bios: bool) -> str:
    """Retorna condição para incluir/excluir BIOS."""
    if keep_bios:
        return ""
    return "m.isbios = 0"

def build_device_condition(keep_devices: bool) -> str:
    """Retorna condição para incluir/excluir Devices."""
    if keep_devices:
        return ""
    return "m.isdevice = 0"

def build_mechanical_condition() -> str:
    """Exclui máquinas mecânicas (a menos que sejam explicitamente incluídas)."""
    return "m.ismechanical = 0"

def build_runnable_condition() -> str:
    """Somente máquinas executáveis."""
    return "m.runnable = 1"

def build_conditions(profile) -> List[str]:
    """Constrói lista de condições SQL a partir do perfil."""
    conditions = []
    
    # Runnability
    conditions.append(build_runnable_condition())
    
    # Categorias
    cat_cond = build_category_condition(profile.categories)
    if cat_cond:
        conditions.append(cat_cond)
    
    # Emulação
    emul_cond = build_emulation_condition(profile.emulation_status)
    if emul_cond:
        conditions.append(emul_cond)
    
    # Clones
    clone_cond = build_clone_condition(profile.include_clones, profile.set_type.value)
    if clone_cond:
        conditions.append(clone_cond)
    
    # BIOS, Devices
    if not profile.keep_bios:
        conditions.append(build_bios_condition(False))
    if not profile.keep_devices:
        conditions.append(build_device_condition(False))
    
    # (Opcional) Excluir mecânicas explicitamente – podemos adicionar como regra geral,
    # mas se o usuário quiser manter, deve incluir a categoria "Mechanical" na lista.
    # Por padrão, se não houver categorias selecionadas, incluímos todas,
    # então não aplicamos esse filtro automaticamente.
    
    return conditions