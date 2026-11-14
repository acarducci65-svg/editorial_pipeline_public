"""Optional F5 audio providers."""

from editorial_pipeline.adapters.audio.base import AudioProvider, AudioResult, AudioUnavailableError
from editorial_pipeline.adapters.audio.notebooklm import NotebookLMAdapter
from editorial_pipeline.adapters.audio.script_only import ScriptOnlyAdapter

__all__ = [
    "AudioProvider",
    "AudioResult",
    "AudioUnavailableError",
    "NotebookLMAdapter",
    "ScriptOnlyAdapter",
]
