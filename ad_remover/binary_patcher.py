"""主二进制广告端点打补丁器。

将主二进制中明文出现的广告请求域名，按「等长（按字节）」替换为 `0.0.0.0`，
使广告网络请求解析到无效地址而失败。等长替换保证：
  - 字符串仍以 NULL 正确结尾（超出部分补 NULL）；
  - 不改变文件偏移，Mach-O 段布局不受影响。
修改前自动备份原二进制。打补丁会破坏原有代码签名，需重签名后方可安装（见 README）。

默认仅替换 ad_endpoints（确属广告）。--include-tracking 可一并替换埋点域名（会同时影响统计，谨慎使用）。
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any, Dict, List

from . import config


def _find_executable(app_dir: Path) -> Path | None:
    for cand in (app_dir / app_dir.name.replace(".app", ""), app_dir / "AutoMobile"):
        if cand.is_file():
            return cand
    for p in app_dir.iterdir():
        if p.is_file() and p.name not in ("Info.plist", "PkgInfo"):
            # Mach-O 可执行通常较大且无扩展名
            if p.stat().st_size > 1_000_000:
                return p
    return None


def patch_binary(app_dir: Path, sig: Dict[str, Any] | None = None,
                 dry_run: bool = False, include_tracking: bool = False,
                 replacement: str = "0.0.0.0") -> Dict[str, Any]:
    sig = sig or config.get_signatures()
    app_dir = Path(app_dir)
    exe = _find_executable(app_dir)
    result: Dict[str, Any] = {"dry_run": dry_run, "executable": str(exe) if exe else None,
                              "patched": {}, "backup": None, "error": None}
    if exe is None:
        result["error"] = "未找到主二进制"
        return result

    # 唯一真源：ad_endpoints（路线 B 的 dylib 也复用同一份域名清单）
    repl_map: Dict[str, str] = {ep: replacement for ep in sig.get("ad_endpoints", [])}
    if include_tracking:
        for ep in sig.get("tracking_endpoints", []):
            repl_map.setdefault(ep, replacement)

    try:
        data = bytearray(exe.read_bytes())
    except Exception as e:  # noqa
        result["error"] = str(e)
        return result

    total = 0
    for domain, _rep in repl_map.items():
        d = domain.encode("utf-8")
        if len(d) == 0:
            continue
        start = 0
        count = 0
        while True:
            idx = data.find(d, start)
            if idx == -1:
                break
            # 等长替换：新主机名补 NULL 至原长度
            new = replacement.encode("utf-8")[:len(d)]
            new = new + b"\x00" * (len(d) - len(new))
            data[idx:idx + len(d)] = new
            count += 1
            start = idx + len(d)
        if count:
            result["patched"][domain] = count
            total += count

    result["total_patched"] = total
    if dry_run or total == 0:
        return result

    backup = exe.with_suffix(exe.suffix + ".adremover.bak")
    if not backup.exists():
        shutil.copy2(exe, backup)
        result["backup"] = str(backup)

    exe.write_bytes(bytes(data))
    return result


if __name__ == "__main__":
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else config.DEFAULT_APP_DIR
    dry = "--dry-run" in sys.argv
    tr = "--include-tracking" in sys.argv
    r = patch_binary(Path(t), dry_run=dry, include_tracking=tr)
    print(r)
