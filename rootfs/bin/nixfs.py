#!/usr/local/bin/python

import argparse, contextlib, email.parser, email.policy, errno, logging, os, os.path, struct, sys, tempfile
from functools import lru_cache
from pathlib import Path
from threading import RLock
from fuse import FUSE, FuseOSError, Operations, LoggingMixIn
from urllib3 import PoolManager
from concurrent.futures import ThreadPoolExecutor


class URLHandler:
    http_pool = PoolManager()

    @staticmethod
    def get_ok(url):
        response = URLHandler.http_pool.request("GET", url, preload_content=False)
        if 300 <= response.status < 400:
            redir_url = response.headers["Location"]
            return URLHandler.get_ok(redir_url)
        if response.status < 200 or response.status >= 400:
            raise Exception(f"{url} status {response.status} not ok")
        return response


class NarReader:
    narinfo_parser = email.parser.BytesHeaderParser(policy=email.policy.strict)

    @staticmethod
    def basename_hash(basename):
        return basename[:32]

    @staticmethod
    def read_limit(r, size):
        return r.read1(size)

    @staticmethod
    def read_exact(r, size):
        piece = r.read1(size)
        piece_len = len(piece)
        if piece_len == size:
            return piece
        remaining = size - piece_len
        pieces = [piece]
        while remaining:
            piece = r.read1(remaining)
            pieces.append(piece)
            remaining -= len(piece)
        return b"".join(pieces)

    @staticmethod
    def skip_exact(r, size):
        remaining = size
        while remaining:
            piece = r.read1(remaining)
            remaining -= len(piece)

    @staticmethod
    def read_int(r):
        b = NarReader.read_exact(r, 8)
        return struct.unpack("<Q", b)[0]

    @staticmethod
    def skip_padding(r, length):
        NarReader.skip_exact(r, 8 - (length & 7) if length & 7 else 0)

    @staticmethod
    def read_bytes(r):
        length = NarReader.read_int(r)
        if not length:
            return b""
        b = NarReader.read_exact(r, length)
        NarReader.skip_padding(r, length)
        return b

    @staticmethod
    def generate_binary(r):
        length = NarReader.read_int(r)
        remaining = length
        while remaining:
            piece = NarReader.read_limit(r, remaining)
            yield piece
            remaining -= len(piece)
        NarReader.skip_padding(r, length)

    @staticmethod
    def expect_bytes(r, expected):
        b = NarReader.read_bytes(r)
        if b != expected:
            raise Exception("unexpected %r, expected %r" % (b, expected))

    @staticmethod
    def generate_pair_keys(r):
        NarReader.expect_bytes(r, b"(")
        while True:
            k = NarReader.read_bytes(r)
            if k == b")":
                break
            yield k

    @staticmethod
    def unpack_dir_entry(dst, r):
        name = None
        for k in NarReader.generate_pair_keys(r):
            if k == b"name":
                name = NarReader.read_bytes(r)
            elif k == b"node":
                NarReader.unpack_node(os.path.join(dst, str(name, "utf-8")), r)
            else:
                raise Exception("dir entry unrecognized key %r" % k)

    @staticmethod
    def unpack_node(dst, r):
        type = None
        executable = False
        for k in NarReader.generate_pair_keys(r):
            if k == b"type":
                type = NarReader.read_bytes(r)
                if type == b"regular":
                    pass
                elif type == b"symlink":
                    pass
                elif type == b"directory":
                    os.mkdir(dst)
                else:
                    raise Exception("unrecognized type %r" % type)
            elif k == b"executable":
                NarReader.expect_bytes(r, b"")
                executable = True
            elif k == b"contents":
                dst_fd = os.open(
                    dst, os.O_WRONLY | os.O_CREAT, 0o777 if executable else 0o666
                )
                for b in NarReader.generate_binary(r):
                    os.write(dst_fd, b)
                os.close(dst_fd)
            elif k == b"target":
                target = NarReader.read_bytes(r)
                os.symlink(target, dst)
            elif k == b"entry":
                NarReader.unpack_dir_entry(dst, r)
            else:
                raise Exception("node unrecognized key %r" % k)

    @staticmethod
    def unpack(dst, reader):
        NarReader.expect_bytes(reader, b"nix-archive-1")
        NarReader.unpack_node(dst, reader)


class DecompressReader:
    def __init__(self, r, decompressor):
        self.r = r
        self.decompressor = decompressor

    def read1(self, size):
        while self.decompressor.needs_input:
            piece_in = self.r.read1(8192)
            piece = self.decompressor.decompress(piece_in, size)
            if piece:
                return piece
        piece = self.decompressor.decompress(b"", size)
        return piece

    def finish(self):
        piece_in = self.r.read()
        if not self.decompressor.eof:
            self.decompressor.decompress(piece_in)

    def close(self):
        self.r.close()


