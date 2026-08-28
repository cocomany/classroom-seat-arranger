#!/usr/bin/env python3
"""提供统一的中文命令行帮助与常见参数错误提示。"""

from __future__ import annotations

import argparse
import re
import sys
from typing import NoReturn


def _translate(text: str) -> str:
    replacements = (
        ("usage:", "用法："),
        ("positional arguments:", "位置参数："),
        ("options:", "选项："),
        ("optional arguments:", "可选参数："),
        ("show this help message and exit", "显示帮助并退出"),
        ("the following arguments are required:", "缺少必填参数："),
        ("unrecognized arguments:", "无法识别的参数："),
        ("invalid choice:", "无效选项："),
        ("expected one argument", "需要提供一个值"),
    )
    for source, target in replacements:
        text = text.replace(source, target)
    return re.sub(r"^argument ([^:]+):", r"参数 \1：", text)


class ChineseArgumentParser(argparse.ArgumentParser):
    """将 argparse 默认可见文案转换为中文。"""

    def format_help(self) -> str:
        return _translate(super().format_help())

    def format_usage(self) -> str:
        return _translate(super().format_usage())

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(2, f"{self.prog}：参数错误：{_translate(message)}\n")
