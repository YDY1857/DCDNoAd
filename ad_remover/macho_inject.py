"""纯 Python Mach-O dylib 注入器（无第三方依赖，Windows 可直接运行）。

将 `adblock.dylib` 注入 App 主二进制：在 64 位 Mach-O 的 load commands 区插入
一条 `LC_LOAD_DYLIB`（指向 `@executable_path/adblock.dylib`），并把因插入而
向后平移的所有文件偏移字段（段 fileoff、符号表、dyld_info、代码签名等）同步
增加插入字节数，保证结构合法。

支持：
  - 单架构 64 位 Mach-O（本 App 即为此类型，为主要路径，已校验）
  - 通用二进制（FAT）中的 64 位切片（best-effort，按架构顺序逐个注入）

注意：注入后原代码签名失效，安装前必须重签名（见 README / repack.py）。
"""
from __future__ import annotations

import shutil
import struct
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---- 常量 ----
MH_MAGIC_64 = 0xFEEDFACF
MH_CIGAM_64 = 0xCFFAEDFE
FAT_MAGIC = 0xCAFEBABE
FAT_CIGAM = 0xBEBAFECA
FAT_MAGIC_64 = 0xCAFEBABF
FAT_CIGAM_64 = 0xBFBAFECA

LC_SEGMENT_64 = 0x19
LC_SEGMENT = 0x1
LC_SYMTAB = 0x2
LC_DYSYMTAB = 0xB
LC_DYLD_INFO = 0x22
LC_DYLD_INFO_ONLY = 0x80000022
LC_CODE_SIGNATURE = 0x1D
LC_ENCRYPTION_INFO_64 = 0x2C
LC_FUNCTION_STARTS = 0x26
LC_DATA_IN_CODE = 0x29
LC_ATOM_INFO = 0x2E

CPU_TYPE_ARM64 = 0x0100000C

# LC 中需要随插入平移的「文件偏移」字段：相对该 LC 起始的偏移 + 字段宽度
OFFSET_FIELDS = {
    LC_SYMTAB: [(0x8, 4), (0xC, 4)],
    LC_DYSYMTAB: [(0x8, 4), (0xC, 4), (0x10, 4), (0x14, 4), (0x18, 4), (0x1C, 4)],
    LC_DYLD_INFO: [(0x8, 4), (0xC, 4), (0x10, 4), (0x14, 4), (0x18, 4)],
    LC_DYLD_INFO_ONLY: [(0x8, 4), (0xC, 4), (0x10, 4), (0x14, 4), (0x18, 4)],
    LC_CODE_SIGNATURE: [(0x8, 4)],
    LC_ENCRYPTION_INFO_64: [(0x10, 4), (0x14, 4)],
    LC_FUNCTION_STARTS: [(0x8, 4)],
    LC_DATA_IN_CODE: [(0x8, 4)],
    LC_ATOM_INFO: [(0x8, 4)],
}

INSERTION_POINT = 32  # 64 位 Mach-O 头部固定 32 字节，load commands 从此开始


def _u32(b: bytes, off: int, e: str = "<") -> int:
    return struct.unpack_from(e + "I", b, off)[0]


def _u64(b: bytes, off: int, e: str = "<") -> int:
    return struct.unpack_from(e + "Q", b, off)[0]


def _set_u32(b: bytearray, off: int, val: int, e: str = "<") -> None:
    struct.pack_into(e + "I", b, off, val & 0xFFFFFFFF)


def _set_u64(b: bytearray, off: int, val: int, e: str = "<") -> None:
    struct.pack_into(e + "Q", b, off, val & 0xFFFFFFFFFFFFFFFF)


def _cstr(b: bytes, off: int) -> str:
    end = b.find(b"\x00", off)
    if end == -1:
        end = len(b)
    return b[off:end].decode("utf-8", "replace")


def _build_lc_loaddylib(install_name: str) -> bytes:
    name = install_name.encode("utf-8") + b"\x00"
    pad = (4 - (len(name) % 4)) % 4
    name_padded = name + b"\x00" * pad
    # dylib_command: cmd(4) cmdsize(4) name_offset(4) timestamp(4) current_version(4) compat_version(4)
    header = struct.pack("<IIIIII", 0x0C, 24 + len(name_padded), 24, 0, 0, 0)
    return header + name_padded


