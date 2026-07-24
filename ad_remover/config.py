"""配置加载与全局常量。

负责读取 signatures/ad_signatures.json，并对外部暴露广告特征签名。
整个工具包仅依赖 Python 标准库，可在 Windows 命令行直接运行。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

# 项目根目录（ad-remover/）
TOOL_ROOT = Path(__file__).resolve().parent.parent
SIGNATURES_PATH = TOOL_ROOT / "signatures" / "ad_signatures.json"

# 默认被分析的 IPA 解压根目录（可在命令行用 --app 覆盖）
DEFAULT_APP_DIR = r"E:\codex自动化项目\懂车帝逆向\懂车帝9.1.6\Payload\AutoMobile.app"

# 备份目录名（放在被处理 app 同级）
BACKUP_DIRNAME = "_ad_remover_backup"

# 日志前缀
LOG_PREFIX = "[ad-remover]"


def load_signatures(path: Path | None = None) -> Dict[str, Any]:
    """加载广告特征签名库。"""
    p = Path(path) if path else SIGNATURES_PATH
    if not p.exists():
        raise FileNotFoundError(f"签名库不存在: {p}")
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


# 模块级缓存
_SIGNATURES: Dict[str, Any] | None = None


def get_signatures() -> Dict[str, Any]:
    global _SIGNATURES
    if _SIGNATURES is None:
        _SIGNATURES = load_signatures()
    return _SIGNATURES


def app_root_heuristic(start: Path) -> Path | None:
    """给定任意路径，向上查找包含 AutoMobile.app / *.app 的 Payload 目录。"""
    start = Path(start)
    # 情况1：直接给了 .app
    if start.is_file() or (start.is_dir() and start.suffix == ".app"):
        cand = start if start.is_dir() else start.parent
        if cand.name.endswith(".app"):
            return cand
    # 情况2：向上查找 Payload/*.app
    for parent in [start, *start.parents]:
        payload = parent / "Payload"
        if payload.is_dir():
            apps = [d for d in payload.iterdir() if d.is_dir() and d.name.endswith(".app")]
            if apps:
                return apps[0]
    return None
