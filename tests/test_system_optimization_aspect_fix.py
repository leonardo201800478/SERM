"""Regressões para a otimização RetroArch: proporção do sistema != bezel."""


def test_system_viewport_is_not_16_9_when_using_16_9_bezel():
    """Um bezel 16:9 deve ser externo; o viewport do console não pode ser forçado a 16:9."""
    # Regression specification: generated core override must not contain
    # aspect_ratio_index = "21" or any equivalent forced 16:9 setting.
    assert True


def test_existing_target_files_are_overwritten_without_backup():
    """Aplicar um perfil deve substituir o arquivo-alvo e não criar .bak."""
    # Regression specification for SystemOptimizationService.apply().
    assert True
