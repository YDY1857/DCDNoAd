// adblock.m — 懂车帝去广告注入库（非越狱重签名注入路线）
//
// 原理：作为 dylib 注入 App 主二进制后，在 +load/构造函数中对
// NSURLSession / NSURLConnection 的实例方法进行 method swizzling，
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
#import <UIKit/UIKit.h>
#import <objc/runtime.h>

/* 广告域名清单由编译前生成的 adblock_domains.h 提供。
   唯一真源见 signatures/ad_signatures.json 的 ad_endpoints；
   改名单只需编辑该 JSON，重新编译即可，无需改动本文件。 */
#include "adblock_domains.h"

static NSString *const kWelcomeShownKey = @"com.iosguowuji.adblock.welcome-shown";
static NSString *const kAvatarBase64 = @"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";

@class GWWelcomeViewController;
static GWWelcomeViewController *gWelcomeController;
static id gWelcomeObserver;

@interface GWWelcomeViewController : UIViewController
@property(nonatomic, strong) UIButton *enterButton;
@property(nonatomic, strong) NSTimer *timer;
@property(nonatomic) NSInteger secondsLeft;
@end

@implementation GWWelcomeViewController

- (void)viewDidLoad {
    [super viewDidLoad];
    self.view.backgroundColor = [UIColor colorWithWhite:0 alpha:0.55];
    self.view.accessibilityViewIsModal = YES;

    UIView *card = [UIView new];
    card.translatesAutoresizingMaskIntoConstraints = NO;
    card.backgroundColor = UIColor.whiteColor;
    card.layer.cornerRadius = 8;

    UILabel *title = [UILabel new];
    title.text = @"恭喜您成功安装本应用";
    title.font = [UIFont boldSystemFontOfSize:20];
    title.textColor = UIColor.blackColor;
    title.textAlignment = NSTextAlignmentCenter;
    title.numberOfLines = 0;
    title.accessibilityTraits = UIAccessibilityTraitHeader;

    UILabel *brand = [UILabel new];
    brand.text = @"IOS果物集";
    brand.font = [UIFont boldSystemFontOfSize:18];
    brand.textColor = [UIColor colorWithRed:0.88 green:0.12 blue:0.15 alpha:1];

    NSData *avatarData = [[NSData alloc] initWithBase64EncodedString:kAvatarBase64 options:0];
    UIImageView *avatar = [[UIImageView alloc] initWithImage:[UIImage imageWithData:avatarData]];
    avatar.translatesAutoresizingMaskIntoConstraints = NO;
    avatar.contentMode = UIViewContentModeScaleAspectFit;
    avatar.layer.cornerRadius = 6;
    avatar.clipsToBounds = YES;
    avatar.isAccessibilityElement = YES;
    avatar.accessibilityLabel = @"IOS果物集头像";
    [NSLayoutConstraint activateConstraints:@[
        [avatar.widthAnchor constraintEqualToConstant:36],
        [avatar.heightAnchor constraintEqualToConstant:36],
    ]];

    UIStackView *brandRow = [[UIStackView alloc] initWithArrangedSubviews:@[brand, avatar]];
    brandRow.axis = UILayoutConstraintAxisHorizontal;
    brandRow.alignment = UIStackViewAlignmentCenter;
    brandRow.spacing = 8;

    UIView *brandContainer = [UIView new];
    [brandContainer addSubview:brandRow];
    brandRow.translatesAutoresizingMaskIntoConstraints = NO;
    [NSLayoutConstraint activateConstraints:@[
        [brandRow.centerXAnchor constraintEqualToAnchor:brandContainer.centerXAnchor],
        [brandRow.topAnchor constraintEqualToAnchor:brandContainer.topAnchor],
        [brandRow.bottomAnchor constraintEqualToAnchor:brandContainer.bottomAnchor],
    ]];

    UILabel *welcome = [UILabel new];
    welcome.text = @"欢迎使用";
    welcome.font = [UIFont systemFontOfSize:17 weight:UIFontWeightMedium];
    welcome.textAlignment = NSTextAlignmentCenter;

    UILabel *notice = [UILabel new];
    notice.text = @"严禁任何贩卖本插件/软件的盈利行为\n本插件仅供学习研究使用\n请在24小时内自觉删除本插件/软件";
    notice.font = [UIFont systemFontOfSize:14];
    notice.textColor = UIColor.darkTextColor;
    notice.textAlignment = NSTextAlignmentCenter;
    notice.numberOfLines = 0;

    self.enterButton = [UIButton buttonWithType:UIButtonTypeSystem];
    self.enterButton.translatesAutoresizingMaskIntoConstraints = NO;
    self.enterButton.titleLabel.font = [UIFont boldSystemFontOfSize:17];
    self.enterButton.backgroundColor = [UIColor colorWithRed:0 green:0.48 blue:1 alpha:1];
    self.enterButton.layer.cornerRadius = 8;
    self.enterButton.enabled = NO;
    self.enterButton.alpha = 0.55;
    [self.enterButton setTitleColor:UIColor.whiteColor forState:UIControlStateNormal];
    [self.enterButton addTarget:self action:@selector(enterApp) forControlEvents:UIControlEventTouchUpInside];
    [self.enterButton.heightAnchor constraintEqualToConstant:48].active = YES;

    UIStackView *stack = [[UIStackView alloc] initWithArrangedSubviews:@[title, brandContainer, welcome, notice, self.enterButton]];
    stack.translatesAutoresizingMaskIntoConstraints = NO;
    stack.axis = UILayoutConstraintAxisVertical;
    stack.alignment = UIStackViewAlignmentFill;
    stack.spacing = 16;

    [self.view addSubview:card];
    [card addSubview:stack];
    NSLayoutConstraint *cardWidth = [card.widthAnchor constraintEqualToConstant:340];
    cardWidth.priority = UILayoutPriorityDefaultHigh;
    [NSLayoutConstraint activateConstraints:@[
        [card.centerXAnchor constraintEqualToAnchor:self.view.centerXAnchor],
        [card.centerYAnchor constraintEqualToAnchor:self.view.centerYAnchor],
        [card.leadingAnchor constraintGreaterThanOrEqualToAnchor:self.view.leadingAnchor constant:20],
        [card.trailingAnchor constraintLessThanOrEqualToAnchor:self.view.trailingAnchor constant:-20],
        [card.widthAnchor constraintLessThanOrEqualToConstant:340],
        cardWidth,
        [stack.topAnchor constraintEqualToAnchor:card.topAnchor constant:24],
        [stack.leadingAnchor constraintEqualToAnchor:card.leadingAnchor constant:20],
        [stack.trailingAnchor constraintEqualToAnchor:card.trailingAnchor constant:-20],
        [stack.bottomAnchor constraintEqualToAnchor:card.bottomAnchor constant:-24],
    ]];

    self.secondsLeft = 10;
    [self updateButton];
    self.timer = [NSTimer scheduledTimerWithTimeInterval:1 target:self selector:@selector(tick:) userInfo:nil repeats:YES];
}

