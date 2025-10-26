"""
Lightweight MCP wrapper package for the RSNA DICOM Anonymizer.

This package intentionally lives outside the core anonymizer code so it can
reuse the existing controllers without modifying them.
"""

from __future__ import annotations

__all__ = ["config", "service", "server", "state"]
