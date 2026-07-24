"""Info.plist 广告配置加固器。

移除广告相关的 URL Scheme 与 Query Scheme，并可关闭 ATS 任意加载。
修改前自动备份 Info.plist。支持 --dry-run。
"""
from __future__ import annotations

import plistlib
import shutil
from pathlib import Path
from typing import Any, Dict, List

from . import config


def patch_plist(app_dir: Path, sig: Dict[str, Any] | None = None,
                dry_run: bool = False, disable_ats: bool = False) -> Dict[str, Any]:
    sig = sig or config.get_signatures()
    app_dir = Path(app_dir)
    plist = app_dir / "Info.plist"
    result: Dict[str, Any] = {"dry_run": dry_run, "exists": plist.exists(),
                              "removed_url_schemes": [], "removed_query_schemes": [],
                              "ats_disabled": False, "backup": None}
    if not plist.exists():
        return result

    with plist.open("rb") as f:
        p = plistlib.load(f)

    flag_schemes = sig.get("plist_ad_url_schemes_to_flag", [])
    ad_query = set(sig.get("plist_queries_schemes_ad_related", []))

    # URL Types
    url_types = p.get("CFBundleURLTypes", [])
    new_types = []
    for ut in url_types:
        schemes = ut.get("CFBundleURLSchemes", [])
        kept = [s for s in schemes if not any(k in s for k in flag_schemes)]
        removed = [s for s in schemes if any(k in s for k in flag_schemes)]
        result["removed_url_schemes"].extend(removed)
        if kept:
            ut = dict(ut)
            ut["CFBundleURLSchemes"] = kept
            new_types.append(ut)
    p["CFBundleURLTypes"] = new_types

    # Query Schemes
    queries = p.get("LSApplicationQueriesSchemes", [])
    kept_q = [q for q in queries if q not in ad_query]
    removed_q = [q for q in queries if q in ad_query]
    result["removed_query_schemes"] = removed_q
    p["LSApplicationQueriesSchemes"] = kept_q

    # ATS
    if disable_ats:
        ats = p.get("NSAppTransportSecurity", {})
        if ats.get("NSAllowsArbitraryLoads"):
            ats["NSAllowsArbitraryLoads"] = False
            p["NSAppTransportSecurity"] = ats
            result["ats_disabled"] = True

    if dry_run:
        return result

    # 备份
    backup = app_dir / "_Info.plist.adremover.bak"
    shutil.copy2(plist, backup)
    result["backup"] = str(backup)

    with plist.open("wb") as f:
        plistlib.dump(p, f)
    return result


if __name__ == "__main__":
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else config.DEFAULT_APP_DIR
    dry = "--dry-run" in sys.argv
    dis = "--disable-ats" in sys.argv
    r = patch_plist(Path(t), dry_run=dry, disable_ats=dis)
    print(r)
