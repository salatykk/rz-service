import os
import struct

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

MAGIC = b"RZSVC"
VERSION = 1
KDF_ARGON2ID = 1
CHUNK_SIZE = 1024 * 1024
NONCE_SIZE = 12
SALT_SIZE = 16
DEFAULT_MEM_KIB = 64 * 1024
DEFAULT_TIME_COST = 3
DEFAULT_PARALLELISM = 1


class ContainerError(Exception):
    pass


class WrongPasswordError(Exception):
    pass


class CancelledError(Exception):
    pass


def _derive_key(password, salt, mem_kib, time_cost, parallelism):
    kdf = Argon2id(
        salt=salt,
        length=32,
        memory_cost=mem_kib,
        iterations=time_cost,
        lanes=parallelism,
    )
    return kdf.derive(password.encode("utf-8"))


def _write_header(fileobj, salt, mem_kib, time_cost, parallelism):
    fileobj.write(MAGIC)
    fileobj.write(struct.pack(">BB", VERSION, KDF_ARGON2ID))
    fileobj.write(struct.pack(">I", mem_kib))
    fileobj.write(struct.pack(">H", time_cost))
    fileobj.write(struct.pack(">B", parallelism))
    fileobj.write(struct.pack(">B", len(salt)))
    fileobj.write(salt)


def _read_header(fileobj):
    magic = fileobj.read(len(MAGIC))
    if magic != MAGIC:
        raise ContainerError("Файл не является контейнером RZ Service (.rzx)")
    version, kdf_id = struct.unpack(">BB", fileobj.read(2))
    if version != VERSION:
        raise ContainerError("Неподдерживаемая версия контейнера RZ Service")
    if kdf_id != KDF_ARGON2ID:
        raise ContainerError("Неподдерживаемый алгоритм ключа")
    mem_kib = struct.unpack(">I", fileobj.read(4))[0]
    time_cost = struct.unpack(">H", fileobj.read(2))[0]
    parallelism = fileobj.read(1)[0]
    salt_len = fileobj.read(1)[0]
    salt = fileobj.read(salt_len)
    if len(salt) != salt_len:
        raise ContainerError("Контейнер повреждён")
    return {
        "version": version,
        "kdf": kdf_id,
        "mem_kib": mem_kib,
        "time_cost": time_cost,
        "parallelism": parallelism,
        "salt": salt,
    }


def probe(src_path):
    with open(src_path, "rb") as fin:
        return _read_header(fin)


def encrypt_file(src_path, dst_path, password,
                 mem_kib=DEFAULT_MEM_KIB,
                 time_cost=DEFAULT_TIME_COST,
                 parallelism=DEFAULT_PARALLELISM,
                 progress_cb=None,
                 cancel_check=None):
    salt = os.urandom(SALT_SIZE)
    total = os.path.getsize(src_path)
    done = 0
    with open(src_path, "rb") as fin, open(dst_path, "wb") as fout:
        _write_header(fout, salt, mem_kib, time_cost, parallelism)
        key = _derive_key(password, salt, mem_kib, time_cost, parallelism)
        aes = AESGCM(key)
        while True:
            if cancel_check is not None and cancel_check():
                raise CancelledError()
            chunk = fin.read(CHUNK_SIZE)
            if not chunk:
                break
            nonce = os.urandom(NONCE_SIZE)
            fout.write(nonce)
            fout.write(aes.encrypt(nonce, chunk, None))
            done += len(chunk)
            if progress_cb is not None:
                progress_cb(done, total)
    if progress_cb is not None:
        progress_cb(total, total)


def decrypt_file(src_path, dst_path, password,
                 progress_cb=None,
                 cancel_check=None):
    total = os.path.getsize(src_path)
    with open(src_path, "rb") as fin:
        params = _read_header(fin)
        key = _derive_key(password, params["salt"], params["mem_kib"],
                          params["time_cost"], params["parallelism"])
        aes = AESGCM(key)
        done = fin.tell()
        with open(dst_path, "wb") as fout:
            while True:
                if cancel_check is not None and cancel_check():
                    raise CancelledError()
                nonce = fin.read(NONCE_SIZE)
                if not nonce:
                    break
                if len(nonce) != NONCE_SIZE:
                    raise ContainerError("Контейнер повреждён")
                ct = fin.read(CHUNK_SIZE + 16)
                if len(ct) < 16:
                    raise ContainerError("Контейнер повреждён")
                try:
                    plain = aes.decrypt(nonce, ct, None)
                except InvalidTag as exc:
                    raise WrongPasswordError("Неверный пароль") from exc
                fout.write(plain)
                done += len(ct)
                if progress_cb is not None:
                    progress_cb(done, total)
    if progress_cb is not None:
        progress_cb(total, total)
    return params


def check_password(src_path, password):
    with open(src_path, "rb") as fin:
        params = _read_header(fin)
        key = _derive_key(password, params["salt"], params["mem_kib"],
                          params["time_cost"], params["parallelism"])
        aes = AESGCM(key)
        nonce = fin.read(NONCE_SIZE)
        if len(nonce) != NONCE_SIZE:
            raise ContainerError("Контейнер повреждён")
        ct = fin.read(CHUNK_SIZE + 16)
        if len(ct) < 16:
            raise ContainerError("Контейнер повреждён")
        try:
            aes.decrypt(nonce, ct, None)
        except InvalidTag:
            return False
        return True