def _already_injected(macho: bytes, e: str, install_name: str) -> bool:
    ncmds = _u32(macho, 16, e)
    off = INSERTION_POINT
    for _ in range(ncmds):
        cmd = _u32(macho, off, e)
        cmdsize = _u32(macho, off + 4, e)
        if cmd in (0x0C, 0x0D, 0x0E):  # LC_LOAD_DYLIB / LC_LOAD_WEAK_DYLIB / LC_REEXPORT_DYLIB
            name_off = off + _u32(macho, off + 8, e)
            if _cstr(macho, name_off) == install_name:
                return True
        if cmdsize <= 0:
            break
        off += cmdsize
    return False


def _inject_thin(macho: bytearray, install_name: str) -> Tuple[bytearray, bool]:
    """对单个 64 位 Mach-O 切片插入 LC_LOAD_DYLIB。返回 (新数据, 是否插入)。"""
    magic = _u32(macho, 0)
    if magic == MH_MAGIC_64:
        e = "<"
    elif magic == MH_CIGAM_64:
        e = ">"
    else:
        # 仅支持 64 位；32 位/未知直接跳过
        return macho, False

    if _already_injected(bytes(macho), e, install_name):
        return macho, False

    ncmds = _u32(macho, 16, e)
    sizeofcmds = _u32(macho, 20, e)
    new_lc = _build_lc_loaddylib(install_name)
    insert_size = len(new_lc)

    # 头部(32) + 新LC + 原有LC
    new_data = bytearray(macho[:INSERTION_POINT]) + bytearray(new_lc) + bytearray(macho[INSERTION_POINT:])

    _set_u32(new_data, 16, ncmds + 1, e)
    _set_u32(new_data, 20, sizeofcmds + insert_size, e)

    off = INSERTION_POINT + insert_size
    for _ in range(ncmds):
        cmd = _u32(new_data, off, e)
        cmdsize = _u32(new_data, off + 4, e)
        if cmd == LC_SEGMENT_64:
            # 段 fileoff 必须随插入平移（含 __TEXT=0）
            fo = off + 0x28
            _set_u64(new_data, fo, _u64(new_data, fo, e) + insert_size, e)
        elif cmd == LC_SEGMENT:
            fo = off + 0x18
            _set_u32(new_data, fo, _u32(new_data, fo, e) + insert_size, e)
        else:
            for f_off, f_size in OFFSET_FIELDS.get(cmd, []):
                abs_off = off + f_off
                if f_size == 4:
                    v = _u32(new_data, abs_off, e)
                    if v >= INSERTION_POINT:
                        _set_u32(new_data, abs_off, v + insert_size, e)
                else:
                    v = _u64(new_data, abs_off, e)
                    if v >= INSERTION_POINT:
                        _set_u64(new_data, abs_off, v + insert_size, e)
        if cmdsize <= 0:
            break
        off += cmdsize

    return new_data, True


def _validate_thin(macho: bytes) -> List[str]:
    """重新解析并做基础结构校验，返回问题列表。"""
    problems: List[str] = []
    e = "<" if _u32(macho, 0) == MH_MAGIC_64 else ">"
    ncmds = _u32(macho, 16, e)
    sizeofcmds = _u32(macho, 20, e)
    off = INSERTION_POINT
    total = 0
    for _ in range(ncmds):
        cmdsize = _u32(macho, off + 4, e)
        if cmdsize <= 0:
            problems.append(f"非法 cmdsize=0 @ {off}")
            break
        total += cmdsize
        off += cmdsize
    if total != sizeofcmds:
        problems.append(f"sizeofcmds 不一致: 求和={total} 头部={sizeofcmds}")
    if off > len(macho) + 1:
        problems.append("load commands 超出文件范围")
    return problems


