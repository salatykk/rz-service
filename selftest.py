import os
import shutil
import tempfile

from rzservice import archive, crypto


def _make_src(root):
    src = os.path.join(root, "src")
    os.makedirs(os.path.join(src, "sub"))
    for i in range(3):
        with open(os.path.join(src, f"file{i}.txt"), "w", encoding="utf-8") as f:
            f.write("hello RZ Service " * 2000)
    with open(os.path.join(src, "sub", "nested.bin"), "wb") as f:
        f.write(os.urandom(4096))
    return src


def main():
    tmp = tempfile.mkdtemp(prefix="rz_selftest_")
    try:
        src = _make_src(tmp)
        rar_available = bool(archive.find_rar())
        print("WinRAR найден:", rar_available)
        for fmt in ("zip", "rar"):
            if fmt == "rar" and not rar_available:
                print("RAR пропущен: WinRAR не установлен")
                continue
            rar = os.path.join(tmp, f"out_{fmt}.rzx")
            stats = archive.archive(src, rar, "SuperSecret123!", fmt=fmt)
            print(fmt, "архив:", stats)
            assert crypto.check_password(rar, "SuperSecret123!")
            assert not crypto.check_password(rar, "wrong")
            assert open(rar, "rb").read(5) == b"RZSVC"
            tmp2, zp = archive.decrypt_to_temp(rar, "SuperSecret123!")
            try:
                with archive.open_archive(zp) as ar:
                    names = sorted(zi.filename for zi in ar.infolist())
                    print(fmt, "содержимое:", names)
                    for expected in ("src/file0.txt", "src/file1.txt",
                                     "src/file2.txt", "src/sub/nested.bin"):
                        assert expected in names, names
            finally:
                shutil.rmtree(tmp2, ignore_errors=True)
            print(fmt, "OK")
        print("SELFTEST PASSED")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
