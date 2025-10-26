"""
Core orchestration layer for the anonymizer MCP server.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Iterable

from anonymizer.model.project import ProjectModel
from anonymizer.utils.logging import set_anonymizer_log_level

from .config import MCPConfig
from .state import ProcessingState

logger = logging.getLogger(__name__)


class AnonymizerService:
    """
    Thin wrapper that feeds local DICOM files into the existing AnonymizerController.
    """

    SUPPORTED_EXTENSIONS = {".dcm", ".dicom", ".ima", ""}  # include extensionless files

    def __init__(self, config: MCPConfig) -> None:
        self.config = config
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

        self._model: ProjectModel | None = None
        self._controller = None
        self.state = ProcessingState(config.state_file)

    def _configure_model(self, model: ProjectModel) -> None:
        model.storage_dir = self.config.paths.output_dir
        model.remove_pixel_phi = self.config.processing.remove_pixel_phi
        if self.config.processing.anonymizer_script_path:
            model.anonymizer_script_path = self.config.processing.anonymizer_script_path

        if self.config.identity.site_id:
            model.site_id = self.config.identity.site_id
        if self.config.identity.uid_root:
            model.uid_root = self.config.identity.uid_root

        level = getattr(logging, self.config.logging.level, logging.INFO)
        model.logging_levels.anonymizer = level
        set_anonymizer_log_level(level)

        # Ensure derived storage directories exist
        model.storage_dir.mkdir(parents=True, exist_ok=True)
        model.private_dir().mkdir(parents=True, exist_ok=True)
        model.images_dir().mkdir(parents=True, exist_ok=True)

    def _ensure_model(self) -> ProjectModel:
        if self._model is None:
            model = ProjectModel()
            self._configure_model(model)
            self._model = model
        return self._model

    def _ensure_controller(self):
        if self._controller is None:
            from anonymizer.controller.anonymizer import AnonymizerController

            model = self._ensure_model()
            self._controller = AnonymizerController(model)
        return self._controller

    def shutdown(self) -> None:
        if self._controller:
            self._controller.stop()
        self.state.save()

    def anonymize_now(self, force_rescan: bool = False) -> dict[str, int | float]:
        controller = self._ensure_controller()
        start = time.perf_counter()
        if force_rescan:
            self.state.reset()

        candidates = list(self._collect_candidates())
        if self.config.limits.max_concurrent_files:
            candidates = candidates[: self.config.limits.max_concurrent_files]

        enqueued = 0
        completed = 0
        errors = 0

        for path in candidates:
            if not force_rescan and self.state.is_processed(path):
                continue

            enqueued += 1
            error_msg, _ = controller.anonymize_file(path)
            if error_msg:
                errors += 1
                logger.error("Anonymization failed for %s: %s", path, error_msg)
            else:
                completed += 1
                self.state.mark_processed(path)

        self.state.save()
        duration_ms = (time.perf_counter() - start) * 1000
        quarantine_files = self._count_quarantine_files()

        return {
            "files_seen": len(candidates),
            "enqueued": enqueued,
            "completed": completed,
            "errors": errors,
            "quarantined": quarantine_files,
            "duration_ms": round(duration_ms, 2),
        }

    def status(self) -> dict[str, object]:
        controller = self._ensure_controller()
        datasets_q, pixel_q = controller.queued()
        totals = controller.model.get_totals()
        return {
            "queue": {"datasets": datasets_q, "pixel_phi": pixel_q},
            "totals": totals._asdict(),
            "input_files": self._count_input_files(),
            "output_files": self._count_output_files(),
            "quarantine_files": self._count_quarantine_files(),
        }

    def _collect_candidates(self) -> Iterable[Path]:
        root = self.config.paths.input_dir
        iterator = root.rglob("*") if self.config.processing.recursive_scan else root.glob("*")
        for path in iterator:
            if not path.is_file():
                continue
            if path.suffix.lower() in self.SUPPORTED_EXTENSIONS:
                yield path

    def _count_input_files(self) -> int:
        return sum(1 for _ in self._collect_candidates())

    def _count_output_files(self) -> int:
        images_dir = self._ensure_model().images_dir()
        if not images_dir.exists():
            return 0
        return sum(1 for file in images_dir.rglob("*") if file.is_file())

    def _count_quarantine_files(self) -> int:
        controller = self._ensure_controller()
        qpath = controller.get_quarantine_path()
        if not qpath.exists():
            return 0
        return sum(1 for file in qpath.rglob("*") if file.is_file())
