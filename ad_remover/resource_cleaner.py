"""广告资源清理器。

安全移除广告资源文件与广告 SDK 资源包（*.bundle）。所有删除前会先备份到
同级 _ad_remover_backup/ 目录，支持 --dry-run 预演。二进制不被此模块改动。
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any, Dict, List

from . import config


def _backup(app_dir: Path, targets: List[Path]) -> Path:
    backup_root = app_dir.parent / config.BACKUP_DIRNAME
    backup_root.mkdir(parents=True, exist_ok=True)
    for t in targets:
        if not t.exists():
            continue
        rel = t.relative_to(app_dir)
        dest = backup_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if t.is_dir():
            shutil.copytree(t, dest, dirs_exist_ok=True)
        else:
            shutil.copy2(t, dest)
    return backup_root


def clean(app_dir: Path, sig: Dict[str, Any] | None = None,
          dry_run: bool = False, no_backup: bool = False) -> Dict[str, Any]:
    sig = sig or config.get_signatures()
    app_dir = Path(app_dir)
    # 依据签名重新定位（不依赖扫描 JSON，直接判定，便于独立运行）
    targets: List[Path] = []

    for p in app_dir.rglob("*"):
        if not (p.is_file() or p.is_dir()):
            continue
        name = p.name
        hit = False
        for pat in sig.get("ad_resource_filename_patterns", []):
            if re.match(pat, name, re.IGNORECASE):
                hit = True
                break
        if not hit and name.endswith(".bundle") and name in sig.get("ad_bundle_names", []):
            hit = True
        if not hit and name.endswith(".framework") and name in sig.get("ad_frameworks_names", []):
            hit = True
        if hit:
            targets.append(p)

    result: Dict[str, Any] = {
        "dry_run": dry_run,
        "targets": [str(t.relative_to(app_dir)).replace("\\", "/") for t in targets],
        "removed": [],
        "backup_dir": None,
        "total_size": 0,
    }
    if not targets:
        return result

    total = sum((t.stat().st_size if t.is_file() else sum(f.stat().st_size for f in t.rglob('*') if f.is_file()))
                for t in targets)
    result["total_size"] = total

    if not dry_run and not no_backup:
        result["backup_dir"] = str(_backup(app_dir, targets))

    for t in targets:
        rel = str(t.relative_to(app_dir)).replace("\\", "/")
        if dry_run:
            continue
        if t.is_dir():
            shutil.rmtree(t)
        else:
            t.unlink()
        result["removed"].append(rel)
    return result


if __name__ == "__main__":
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else config.DEFAULT_APP_DIR
    dry = "--dry-run" in sys.argv
    r = clean(Path(t), dry_run=dry)
    print(f"dry_run={r['dry_run']} targets={len(r['targets'])} removed={len(r['removed'])}")
    for x in r["targets"]:
        print("  -", x)
