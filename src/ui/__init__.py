#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
UI 包 - 提供 TUI 和 GUI 两种交互界面

公共接口:
    run_tui(llm)  - 终端交互模式
    run_gui(llm)  - Gradio Web 界面
    parse_profile_from_natural_language(description, llm) - 解析学生档案
    display_homeworks(sections) - 渲染作业 HTML
"""

from src.ui.tui import run_tui
from src.ui.gui import run_gui
from src.ui.shared import parse_profile_from_natural_language, display_homeworks

__all__ = [
    "run_tui",
    "run_gui",
    "parse_profile_from_natural_language",
    "display_homeworks",
]
