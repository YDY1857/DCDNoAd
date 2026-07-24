"""广告去除工具包包初始化。"""
from . import config
from . import scanner
from . import reporter
from . import resource_cleaner
from . import plist_patcher
from . import binary_patcher
from .cli import main, build_parser

__all__ = [
    "config", "scanner", "reporter",
    "resource_cleaner", "plist_patcher", "binary_patcher",
    "main", "build_parser",
]
__version__ = "1.0.0"
