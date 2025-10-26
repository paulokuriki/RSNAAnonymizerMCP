"""
Configuration loader for the anonymizer MCP wrapper.

The YAML schema mirrors the structure documented in claude.md.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, MutableMapping

import yaml


class ConfigError(ValueError):
    """Raised when the YAML configuration is missing required attributes."""


def _expand_path(value: str | Path, base_dir: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return path.expanduser()


@dataclass(slots=True)
class PathSettings:
    input_dir: Path
    output_dir: Path
    quarantine_dir: Path
    temp_dir: Path

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any], base_dir: Path) -> "PathSettings":
        if "input_dir" not in data or "output_dir" not in data:
            raise ConfigError("`paths.input_dir` and `paths.output_dir` are required.")

        input_dir = _expand_path(data["input_dir"], base_dir)
        output_dir = _expand_path(data["output_dir"], base_dir)

        quarantine_value = data.get("quarantine_dir")
        temp_value = data.get("temp_dir")

        default_quarantine = output_dir / "private" / "quarantine"
        if quarantine_value:
            candidate = _expand_path(quarantine_value, base_dir)
            if not candidate.is_relative_to(output_dir):
                raise ConfigError("`paths.quarantine_dir` must live inside `paths.output_dir`.")
            quarantine_dir = candidate
        else:
            quarantine_dir = default_quarantine
        temp_dir = (
            _expand_path(temp_value, base_dir)
            if temp_value
            else Path(tempfile.gettempdir()).joinpath("rsna_anonymizer_mcp")
        )

        # Ensure directories exist (input must already exist, outputs are created)
        if not input_dir.exists():
            raise ConfigError(f"Input directory does not exist: {input_dir}")

        output_dir.mkdir(parents=True, exist_ok=True)
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        temp_dir.mkdir(parents=True, exist_ok=True)

        return cls(
            input_dir=input_dir,
            output_dir=output_dir,
            quarantine_dir=quarantine_dir,
            temp_dir=temp_dir,
        )


@dataclass(slots=True)
class ProcessingSettings:
    recursive_scan: bool = False
    remove_pixel_phi: bool = False
    anonymizer_script_path: Path | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any], base_dir: Path) -> "ProcessingSettings":
        script_value = data.get("anonymizer_script_path")
        script_path = _expand_path(script_value, base_dir) if script_value else None
        return cls(
            recursive_scan=bool(data.get("recursive_scan", False)),
            remove_pixel_phi=bool(data.get("remove_pixel_phi", False)),
            anonymizer_script_path=script_path,
        )


@dataclass(slots=True)
class IdentitySettings:
    site_id: str | None = None
    uid_root: str | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "IdentitySettings":
        return cls(
            site_id=(data.get("site_id") or None),
            uid_root=(data.get("uid_root") or None),
        )


@dataclass(slots=True)
class LoggingSettings:
    level: str = "INFO"

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "LoggingSettings":
        level = data.get("level", "INFO")
        if not isinstance(level, str):
            raise ConfigError("`logging.level` must be a string.")
        return cls(level=level.upper())


@dataclass(slots=True)
class LimitSettings:
    max_concurrent_files: int | None = None

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "LimitSettings":
        value = data.get("max_concurrent_files")
        if value is None:
            return cls(max_concurrent_files=None)
        if not isinstance(value, int) or value <= 0:
            raise ConfigError("`limits.max_concurrent_files` must be a positive integer.")
        return cls(max_concurrent_files=value)


@dataclass(slots=True)
class MCPConfig:
    paths: PathSettings
    processing: ProcessingSettings
    identity: IdentitySettings
    logging: LoggingSettings
    limits: LimitSettings
    state_filename: str = field(default=".anonymizer_mcp_state.json")

    @property
    def state_file(self) -> Path:
        return self.paths.temp_dir / self.state_filename

    @classmethod
    def from_file(cls, yaml_path: str | Path) -> "MCPConfig":
        path = Path(yaml_path).expanduser()
        if not path.exists():
            raise ConfigError(f"Configuration file not found: {path}")

        raw_data = path.read_text(encoding="utf-8")
        payload = yaml.safe_load(raw_data) or {}
        if not isinstance(payload, MutableMapping):
            raise ConfigError("Configuration file must contain a mapping at the top level.")

        base_dir = path.parent
        paths = PathSettings.from_mapping(payload.get("paths", {}), base_dir)
        processing = ProcessingSettings.from_mapping(payload.get("processing", {}), base_dir)
        identity = IdentitySettings.from_mapping(payload.get("identity", {}))
        logging_settings = LoggingSettings.from_mapping(payload.get("logging", {}))
        limits = LimitSettings.from_mapping(payload.get("limits", {}))

        return cls(
            paths=paths,
            processing=processing,
            identity=identity,
            logging=logging_settings,
            limits=limits,
        )
