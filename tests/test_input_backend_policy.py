from serm_v2.services.input_backend_policy import (
    InputBackend,
    InputBackendPolicyService,
)


def test_mame_windows_prefers_winhybrid_and_keeps_ctrlr() -> None:
    policy = InputBackendPolicyService.for_mame()

    assert policy.preferred is InputBackend.WINDOWS_HYBRID
    assert policy.supports_ctrlr is True
    assert policy.supports_controller_map is False
    assert policy.runtime_passthrough is True
    assert InputBackend.DIRECTINPUT in policy.fallbacks


def test_retroarch_windows_prefers_xinput() -> None:
    policies = InputBackendPolicyService.for_retroarch()

    assert len(policies) == 1
    policy = policies[0]
    assert policy.preferred is InputBackend.RETROARCH_XINPUT
    assert InputBackend.RETROARCH_DIRECTINPUT in policy.fallbacks
    assert policy.runtime_passthrough is True
