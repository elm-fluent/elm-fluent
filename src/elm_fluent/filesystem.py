"""Simple filesystem abstraction replacing pyfilesystem2.

Provides a thin wrapper around pathlib/os operations, supporting the
"chrooted" sub-filesystem pattern used by the rest of the codebase.
"""

import fnmatch
import os
import pathlib
import re
from dataclasses import dataclass
from typing import Iterator


def _glob_to_regex(pattern: str) -> re.Pattern[str]:
    """Convert a glob pattern (with ** support) to a regex.

    Handles ** as matching zero or more path segments.
    """
    # Split on ** to handle recursive matching
    parts = pattern.split("**")
    regex_parts = []
    for i, part in enumerate(parts):
        # Strip leading/trailing path separators from inner parts
        if i > 0:
            part = part.lstrip("/")
        if i < len(parts) - 1:
            part = part.rstrip("/")
        # Convert fnmatch pattern to regex (without the \Z anchor)
        translated = fnmatch.translate(part)
        # Remove the trailing \Z (end anchor)
        translated = translated.removesuffix(r"\Z")
        regex_parts.append(translated)
    # Join with pattern that matches any path segments (including empty)
    result = r"(?:.*/)?" .join(regex_parts) + r"\Z"
    return re.compile(result)


@dataclass
class DirEntry:
    """Simplified directory entry, similar to os.DirEntry."""

    name: str
    is_dir: bool


@dataclass
class GlobMatch:
    """Result of a glob operation, with a path relative to the filesystem root."""

    path: str


