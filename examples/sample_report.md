# 懂车帝 (Dongchedi) 9.1.6 — 广告模块详细分析报告

> 生成时间: 2026-07-24 17:10:41  
> 分析目标: `E:\codex自动化项目\懂车帝逆向\懂车帝9.1.6\Payload\AutoMobile.app`  
> 主二进制: `E:\codex自动化项目\懂车帝逆向\懂车帝9.1.6\Payload\AutoMobile.app\AutoMobile` (约 414.3 MB)

## 1. 执行摘要

- **第三方广告平台**: 检测到 5 类（详见第 5 节），核心为字节跳动 **穿山甲/Pangle (ABU 聚合)**。
- **广告资源文件**: 9 个（开屏/信息流/横幅/激励等动效与图片）。
- **广告 SDK 资源包**: 4 个（BDADetailSDKResource / BDAComponentsSDKResource / ADFeelGood / BDAlogProtocol）。
- **广告相关字符串片段**: 主二进制中命中 16 类关键字。
- **广告网络端点**: 主二进制中命中 12 个域名。
- **广告相关体积**: 约 447.9 KB（含资源与 SDK 包）。
- **广告 SDK 集成方式**: 静态链接进主二进制（未发现独立 `BUAdSDK.framework`），由 `BDADetailSDK` / `BDAComponentsSDK` 资源包提供素材。

## 2. 广告代码位置

### 2.1 广告资源文件（`ad_*` 素材）

位于 `AutoMobile.app/` 根目录，承载广告的动效与视觉素材：

| 文件 | 类别 | 大小 |
| --- | --- | --- |
| `ad_banner_black_btn.json` | ad_resource | 19.7 KB |
| `ad_banner_white_btn.json` | ad_resource | 19.2 KB |
| `ad_banner_yellow_btn.json` | ad_resource | 19.5 KB |
| `ad_double_feed_wipe.json` | ad_resource | 261.6 KB |
| `ad_double_feed_wipe.webp` | ad_resource | 35.3 KB |
| `ad_feed_shake.json` | ad_resource | 1.8 KB |
| `ad_feed_wipe.json` | ad_resource | 5.5 KB |
| `ad_feed_wipe_bg.png` | ad_resource | 4.8 KB |
| `ad_webview_bottom_ arrow.json` | ad_resource | 2.5 KB |

### 2.2 广告 SDK 资源包（*.bundle）

| Bundle | 说明 | 大小 |
| --- | --- | --- |
| `ADFeelGood.bundle` | 广告体验/反馈相关资源 | 5.9 KB |
| `BDAComponentsSDKResource.bundle` | 穿山甲组件广告 SDK 资源 | 25.3 KB |
| `BDADetailSDKResource.bundle` | 穿山甲详情广告 SDK 资源 | 45.9 KB |
| `BDAlogProtocol.bundle` | 广告日志协议资源 | 1.1 KB |

### 2.3 主二进制中的广告符号（部分混淆）

主二进制经混淆处理，但以下明文片段仍可被定位：

| 字符串片段 | 出现次数 | 推断用途 |
| --- | --- | --- |
| `AdInfo` | 99 | 广告数据模型 |
| `showAd` | 92 | 展示广告方法 |
| `loadAd` | 37 | 加载广告方法 |
| `Advertisement` | 29 | 广告实体/配置 |
| `AdView` | 28 | 广告视图容器 |
| `AdWebView` | 24 | 广告内嵌 WebView（落地页/互动） |
| `loaderAd` | 11 | 广告加载器 |
| `SplashAdId` | 9 | 开屏广告位 ID（触发开屏广告） |
| `loadControlAd` | 8 | 控制类广告加载 |
| `loadAppAd` | 8 | App 下载类广告加载 |
| `AdRequest` | 6 | 广告请求构造 |
| `AdFeedbackView` | 6 | 广告反馈/关闭按钮视图 |
| `PangleSchemeParams` | 5 | Pangle 拉起第三方 App 的 scheme 参数 |
| `ABUIUserAuditInfoModel` | 3 | ABU 聚合审计信息模型 |
| `AdConfig` | 1 | 广告配置 |
| `PangleBannerAdvertisementPlugin` | 1 | Pangle 横幅广告插件 |

## 3. 广告加载机制

根据静态特征推断的整体流程（无法在此环境动态验证，需重签名后真机确认）：

1. **初始化**: 应用启动时由 `BDADetailSDK` / `BDAComponentsSDK` 初始化穿山甲聚合 SDK（ABU 层），
   读取 `AdConfig` 与广告位 ID（如 `SplashAdId`）。
2. **请求**: 通过 `AdRequest` 向广告端点拉取广告（见第 4 节域名）。
3. **渲染**: 命中后由 `AdView` / `AdWebView` 渲染；开屏广告用 `SplashAdId` 对应素材，
   信息流广告使用 `ad_double_feed_wipe` / `ad_feed_wipe` 等动效资源，横幅使用 `ad_banner_*_btn.json`。
