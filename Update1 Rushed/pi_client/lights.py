"""
lights.py — LED Control (MANUAL MODE — No GPIO used)
=====================================================
UPDATE1 RUSHED CHANGES:
    - White LED and UV-A LED are switched ON/OFF MANUALLY by the operator.
    - No MOSFETs, no GPIO pins, no software control at all.
    - This module is kept as a STUB so that imports in main.py still work
      without modification.
    - All methods are no-ops (do nothing silently).

Physical operation:
    1. Operator turns White LEDs ON by hand (before starting scan).
    2. Scan runs: motor rotates, camera captures 8 RGB frames.
    3. If UV scan desired: operator switches to UV LEDs by hand
       (handled as a completely separate manual session if needed).
"""

import logging
log = logging.getLogger(__name__)


class LightController:
    """
    STUB — All LED control is manual in this build.
    Methods exist for import compatibility but do nothing.
    """

    def __init__(self):
        # No GPIO, no MOSFET — manual control only
        log.info("LightController: MANUAL MODE — LEDs controlled by operator, not software.")

    # ── Stubs (do nothing) ────────────────────────────────────────────────────

    def white_on(self):
        """MANUAL: Operator turns White LEDs on by hand."""
        pass

    def white_off(self):
        """MANUAL: Operator turns White LEDs off by hand."""
        pass

    def uv_on(self):
        """MANUAL: Operator turns UV LEDs on by hand."""
        pass

    def uv_off(self):
        """MANUAL: Operator turns UV LEDs off by hand."""
        pass

    def off_all(self):
        """MANUAL: No-op."""
        pass

    def capture_white(self):
        """Returns a no-op context manager for compatibility."""
        return _NoOpContext()

    def capture_uv(self):
        """Returns a no-op context manager for compatibility."""
        return _NoOpContext()

    def cleanup(self):
        pass


class _NoOpContext:
    """No-op context manager — used instead of real light switching."""
    def __enter__(self):
        return self
    def __exit__(self, *_):
        pass
