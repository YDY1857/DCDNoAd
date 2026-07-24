"""命令行入口。

用法（Windows 命令提示符 / PowerShell 均可）：
    python ad_remover/cli.py scan --app "路径\\AutoMobile.app"
    python ad_remover/cli.py report --app "路径\\AutoMobile.app"
    python ad_remover/cli.py clean --app "路径\\AutoMobile.app" --dry-run
    python ad_remover/cli.py patch-plist --app "路径\\AutoMobile.app"
    python ad_remover/cli.py patch-binary --app "路径\\AutoMobile.app"
    python ad_remover/cli.py all --app "路径\\AutoMobile.app"

也可不带参数使用默认路径（见 config.DEFAULT_APP_DIR）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import config
from . import scanner
from . import reporter
from . import resource_cleaner
from . import plist_patcher
from . import binary_patcher
from . import macho_inject
from . import repack


def _resolve_app(args) -> Path:
    if getattr(args, "app", None):
        p = Path(args.app)
        found = config.app_root_heuristic(p)
        if found:
            return found
        return p
    return Path(config.DEFAULT_APP_DIR)


def cmd_scan(args):
    app = _resolve_app(args)
    print(f"{config.LOG_PREFIX} 扫描: {app}")
    r = scanner.scan(app)
    out = Path(args.out) if args.out else (config.TOOL_ROOT / "report")
    out.mkdir(parents=True, exist_ok=True)
    (out / "ad_module_scan.json").write_text(
        json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    res = r["resources"]
    print(f"  - 广告资源文件: {sum(1 for x in res if x['category']=='ad_resource')}")
    print(f"  - 广告 SDK 包:  {sum(1 for x in res if x['category']=='ad_bundle')}")
    print(f"  - 二进制字符串片段: {len(r['binary'].get('fragments', {}))} 类")
    print(f"  - 广告端点: {len(r['binary'].get('endpoints', {}))} 个")
    print(f"{config.LOG_PREFIX} 扫描结果已保存: {out / 'ad_module_scan.json'}")
    return 0


def cmd_report(args):
    app = _resolve_app(args)
    r = scanner.scan(app)
    out = Path(args.out) if args.out else (config.TOOL_ROOT / "report")
    paths = reporter.write_report(r, out)
    print(f"{config.LOG_PREFIX} 报告已生成:")
    for k, v in paths.items():
        print(f"    {k}: {v}")
    return 0


def cmd_clean(args):
    app = _resolve_app(args)
    r = resource_cleaner.clean(app, dry_run=args.dry_run, no_backup=args.no_backup)
    print(f"{config.LOG_PREFIX} clean dry_run={r['dry_run']} 目标={len(r['targets'])} 已删={len(r['removed'])}")
    if r["backup_dir"]:
        print(f"    备份目录: {r['backup_dir']}")
    for x in r["targets"]:
        print(f"    - {x}")
    return 0


def cmd_patch_plist(args):
    app = _resolve_app(args)
    r = plist_patcher.patch_plist(app, dry_run=args.dry_run, disable_ats=args.disable_ats)
    print(f"{config.LOG_PREFIX} patch-plist dry_run={r['dry_run']}")
    print(f"    移除 URL Scheme: {r['removed_url_schemes']}")
    print(f"    移除 Query Scheme: {r['removed_query_schemes']}")
    if r.get("ats_disabled"):
        print("    ATS 任意加载已关闭")
    if r.get("backup"):
        print(f"    备份: {r['backup']}")
    return 0


def cmd_patch_binary(args):
    app = _resolve_app(args)
    r = binary_patcher.patch_binary(app, dry_run=args.dry_run, include_tracking=args.include_tracking)
    if r.get("error"):
        print(f"{config.LOG_PREFIX} 错误: {r['error']}", file=sys.stderr)
        return 1
    print(f"{config.LOG_PREFIX} patch-binary dry_run={r['dry_run']} 共替换 {r.get('total_patched',0)} 处")
    for d, c in r.get("patched", {}).items():
        print(f"    - {d}: {c} 处 -> 0.0.0.0")
    if r.get("backup"):
        print(f"    备份: {r['backup']}")
    if not r["dry_run"] and r.get("total_patched"):
        print("    ⚠️ 二进制已改动，原代码签名失效，安装前必须重签名（见 README）。")
    return 0


def cmd_inject(args):
    app = _resolve_app(args)
    dylib = Path(args.dylib) if args.dylib else (config.TOOL_ROOT / "adblock.dylib")
    if not dylib.exists():
        print(f"{config.LOG_PREFIX} 错误: 找不到 dylib: {dylib}", file=sys.stderr)
        print(f"   → 请先由 macOS/GitHub Actions 编译 dylib（见 dylib_src/README.md），")
        print(f"     或运行 `python ad_remover.py build-dylib-help` 查看获取方式。")
        return 1
    install_name = args.install_name
    print(f"{config.LOG_PREFIX} 注入 dylib: {dylib} -> {install_name}")
    print(f"{config.LOG_PREFIX} 目标 App: {app}")
    r = macho_inject.inject_dylib(
        app, dylib, install_name=install_name, dry_run=args.dry_run, no_backup=args.no_backup)
    if r.get("error"):
        print(f"{config.LOG_PREFIX} 错误: {r['error']}", file=sys.stderr)
        return 1
    print(f"{config.LOG_PREFIX} 注入结果: injected={r['injected']} fat={r['fat']}")
    if r.get("backup"):
        print(f"    备份: {r['backup']}")
    if r.get("validation"):
        print(f"    结构校验: {'通过' if not r['validation'] else r['validation']}")
    if not r["injected"]:
        print("    （已包含该 dylib，跳过注入）")

    if args.repack and not args.dry_run:
        rp = repack.repack_to_ipa(app, Path(args.out_ipa) if args.out_ipa else None,
                                  strip=not args.no_strip)
        print(f"{config.LOG_PREFIX} 重打包 IPA: {rp.get('out_ipa')} (文件数={rp.get('files')})")
        if rp.get("stripped"):
            print(f"    已清理旧签名: {rp['stripped']}")
        print(repack.resign_notes(str(rp.get("out_ipa"))))
    elif args.repack and args.dry_run:
        rp = repack.repack_to_ipa(app, Path(args.out_ipa) if args.out_ipa else None, dry_run=True)
        print(f"{config.LOG_PREFIX} [dry-run] 预计打包 {rp.get('files')} 个文件")
    return 0


def cmd_build_dylib_help(args):
    print("""获取 adblock.dylib（Windows 无法编译 iOS dylib，需用 macOS / GitHub Actions）：

