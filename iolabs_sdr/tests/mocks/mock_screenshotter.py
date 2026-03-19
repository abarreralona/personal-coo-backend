"""
IOlabs AI SDR Platform — Mock Screenshot Service (Step 9)

Returns fixture screenshots instead of calling the live proprietary scraper.
Used in all tests that exercise the classification pipeline.

Maps website URLs to fixture image paths in tests/fixtures/screenshots/.
If no fixture found for URL → returns a blank white screenshot.
"""

from pathlib import Path

FIXTURE_DIR = Path(__file__).parent.parent / "fixtures" / "screenshots"


class MockScreenshotter:
    """
    Drop-in replacement for the proprietary screenshot HTTP API.
    Used in tests via dependency injection.
    """

    # TODO: Step 9 — implement with fixture registry
    # Maps: domain → {homepage: path, logos_section: path, products: path}

    async def capture(self, url: str, capture_type: str) -> bytes:
        """
        Returns fixture screenshot bytes for the given URL and capture type.
        capture_type: 'homepage' | 'logos_section' | 'products'
        """
        # TODO: Step 9 — implement fixture lookup
        raise NotImplementedError("MockScreenshotter.capture: implemented in Step 9")
