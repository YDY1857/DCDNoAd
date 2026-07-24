@echo off
chcp 65001 >nul
REM ============================================================
REM  懂车帝 IPA 去广告工具 - Windows 一键启动脚本
REM  用法: run.bat [命令] [参数]
REM  示例:
REM    run.bat scan   --app "E:\codex自动化项目\懂车帝逆向\懂车帝9.1.6\Payload\AutoMobile.app"
REM    run.bat report --app "E:\codex自动化项目\懂车帝逆向\懂车帝9.1.6\Payload\AutoMobile.app"
REM    run.bat clean  --app "E:\codex自动化项目\懂车帝逆向\懂车帝9.1.6\Payload\AutoMobile.app" --dry-run
REM    run.bat all    --app "E:\codex自动化项目\懂车帝逆向\懂车帝9.1.6\Payload\AutoMobile.app"
REM ============================================================
setlocal
cd /d "%~dp0"

REM 优先使用 WorkBuddy 管理的 Python；找不到则回退到系统 python
set "PY="
if exist "C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe" (
    set "PY=C:\Users\Administrator\.workbuddy\binaries\python\versions\3.13.12\python.exe"
) else (
    set "PY=python"
)

if "%~1"=="" (
    echo 用法: run.bat [scan^|report^|clean^|patch-plist^|patch-binary^|all] --app "路径\AutoMobile.app" [--dry-run]
    echo 不带 --app 时将使用 config.DEFAULT_APP_DIR 的默认路径。
    exit /b 1
)

"%PY%" ad_remover.py %*
endlocal
