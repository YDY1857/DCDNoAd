# Makefile — 本地编译 adblock.dylib（需 macOS + Xcode Command Line Tools）
# 仅当你想在本地 Mac 编译时使用；CI 由 .github/workflows/build-adblock-dylib.yml 完成。
#
# 重要：广告域名清单的唯一真源是 ../../signatures/ad_signatures.json (ad_endpoints)。
# 编译前由 generate_domains.py 自动生成 adblock_domains.h（请勿手改该头文件）。

.DEFAULT_GOAL := adblock.dylib

SDK := $(shell xcrun --sdk iphoneos --show-sdk-path)
CC  := clang
PY  := python3
CFLAGS := -dynamiclib -arch arm64 -isysroot $(SDK) \
          -miphoneos-version-min=11.0 -fobjc-arc \
          -install_name @executable_path/adblock.dylib

# 域名清单头文件（由唯一真源生成）
adblock_domains.h: generate_domains.py ../../signatures/ad_signatures.json
	$(PY) generate_domains.py

adblock.dylib: adblock.m adblock_domains.h
	$(CC) $(CFLAGS) adblock.m -o adblock.dylib

clean:
	rm -f adblock.dylib adblock_domains.h

.PHONY: clean
