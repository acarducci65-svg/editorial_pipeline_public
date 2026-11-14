"""Deterministic offline podcast script from validated source-bound claims."""

from pathlib import Path
from typing import Any

from editorial_pipeline.adapters.audio.base import AudioProvider, AudioResult
from editorial_pipeline.cli.reports import _sanitize


class ScriptOnlyAdapter(AudioProvider):
    def build(
        self,
        post_id: str,
        draft_text: str,
        sources: list[dict[str, Any]],
        output_dir: Path,
        dry_run: bool = False,
    ) -> AudioResult:
        path = self.destination(post_id, output_dir, "podcast_script.md")
        result = AudioResult(
            status="DRY_RUN" if dry_run else "BUILT",
            provider="script_only",
            script_file=self.result_path(path),
        )
        if dry_run:
            return result
        title = next(
            (line[2:].strip() for line in draft_text.splitlines() if line.startswith("# ")),
            post_id,
        )
        lines = [
            f"# Podcast: {title}",
            "",
            "Copione da revisionare prima della registrazione o del TTS.",
            "",
            "## Intro",
            f"[Speaker] {title}: quali evidenze ci aiutano a capire questo tema?",
            "Esaminiamo le affermazioni verificate e i loro riferimenti.",
        ]
        for index, source in enumerate(sources, 1):
            lines.extend(["", f"## Segmento {index}", f"Fonte: {source['key']}"])
            for claim in source.get("claims", []):
                lines.extend(
                    [f"[Speaker] {claim['text']}", f"Riferimento: {claim['locator']}", "[Pausa]"]
                )
        lines.extend(
            [
                "",
                "## Outro",
                f"[Speaker] Fonti e metodo sono disponibili nell'articolo {post_id}.",
                "Licenza: consultare la licenza editoriale dell'articolo e delle fonti;",
                "la licenza del software non attribuisce diritti sui contenuti.",
                "Bozza audio: revisione umana richiesta; pubblicazione soggetta al Gate 2.",
                "",
            ]
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_sanitize("\n".join(lines)), encoding="utf-8")
        return result
