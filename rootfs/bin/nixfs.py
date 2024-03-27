#!/usr/bin/env python3

import argparse
import ctypes
import logging
import os
import subprocess
from pathlib import Path
from threading import Lock

from fusepy import FUSE, FuseOSError, Operations, LoggingMixIn, fuse_get_context

# Constants for system calls and flags
UNSHARE_SYSCALL_NUMBER = 272  # Syscall number for unshare (x86_64)
CLONE_NEWNS = 0x00020000       # Flag for creating a new mount namespace

# Load libc for system call access
libc = ctypes.CDLL("libc.so.6", use_errno=True)

def setup_environment(root, mount):
    """
    Prepares the environment by creating directories and a symlink.
    """
    os.makedirs(mount, exist_ok=True)
    os.makedirs("/not_nix", exist_ok=True)
    store_path = os.path.join(root, "store")
    os.makedirs(store_path, exist_ok=True)
    symlink_path = os.path.join(root, "nix")
    if not os.path.exists(symlink_path):
        os.symlink(root, symlink_path)

class Loopback(LoggingMixIn, Operations):
    """
    Implements a loopback filesystem using FUSE.
    """
    def __init__(self, root, nix_binary, cache_location):
        self.root = Path(root).resolve()
        self.nix_binary = nix_binary
        self.cache_location = cache_location
        self.rwlock = Lock()

    def _full_path(self, partial):
        """
        Constructs the full path for a given partial path.
        """
        partial_path = Path(partial.lstrip("/"))
        path = self.root / partial_path

        if (partial_path.parts and partial_path.parts[0] != "store") \
                or path.exists():
            return str(path)

        uid, gid, pid = fuse_get_context()
        with open(f"/proc/{pid}/comm", mode="rb") as fd:
            if fd.read().decode().startswith("nix"):
                return str(path)

        # Create a new mount namespace
        result = libc.syscall(UNSHARE_SYSCALL_NUMBER, CLONE_NEWNS)
        if result != 0:
            errno = ctypes.get_errno()
            raise OSError(errno, os.strerror(errno))

        env = os.environ.copy()
        env["NIX_IGNORE_SYMLINK_STORE"] = "1"

        try:
            subprocess.run(["mount", "-n", "--bind", "/not_nix", "/nix"],
                           check=True, text=True)
            subprocess.run([
                self.nix_binary, "copy", "--to", str(self.root),
                "--from", self.cache_location,
                f"/nix/{path.relative_to(self.root)}",
                "--extra-experimental-features", "nix-command"
            ], check=True, text=True, env=env)
        except subprocess.CalledProcessError as e:
            print(f"Error executing command: {e}")

        return str(path)

    # The rest of the methods implement the filesystem operations.
    # These methods are mostly straightforward wrappers around the corresponding os module functions.

    def __call__(self, op, path, *args):
        return super().__call__(op, self._full_path(path), *args)

    def access(self, path, mode):
        if not os.access(path, mode):
            raise FuseOSError(EACCES)

    chmod = os.chmod
    chown = os.chown
    create = os.open

    def getattr(self, path, fh=None):
        st = os.lstat(path)
        return {key: getattr(st, key) for key in (
            "st_atime",
            "st_ctime",
            "st_gid",
            "st_mode",
            "st_mtime",
            "st_nlink",
            "st_size",
            "st_uid")}

    def release(self, path, fh):
        return os.close(fh)

    def flush(self, path, fh):
        return os.fsync(fh)

    def fsync(self, path, datasync, fh):
        if datasync != 0:
            return os.fdatasync(fh)
        else:
            return os.fsync(fh)

    getxattr = None
    link = os.link
    listxattr = None
    mkdir = os.mkdir
    mknod = os.mknod
    open = os.open
    readlink = os.readlink
    rename = os.rename
    rmdir = os.rmdir
    symlink = os.symlink

    def truncate(self, path, length, fh=None):
        with open(path, "r+") as f:
            f.truncate(length)

    unlink = os.unlink
    utimens = os.utime

    def read(self, path, size, offset, fh):
        with self.rwlock:
            os.lseek(fh, offset, os.SEEK_SET)
            return os.read(fh, size)

    def readdir(self, path, fh):
        return [".", ".."] + os.listdir(path)

    def write(self, path, data, offset, fh):
        with self.rwlock:
            os.lseek(fh, offset, os.SEEK_SET)
            return os.write(fh, data)

    def statfs(self, path):
        stv = os.statvfs(path)
        return {key: getattr(stv, key) for key in (
            "f_bavail",
            "f_bfree",
            "f_blocks",
            "f_bsize",
            "f_favail",
            "f_ffree",
            "f_files",
            "f_flag",
            "f_frsize",
            "f_namemax")}

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Loopback Filesystem with Nix Integration")
    parser.add_argument("--root-dir", default="/true_nix",
                        help="Root directory. Default: /true_nix")
    parser.add_argument("--mount-point", default="/nix",
                        help="Mount point. Default: /nix")
    parser.add_argument("--nix-binary", default="/bin/nix",
                        help="Nix binary path. Default: /bin/nix")
    parser.add_argument("--cache-location", default="https://cache.nixos.org",
                        help="Nix cache URL. Default: https://cache.nixos.org")
    args = parser.parse_args()

    setup_environment(args.root_dir, args.mount_point)

    logging.basicConfig(level=logging.INFO)
    fuse = FUSE(Loopback(args.root_dir, args.nix_binary, args.cache_location),
                args.mount_point, foreground=True, allow_other=True)
