# scores.py
"""
Persistent high scores and settings, stored in a small JSON file.

Design goals:
    * **Never lose data**: writes are atomic (temp file + ``os.replace``), so a
      crash or power cut in the middle of a save can't corrupt the file.
    * **Never crash the game**: a corrupted file is renamed to
      ``scores.json.corrupt`` and a fresh one is started.
    * **Decoupled**: games only receive two callables, ``load_scores()`` and
      ``save_scores(dict)``, and never know where/how data is stored. This makes
      them trivial to test with an in-memory store.

File location (first match wins):
    1. the path in the ``RETRO_ARCADE_SCORES`` environment variable;
    2. ``scores.json`` next to the program (source folder or the .exe folder);
    3. if that folder is read-only (e.g. ``C:\\Program Files``), a per-user
       folder: ``%APPDATA%\\RetroArcadeCollection`` on Windows,
       ``~/.local/share/retro-arcade-collection`` elsewhere.

File format::

    {
      "version": 1,
      "scores":   {"snake": 120, "tetris": 4200, ...},
      "settings": {"sound": true, "crt": true}
    }
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

FILE_NAME = "scores.json"
ENV_VAR = "RETRO_ARCADE_SCORES"
SCHEMA_VERSION = 1

LoadFn = Callable[[], dict]
SaveFn = Callable[[dict], None]


def app_dir() -> Path:
    """Folder of the running program (works from source and from PyInstaller)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def user_data_dir() -> Path:
    """Per-user writable folder used when the program folder is read-only."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "RetroArcadeCollection"
    base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    return base / "retro-arcade-collection"


_writable_cache: dict[Path, bool] = {}


def _is_writable(folder: Path) -> bool:
    """True if we can create files in ``folder`` (checked once per folder)."""
    if folder not in _writable_cache:
        try:
            folder.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=folder, delete=True):
                pass
            _writable_cache[folder] = True
        except OSError:
            _writable_cache[folder] = False
    return _writable_cache[folder]


def default_path() -> Path:
    """Resolve where ``scores.json`` should live (see module docstring)."""
    override = os.environ.get(ENV_VAR)
    if override:
        return Path(override).expanduser()
    primary = app_dir()
    if _is_writable(primary):
        return primary / FILE_NAME
    return user_data_dir() / FILE_NAME


class ScoreStore:
    """Read/write access to the JSON file. Cheap to create, safe to share."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path: Path = Path(path) if path is not None else default_path()

    # ------------------------------------------------------------------ io
    def _read_all(self) -> dict[str, Any]:
        """Return the whole document, recovering from missing/corrupt files."""
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return {"version": SCHEMA_VERSION, "scores": {}, "settings": {}}
        except OSError:
            return {"version": SCHEMA_VERSION, "scores": {}, "settings": {}}
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError("root is not an object")
        except (ValueError, json.JSONDecodeError):
            self._quarantine()
            return {"version": SCHEMA_VERSION, "scores": {}, "settings": {}}
        # Legacy format: a flat {"snake": 10, ...} dictionary.
        if "scores" not in data and "settings" not in data:
            data = {"scores": data, "settings": {}}
        data.setdefault("scores", {})
        data.setdefault("settings", {})
        data["version"] = SCHEMA_VERSION
        return data

    def _quarantine(self) -> None:
        """Move a corrupted file aside so the player can inspect it later."""
        try:
            os.replace(self.path, self.path.with_name(self.path.name + ".corrupt"))
        except OSError:
            pass

    def _write_all(self, data: dict[str, Any]) -> None:
        """Atomically write the whole document."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=".scores-", suffix=".tmp", dir=self.path.parent
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, sort_keys=True, ensure_ascii=False)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, self.path)
        except BaseException:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    # -------------------------------------------------------------- scores
    def load_scores(self) -> dict[str, Any]:
        """Return a *copy* of the scores dictionary."""
        return dict(self._read_all()["scores"])

    def save_scores(self, scores: dict[str, Any]) -> None:
        """Merge ``scores`` into the file (other keys are preserved)."""
        try:
            data = self._read_all()
            data["scores"].update(scores)
            self._write_all(data)
        except OSError as exc:  # disk full, permissions... keep playing anyway
            print(f"[scores] Impossibile salvare i punteggi: {exc}", file=sys.stderr)

    # ------------------------------------------------------------ settings
    def get_setting(self, key: str, default: Any = None) -> Any:
        return self._read_all()["settings"].get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        try:
            data = self._read_all()
            data["settings"][key] = value
            self._write_all(data)
        except OSError as exc:
            print(f"[scores] Impossibile salvare le impostazioni: {exc}", file=sys.stderr)

    def callables(self) -> tuple[LoadFn, SaveFn]:
        """Return the ``(load_scores, save_scores)`` pair given to games."""
        return self.load_scores, self.save_scores


def memory_store(initial: dict | None = None) -> tuple[LoadFn, SaveFn]:
    """An in-memory ``(load, save)`` pair - handy for tests and quick demos."""
    box: dict[str, Any] = dict(initial or {})

    def load() -> dict:
        return dict(box)

    def save(new: dict) -> None:
        box.update(new)

    return load, save


def resolve(load_scores: LoadFn | None, save_scores: SaveFn | None) -> tuple[LoadFn, SaveFn]:
    """
    Give games a working store even when they are started on their own
    (``python snake.py``): missing callables fall back to the JSON file.
    """
    if load_scores is not None and save_scores is not None:
        return load_scores, save_scores
    return ScoreStore().callables()


def record_best(
    load_scores: LoadFn,
    save_scores: SaveFn,
    key: str,
    value: float,
    lower_is_better: bool = False,
) -> bool:
    """
    Store ``value`` under ``key`` if it beats the current record.

    Args:
        load_scores / save_scores: The store callables.
        key: Score name, e.g. ``"snake"`` or ``"maze_time_medium"``.
        value: The new result.
        lower_is_better: True for times and move counts.

    Returns:
        True if ``value`` is a new record (and it was saved).
    """
    try:
        current = load_scores().get(key)
    except Exception:
        current = None
    if current is None:
        better = value > 0 or lower_is_better
    elif lower_is_better:
        better = value < current
    else:
        better = value > current
    if better:
        try:
            save_scores({key: value})
        except Exception:
            return False
    return better


def get_best(load_scores: LoadFn, key: str, default: Any = None) -> Any:
    """Read a single record, never raising."""
    try:
        return load_scores().get(key, default)
    except Exception:
        return default