def inject_dylib(app_dir: Path, dylib_path: Path,
                 install_name: str = "@executable_path/adblock.dylib",
                 dry_run: bool = False, no_backup: bool = False) -> Dict:
    """把 dylib 注入 app 主二进制。返回结果字典。"""
    app_dir = Path(app_dir)
    dylib_path = Path(dylib_path)
    result: Dict = {"dry_run": dry_run, "injected": False, "executable": None,
                    "backup": None, "error": None, "fat": False, "validation": []}
    if not dylib_path.exists():
        result["error"] = f"dylib 不存在: {dylib_path}"
        return result

    # 定位主二进制（无扩展名、>1MB）
    exe = None
    cand = app_dir / app_dir.name.replace(".app", "")
    if cand.is_file():
        exe = cand
    else:
        for p in app_dir.iterdir():
            if p.is_file() and p.name not in ("Info.plist", "PkgInfo") and p.stat().st_size > 1_000_000:
                exe = p
                break
    if exe is None:
        result["error"] = "未找到主二进制"
        return result
    result["executable"] = str(exe)

    data = bytearray(exe.read_bytes())
    magic = _u32(data, 0)

    # 先把 dylib 复制进 .app（仅非 dry-run）
    dest_dylib = app_dir / install_name.split("/")[-1]
    if not dry_run:
        if not no_backup and not exe.with_suffix(exe.suffix + ".adremover.bak").exists():
            shutil.copy2(exe, exe.with_suffix(exe.suffix + ".adremover.bak"))
            result["backup"] = str(exe.with_suffix(exe.suffix + ".adremover.bak"))
        if not dest_dylib.exists() or dest_dylib.read_bytes() != dylib_path.read_bytes():
            shutil.copy2(dylib_path, dest_dylib)

    if magic in (FAT_MAGIC, FAT_CIGAM, FAT_MAGIC_64, FAT_CIGAM_64):
        result["fat"] = True
        new_data, inserted = _inject_fat(data, install_name)
    else:
        new_data, inserted = _inject_thin(data, install_name)

    result["injected"] = inserted
    if dry_run or not inserted:
        result["validation"] = _validate_thin(bytes(new_data)) if not result["fat"] else ["FAT: 未做本地校验"]
        return result

    exe.write_bytes(bytes(new_data))
    result["validation"] = _validate_thin(bytes(new_data)) if not result["fat"] else ["FAT: 未做本地校验"]
    return result


def _inject_fat(data: bytearray, install_name: str) -> Tuple[bytearray, bool]:
    magic = _u32(data, 0)
    e = "<" if magic in (FAT_MAGIC, FAT_MAGIC_64) else ">"
    is64 = magic in (FAT_MAGIC_64, FAT_CIGAM_64)
    nfat = _u32(data, 4, e)
    arch_size = 32 if is64 else 20
    base = 8
    arches: List[Tuple[int, int, int, int]] = []  # (cputype, cpusubtype, offset, size)
    for i in range(nfat):
        a = base + i * arch_size
        cputype = _u32(data, a, e)
        cpusubtype = _u32(data, a + 4, e)
        if is64:
            offset = _u64(data, a + 8, e)
            size = _u64(data, a + 16, e)
        else:
            offset = _u32(data, a + 8, e)
            size = _u32(data, a + 12, e)
        arches.append((cputype, cpusubtype, offset, size))

    any_inserted = False
    cumulative = 0
    for idx, (cputype, cpusubtype, offset, size) in enumerate(arches):
        if (cputype & 0x0FFFFFFF) != (CPU_TYPE_ARM64 & 0x0FFFFFFF):
            continue
        slice_ = bytearray(data[offset:offset + size])
        new_slice, inserted = _inject_thin(slice_, install_name)
        if not inserted:
            continue
        delta = len(new_slice) - size
        # 用新切片替换
        data[offset:offset + size] = new_slice
        # 后续架构偏移整体后移 delta
        cumulative += delta
        for j in range(idx + 1, len(arches)):
            arches[j] = (arches[j][0], arches[j][1], arches[j][2] + delta, arches[j][3])
            o2 = base + j * arch_size
            if is64:
                _set_u64(data, o2 + 8, arches[j][2], e)
            else:
                _set_u32(data, o2 + 8, arches[j][2], e)
        # 更新本架构 size
        arches[idx] = (cputype, cpusubtype, offset, len(new_slice))
        o1 = base + idx * arch_size
        if is64:
            _set_u64(data, o1 + 16, len(new_slice), e)
        else:
            _set_u32(data, o1 + 12, len(new_slice), e)
        any_inserted = True
    return data, any_inserted


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("usage: macho_inject.py <app_dir> <dylib_path> [--dry-run]")
        raise SystemExit(1)
    d = inject_dylib(Path(sys.argv[1]), Path(sys.argv[2]), dry_run="--dry-run" in sys.argv)
    print(d)
