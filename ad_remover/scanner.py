"""广告产物扫描器。

在解压后的 iOS app 包（*.app）中，依据签名库识别所有广告相关产物：
  - 广告资源文件（ad_*.json / webp / png ...）
  - 广告 SDK 资源包（*.bundle）
  - 主二进制中的广告字符串片段与网络端点
  - Info.plist 中的广告相关配置
输出结构化的 find_json 供报告与清理阶段复用。
"""
from __future__ import annotations

import re
import json
from pathlib import Path
from typing import Any, Dict, List

from . import config


def _classify_file(path: Path, sig: Dict[str, Any]) -> str | None:
    """返回该文件所属的广告类别，若不是广告相关则返回 None。"""
    name = path.name
    # 1) 文件名模式
    for pat in sig.get("ad_resource_filename_patterns", []):
        if re.match(pat, name, re.IGNORECASE):
            return "ad_resource"
    # 2) bundle 名称
    if name.endswith(".bundle") and name in sig.get("ad_bundle_names", []):
        return "ad_bundle"
    if name.endswith(".framework") and name in sig.get("ad_frameworks_names", []):
        return "ad_framework"
    return None


def _dir_size(d: Path) -> int:
    total = 0
    for f in d.rglob("*"):
        if f.is_file():
            try:
                total += f.stat().st_size
            except OSError:
                pass
    return total


def scan_resources(app_dir: Path, sig: Dict[str, Any]) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    for p in app_dir.rglob("*"):
        cat = None
        if p.is_file():
            cat = _classify_file(p, sig)
        elif p.is_dir():
            # bundle / framework 目录需按目录名判定
            name = p.name
            if name.endswith(".bundle") and name in sig.get("ad_bundle_names", []):
                cat = "ad_bundle"
            elif name.endswith(".framework") and name in sig.get("ad_frameworks_names", []):
                cat = "ad_framework"
        if cat:
            rel = p.relative_to(app_dir)
            size = _dir_size(p) if p.is_dir() else p.stat().st_size
            items.append({
                "category": cat,
                "path": str(rel).replace("\\", "/"),
                "size": size,
            })
    return items


def scan_binary_strings(app_dir: Path, sig: Dict[str, Any]) -> Dict[str, Any]:
    """在主二进制中统计广告字符串片段与端点的出现次数。"""
    exe = None
    for cand in (app_dir / app_dir.name.replace(".app", ""), app_dir / "AutoMobile"):
        if cand.is_file():
            exe = cand
            break
    if exe is None:
        # 通用：找 Mach-O 可执行（无扩展名且可执行）
        for p in app_dir.iterdir():
            if p.is_file() and p.stat().st_mode & 0o111 and p.name not in ("Info.plist", "PkgInfo"):
                exe = p
                break
    result: Dict[str, Any] = {"executable": str(exe) if exe else None, "fragments": {}, "endpoints": {}}
    if exe is None or exe.stat().st_size > 2_000_000_000:
        return result

    fragments = sig.get("ad_string_fragments", [])
    endpoints = list(sig.get("ad_endpoints", [])) + list(sig.get("tracking_endpoints", []))

    try:
        data = exe.read_bytes()
    except Exception as e:  # noqa
        result["error"] = str(e)
        return result

    for frag in fragments:
        n = data.count(frag.encode("utf-8", "ignore"))
        if n:
            result["fragments"][frag] = n
    for ep in endpoints:
        n = data.count(ep.encode("utf-8", "ignore"))
        if n:
            result["endpoints"][ep] = n
    result["_executable_size"] = exe.stat().st_size
    return result


def scan_plist(app_dir: Path, sig: Dict[str, Any]) -> Dict[str, Any]:
    """读取 Info.plist，提取广告相关配置（URL scheme / 查询 scheme / ATS）。"""
    import plistlib
    plist = app_dir / "Info.plist"
    out: Dict[str, Any] = {"exists": plist.exists()}
    if not plist.exists():
        return out
    try:
        with plist.open("rb") as f:
            p = plistlib.load(f)
    except Exception as e:  # noqa
        out["error"] = str(e)
        return out

    url_types = p.get("CFBundleURLTypes", [])
    ad_schemes = []
    for ut in url_types:
        for s in ut.get("CFBundleURLSchemes", []):
            if any(k in s for k in sig.get("plist_ad_url_schemes_to_flag", [])):
                ad_schemes.append({"scheme": s, "name": ut.get("CFBundleURLName")})
    out["ad_url_schemes"] = ad_schemes

    queries = p.get("LSApplicationQueriesSchemes", [])
    ad_queries = [q for q in queries if any(k in q for k in sig.get("plist_queries_schemes_ad_related", []))]
    out["ad_query_schemes"] = ad_queries
    out["ats_allows_arbitrary_loads"] = bool(
        (p.get("NSAppTransportSecurity") or {}).get("NSAllowsArbitraryLoads", False)
    )
    out["user_tracking_desc"] = p.get("NSUserTrackingUsageDescription")
    return out


def scan(app_dir: Path, sig: Dict[str, Any] | None = None) -> Dict[str, Any]:
    sig = sig or config.get_signatures()
    app_dir = Path(app_dir)
    report = {
        "app_dir": str(app_dir),
        "app_name": app_dir.name,
        "resources": scan_resources(app_dir, sig),
        "binary": scan_binary_strings(app_dir, sig),
        "plist": scan_plist(app_dir, sig),
        "platforms": list(sig.get("third_party_platforms", {}).keys()),
    }
    return report


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else config.DEFAULT_APP_DIR
    r = scan(Path(target))
    print(json.dumps(r, ensure_ascii=False, indent=2))