4. **回调**: `adDidLoad` 后调用 `showAd` 展示；用户可经 `AdFeedbackView` 反馈/关闭。
5. **跳转**: `PangleSchemeParams` 用于拉起落地页或第三方 App（通过 `LSApplicationQueriesSchemes` 中登记的 scheme）。

## 4. 广告展示触发条件

- **开屏广告**: 冷启动 / 回到前台时，依据 `SplashAdId` 拉取并全屏展示。
- **信息流广告**: 内容流中按频次插入（对应 `ad_double_feed_wipe` / `ad_feed_shake` / `ad_feed_wipe` 动效）。
- **横幅广告**: 列表/详情页底部（对应 `ad_banner_*_btn.json` 按钮素材）。
- **激励/互动广告**: 通过 `AdWebView` 与 `PangleBannerAdvertisementPlugin` 承载。

### 4.1 广告网络请求端点

主二进制中明文出现的端点（打补丁阶段将替换为 `0.0.0.0` 以阻断广告请求）：

| 域名 | 次数 | 分类 |
| --- | --- | --- |
| `snssdk.com` | 167 | 埋点/追踪 |
| `pstatp.com` | 21 | 埋点/追踪 |
| `toutiao.com` | 21 | 埋点/追踪 |
| `ad.zijieapi.com` | 5 | 广告 |
| `log.zijieapi.com` | 5 | 广告 |
| `log.snssdk.com` | 3 | 埋点/追踪 |
| `ad.oceanengine.com` | 2 | 广告 |
| `ads.tiktok.com` | 2 | 广告 |
| `csjsd.com` | 1 | 广告 |
| `ading.snssdk.com` | 1 | 广告 |
| `adisoffshore.com` | 1 | 广告 |
| `adisglobal.com` | 1 | 广告 |

## 5. 第三方广告平台

### 5.1 穿山甲 / Pangle (ByteDance 聚合广告 SDK)

- **标识**: `ABU`, `CSJ`, `Pangle`, `BUAd`, `BUNative`, `BDADetailSDK`, `BDAComponentsSDK`
- **说明**: 字节跳动旗下广告平台，ABU 为聚合层，CSJ(穿山甲) 为具体广告源。

### 5.2 巨量引擎 (OceanEngine)

- **标识**: `oceanengine.com`, `ad.oceanengine.com`
- **说明**: 字节跳动广告投放平台，承载广告请求与渲染配置。

### 5.3 TikTok Ads

- **标识**: `ads.tiktok.com`
- **说明**: 海外广告投放端点。

### 5.4 字节内部广告服务 (zijieapi)

- **标识**: `ad.zijieapi.com`, `log.zijieapi.com`
- **说明**: 懂车帝/今日头条共用的内部广告与日志端点。

### 5.5 snssdk 广告/埋点域

- **标识**: `ading.snssdk.com`, `snssdk.com`
- **说明**: 字节系通用域名，含广告与埋点流量。

## 6. Info.plist 中的广告相关配置

- **NSAllowsArbitraryLoads (ATS)**: True（允许明文 HTTP，广告/埋点常用）。
- **广告相关 URL Scheme**: 5 个
  - `auto.snssdk.com` (name: haohuoSnssdk)
  - `snssdk36` (name: own)
  - `snssdk36` (name: alipayShare)
  - `pay-dcar.snssdk.com` (name: wechatPay)
  - `pay-dcar.snssdk.com` (name: wxh5pay)
- **广告相关 Query Scheme**: 8 个
  - `snssdk32`, `snssdk6575`, `snssdk35`, `snssdk141`, `snssdk1112`, `snssdk1128`, `snssdk1165`, `snssdk51`
- **用户追踪描述 (NSUserTrackingUsageDescription)**: 请放心，开启权限不会获取你在其他应用的隐私信息，该权限仅用于标识设备并保障服务安全与提升浏览体验


## 7. 去除广告的自动化建议（由配套工具执行）

1. **删除广告资源**: 移除全部 `ad_*` 素材（安全、无副作用）。
2. **删除广告 SDK 资源包**: 移除 `BDADetailSDKResource` / `BDAComponentsSDKResource` / `ADFeelGood` / `BDAlogProtocol`（安全）。
3. **加固 Info.plist**: 移除广告相关 URL/Query Scheme，关闭 ATS 任意加载（可选）。
4. **阻断广告请求**: 将第 4.1 节端点在二进制中等长替换为 `0.0.0.0`，使广告请求失败。
5. **重签名**: 二进制打补丁会破坏原有代码签名，需用开发者证书/自签重新签名后方可安装（详见 README）。

> ⚠️ 注意：功能验证需在越狱设备或持有开发者证书的设备上重签名安装后进行，本工具仅负责分析与改造 IPA 包体。
