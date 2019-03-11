from __future__ import absolute_import, unicode_literals

import os.path


def normpath(fs, path):
    return os.path.normpath(fs.getsyspath(path))
