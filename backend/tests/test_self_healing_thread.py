"""
Verify that optimize_low_confidence_blocks runs on a worker thread, not the
asyncio event loop thread, when invoked via asyncio.to_thread.
"""
import asyncio
import threading
from unittest.mock import MagicMock

import pytest

from app.services.self_healing_ocr import optimize_low_confidence_blocks


class _ThreadRecordingReader:
    """Fake EasyOCR reader that records which thread readtext() is called on."""

    def __init__(self) -> None:
        self.called_from: threading.Thread | None = None

    def readtext(self, image_array):  # noqa: ANN001
        self.called_from = threading.current_thread()
        return []


def test_optimize_is_sync() -> None:
    """optimize_low_confidence_blocks must not be a coroutine function."""
    import inspect

    assert not inspect.iscoroutinefunction(optimize_low_confidence_blocks)


@pytest.mark.asyncio
async def test_readtext_runs_on_worker_thread(tmp_path) -> None:
    """readtext() must not execute on the event loop thread."""
    import numpy as np
    from PIL import Image

    # Create a minimal 10x10 white PNG so the function doesn't early-exit.
    img_path = tmp_path / "test.png"
    Image.new("RGB", (10, 10), color=(255, 255, 255)).save(img_path)

    low_conf_block = {
        "text": "blurry",
        "confidence": 0.30,
        "x": 10.0,
        "y": 10.0,
        "width": 80.0,
        "height": 80.0,
    }

    reader = _ThreadRecordingReader()
    event_loop_thread = threading.current_thread()

    await asyncio.to_thread(
        optimize_low_confidence_blocks,
        str(img_path),
        [low_conf_block],
        reader,  # type: ignore[arg-type]
    )

    # readtext must have been called (the block is low-confidence and crop is valid)
    assert reader.called_from is not None, "readtext() was never called"
    assert reader.called_from is not event_loop_thread, (
        f"readtext() ran on the event loop thread ({event_loop_thread.name}), "
        "which would block the event loop."
    )