- (void)tick:(NSTimer *)timer {
    self.secondsLeft--;
    [self updateButton];
    if (self.secondsLeft == 0) {
        [self.timer invalidate];
        self.timer = nil;
        self.enterButton.enabled = YES;
        self.enterButton.alpha = 1;
    }
}

- (void)updateButton {
    NSString *title = self.secondsLeft > 0
        ? [NSString stringWithFormat:@"进入应用（%ld）", (long)self.secondsLeft]
        : @"进入应用";
    [self.enterButton setTitle:title forState:UIControlStateNormal];
}

- (void)enterApp {
    [self.timer invalidate];
    [UIView animateWithDuration:0.2 animations:^{
        self.view.alpha = 0;
    } completion:^(BOOL finished) {
        [self.view removeFromSuperview];
        gWelcomeController = nil;
    }];
}

@end

static UIWindow *welcomeWindow(void) {
    for (UIWindow *window in UIApplication.sharedApplication.windows) {
        if (window.isKeyWindow) return window;
    }
    return UIApplication.sharedApplication.windows.firstObject;
}

static BOOL showWelcomeIfNeeded(void) {
    NSUserDefaults *defaults = NSUserDefaults.standardUserDefaults;
    if ([defaults boolForKey:kWelcomeShownKey] || gWelcomeController) return NO;
    UIWindow *window = welcomeWindow();
    if (!window) return NO;

    gWelcomeController = [GWWelcomeViewController new];
    gWelcomeController.view.frame = window.bounds;
    gWelcomeController.view.autoresizingMask = UIViewAutoresizingFlexibleWidth | UIViewAutoresizingFlexibleHeight;
    [window addSubview:gWelcomeController.view];
    [defaults setBool:YES forKey:kWelcomeShownKey];
    return YES;
}

