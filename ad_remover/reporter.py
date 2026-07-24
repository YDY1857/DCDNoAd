"""广告模块分析报告生成器。

将 scanner 的输出转换为人类可读的 Markdown 详细报告（广告代码位置、
加载机制、展示触发条件、第三方广告平台），同时保留结构化 JSON。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from . import config


def _fmt_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def build_report(scan: Dict[str, Any], sig: Dict[str, Any] | None = None) -> str:
    sig = sig or config.get_signatures()
    platforms = sig.get("third_party_platforms", {})
    res = scan.get("resources", [])
    binary = scan.get("binary", {})
    plist = scan.get("plist", {})

    ad_res = [r for r in res if r["category"] == "ad_resource"]
    ad_bundles = [r for r in res if r["category"] == "ad_bundle"]
    ad_fw = [r for r in res if r["category"] == "ad_framework"]

    total_ad_size = sum(r["size"] for r in res)

    L: List[str] = []
    L.append("# 懂车帝 (Dongchedi) 9.1.6 — 广告模块详细分析报告")
    L.append("")
    L.append(f"> 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ")
    L.append(f"> 分析目标: `{scan.get('app_dir')}`  ")
    L.append(f"> 主二进制: `{binary.get('executable')}` (约 {_fmt_size(binary.get('_executable_size',0))})")
    L.append("")
    L.append("## 1. 执行摘要")
    L.append("")
    L.append(f"- **第三方广告平台**: 检测到 {len(platforms)} 类（详见第 5 节），核心为字节跳动 **穿山甲/Pangle (ABU 聚合)**。")
    L.append(f"- **广告资源文件**: {len(ad_res)} 个（开屏/信息流/横幅/激励等动效与图片）。")
    L.append(f"- **广告 SDK 资源包**: {len(ad_bundles)} 个（BDADetailSDKResource / BDAComponentsSDKResource / ADFeelGood / BDAlogProtocol）。")
    L.append(f"- **广告相关字符串片段**: 主二进制中命中 {len(binary.get('fragments', {}))} 类关键字。")
    L.append(f"- **广告网络端点**: 主二进制中命中 {len(binary.get('endpoints', {}))} 个域名。")
    L.append(f"- **广告相关体积**: 约 {_fmt_size(total_ad_size)}（含资源与 SDK 包）。")
    L.append("- **广告 SDK 集成方式**: 静态链接进主二进制（未发现独立 `BUAdSDK.framework`），由 `BDADetailSDK` / `BDAComponentsSDK` 资源包提供素材。")
    L.append("")
    L.append("## 2. 广告代码位置")
    L.append("")
    L.append("### 2.1 广告资源文件（`ad_*` 素材）")
    L.append("")
    L.append("位于 `AutoMobile.app/` 根目录，承载广告的动效与视觉素材：")
    L.append("")
    L.append("| 文件 | 类别 | 大小 |")
    L.append("| --- | --- | --- |")
    for r in ad_res:
        L.append(f"| `{r['path']}` | {r['category']} | {_fmt_size(r['size'])} |")
    L.append("")
    L.append("### 2.2 广告 SDK 资源包（*.bundle）")
    L.append("")
    L.append("| Bundle | 说明 | 大小 |")
    L.append("| --- | --- | --- |")
    bundle_desc = {
        "BDADetailSDKResource.bundle": "穿山甲详情广告 SDK 资源",
        "BDAComponentsSDKResource.bundle": "穿山甲组件广告 SDK 资源",
        "ADFeelGood.bundle": "广告体验/反馈相关资源",
        "BDAlogProtocol.bundle": "广告日志协议资源",
    }
    for r in ad_bundles:
        L.append(f"| `{r['path']}` | {bundle_desc.get(r['path'], '广告相关包')} | {_fmt_size(r['size'])} |")
    for r in ad_fw:
        L.append(f"| `{r['path']}` | 广告框架 | {_fmt_size(r['size'])} |")
    L.append("")
    L.append("### 2.3 主二进制中的广告符号（部分混淆）")
    L.append("")
    L.append("主二进制经混淆处理，但以下明文片段仍可被定位：")
    L.append("")
    L.append("| 字符串片段 | 出现次数 | 推断用途 |")
    L.append("| --- | --- | --- |")
    frag_desc = {
        "SplashAdId": "开屏广告位 ID（触发开屏广告）",
        "AdInfo": "广告数据模型",
        "AdView": "广告视图容器",
        "AdWebView": "广告内嵌 WebView（落地页/互动）",
        "Advertisement": "广告实体/配置",
        "AdRequest": "广告请求构造",
        "AdFeedbackView": "广告反馈/关闭按钮视图",
        "showAd": "展示广告方法",
        "loadAd": "加载广告方法",
        "loaderAd": "广告加载器",
        "loadControlAd": "控制类广告加载",
        "loadAppAd": "App 下载类广告加载",
        "adDidLoad": "广告加载完成回调",
        "AdConfig": "广告配置",
        "PangleSchemeParams": "Pangle 拉起第三方 App 的 scheme 参数",
        "PangleBannerAdvertisementPlugin": "Pangle 横幅广告插件",
        "ABUIUserAuditInfoModel": "ABU 聚合审计信息模型",
    }
    for k, v in sorted(binary.get("fragments", {}).items(), key=lambda x: -x[1]):
        L.append(f"| `{k}` | {v} | {frag_desc.get(k, '广告相关')} |")
    L.append("")

    L.append("## 3. 广告加载机制")
    L.append("")
    L.append("根据静态特征推断的整体流程（无法在此环境动态验证，需重签名后真机确认）：")
    L.append("")
    L.append("1. **初始化**: 应用启动时由 `BDADetailSDK` / `BDAComponentsSDK` 初始化穿山甲聚合 SDK（ABU 层），")
    L.append("   读取 `AdConfig` 与广告位 ID（如 `SplashAdId`）。")
    L.append("2. **请求**: 通过 `AdRequest` 向广告端点拉取广告（见第 4 节域名）。")
    L.append("3. **渲染**: 命中后由 `AdView` / `AdWebView` 渲染；开屏广告用 `SplashAdId` 对应素材，")
    L.append("   信息流广告使用 `ad_double_feed_wipe` / `ad_feed_wipe` 等动效资源，横幅使用 `ad_banner_*_btn.json`。")
    L.append("4. **回调**: `adDidLoad` 后调用 `showAd` 展示；用户可经 `AdFeedbackView` 反馈/关闭。")
    L.append("5. **跳转**: `PangleSchemeParams` 用于拉起落地页或第三方 App（通过 `LSApplicationQueriesSchemes` 中登记的 scheme）。")
    L.append("")
    L.append("## 4. 广告展示触发条件")
    L.append("")
    L.append("- **开屏广告**: 冷启动 / 回到前台时，依据 `SplashAdId` 拉取并全屏展示。")
    L.append("- **信息流广告**: 内容流中按频次插入（对应 `ad_double_feed_wipe` / `ad_feed_shake` / `ad_feed_wipe` 动效）。")
    L.append("- **横幅广告**: 列表/详情页底部（对应 `ad_banner_*_btn.json` 按钮素材）。")
    L.append("- **激励/互动广告**: 通过 `AdWebView` 与 `PangleBannerAdvertisementPlugin` 承载。")
    L.append("")
    L.append("### 4.1 广告网络请求端点")
    L.append("")
    L.append("主二进制中明文出现的端点（打补丁阶段将替换为 `0.0.0.0` 以阻断广告请求）：")
    L.append("")
    L.append("| 域名 | 次数 | 分类 |")
    L.append("| --- | --- | --- |")
    ad_eps = set(sig.get("ad_endpoints", []))
    track_eps = set(sig.get("tracking_endpoints", []))
    for ep, n in sorted(binary.get("endpoints", {}).items(), key=lambda x: -x[1]):
        cat = "广告" if ep in ad_eps else ("埋点/追踪" if ep in track_eps else "其它")
        L.append(f"| `{ep}` | {n} | {cat} |")
    L.append("")
    L.append("## 5. 第三方广告平台")
    L.append("")
    for key, info in platforms.items():
        L.append(f"### 5.{list(platforms.keys()).index(key)+1} {info.get('name')}")
        L.append("")
        L.append(f"- **标识**: {', '.join('`'+i+'`' for i in info.get('identifiers', []))}")
        L.append(f"- **说明**: {info.get('note','')}")
        L.append("")
    L.append("## 6. Info.plist 中的广告相关配置")
    L.append("")
    if plist.get("exists"):
        L.append(f"- **NSAllowsArbitraryLoads (ATS)**: {plist.get('ats_allows_arbitrary_loads')}（允许明文 HTTP，广告/埋点常用）。")
        L.append(f"- **广告相关 URL Scheme**: {len(plist.get('ad_url_schemes', []))} 个")
        for s in plist.get("ad_url_schemes", []):
            L.append(f"  - `{s['scheme']}` (name: {s['name']})")
        L.append(f"- **广告相关 Query Scheme**: {len(plist.get('ad_query_schemes', []))} 个")
        if plist.get("ad_query_schemes"):
            L.append(f"  - {', '.join('`'+q+'`' for q in plist.get('ad_query_schemes', []))}")
        L.append(f"- **用户追踪描述 (NSUserTrackingUsageDescription)**: {plist.get('user_tracking_desc') or '未设置'}")
    else:
        L.append("- 未找到 Info.plist")
    L.append("")
    L.append("## 7. 去除广告的自动化建议（由配套工具执行）")
    L.append("")
    L.append("1. **删除广告资源**: 移除全部 `ad_*` 素材（安全、无副作用）。")
    L.append("2. **删除广告 SDK 资源包**: 移除 `BDADetailSDKResource` / `BDAComponentsSDKResource` / `ADFeelGood` / `BDAlogProtocol`（安全）。")
    L.append("3. **加固 Info.plist**: 移除广告相关 URL/Query Scheme，关闭 ATS 任意加载（可选）。")
    L.append("4. **阻断广告请求**: 将第 4.1 节端点在二进制中等长替换为 `0.0.0.0`，使广告请求失败。")
    L.append("5. **重签名**: 二进制打补丁会破坏原有代码签名，需用开发者证书/自签重新签名后方可安装（详见 README）。")
    L.append("")
    L.append("> ⚠️ 注意：功能验证需在越狱设备或持有开发者证书的设备上重签名安装后进行，本工具仅负责分析与改造 IPA 包体。")
    return "\n".join(L)


def write_report(scan: Dict[str, Any], out_dir: Path, sig: Dict[str, Any] | None = None) -> Dict[str, str]:
    sig = sig or config.get_signatures()
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    md = build_report(scan, sig)
    md_path = out_dir / "ad_module_analysis_report.md"
    json_path = out_dir / "ad_module_scan.json"
    md_path.write_text(md, encoding="utf-8")
    json_path.write_text(json.dumps(scan, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"markdown": str(md_path), "json": str(json_path)}


if __name__ == "__main__":
    import sys
    from . import scanner as _scanner
    t = sys.argv[1] if len(sys.argv) > 1 else config.DEFAULT_APP_DIR
    s = _scanner.scan(Path(t))
    paths = write_report(s, Path("report"))
    print("报告已生成:")
    for k, v in paths.items():
        print(f"  {k}: {v}")
