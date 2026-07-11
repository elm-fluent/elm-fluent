"""Tests for the filesystem abstraction module."""

import os
import tempfile

import pytest

from elm_fluent.filesystem import FileSystem, MemoryFileSystem, _glob_to_regex


class TestGlobToRegex:
    def test_simple_extension(self):
        regex = _glob_to_regex("*.ftl")
        assert regex.match("foo.ftl")
        assert regex.match("bar.ftl")
        assert not regex.match("foo.txt")

    def test_recursive_glob(self):
        regex = _glob_to_regex("**/*.ftl")
        assert regex.match("foo.ftl")
        assert regex.match("a/foo.ftl")
        assert regex.match("a/b/foo.ftl")
        assert regex.match("a/b/c/foo.ftl")
        assert not regex.match("foo.txt")
        assert not regex.match("a/foo.txt")


class TestMemoryFileSystem:
    def test_makedir_and_exists(self):
        fs = MemoryFileSystem()
        assert fs.exists("/")
        fs.makedir("mydir")
        assert fs.exists("mydir")
        assert fs.isdir("mydir")

    def test_writetext_and_readtext(self):
        fs = MemoryFileSystem()
        fs.makedir("dir")
        fs.writetext("dir/file.txt", "hello")
        assert fs.readtext("dir/file.txt") == "hello"

    def test_readtext_not_found(self):
        fs = MemoryFileSystem()
        with pytest.raises(FileNotFoundError):
            fs.readtext("nonexistent")

    def test_open_read_binary(self):
        fs = MemoryFileSystem()
        fs.writetext("/file.txt", "hello")
        with fs.open("/file.txt", "rb") as f:
            assert f.read() == b"hello"

    def test_open_write_binary(self):
        fs = MemoryFileSystem()
        fs.makedir("/")
        with fs.open("/file.bin", "wb") as f:
            f.write(b"binary data")
        assert fs.readtext("/file.bin") == "binary data"

    def test_makedirs(self):
        fs = MemoryFileSystem()
        fs.makedirs("a/b/c")
        assert fs.isdir("a")
        assert fs.isdir("a/b")
        assert fs.isdir("a/b/c")

    def test_scandir(self):
        fs = MemoryFileSystem()
        fs.makedir("root")
        fs.makedir("root/sub1")
        fs.makedir("root/sub2")
        fs.writetext("root/file.txt", "x")
        entries = sorted(fs.scandir("root"), key=lambda e: e.name)
        names = [e.name for e in entries]
        assert "file.txt" in names
        assert "sub1" in names
        assert "sub2" in names

    def test_opendir(self):
        fs = MemoryFileSystem()
        fs.makedir("root")
        fs.makedir("root/sub")
        fs.writetext("root/sub/file.txt", "content")

        sub_fs = fs.opendir("root")
        assert sub_fs.exists("sub")
        assert sub_fs.readtext("sub/file.txt") == "content"

    def test_opendir_chained(self):
        fs = MemoryFileSystem()
        fs.makedir("a")
        fs.makedir("a/b")
        fs.writetext("a/b/file.ftl", "msg = Hello")

        sub = fs.opendir("a").opendir("b")
        assert sub.exists("file.ftl")
        assert sub.readtext("file.ftl") == "msg = Hello"

    def test_glob(self):
        fs = MemoryFileSystem()
        fs.makedir("dir")
        fs.writetext("dir/a.ftl", "x")
        fs.writetext("dir/b.txt", "y")
        matches = [m.path for m in fs.glob("**/*.ftl")]
        assert "/dir/a.ftl" in matches
        assert "/dir/b.txt" not in matches

    def test_glob_in_subfs(self):
        fs = MemoryFileSystem()
        fs.makedir("locales")
        fs.makedir("locales/en")
        fs.writetext("locales/en/foo.ftl", "foo = Foo")
        fs.writetext("locales/en/bar.ftl", "bar = Bar")

        sub = fs.opendir("locales").opendir("en")
        matches = sorted(m.path for m in sub.glob("**/*.ftl"))
        assert matches == ["/bar.ftl", "/foo.ftl"]

    def test_walk_files(self):
        fs = MemoryFileSystem()
        fs.writetext("/a.txt", "x")
        fs.writetext("/dir/b.txt", "y")
        files = sorted(fs.walk_files())
        assert files == ["/a.txt", "/dir/b.txt"]

    def test_walk_files_in_subfs(self):
        fs = MemoryFileSystem()
        fs.writetext("/root/a.txt", "x")
        fs.writetext("/root/sub/b.txt", "y")
        fs.writetext("/other/c.txt", "z")

        sub = fs.opendir("root")
        files = sorted(sub.walk_files())
        assert files == ["/a.txt", "/sub/b.txt"]

    def test_opendir_dot(self):
        """opendir('.') should give access to same files."""
        fs = MemoryFileSystem()
        fs.makedir("locales")
        fs.writetext("locales/file.ftl", "x")

        sub = fs.opendir(".")
        assert sub.exists("locales")
        assert sub.isdir("locales")


class TestFileSystem:
    def test_basic_operations(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fs = FileSystem(tmpdir)
            assert fs.exists(".")
            assert fs.isdir(".")

            # Write and read
            fs.writetext("test.txt", "hello world")
            assert fs.exists("test.txt")
            assert fs.readtext("test.txt") == "hello world"

    def test_makedirs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fs = FileSystem(tmpdir)
            fs.makedirs("a/b/c")
            assert fs.isdir("a/b/c")

    def test_opendir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fs = FileSystem(tmpdir)
            fs.makedirs("sub")
            fs.writetext("sub/file.txt", "content")

            sub_fs = fs.opendir("sub")
            assert sub_fs.exists("file.txt")
            assert sub_fs.readtext("file.txt") == "content"

    def test_scandir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fs = FileSystem(tmpdir)
            os.makedirs(os.path.join(tmpdir, "dir1"))
            os.makedirs(os.path.join(tmpdir, "dir2"))
            with open(os.path.join(tmpdir, "file.txt"), "w") as f:
                f.write("x")

            entries = sorted(fs.scandir("."), key=lambda e: e.name)
            names = [e.name for e in entries]
            assert "dir1" in names
            assert "dir2" in names
            assert "file.txt" in names

    def test_glob(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fs = FileSystem(tmpdir)
            fs.makedirs("sub")
            fs.writetext("sub/a.ftl", "x")
            fs.writetext("sub/b.txt", "y")

            matches = [m.path for m in fs.glob("**/*.ftl")]
            assert "/sub/a.ftl" in matches

    def test_walk_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fs = FileSystem(tmpdir)
            fs.writetext("a.txt", "x")
            fs.makedirs("sub")
            fs.writetext("sub/b.txt", "y")

            files = sorted(fs.walk_files())
            assert "/a.txt" in files
            assert "/sub/b.txt" in files

    def test_getsyspath(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fs = FileSystem(tmpdir)
            syspath = fs.getsyspath("some/path")
            assert syspath == os.path.join(os.path.realpath(tmpdir), "some/path")

    def test_open_binary(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            fs = FileSystem(tmpdir)
            with fs.open("test.bin", "wb") as f:
                f.write(b"binary data")
            with fs.open("test.bin", "rb") as f:
                assert f.read() == b"binary data"