方式 1 — GitHub Actions 自动编译（推荐，配合你的手动上传）：
  1) 把本仓库（含 .github/workflows/）推送到 GitHub
  2) 打开仓库 Actions → Build adblock.dylib → 下载 Artifact: adblock.dylib
  3) 放到 ad-remover/ 根目录，或 inject 时用 --dylib 指定

方式 2 — 本地 Mac 编译：
  cd dylib_src/adblock && make

详见 dylib_src/README.md。
""")
    return 0


def cmd_all(args):
    app = _resolve_app(args)
    print(f"{config.LOG_PREFIX} === 执行全流程: scan -> report -> clean -> patch-plist -> patch-binary ===")
    scanner.scan(app)
    cmd_report(args)
    cr = resource_cleaner.clean(app, dry_run=args.dry_run, no_backup=args.no_backup)
    print(f"{config.LOG_PREFIX} clean: 目标={len(cr['targets'])} 已删={len(cr['removed'])}")
    plist_patcher.patch_plist(app, dry_run=args.dry_run, disable_ats=args.disable_ats)
    br = binary_patcher.patch_binary(app, dry_run=args.dry_run, include_tracking=args.include_tracking)
    print(f"{config.LOG_PREFIX} patch-binary: 共替换 {br.get('total_patched',0)} 处")
    if not args.dry_run:
        print(f"{config.LOG_PREFIX} 全部完成。请重签名后安装验证。")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="ad_remover",
        description="懂车帝 IPA 广告模块分析与去广告工具（Windows 命令行可用，仅依赖 Python 标准库）")
    sub = p.add_subparsers(dest="command", required=True)

    def add_common(sp):
        sp.add_argument("--app", help="AutoMobile.app 路径或含 Payload 的目录；缺省用 config.DEFAULT_APP_DIR")
        sp.add_argument("--out", help="报告输出目录（scan/report 用）")

    sp = sub.add_parser("scan", help="扫描广告产物并保存 JSON")
    add_common(sp); sp.set_defaults(func=cmd_scan)
    sp = sub.add_parser("report", help="生成广告模块详细分析报告 (Markdown+JSON)")
    add_common(sp); sp.set_defaults(func=cmd_report)
    sp = sub.add_parser("clean", help="删除广告资源与 SDK 包（安全）")
    sp.add_argument("--app"); sp.add_argument("--dry-run", action="store_true")
    sp.add_argument("--no-backup", action="store_true", help="不备份直接删除（不推荐）")
    sp.set_defaults(func=cmd_clean)
    sp = sub.add_parser("patch-plist", help="加固 Info.plist（移除广告 scheme）")
    sp.add_argument("--app"); sp.add_argument("--dry-run", action="store_true")
    sp.add_argument("--disable-ats", action="store_true", help="同时关闭 ATS 任意加载")
    sp.set_defaults(func=cmd_patch_plist)
    sp = sub.add_parser("patch-binary", help="二进制广告端点替换为 0.0.0.0")
    sp.add_argument("--app"); sp.add_argument("--dry-run", action="store_true")
    sp.add_argument("--include-tracking", action="store_true", help="一并替换埋点域名（影响统计）")
    sp.set_defaults(func=cmd_patch_binary)
    sp = sub.add_parser("all", help="依次执行 report+clean+patch-plist+patch-binary")
    add_common(sp)
    sp.add_argument("--dry-run", action="store_true")
    sp.add_argument("--no-backup", action="store_true")
    sp.add_argument("--disable-ats", action="store_true")
    sp.add_argument("--include-tracking", action="store_true")
    sp.set_defaults(func=cmd_all)
    sp = sub.add_parser("inject", help="【重签名注入路线】注入 adblock.dylib 并重打包 IPA")
    sp.add_argument("--app")
    sp.add_argument("--dylib", help="adblock.dylib 路径（缺省 ad-remover/adblock.dylib）")
    sp.add_argument("--install-name", default="@executable_path/adblock.dylib",
                    help="注入后在二进制中登记的名（默认 @executable_path/adblock.dylib）")
    sp.add_argument("--repack", action="store_true", help="注入后重打包为 .ipa")
    sp.add_argument("--out-ipa", help="输出 .ipa 路径")
    sp.add_argument("--no-strip", action="store_true", help="重打包时不清理旧签名")
    sp.add_argument("--dry-run", action="store_true")
    sp.add_argument("--no-backup", action="store_true")
    sp.set_defaults(func=cmd_inject)
    sp = sub.add_parser("build-dylib-help", help="查看如何获取 adblock.dylib")
    sp.set_defaults(func=cmd_build_dylib_help)
    return p


def main(argv=None):
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
