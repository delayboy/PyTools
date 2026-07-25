"""
轻量布局容器：HBox 横排 / VBox 竖排，带颜色边框
"""
from PIL import Image
from PIL import ImageTk
from __future__ import annotations
import cv2 as cv2
import numpy as np
import os as os
import platform as platform
import re as re
import threading as threading
import tkinter as tk
import tkinter as tkinter
from tkinter import filedialog
from tkinter import ttk
import typing
from typing import Any
from typing import Generic
from typing import TypeVar
__all__ = ['Any', 'Generic', 'HorizonBox', 'Image', 'ImageMultiCanvas', 'ImageTk', 'MainUIBase', 'SimpleButton', 'SimpleTextView', 'TypeVar', 'VerticalBox', 'XmlTableUI', 'ask_choice', 'cv2', 'example', 'filedialog', 'np', 'os', 'platform', 're', 'threading', 'tk', 'tkinter', 'ttk']
class HorizonBox(_BorderFrame):
    """
    横向排列容器，蓝色边框
    """
    def __init__(self, master: tk.Misc, border_width: int = 2, spacing: int = 4, border_color: str = '#3399FF', **kw):
        ...
    def add(self, child: tk.Widget, **grid_kw) -> typing.Any:
        """
        将 child 放入下一列，自动处理列间距
        """
    def add_stretch(self, weight: int = 1):
        """
        插入一个弹性空白列，用于推开后续控件或吸收多余空间
        """
    def grid(self, row = 0, column = 0, cnf = None, **kw) -> HorizonBox:
        ...
class ImageMultiCanvas(tkinter.Frame):
    """
    多图显示控件，封装Canvas+Scrollbar+图像缩放显示逻辑，支持鼠标滚轮缩放和拖拽（仅row=0）
    """
    @staticmethod
    def _ImageMultiCanvas__get_channel_num(img: np.ndarray):
        ...
    def _ImageMultiCanvas__array_to_pil(self, img_array: np.ndarray) -> Image.Image:
        """
        np.ndarray -> PIL.Image，自动缩放到 600 以内
        """
    def _ImageMultiCanvas__on_enter(self, event):
        ...
    def _ImageMultiCanvas__on_leave(self, event):
        ...
    def _ImageMultiCanvas__on_mouse_wheel(self, event, direction = None):
        ...
    def _ImageMultiCanvas__pan_image(self, event):
        ...
    def _ImageMultiCanvas__scroll_canvas(self, event):
        ...
    def _ImageMultiCanvas__start_pan(self, event):
        ...
    def _ImageMultiCanvas__update_scroll(self):
        ...
    def __init__(self, master, width = 600, height = 700, **kwargs):
        ...
    def show_image(self, img_array: np.ndarray, show_text: str = '', row = 0):
        """
        显示图像到指定行；row=0 支持滚轮缩放和拖拽
        """
class MainUIBase(tkinter.Tk):
    """
    顶部工具栏控件：按钮组 + 文本显示区
    """
    @staticmethod
    def ask_file_path(is_dir: bool = False, save: bool = False) -> tuple[str, ...] | str:
        ...
    @staticmethod
    def format_bounds(bounds) -> tuple[int, int, int, int]:
        ...
    @staticmethod
    def show_message_box(text = 'Are you sure'):
        ...
    def __init__(self, button_list = ('开始', '播放游戏画面', '清空', '测试')):
        ...
    def add_to_tree(self, root_id: str, name: str, xpath: str = '', txt: str = '', bounds: str = '') -> str:
        ...
    def change_draw_mode(self):
        ...
    def change_pause_mode(self, value: bool = None):
        ...
    def close_window(self):
        ...
    def delete_all_tree(self):
        ...
    def expend_all_tree(self):
        ...
    def get_cache_img(self) -> np.ndarray:
        ...
    def get_simple_button(self, button_name: str) -> SimpleButton:
        ...
    def get_text(self) -> str:
        ...
    def set_simple_button_callback(self, callback: typing.Callable[[], None], button_name: str = '测试'):
        ...
    def set_top(self, is_top: bool):
        ...
    def set_xml_on_select_callback(self, on_select: typing.Callable[[str, tuple], None]):
        ...
    def show_image(self, img_array: np.ndarray, show_text: str = '', row = 0, use_cache = True, add_to_summery = False):
        ...
    def show_text(self, text: str):
        ...
    def wait_pause_signal(self):
        ...
class SimpleButton(tkinter.Button):
    def __init__(self, text: str, master = None, cnf = None, **kw):
        ...
    def get_text(self) -> str:
        ...
    def grid(self, row = 0, column = 0, cnf = None, **kw) -> SimpleButton:
        ...
    def set_button_callback(self, callback: typing.Callable) -> SimpleButton:
        ...
    def set_text(self, text: str):
        ...
class SimpleTextView(tkinter.Text):
    def _SimpleTextView__update_text_widget(self, var_name, unknown, action = 'write'):
        ...
    def __init__(self, text: str, master = None, cnf = None, wrap = 'word', height = 10, width = 50, **kw):
        ...
    def get_text(self) -> str:
        ...
    def grid(self, row = 0, column = 0, span = 4, cnf = None, **kw) -> SimpleTextView:
        ...
    def set_text(self, text: str):
        ...
class VerticalBox(_BorderFrame):
    """
    纵向排列容器，红色边框
    """
    def __init__(self, master: tk.Misc, border_width: int = 1, spacing: int = 6, border_color: str = '#FF4444', **kw):
        ...
    def add(self, child: tk.Widget, **grid_kw) -> typing.Any:
        """
        将 child 放入下一行，自动处理行间距
        """
    def add_stretch(self, weight: int = 1):
        """
        插入一个弹性空行，用于吸收多余垂直空间
        """
    def grid(self, row = 0, column = 0, cnf = None, **kw) -> VerticalBox:
        ...
class XmlTableUI(tkinter.Frame):
    """
    Android XML布局树控件，封装Treeview+Scrollbar+节点操作逻辑
    """
    def _XmlTableUI__copy_selected(self, event = None):
        """
        复制所有选中节点的信息到剪贴板（多行文本）
        """
    def _XmlTableUI__expand_children(self, parent: str):
        ...
    def _XmlTableUI__on_item_selected(self, event):
        ...
    def __init__(self, master = None, on_select: typing.Callable[[str, tuple], None] = None, **kwargs):
        ...
    def add_item(self, root_id: str, name: str, xpath: str = '', txt: str = '', bounds: str = '') -> str:
        ...
    def clear(self):
        ...
    def expand_all(self):
        ...
    def has_items(self) -> bool:
        ...
    def set_on_select_callback(self, on_select: typing.Callable[[str, tuple], None]):
        ...
class _BorderFrame(tkinter.Frame):
    """
    用 Canvas + inner Frame 模拟带颜色边框的容器，
        因为原生 ttk.Frame 不支持自定义边框颜色。
    """
    def __init__(self, master: tk.Misc, border_color: str, border_width: int = 2, **kw):
        ...
    @property
    def container(self) -> tk.Frame:
        """
        子控件应 pack / grid 到 container 上
        """
def ask_choice(title: str, message: str, options: list[str], default: str = None) -> str | None:
    """
    弹出带下拉选择的确认框，返回选中的值；点取消返回 None。
    """
def example():
    ...
