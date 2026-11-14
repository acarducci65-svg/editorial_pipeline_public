"""Optional F5 audio providers; NotebookLM is the editorial standard, TTS is deprecated."""

from editorial_pipeline.adapters.audio.base import AudioProvider, AudioResult, AudioUnavailableError
from editorial_pipeline.adapters.audio.notebooklm import (
    AUDIO_FORMATS,
    NotebookLMAdapter,
    NotebookLMAudioAdapter,
)
from editorial_pipeline.adapters.audio.script_only import ScriptOnlyAdapter
from editorial_pipeline.adapters.audio.tts import TTS_DEPRECATION, LocalTtsAudioProvider

__all__ = [
    "AUDIO_FORMATS",
    "TTS_DEPRECATION",
    "AudioProvider",
    "AudioResult",
    "AudioUnavailableError",
    "LocalTtsAudioProvider",
    "NotebookLMAdapter",
    "NotebookLMAudioAdapter",
    "ScriptOnlyAdapter",
]
