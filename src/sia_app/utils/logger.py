"""Configuração única de logs rotativos."""

from __future__ import annotations

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any

from sia_app.paths import get_runtime_paths


class LoggerConfig:
    DEFAULT_CONFIG: dict[str, Any] = {
        "log_level": logging.INFO,
        "log_format": "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
        "date_format": "%Y-%m-%d %H:%M:%S",
        "log_dir": str(get_runtime_paths().logs),
        "max_file_size_mb": 10,
        "backup_count": 5,
        "encoding": "utf-8",
        "enable_console": True,
        "enable_file": True,
    }
    _configured_loggers: dict[str, logging.Logger] = {}

    @classmethod
    def setup_logger(
        cls, logger_name: str = "SIASystem", config: dict[str, Any] | None = None
    ) -> logging.Logger:
        final_config = {**cls.DEFAULT_CONFIG, **(config or {})}
        logger = logging.getLogger(logger_name)
        logger.setLevel(final_config["log_level"])

        for handler in logger.handlers[:]:
            handler.close()
            logger.removeHandler(handler)

        formatter = logging.Formatter(
            final_config["log_format"], datefmt=final_config["date_format"]
        )
        if final_config["enable_file"]:
            log_dir = Path(final_config["log_dir"])
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"{logger_name.lower()}_{datetime.now():%Y%m%d}.log"
            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=int(final_config["max_file_size_mb"] * 1024 * 1024),
                backupCount=int(final_config["backup_count"]),
                encoding=final_config["encoding"],
            )
            file_handler.setLevel(final_config["log_level"])
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        if final_config["enable_console"]:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(final_config["log_level"])
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        logger.propagate = False
        cls._configured_loggers[logger_name] = logger
        return logger

    @classmethod
    def get_logger(cls, logger_name: str = "SIASystem") -> logging.Logger:
        return cls._configured_loggers.get(logger_name) or cls.setup_logger(logger_name)

    @classmethod
    def update_log_level(cls, logger_name: str, level: int) -> None:
        logger = cls.get_logger(logger_name)
        logger.setLevel(level)
        for handler in logger.handlers:
            handler.setLevel(level)

    @classmethod
    def add_file_handler(cls, logger_name: str, filepath: str) -> None:
        logger = cls.get_logger(logger_name)
        target = str(Path(filepath).resolve())
        if any(getattr(handler, "baseFilename", None) == target for handler in logger.handlers):
            return
        handler = RotatingFileHandler(target, maxBytes=10 * 1024 * 1024, backupCount=3, encoding="utf-8")
        handler.setFormatter(logging.Formatter(cls.DEFAULT_CONFIG["log_format"]))
        handler.setLevel(logger.level)
        logger.addHandler(handler)


def setup_logger(logger_name: str = "SIASystem", **kwargs: Any) -> logging.Logger:
    return LoggerConfig.setup_logger(logger_name, kwargs)


def get_logger(logger_name: str = "SIASystem") -> logging.Logger:
    return LoggerConfig.get_logger(logger_name)


def setup_development_logger() -> logging.Logger:
    return LoggerConfig.setup_logger("SIASystem_Dev", {"log_level": logging.DEBUG})


def setup_production_logger() -> logging.Logger:
    return LoggerConfig.setup_logger("SIASystem_Prod", {"enable_console": False})


def setup_test_logger() -> logging.Logger:
    return LoggerConfig.setup_logger(
        "SIASystem_Test", {"log_level": logging.WARNING, "enable_file": False}
    )
