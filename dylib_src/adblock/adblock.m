// adblock.m — 懂车帝去广告注入库（非越狱重签名注入路线）
//
// 原理：作为 dylib 注入 App 主二进制后，在 +load/构造函数中对
// NSURLSession / NSURLConnection 的类方法进行 method swizzling，
// 在请求发出前把广告域名（与 signatures/ad_signatures.json 的 ad_endpoints 一致）重定向到
// http://0.0.0.0/，使广告请求快速失败、广告无法加载。
//
// 该方案不依赖任何具体广告类/方法名（App 已混淆），只在网络层拦截，
// 因此对混淆具有天然鲁棒性。仅依赖 Objective-C runtime，无需 Cydia
// Substrate / fishhook，可直接用 Xcode Clang 编译为 iOS dylib。
//
// 编译（macOS + Xcode）：
//   clang -dynamiclib -arch arm64 \
//     -isysroot $(xcrun --sdk iphoneos --show-sdk-path) \
//     -miphoneos-version-min=11.0 -fobjc-arc \
//     -install_name @executable_path/adblock.dylib \
//     adblock.m -o adblock.dylib
// CI 中由 .github/workflows/build-adblock-dylib.yml 自动完成。

#import <Foundation/Foundation.h>
#import <objc/runtime.h>

/* 广告域名清单由编译前生成的 adblock_domains.h 提供。
   唯一真源见 signatures/ad_signatures.json 的 ad_endpoints；
   改名单只需编辑该 JSON，重新编译即可，无需改动本文件。 */
#include "adblock_domains.h"

static BOOL isAdHost(NSString *host) {
    if (host.length == 0) return NO;
    for (int i = 0; kAdHosts[i] != NULL; i++) {
        NSString *needle = [NSString stringWithUTF8String:kAdHosts[i]];
        if ([host rangeOfString:needle options:NSCaseInsensitiveSearch].location != NSNotFound) {
            return YES;
        }
    }
    return NO;
}

// 把广告请求重定向到 0.0.0.0，使其连接被拒、快速失败（与二进制补丁策略一致）
static NSURLRequest *rewriteIfAd(NSURLRequest *req) {
    NSURL *url = req.URL;
    if (url && isAdHost(url.host)) {
        NSURL *blocked = [NSURL URLWithString:@"http://0.0.0.0/"];
        NSMutableURLRequest *m = [req mutableCopy];
        m.URL = blocked;
        return m;
    }
    return req;
}

static void swizzle_class_method(Class cls, SEL orig, SEL repl) {
    if (!cls) return;
    Method m1 = class_getClassMethod(cls, orig);
    Method m2 = class_getClassMethod(cls, repl);
    if (m1 && m2) method_exchangeImplementations(m1, m2);
}

// === NSURLSession 交换实现（类方法）===
@interface NSURLSession (AdBlock)
+ (id)adblock_dataTaskWithRequest:(NSURLRequest *)req;
+ (id)adblock_dataTaskWithRequest:(NSURLRequest *)req
                 completionHandler:(void (^)(NSData *, NSURLResponse *, NSError *))h;
@end

@implementation NSURLSession (AdBlock)
+ (id)adblock_dataTaskWithRequest:(NSURLRequest *)req {
    // 交换后，此处 self 调用 adblock_dataTaskWithRequest: 实际指向原始实现
    return [self adblock_dataTaskWithRequest:rewriteIfAd(req)];
}
+ (id)adblock_dataTaskWithRequest:(NSURLRequest *)req
                 completionHandler:(void (^)(NSData *, NSURLResponse *, NSError *))h {
    return [self adblock_dataTaskWithRequest:rewriteIfAd(req) completionHandler:h];
}
@end

// === NSURLConnection 交换实现（实例方法）===
@interface NSURLConnection (AdBlock)
- (instancetype)adblock_initWithRequest:(NSURLRequest *)req delegate:(id)delegate;
@end

@implementation NSURLConnection (AdBlock)
- (instancetype)adblock_initWithRequest:(NSURLRequest *)req delegate:(id)delegate {
    return [self adblock_initWithRequest:rewriteIfAd(req) delegate:delegate];
}
@end

__attribute__((constructor)) static void adblock_init(void) {
    swizzle_class_method(objc_getClass("NSURLSession"),
                  @selector(dataTaskWithRequest:),
                  @selector(adblock_dataTaskWithRequest:));
    swizzle_class_method(objc_getClass("NSURLSession"),
                  @selector(dataTaskWithRequest:completionHandler:),
                  @selector(adblock_dataTaskWithRequest:completionHandler:));

    Class connCls = objc_getClass("NSURLConnection");
    if (connCls) {
        Method m1 = class_getInstanceMethod(connCls, @selector(initWithRequest:delegate:));
        Method m2 = class_getInstanceMethod(connCls, @selector(adblock_initWithRequest:delegate:));
        if (m1 && m2) method_exchangeImplementations(m1, m2);
    }
}
