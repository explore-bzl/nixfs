#!/usr/bin/env python3

import argparse
import ctypes
import logging
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import RLock, Condition

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn

def setup_environment(root, mount):
    """
    Prepares the environment by creating directories and a symlink.
    """
    os.makedirs(mount, exist_ok=True)
    os.makedirs("/nix", exist_ok=True)
    os.makedirs(os.path.join(root, "store"), exist_ok=True)
    symlink_path = os.path.join(root, "nix")
    if not os.path.isfile(symlink_path):
        os.symlink(root, symlink_path, target_is_directory=True)


class Loopback(LoggingMixIn, Operations):
    def __init__(self, root, nix_binary, cache_location):
        self.root = os.path.realpath(root)
        self.nix_binary = nix_binary
        self.cache_location = cache_location
        self.rwlock = RLock()
        self.processed_paths = set()  # Cache for successfully processed paths
        self.copy_condition = Condition(self.rwlock)
        self.nix_copy_futures = {}
        self.nix_executor = ThreadPoolExecutor(max_workers=10)

    def _full_path(self, partial):
        partial_path = Path(partial.lstrip("/"))
        path = os.path.join(self.root, partial_path)

        if len(partial_path.parts) <= 1 or partial_path.parts[0] != "store":
            return str(path)

        package_hash = partial_path.parts[1]
        with self.rwlock:
            if package_hash in self.processed_paths:
                return str(path)
            if package_hash not in self.nix_copy_futures:
                # Submit new nix copy task
                future = self.nix_executor.submit(
                    self._run_nix_copy_group, package_hash
                )
                self.nix_copy_futures[package_hash] = future
                future.add_done_callback(lambda f: self._mark_processed(package_hash))
            else:
                future = self.nix_copy_futures[package_hash]

        # Wait for the nix copy operation to complete for store paths asynchronously
        future.result().wait()

        return str(path)

    def _mark_processed(self, package_hash):
        with self.rwlock:
            self.processed_paths.add(package_hash)
            del self.nix_copy_futures[package_hash]

    def _run_nix_copy_group(self, package_hash):
        nix_store_path = os.path.join("/nix/store", package_hash)
        command = [
            "unshare",
            "-m",
            "sh",
            "-c",
            " ".join(["mount", "-n", "--bind", "/proc/self/cwd", "/nix"])
            + " ; "
            + " ".join(
                [
                    self.nix_binary,
                    "copy",
                    "--to",
                    self.root,
                    "--from",
                    self.cache_location,
                    nix_store_path,
                    "--extra-experimental-features",
                    "nix-command",
                ]
            ),
        ]
        env = {"NIX_IGNORE_SYMLINK_STORE": "1"}

        # Execute the subprocess in a non-blocking way
        process = subprocess.Popen(command, env=env)
        return process

    def __call__(self, op, path, *args):
        return super().__call__(op, self._full_path(path), *args)

    def access(self, path, mode):
        if not os.access(path, mode):
            raise FuseOSError(os.errno.EACCES)

    chmod = os.chmod
    chown = os.chown
    create = os.open

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

    def release(self, path, fh):
        return os.close(fh)

    def flush(self, path, fh):
        return os.fsync(fh)

    def fsync(self, path, datasync, fh):
        return os.fdatasync(fh) if datasync != 0 else os.fsync(fh)

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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Loopback Filesystem with Nix Integration"
    )
    parser.add_argument(
        "--root-dir", default="/true_nix", help="Root directory. Default: /true_nix"
    )
    parser.add_argument(
        "--mount-point", default="/root/nix", help="Mount point. Default: /nix"
    )
    parser.add_argument(
        "--nix-binary", default="/bin/nix", help="Nix binary path. Default: /bin/nix"
    )
    parser.add_argument(
        "--cache-location",
        default="https://cache.nixos.org",
        help="Nix cache URL. Default: https://cache.nixos.org",
    )
    args = parser.parse_args()

    setup_environment(args.root_dir, args.mount_point)

    logging.basicConfig(level=logging.INFO)
    fuse = FUSE(
        Loopback(args.root_dir, args.nix_binary, args.cache_location),
        args.mount_point,
        foreground=True,
        allow_other=True,
    )