class FileSystem:
    """A filesystem rooted at a given directory.

    All paths are relative to root_path. This replaces pyfilesystem2's
    OSFS and the opendir() chaining pattern.
    """

    def __init__(self, root_path: str | os.PathLike[str]) -> None:
        self._root = pathlib.Path(root_path).resolve()

    def _resolve(self, path: str) -> pathlib.Path:
        return self._root / path

    def exists(self, path: str) -> bool:
        return self._resolve(path).exists()

    def isdir(self, path: str) -> bool:
        return self._resolve(path).is_dir()

    def open(self, path: str, mode: str = "r"):
        return self._resolve(path).open(mode)

    def makedirs(self, path: str) -> None:
        self._resolve(path).mkdir(parents=True, exist_ok=True)

    def makedir(self, path: str) -> "FileSystem":
        """Create a single directory and return a FileSystem rooted there."""
        resolved = self._resolve(path)
        resolved.mkdir(exist_ok=True)
        return FileSystem(resolved)

    def scandir(self, path: str) -> Iterator[DirEntry]:
        resolved = self._resolve(path)
        for entry in os.scandir(resolved):
            yield DirEntry(name=entry.name, is_dir=entry.is_dir())

    def opendir(self, path: str) -> "FileSystem":
        """Return a new FileSystem rooted at the given subdirectory."""
        return FileSystem(self._resolve(path))

    def glob(self, pattern: str) -> Iterator[GlobMatch]:
        for p in self._root.glob(pattern):
            # Return path relative to root, with leading /
            rel = "/" + str(p.relative_to(self._root))
            yield GlobMatch(path=rel)

    def getsyspath(self, path: str) -> str:
        return str(self._resolve(path))

    def writetext(self, path: str, text: str) -> None:
        resolved = self._resolve(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(text)

    def readtext(self, path: str) -> str:
        return self._resolve(path).read_text()

    def walk_files(self) -> Iterator[str]:
        """Yield all file paths relative to root, with leading /."""
        for dirpath, _dirnames, filenames in os.walk(self._root):
            for filename in filenames:
                full = pathlib.Path(dirpath) / filename
                rel = "/" + str(full.relative_to(self._root))
                yield rel


class MemoryFileSystem:
    """In-memory filesystem for testing.

    Implements the same interface as FileSystem but stores everything
    in dictionaries.
    """

    def __init__(self, files: dict[str, bytes | str] | None = None, dirs: set[str] | None = None) -> None:
        self._files: dict[str, bytes | str] = dict(files) if files else {}
        self._dirs: set[str] = set(dirs) if dirs else {"/"}

    def _normpath(self, path: str) -> str:
        """Normalize path to always start with / and have no trailing /."""
        if not path.startswith("/"):
            path = "/" + path
        path = os.path.normpath(path)
        return path

    def exists(self, path: str) -> bool:
        path = self._normpath(path)
        return path in self._files or path in self._dirs

    def isdir(self, path: str) -> bool:
        return self._normpath(path) in self._dirs

    def open(self, path: str, mode: str = "r"):
        import io

        path = self._normpath(path)
        if "r" in mode:
            if path not in self._files:
                raise FileNotFoundError(path)
            data = self._files[path]
            if "b" in mode:
                if isinstance(data, str):
                    data = data.encode("utf-8")
                return io.BytesIO(data)
            else:
                if isinstance(data, bytes):
                    data = data.decode("utf-8")
                return io.StringIO(data)
        elif "w" in mode:
            # Ensure parent directory exists
            parent = os.path.dirname(path)
            if parent and parent not in self._dirs:
                raise FileNotFoundError(f"Parent directory does not exist: {parent}")

            class _Writer:
                def __init__(self_w):
                    if "b" in mode:
                        self_w._buf = io.BytesIO()
                    else:
                        self_w._buf = io.StringIO()

                def __enter__(self_w):
                    return self_w

                def __exit__(self_w, *args):
                    self._files[path] = self_w._buf.getvalue()

                def write(self_w, data):
                    self_w._buf.write(data)

            return _Writer()
        else:
            raise ValueError(f"Unsupported mode: {mode}")

    def makedirs(self, path: str) -> None:
        path = self._normpath(path)
        parts = path.split("/")
        for i in range(1, len(parts) + 1):
            self._dirs.add("/".join(parts[:i]) or "/")

    def makedir(self, path: str) -> "MemoryFileSystem":
        path = self._normpath(path)
        self._dirs.add(path)
        # Return a sub-filesystem view
        return self.opendir(path)

    def scandir(self, path: str) -> Iterator[DirEntry]:
        path = self._normpath(path)
        prefix = path.rstrip("/") + "/"
        seen = set()
        # Check files
        for fpath in self._files:
            if fpath.startswith(prefix):
                rest = fpath[len(prefix):]
                name = rest.split("/")[0]
                if name not in seen:
                    seen.add(name)
                    # Check if it's a directory
                    is_dir = "/" in rest
                    yield DirEntry(name=name, is_dir=is_dir)
        # Check directories
        for dpath in self._dirs:
            if dpath.startswith(prefix):
                rest = dpath[len(prefix):]
                name = rest.split("/")[0]
                if name and name not in seen:
                    seen.add(name)
                    yield DirEntry(name=name, is_dir=True)

    def opendir(self, path: str) -> "MemoryFileSystem":
        """Return a view rooted at the given subdirectory."""
        return _MemorySubFS(self, self._normpath(path))

    def glob(self, pattern: str) -> Iterator[GlobMatch]:
        regex = _glob_to_regex(pattern)
        for fpath in sorted(self._files.keys()):
            # Match against relative path from root
            rel = fpath.lstrip("/")
            if regex.match(rel):
                yield GlobMatch(path=fpath)

    def getsyspath(self, path: str) -> str:
        return self._normpath(path)

    def writetext(self, path: str, text: str) -> None:
        path = self._normpath(path)
        self._files[path] = text

    def readtext(self, path: str) -> str:
        path = self._normpath(path)
        if path not in self._files:
            raise FileNotFoundError(path)
        data = self._files[path]
        if isinstance(data, bytes):
            return data.decode("utf-8")
        return data

    def walk_files(self) -> Iterator[str]:
        for fpath in sorted(self._files.keys()):
            yield fpath


class _MemorySubFS(MemoryFileSystem):
    """A view into a MemoryFileSystem rooted at a subdirectory."""

    def __init__(self, parent: MemoryFileSystem, root: str) -> None:
        # Don't call super().__init__() - we delegate to parent
        self._parent = parent
        self._root_prefix = root.rstrip("/")

    def _to_parent_path(self, path: str) -> str:
        path = path.lstrip("/")
        if path:
            return self._root_prefix + "/" + path
        return self._root_prefix

    def exists(self, path: str) -> bool:
        return self._parent.exists(self._to_parent_path(path))

    def isdir(self, path: str) -> bool:
        return self._parent.isdir(self._to_parent_path(path))

    def open(self, path: str, mode: str = "r"):
        return self._parent.open(self._to_parent_path(path), mode)

    def makedirs(self, path: str) -> None:
        self._parent.makedirs(self._to_parent_path(path))

    def makedir(self, path: str) -> "MemoryFileSystem":
        return self._parent.makedir(self._to_parent_path(path))

    def scandir(self, path: str) -> Iterator[DirEntry]:
        return self._parent.scandir(self._to_parent_path(path))

    def opendir(self, path: str) -> "MemoryFileSystem":
        return self._parent.opendir(self._to_parent_path(path))

    def glob(self, pattern: str) -> Iterator[GlobMatch]:
        regex = _glob_to_regex(pattern)
        prefix = self._root_prefix + "/"
        for fpath in sorted(self._parent._files.keys()):
            if fpath.startswith(prefix):
                rel = fpath[len(prefix):]
                if regex.match(rel):
                    yield GlobMatch(path="/" + rel)

    def getsyspath(self, path: str) -> str:
        return self._to_parent_path(path)

    def writetext(self, path: str, text: str) -> None:
        self._parent.writetext(self._to_parent_path(path), text)

    def readtext(self, path: str) -> str:
        return self._parent.readtext(self._to_parent_path(path))

    def walk_files(self) -> Iterator[str]:
        prefix = self._root_prefix + "/"
        for fpath in sorted(self._parent._files.keys()):
            if fpath.startswith(prefix):
                yield "/" + fpath[len(prefix):]
