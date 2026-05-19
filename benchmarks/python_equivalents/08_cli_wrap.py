"""Example 08: CLI tool wrapper with error handling.

Wraps ffmpeg for video conversion, with proper return value handling
(success → output path, failure → error reason).
"""
from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Union

logger = logging.getLogger(__name__)


class ConversionError(Exception):
    """Raised when ffmpeg conversion fails."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def convert_video(
    input_path: str,
    output_path: str,
    codec: str = "libx264",
) -> Union[str, ConversionError]:
    """Convert a video file using ffmpeg.

    Returns the output path on success, or a ConversionError on failure.
    This function never raises — errors are returned as values (like Lumen's
    fail_safe pattern).
    """
    input_p = Path(input_path)
    if not input_p.exists():
        return ConversionError(f"Input file not found: {input_path}")

    cmd = ["ffmpeg", "-i", input_path, "-c:v", codec, output_path]
    logger.info("Running: %s", " ".join(cmd))

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    if result.returncode == 0:
        logger.info("Conversion successful: %s", output_path)
        return output_path
    else:
        stderr_summary = result.stderr.strip().splitlines()[-1] if result.stderr.strip() else "unknown error"
        return ConversionError(stderr_summary)


def main() -> None:
    outcome = convert_video("./input.mp4", "./output.mp4")
    if isinstance(outcome, ConversionError):
        print(f"Error: {outcome.reason}")
    else:
        print(f"Converted successfully: {outcome}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
