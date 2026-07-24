# 懂车帝 (Dongchedi) 9.1.6 — 广告模块分析与去广告工具包

针对已解压的 iOS IPA 应用（`Payload/AutoMobile.app`），自动化完成：
**广告模块分析 → 去广告改造 → 重打包/注入 → 重签名安装**。

> ⚠️ 法律与合规提示：本工具仅用于你**拥有合法权利**的设备/应用（如自有的开发者包、已付费去广告版本的研究）。
> 去除广告会改变应用原有行为，且改动会破坏代码签名，**必须重签名后方可安装**。请在合法授权范围内使用。

---

## 1. 环境要求

- **Windows 10/11**（亦可在 macOS/Linux 运行）
- **Python 3.8+**（仅使用标准库，**无需 `pip install`**）
  - WorkBuddy 用户可直接使用内置 Python：
    `C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe`
- 一条命令即可运行，**无需任何第三方依赖**。
- **（仅 dylib 路线需要）iOS dylib 编译环境**：macOS + Xcode，或本仓库自带的 GitHub Actions 自动编译。

## 2. 两条去广告路线（先选路线）

| 路线 | 命令 | 适用环境 | 原理 |
| --- | --- | --- | --- |
| **A. 静态二进制补丁** | `all` | 越狱机 / 重签名安装 | 直接改写主二进制里的广告域名 + 删素材 |
| **B. dylib 注入（推荐你的场景）** | `inject` | **非越狱重签名注入脱壳包** | 把 `adblock.dylib` 注入主二进制，运行时网络层拦截广告请求 |

> 你确认的目标环境是 **「重签名注入安装脱壳包」**，对应 **路线 B**。
> 路线 B 的 `adblock.dylib` 必须由 macOS/Xcode 编译（Windows 无法交叉编译），
> 本仓库已内置 **GitHub Actions 工作流**，push 后自动用 GitHub 的 macOS runner 编译并产出 `adblock.dylib`。

## 3. 目录结构

```
ad-remover/
├── ad_remover.py              # 顶层启动器（python ad_remover.py <命令>）
├── run.bat                    # Windows 一键启动脚本
├── requirements.txt           # 依赖说明（仅标准库）
├── README.md                  # 本文件
├── UPLOAD_GUIDE.md            # GitHub 手动上传完整教程（网页无法直传文件夹）
├── signatures/
│   └── ad_signatures.json     # 广告特征签名库（端点/资源名/SDK 包/平台，可编辑）
├── ad_remover/
│   ├── __init__.py
│   ├── config.py              # 配置加载与路径推断
│   ├── scanner.py             # 扫描广告产物（资源/包/二进制字符串/端点/plist）
│   ├── reporter.py            # 生成详细分析报告 (Markdown+JSON)
│   ├── resource_cleaner.py    # 安全删除广告资源与 SDK 包（带备份）
│   ├── plist_patcher.py       # 加固 Info.plist（移除广告 scheme）
│   ├── binary_patcher.py      # 路线A：二进制广告端点等长替换为 0.0.0.0
│   ├── macho_inject.py        # 路线B：纯 Python 向 Mach-O 注入 LC_LOAD_DYLIB
│   ├── repack.py              # 路线B：重打包 IPA + 重签名命令说明
│   └── cli.py                 # 命令行接口
├── dylib_src/                 # 路线B 的注入库源码（需 macOS/CI 编译）
│   ├── README.md              # dylib 编译与获取说明
│   └── adblock/
│       ├── adblock.m          # Objective-C 去广告注入库（网络层拦截广告域名）
│       ├── generate_domains.py# 由签名库生成 adblock_domains.h（域名清单唯一真源）
│       └── Makefile           # 本地 macOS 编译脚本（先生成头文件再编译）
├── .github/workflows/         # GitHub Actions 自动编译 adblock.dylib
│   └── build-adblock-dylib.yml
├── report/                    # 运行后生成的报告（ad_module_analysis_report.md 等）
└── examples/                  # 示例
```

## 4. 命令一览

| 命令 | 作用 |
| --- | --- |
| `scan` | 扫描广告产物，保存 `report/ad_module_scan.json` |
| `report` | 生成**广告模块详细分析报告** `report/ad_module_analysis_report.md` |
| `clean` | 删除广告资源文件与广告 SDK 包（安全，默认先备份） |
| `patch-plist` | 移除 Info.plist 中广告相关 URL/Query Scheme（`--disable-ats` 可关 ATS） |
| `patch-binary` | 路线A：将二进制中广告域名等长替换为 `0.0.0.0` |
| `all` | 路线A：依次执行 report → clean → patch-plist → patch-binary |
| `inject` | **路线B**：注入 `adblock.dylib` 并可选重打包 IPA |
| `build-dylib-help` | 查看如何获取 `adblock.dylib` |

通用参数：
- `--app "路径\AutoMobile.app"`：指定目标；可传 `.app` 或含 `Payload` 的目录。
- `--dry-run`：仅预演，不改动任何文件。

