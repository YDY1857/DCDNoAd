"""重打包与重签名编排（Windows 可用；重签名依赖外部工具）。

- repack_to_ipa: 把改好的 .app 重新压缩为 Payload/xxx.app 结构的 .ipa
- strip_signature: 移除旧的 _CodeSignature / embedded.mobileprovision（重签前清理）
- resign_notes: 输出 Windows(zsign) 与 macOS(codesign) 两种重签命令

⚠️ 重签名本身需外部程序：
  - Windows: zsign（https://github.com/zhlynn/zsign）—— 纯 C，可编译为 Windows exe
  - macOS: 系统 codesign / Xcode
本模块只负责打包与给出命令，不内嵌签名实现。
"""
from __future__ import annotations

import shutil
import zipfile
from pathlib import Path
from typing import Dict, List


def strip_signature(app_dir: Path, dry_run: bool = False) -> Dict[str, List[str]]:
    """移除旧的代码签名与 provisioning，便于用新证书重签。"""
    app_dir = Path(app_dir)
    removed: List[str] = []
    sig = app_dir / "_CodeSignature"
    prov = app_dir / "embedded.mobileprovision"
    for target in (sig, prov):
        if target.exists():
            removed.append(str(target))
            if not dry_run:
                if target.is_dir():
                    shutil.rmtree(target)
                else:
                    target.unlink()
    return {"removed": removed, "dry_run": dry_run}


def repack_to_ipa(app_dir: Path, out_ipa: Path | None = None,
                  strip: bool = True, dry_run: bool = False) -> Dict:
    """把 .app 重新打包为 .ipa（Payload/AutoMobile.app 结构）。"""
    app_dir = Path(app_dir)
    payload = app_dir.parent  # .../Payload
    if out_ipa is None:
        out_ipa = app_dir.with_suffix(".ipa")
    out_ipa = Path(out_ipa)

    result: Dict = {"out_ipa": str(out_ipa), "dry_run": dry_run, "files": 0, "error": None}

    if strip:
        s = strip_signature(app_dir, dry_run=dry_run)
        result["stripped"] = s["removed"]

    def iter_files(root: Path):
        for p in sorted(root.rglob("*")):
            if p.is_file():
                yield p

    if dry_run:
        # 仅统计
        result["files"] = sum(1 for _ in iter_files(payload))
        return result

    if out_ipa.exists():
        out_ipa.unlink()
    with zipfile.ZipFile(out_ipa, "w", zipfile.ZIP_DEFLATED) as z:
        for f in iter_files(payload):
            arcname = f.relative_to(payload.parent)  # 含 Payload/ 前缀
            z.write(f, str(arcname).replace("\\", "/"))
            result["files"] += 1
    return result


def resign_notes(out_ipa: str, identity: str = "Apple Development: xxx@xxx") -> str:
    """返回重签名命令示例文本。"""
    return f"""# ===== 重签名（安装前必须执行）=====

方案 A：Windows 用 zsign（推荐，无需 Mac）
  1) 准备：下载/编译 zsign.exe
  2) 准备：签名证书 .p12 + 描述文件 embedded.mobileprovision（开发者账号生成）
  3) 执行：
     zsign -k cert.p12 -p <p12密码> -m embedded.mobileprovision \\
           -z 1234567890ABCDEFGHIJKLMNOPQRSTUVWXYZ \\
           -o signed.ipa {out_ipa}

方案 B：macOS 用 codesign
  unzip -o {out_ipa} -d /tmp/app
  /usr/bin/codesign -f -s "{identity}" \\
        --entitlements entitlements.plist /tmp/app/Payload/AutoMobile.app
  cd /tmp/app && zip -r signed.ipa Payload

重签后用 AltStore / Sideloadly / 爱思助手 等安装到设备。
"""


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("usage: repack.py <app_dir> [out.ipa] [--dry-run]")
        raise SystemExit(1)
    d = repack_to_ipa(Path(sys.argv[1]),
                      Path(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith("-") else None,
                      dry_run="--dry-run" in sys.argv)
    print(d)
