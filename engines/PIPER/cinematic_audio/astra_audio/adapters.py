"""Optional AI adapter contracts. No model/API is bundled or required."""
from typing import Protocol, Any

class AudioUnderstandingAdapter(Protocol):
    def classify_segments(self, audio_path: str) -> list[dict[str, Any]]:
        """Return timestamped labels/confidence; must not modify audio."""
        ...

class SourceSeparationAdapter(Protocol):
    def separate(self, audio_path: str, targets: list[str], output_dir: str) -> dict:
        """Optional model-backed separation; caller must audition every stem."""
        ...

class SpeechEnhancementAdapter(Protocol):
    def enhance(self, audio_path: str, output_path: str, preserve_emotion: bool = True) -> dict:
        """Optional speech enhancement; never overwrite source."""
        ...