class IdentityReader:
    def __init__(self, r):
        self.r = r

    def read1(self, size):
        return self.r.read1(size)

    def finish(self):
        self.r.read()

    def close(self):
        self.r.close()


class CacheHandler:
    @staticmethod
    @lru_cache(maxsize=128)
    def get_narinfo(base, hash):
        with URLHandler.get_ok(f"{base}/{hash}.narinfo") as response:
            response_data = response.read()
        return NarReader.narinfo_parser.parsebytes(response_data)

    @staticmethod
    def file_url(base, narinfo):
        return f"{base}/{narinfo['URL']}"

    @staticmethod
    def get_nar_reader(base, narinfo):
        compression = narinfo.get("Compression", "none")
        if compression == "bzip2":
            import bz2

            decompressor = bz2.BZ2Decompressor()
        elif compression == "xz":
            import lzma

            decompressor = lzma.LZMADecompressor(lzma.FORMAT_XZ)
        elif compression == "none":
            decompressor = None
        else:
            raise Exception("narinfo unsupported compression %s" % compression)
        file_url = CacheHandler.file_url(base, narinfo)

        file_reader = URLHandler.get_ok(file_url)

        if decompressor is None:
            nar_reader = IdentityReader(file_reader)
        else:
            nar_reader = DecompressReader(file_reader, decompressor)

        return nar_reader


class InstallationManager:
    encountered_hashes = set()

    @staticmethod
    def collect_recursive(store_prefix, base, basename):
        hash = NarReader.basename_hash(basename)
        if hash in InstallationManager.encountered_hashes:
            return
        InstallationManager.encountered_hashes.add(hash)
        store_path = os.path.join(store_prefix, basename)
        if os.path.lexists(store_path):
            print(store_path, "exists", file=sys.stderr, flush=True)
            return
        narinfo = CacheHandler.get_narinfo(base, hash)
        # for refs_header in narinfo.get_all('references', ()):
        #  for ref in refs_header.split():
        #    yield from InstallationManager.collect_recursive(store_prefix, base, ref)
        yield basename, narinfo

    @staticmethod
    def download_one(temp, store_prefix, base, basename, narinfo):
        unpack_dst = os.path.join(temp, basename)
        print("downloading", basename, file=sys.stderr, flush=True)
        with contextlib.closing(
            CacheHandler.get_nar_reader(base, narinfo)
        ) as nar_reader:
            NarReader.unpack(unpack_dst, nar_reader)
            nar_reader.finish()
        os.rename(unpack_dst, os.path.join(store_prefix, basename))

    @staticmethod
    def install_closure(temp, store_prefix, base, top_basename):
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(
                    InstallationManager.download_one,
                    temp,
                    store_prefix,
                    base,
                    basename,
                    narinfo,
                )
                for basename, narinfo in InstallationManager.collect_recursive(
                    store_prefix, base, top_basename
                )
            ]
            for future in futures:
                future.result()  # Wait for all downloads and unpacking to complete

    @staticmethod
    def install_package(store_prefix, base, package):
        os.makedirs(store_prefix, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="install-", dir=store_prefix) as temp:
            InstallationManager.install_closure(temp, store_prefix, base, package)


def setup_environment(root, mount):
    """
    Prepares the environment by creating directories and a symlink.
    """
    os.makedirs(mount, exist_ok=True)
    os.makedirs(os.path.join(root, "store"), exist_ok=True)
    symlink_path = os.path.join(root, "nix")

    if os.path.islink(symlink_path):
        if os.readlink(symlink_path) != root:
            os.unlink(symlink_path)
            os.symlink(root, symlink_path, target_is_directory=True)
    else:
        os.symlink(root, symlink_path, target_is_directory=True)


class Loopback(LoggingMixIn, Operations):
    def __init__(self, root, nix_binary, cache_location):
        self.root = os.path.realpath(root)
        self.nix_binary = nix_binary
        self.cache_location = cache_location
        self.rwlock = RLock()
        self.processed_paths = set()  # Cache for successfully processed paths

    @lru_cache(maxsize=1024)  # Cache up to 1024 paths
    def _full_path(self, partial):
        partial_path = Path(partial.lstrip("/"))
        path = os.path.join(self.root, partial_path)

        if len(partial_path.parts) <= 1 or partial_path.parts[0] != "store":
            return str(path)

        package_hash = partial_path.parts[1]
        if package_hash in self.processed_paths:
            return str(path)
        else:
            InstallationManager.install_package(
                os.path.join(self.root, "store"),
                self.cache_location,
                package_hash,
            )
            self.processed_paths.add(package_hash)

        return str(path)

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
    write = os.write

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
