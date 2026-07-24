# dylib_src — 去广告注入库（非越狱重签名路线）

该目录包含注入到脱壳 IPA 主二进制的 `adblock.dylib` 源码。

## 文件
- `adblock/adblock.m` — Objective-C 源码：在 `+load` 阶段对 `NSURLSession` /
  `NSURLConnection` 做 method swizzling，把广告域名请求重定向到 `http://0.0.0.0/`。
- `adblock/Makefile` — 本地 macOS 编译脚本。
- `.github/workflows/build-adblock-dylib.yml` — 推送后由 GitHub macOS runner
  自动编译并上传 `adblock.dylib` 构件（Artifact）。

## 为什么需要 macOS 编译
iOS 的 `.dylib` 只能用 Apple Clang + iOS SDK 编译，**Windows 无法交叉编译**。
因此本仓库采用 GitHub Actions 云端编译：你 push 代码后，GitHub 自动产出
`adblock.dylib`，下载后由 Windows 工具 `ad_remover.py inject` 注入并重打包。

## 本地编译（有 Mac 时）
```bash
cd dylib_src/adblock
make
# 产出 adblock.dylib
```

## 下载 CI 编译产物
1. 打开仓库 `Actions` 页 → 选 `Build adblock.dylib` 最近一次成功运行
2. 右侧 `Artifacts` → 下载 `adblock.dylib`
3. 将其放到 `ad-remover/` 根目录（或 inject 时用 `--dylib` 指定路径）
