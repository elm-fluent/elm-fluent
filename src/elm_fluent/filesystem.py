"""Simple filesystem abstraction replacing pyfilesystem2.

Provides a thin wrapper around pathlib/os operations, supporting the
"chrooted" sub-filesystem pattern used by the rest of the codebase.
"""

import fnmatch
import os
import pathlib
from collections.abc import Iterator
from dataclasses import dataclass


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
                rest = fpath[len(prefix) :]
                name = rest.split("/")[0]
                if name not in seen:
                    seen.add(name)
                    # Check if it's a directory
                    is_dir = "/" in rest
                    yield DirEntry(name=name, is_dir=is_dir)
        # Check directories
        for dpath in self._dirs:
            if dpath.startswith(prefix):
                rest = dpath[len(prefix) :]
                name = rest.split("/")[0]
                if name and name not in seen:
                    seen.add(name)
                    yield DirEntry(name=name, is_dir=True)

    def opendir(self, path: str) -> "MemoryFileSystem":
        """Return a view rooted at the given subdirectory."""
        if path == ".":
            return self
        if path.endswith("/"):
            path = path.rstrip("/")
        if not path.startswith("/"):
            path = "/" + path
        files = {name[len(path) :]: data for name, data in self._files.items() if name.startswith(path)}
        dirs = {d[len(path) :] for d in self._dirs if d.startswith(path)}
        return MemoryFileSystem(files=files, dirs=dirs)

    def glob(self, pattern: str) -> Iterator[GlobMatch]:
        for fpath in sorted(self._files.keys()):
            # Match against relative path from root
            rel = fpath.lstrip("/")
            if fnmatch.fnmatch(rel, pattern):
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
        yield from sorted(self._files.keys())
