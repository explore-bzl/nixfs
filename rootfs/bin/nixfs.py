#!/usr/bin/env python3

import logging
import os
import subprocess
from errno import EACCES
from pathlib import Path
from threading import Lock

from fusepy import FUSE, FuseOSError, Operations, LoggingMixIn, fuse_get_context


class Loopback(LoggingMixIn, Operations):
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.rwlock = Lock()

    def _full_path(self, partial):
        partial_path = Path(partial.lstrip("/"))
        path = self.root / partial_path

        if not partial_path.parts[0] == "store" or path.exists():
            return str(path)

        uid, gid, pid = fuse_get_context()
        with open(f"/proc/{pid}/comm", mode="rb") as fd:
            content = fd.read().decode().split("\n")[0]
            if content.startswith("nix"):
                return str(path)

        subprocess.run(
            [
                "unshare",
                "-m",
                "sh",
                "-c",
                f"mount -n --bind /not_nix /nix; NIX_IGNORE_SYMLINK_STORE=1 nix copy --to {self.root} --from https://cache.nixos.org /nix/{partial_path} --extra-experimental-features nix-command",
            ],
            check=True,
        )

        return str(path)

    def __call__(self, op, path, *args):
        return super().__call__(op, self._full_path(path), *args)

    def access(self, path, mode):
        if not os.access(path, mode):
            raise FuseOSError(EACCES)

    chmod = os.chmod
    chown = os.chown

    def create(self, path, mode):
        return os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)

    def flush(self, path, fh):
        return os.fsync(fh)

    def fsync(self, path, datasync, fh):
        if datasync != 0:
            return os.fdatasync(fh)
        else:
            return os.fsync(fh)

    def getattr(self, path, fh=None):
        st = os.lstat(path)
        return {
            key: getattr(st, key)
            for key in (
                "st_atime",
                "st_ctime",
                "st_gid",
                "st_mode",
                "st_mtime",
                "st_nlink",
                "st_size",
                "st_uid",
            )
        }

    getxattr = None

    def link(self, target, source):
        return os.link(self.root / source, target)

    listxattr = None
    mkdir = os.mkdir
    mknod = os.mknod
    open = os.open

    def read(self, path, size, offset, fh):
        with self.rwlock:
            os.lseek(fh, offset, os.SEEK_SET)
            return os.read(fh, size)

    def readdir(self, path, fh):
        return [".", ".."] + os.listdir(path)

    readlink = os.readlink

    def release(self, path, fh):
        return os.close(fh)

    def rename(self, old, new):
        return os.rename(old, self.root / new)

    rmdir = os.rmdir

    def statfs(self, path):
        stv = os.statvfs(path)
        return {
            key: getattr(stv, key)
            for key in (
                "f_bavail",
                "f_bfree",
                "f_blocks",
                "f_bsize",
                "f_favail",
                "f_ffree",
                "f_files",
                "f_flag",
                "f_frsize",
                "f_namemax",
            )
        }

    def symlink(self, target, source):
        return os.symlink(source, target)

    def truncate(self, path, length, fh=None):
        with open(path, "r+") as f:
            f.truncate(length)

    unlink = os.unlink
    utimens = os.utime

    def write(self, path, data, offset, fh):
        with self.rwlock:
            os.lseek(fh, offset, os.SEEK_SET)
            return os.write(fh, data)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    parser.add_argument("mount")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)
    fuse = FUSE(Loopback(args.root), args.mount, foreground=True, allow_other=True)
