import os.path


def normpath(fs, path):
    return os.path.normpath(fs.getsyspath(path))