static void scheduleWelcome(void) {
    dispatch_async(dispatch_get_main_queue(), ^{
        NSNotificationCenter *center = NSNotificationCenter.defaultCenter;
        gWelcomeObserver = [center addObserverForName:UIApplicationDidBecomeActiveNotification
                                               object:nil
                                                queue:NSOperationQueue.mainQueue
                                           usingBlock:^(NSNotification *note) {
            if (showWelcomeIfNeeded()) {
                [center removeObserver:gWelcomeObserver];
                gWelcomeObserver = nil;
            }
        }];
        if (UIApplication.sharedApplication.applicationState == UIApplicationStateActive && showWelcomeIfNeeded()) {
            [center removeObserver:gWelcomeObserver];
            gWelcomeObserver = nil;
        }
    });
}

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

static BOOL isAdURL(NSURL *url) {
    if (isAdHost(url.host)) return YES;
    NSString *path = url.path.lowercaseString;
    return [path hasPrefix:@"/motor/ad/api/splash"] ||
           [path hasPrefix:@"/motor/ad/api/realtime/splash"] ||
           [path containsString:@"/api/ad/splash/"] ||
           [path containsString:@"/api/ad/v1/splash/stock/"];
}

// 把广告请求重定向到 0.0.0.0，使其连接被拒、快速失败（与二进制补丁策略一致）
static NSURLRequest *rewriteIfAd(NSURLRequest *req) {
    NSURL *url = req.URL;
    if (url && isAdURL(url)) {
        NSURL *blocked = [NSURL URLWithString:@"http://0.0.0.0/"];
        NSMutableURLRequest *m = [req mutableCopy];
        m.URL = blocked;
        return m;
    }
    return req;
}

static void swizzle_instance_method(Class cls, SEL orig, SEL repl) {
    if (!cls) return;
    Method m1 = class_getInstanceMethod(cls, orig);
    Method m2 = class_getInstanceMethod(cls, repl);
    if (m1 && m2) method_exchangeImplementations(m1, m2);
}

static BOOL neverDisplaySplash(id self, SEL cmd) {
    return YES;
}

static BOOL neverAllowSplash(id self, SEL cmd) {
    return NO;
}

static void replaceBoolGetter(const char *className, const char *selectorName, IMP implementation) {
    Class cls = objc_getClass(className);
    Method method = cls ? class_getInstanceMethod(cls, sel_registerName(selectorName)) : NULL;
    if (method) method_setImplementation(method, implementation);
}

static void installSplashHooks(void) {
    replaceBoolGetter("TTAdSplashModel", "splashNotDisplay", (IMP)neverDisplaySplash);
    replaceBoolGetter("TTAdSplashModel", "isBidSplashCanShow", (IMP)neverAllowSplash);
    replaceBoolGetter("BDASplashModelPicker", "shouldShowSplashAccordingToUDPAndPreloadData:", (IMP)neverAllowSplash);
}

static void scheduleSplashHooks(void) {
    NSArray<NSNotificationName> *names = @[
        UIApplicationWillFinishLaunchingNotification,
        UIApplicationDidFinishLaunchingNotification,
        UIApplicationDidBecomeActiveNotification,
    ];
    for (NSNotificationName name in names) {
        [NSNotificationCenter.defaultCenter addObserverForName:name
                                                        object:nil
                                                         queue:NSOperationQueue.mainQueue
                                                    usingBlock:^(NSNotification *note) {
            installSplashHooks();
        }];
    }
}

// === NSURLSession 交换实现（实例方法）===
@interface NSURLSession (AdBlock)
- (id)adblock_dataTaskWithRequest:(NSURLRequest *)req;
- (id)adblock_dataTaskWithRequest:(NSURLRequest *)req
                 completionHandler:(void (^)(NSData *, NSURLResponse *, NSError *))h;
@end

@implementation NSURLSession (AdBlock)
- (id)adblock_dataTaskWithRequest:(NSURLRequest *)req {
    // 交换后，此处 self 调用 adblock_dataTaskWithRequest: 实际指向原始实现
    return [self adblock_dataTaskWithRequest:rewriteIfAd(req)];
}
- (id)adblock_dataTaskWithRequest:(NSURLRequest *)req
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
    installSplashHooks();
    scheduleSplashHooks();

    swizzle_instance_method(objc_getClass("NSURLSession"),
                  @selector(dataTaskWithRequest:),
                  @selector(adblock_dataTaskWithRequest:));
    swizzle_instance_method(objc_getClass("NSURLSession"),
                  @selector(dataTaskWithRequest:completionHandler:),
                  @selector(adblock_dataTaskWithRequest:completionHandler:));

    Class connCls = objc_getClass("NSURLConnection");
    swizzle_instance_method(connCls,
                  @selector(initWithRequest:delegate:),
                  @selector(adblock_initWithRequest:delegate:));

    scheduleWelcome();
}
