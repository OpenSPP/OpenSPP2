import mimetypes
import os
import shutil
import tempfile

from odoo.tools.mimetypes import guess_mimetype


def check_name(name):
    """Validate a candidate filename.

    Reject absolute paths and any name containing path separators to
    prevent path traversal outside the temporary directory.
    """
    # Disallow absolute paths and directory traversal
    if os.path.isabs(name):
        return False
    normalized = name.replace("\\", "/")
    if "/" in normalized:
        return False

    tmp_dir = tempfile.mkdtemp()
    try:
        # Name validation above rejects absolute paths and any path
        # separators, so this join stays confined to tmp_dir.
        open(
            os.path.join(tmp_dir, name), "a"
        ).close()  # nosemgrep: odoo-path-traversal - Name is validated to reject absolute paths and path separators before joining.
    except OSError:
        return False
    finally:
        shutil.rmtree(tmp_dir)
    return True


def compute_name(name, suffix, escape_suffix):
    if escape_suffix:
        name, extension = os.path.splitext(name)
        return f"{name}({suffix}){extension}"
    else:
        return f"{name}({suffix})"


def unique_name(name, names, escape_suffix=False):
    if name not in names:
        return name
    else:
        suffix = 1
        name = compute_name(name, suffix, escape_suffix)
        while name in names:
            suffix += 1
            name = compute_name(name, suffix, escape_suffix)
        return name


def guess_extension(filename=None, mimetype=None, binary=None):
    extension = filename and os.path.splitext(filename)[1][1:].strip().lower()
    if not extension and mimetype and mimetype != "application/x-empty":
        extension = mimetypes.guess_extension(mimetype)[1:].strip().lower()
    if not extension and binary:
        mimetype = guess_mimetype(binary, default="")
        extension = mimetypes.guess_extension(mimetype)[1:].strip().lower()
    return extension