## 5. 路线 B 完整流程（重签名注入脱壳包）

### 步骤 1：获取 adblock.dylib（两种方式）
- **方式 1（推荐，配合你的手动上传）**：把本仓库推到 GitHub 后，打开仓库
  `Actions` → `Build adblock.dylib` → 下载 Artifact `adblock.dylib`，放到 `ad-remover/` 根目录。
- **方式 2（本地有 Mac）**：`cd dylib_src/adblock && make`。
- 详见 `dylib_src/README.md`。若未获取到 dylib，`inject` 会直接报错提示。

### 步骤 2：注入 + 重打包（Windows 命令行）
```bat
cd ad-remover
:: 先预演，确认无误
run.bat inject --app "E:\codex自动化项目\懂车帝逆向\懂车帝9.1.6\Payload\AutoMobile.app" --dry-run
:: 正式注入并把 .app 重打包为 .ipa（--out-ipa 可指定输出）
run.bat inject --app "E:\codex自动化项目\懂车帝逆向\懂车帝9.1.6\Payload\AutoMobile.app" --repack
```
`inject` 会：① 把 `adblock.dylib` 复制进 `.app`；② 在主二进制插入
`LC_LOAD_DYLIB @executable_path/adblock.dylib`（纯 Python 改写 Mach-O，已对真实二进制校验通过）；
③ `--repack` 时重打包为 `Payload/AutoMobile.app` 结构的 `.ipa` 并清理旧签名。

### 步骤 3：重签名（必须）
注入破坏了原签名，安装前需重签。输出已含命令示例，二选一：
- **Windows 用 zsign**（推荐，无需 Mac）：
  ```
  zsign -k cert.p12 -p <p12密码> -m embedded.mobileprovision -z <TeamID> -o signed.ipa AutoMobile.ipa
  ```
- **macOS 用 codesign**：解包后 `codesign -f -s "Apple Development: ..." AutoMobile.app` 再压回。

### 步骤 4：安装
用 AltStore / Sideloadly / 爱思助手 等把 `signed.ipa` 装到设备验证广告是否消失。

## 6. 路线 A（静态补丁）快速开始

```bat
cd ad-remover
run.bat scan   --app "E:\codex自动化项目\懂车帝逆向\懂车帝9.1.6\Payload\AutoMobile.app"
run.bat report --app "E:\codex自动化项目\懂车帝逆向\懂车帝9.1.6\Payload\AutoMobile.app"
run.bat all    --app "E:\codex自动化项目\懂车帝逆向\懂车帝9.1.6\Payload\AutoMobile.app" --dry-run
run.bat all    --app "E:\codex自动化项目\懂车帝逆向\懂车帝9.1.6\Payload\AutoMobile.app"
```
完成后同样需重签名（`patch-binary` 改动了二进制）后安装。

## 7. 技术说明

- **广告 SDK 集成方式**：穿山甲/Pangle（ABU 聚合）被**静态链接**进主二进制（未发现独立 `BUAdSDK.framework`），
  素材由 `BDADetailSDKResource` / `BDAComponentsSDKResource` 等 `.bundle` 提供。
- **路线 B 的健壮性**：`adblock.dylib` 在网络层（`NSURLSession` / `NSURLConnection`）拦截广告域名并
  重定向到 `http://0.0.0.0`，**不依赖具体广告类名/方法名**，对混淆天然鲁棒；仅用 Obj-C runtime，无需 fishhook/Substrate。
- **路线 B 的 Mach-O 注入策略**：在 64 位 Mach-O 的 load commands 区插入 `LC_LOAD_DYLIB`，并把因插入而
  向后平移的所有文件偏移（段 fileoff、符号表、dyld_info、代码签名 dataoff 等）同步增加插入字节数，
  保证结构合法（已在真实 434MB 主二进制上验证：文件增大 56 字节、ncmds 155→156、各偏移正确平移）。
- **可逆性**：`clean` / `patch-plist` / `inject` 均在改动前自动备份（`_ad_remover_backup/`、`*.adremover.bak`）。

## 8. 发布到 GitHub（手动上传）

由于 GitHub 网页端**不能直接上传文件夹**，请按 [UPLOAD_GUIDE.md](UPLOAD_GUIDE.md) 的逐文件教程操作，
或改用 GitHub Desktop（可整体拖入并自动遵循 .gitignore）。
**注意**：本版新增的 `dylib_src/`、`ad_remover/macho_inject.py`、`ad_remover/repack.py`、
以及 `.github/workflows/build-adblock-dylib.yml` 都需一并上传，否则路线 B 与自动编译无法使用。

## 9. 可扩展性

编辑 `signatures/ad_signatures.json` 的 `ad_endpoints` 即可增删被拦截的广告域名——**路线 A（二进制补丁）与路线 B（dylib 注入）共用同一份清单（唯一真源）**，改一处即两路同步生效，无需改动任何代码。
