"""Políticas de backend de entrada por emulador.

A política descreve como o emulador deve acessar o hardware durante a
execução. Ela não cria um driver virtual e não encaminha eventos através do
SERM.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class InputBackend(StrEnum):
    """Backend de entrada efetivamente consumido pelo emulador."""

    WINDOWS_HYBRID = "winhybrid"
    XINPUT = "xinput"
    DIRECTINPUT = "dinput"
    SDL_GAME = "sdlgame"
    RETROARCH_XINPUT = "retroarch-xinput"
    RETROARCH_DIRECTINPUT = "retroarch-dinput"
    RETROARCH_SDL2 = "retroarch-sdl2"
    NATIVE = "native"


@dataclass(frozen=True, slots=True)
class InputBackendPolicy:
    """Contrato declarativo para a última milha de entrada do emulador."""

    emulator: str
    platform: str
    preferred: InputBackend
    fallbacks: tuple[InputBackend, ...] = ()
    supports_controller_map: bool = False
    supports_ctrlr: bool = False
    runtime_passthrough: bool = True
    rationale: str = ""


class InputBackendPolicyService:
    """Resolve a política de entrada sem alterar o dispositivo físico."""

    @staticmethod
    def for_mame(platform: str = "windows") -> InputBackendPolicy:
        if platform.casefold() == "windows":
            return InputBackendPolicy(
                emulator="mame",
                platform="windows",
                preferred=InputBackend.WINDOWS_HYBRID,
                fallbacks=(InputBackend.DIRECTINPUT, InputBackend.XINPUT),
                supports_controller_map=False,
                supports_ctrlr=True,
                rationale=(
                    "No Windows, preservar winhybrid permite XInput para gamepads "
                    "compatíveis e DirectInput para periféricos não-XInput, como "
                    "volantes."
                ),
            )
        return InputBackendPolicy(
            emulator="mame",
            platform=platform,
            preferred=InputBackend.NATIVE,
            supports_ctrlr=True,
            rationale="Usar o backend nativo da plataforma; não impor SDL ao MAME.",
        )

    @staticmethod
    def for_retroarch(platform: str = "windows") -> tuple[InputBackendPolicy, ...]:
        if platform.casefold() == "windows":
            return (
                InputBackendPolicy(
                    emulator="retroarch",
                    platform="windows",
                    preferred=InputBackend.RETROARCH_XINPUT,
                    fallbacks=(
                        InputBackend.RETROARCH_DIRECTINPUT,
                        InputBackend.RETROARCH_SDL2,
                    ),
                    runtime_passthrough=True,
                    rationale="Priorizar o driver XInput nativo quando o dispositivo o suportar.",
                ),
            )
        return (
            InputBackendPolicy(
                emulator="retroarch",
                platform=platform,
                preferred=InputBackend.NATIVE,
                runtime_passthrough=True,
                rationale="Delegar a escolha ao driver nativo do RetroArch.",
            ),
        )


__all__ = ["InputBackend", "InputBackendPolicy", "InputBackendPolicyService"]
