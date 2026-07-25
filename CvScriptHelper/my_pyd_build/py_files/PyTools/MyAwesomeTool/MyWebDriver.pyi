"""

Python 版 MyWebDriver，对齐 Java 端 MyWebDriver + CDPNode 的 CDP 体系。

设计要点：
- 全程通过 CDP（execute_cdp_cmd）完成 DOM 解析、坐标计算、鼠标/键盘派发，零 JS 注入
- DOM.getDocument 一次性拉取整棵树（含 shadow / iframe），本地内存遍历，避开逐元素 round-trip
- 鼠标/键盘走 Input.dispatchMouseEvent / Input.dispatchKeyEvent / Input.insertText
- 跨 iframe 可用：依赖 backendNodeId，不需要 switchTo()

依赖：selenium>=4.28（与 Java 端 selenium 4.28 对齐），psutil
"""
from PyTools.MyAwesomeTool.MyUtil import build_logger
from __future__ import annotations
import base64 as base64
import cv2 as cv2
import logging
import numpy as np
import os as os
import psutil as psutil
from selenium.common.exceptions import NoAlertPresentException
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
import socket as socket
import time as time
import typing
from typing import Any
__all__ = ['ActionChains', 'Any', 'By', 'CDPNode', 'ChromeOptions', 'EC', 'EdgeOptions', 'KeyEventCodes', 'MyWebDriver', 'NoAlertPresentException', 'SKIP_TAGS', 'TIMEOUT', 'WebDriverWait', 'WebElement', 'base64', 'base64_to_png_bytes', 'build_logger', 'cv2', 'is_port_in_use', 'is_process_running', 'logger', 'np', 'os', 'psutil', 'socket', 'time', 'webdriver']
class CDPNode:
    """
    CDP DOM 节点快照，对齐 Java 端 CDPNode。
    """
    __slots__: typing.ClassVar[tuple] = ('node_id', 'backend_node_id', 'node_type', 'node_name', 'node_value', 'local_name', 'attributes', 'children', 'shadow_root_type', 'frame_id', 'parent')
    def __init__(self):
        ...
    def cdpGetTextContent(self) -> str:
        ...
    def crawlAllElement(self) -> str:
        """
        对齐 Java crawlAllElement：聚合全部可见文本节点内容。
        """
    def crawl_all_element(self) -> str:
        """
        对齐 Java crawlAllElement：聚合全部可见文本节点内容。
        """
    def enumCDPNodes(self, visitor: typing.Callable[['CDPNode', int], int]) -> bool:
        ...
    def enum_nodes(self, visitor: typing.Callable[['CDPNode', int], int]) -> bool:
        ...
    def findCDPNodeById(self, id_value: str) -> 'CDPNode' | None:
        ...
    def findCDPNodesByAttr(self, attr_key: str, value: str) -> list['CDPNode']:
        ...
    def findCDPNodesByClassName(self, class_name: str) -> list[tuple['CDPNode', str]]:
        """
        返回 (node, class_attr原文) 列表，对齐 Java CDPNodesByClassName。
        """
    def findCDPNodesByTagName(self, tag_name: str) -> list['CDPNode']:
        ...
    def findCDPNodesByText(self, text: str, use_equal: bool = False) -> list['CDPNode']:
        ...
    def find_node_by_id(self, id_value: str) -> 'CDPNode' | None:
        ...
    def find_nodes_by_attr(self, attr_key: str, value: str) -> list['CDPNode']:
        ...
    def find_nodes_by_class(self, class_name: str) -> list[tuple['CDPNode', str]]:
        """
        返回 (node, class_attr原文) 列表，对齐 Java CDPNodesByClassName。
        """
    def find_nodes_by_tag(self, tag_name: str) -> list['CDPNode']:
        ...
    def find_nodes_by_text(self, text: str, use_equal: bool = False) -> list['CDPNode']:
        ...
    def getAttr(self, name: str) -> str | None:
        ...
    def getBody(self) -> 'CDPNode' | None:
        ...
    def get_attr(self, name: str) -> str | None:
        ...
    def get_body(self) -> 'CDPNode' | None:
        ...
    def get_text_content(self) -> str:
        ...
    def isDocument(self) -> bool:
        ...
    def isElement(self) -> bool:
        ...
    def isShadowRoot(self) -> bool:
        ...
    def isText(self) -> bool:
        ...
    def is_document(self) -> bool:
        ...
    def is_element(self) -> bool:
        ...
    def is_shadow_root(self) -> bool:
        ...
    def is_text(self) -> bool:
        ...
    def walk_cdp_tree(self, visitor: typing.Callable[['CDPNode', int], int]) -> bool:
        """
        
                非递归 DOM 树遍历（对齐 Java walkCDPTree）。
                返回 True=visitor 提前终止，False=正常完成。
                visitor 返回：0=终止, 1=跳过子树, 2=继续
                跳过规则：script/style/head 直接跳过；iframe 跳过 visitor 但仍递归 children
                
        """
class KeyEventCodes:
    """
    按键名 → Windows 虚拟键码映射，对齐 Java 端 KeyEventCodes。
    """
    CODES: typing.ClassVar[dict] = {}
    @classmethod
    def _init(cls):
        ...
    @classmethod
    def get_code(cls, key: str) -> int:
        ...
class MyWebDriver:
    """
    对齐 Java MyWebDriver：CDP 驱动的浏览器自动化封装。
    """
    def __init__(self, edge: bool = True):
        ...
    def _cdp(self, cmd: str, params: dict[str, typing.Any]) -> dict[str, typing.Any]:
        ...
    def _cdp_dispatch_mouse_click(self, x: float, y: float) -> bool:
        ...
    def _cdp_get_center(self, node: CDPNode) -> tuple[float, float] | None:
        ...
    def _cdp_resolve_node_id(self, node: CDPNode) -> str | None:
        ...
    def _cdp_triple_click(self, node: CDPNode) -> bool:
        """
        对齐 Java cdpTripleClick：clickCount=3 的 press+release 全选。
        """
    def _init_chrome(self, user_dir: str) -> None:
        ...
    def _init_edge(self, user_dir: str) -> None:
        ...
    def _node_clip_box(self, node: CDPNode) -> dict[str, typing.Any] | None:
        ...
    def _wait(self, by: By, value: str, timeout_seconds: int) -> None:
        ...
    def addCookie(self, cookie: dict[str, typing.Any]) -> None:
        ...
    def add_cookie(self, cookie: dict[str, typing.Any]) -> None:
        ...
    def cancelAlert(self) -> None:
        ...
    def cancel_alert(self) -> None:
        ...
    def capture_page_with_driver(self) -> np.ndarray:
        ...
    def cdpCallFunctionOn(self, node: CDPNode, function_js: str, *args: typing.Any) -> typing.Any:
        """
        对齐 Java cdpCallFunctionOn：DOM.resolveNode → Runtime.callFunctionOn。
        """
    def cdpCheck(self, node: CDPNode, checked: bool) -> bool:
        """
        对齐 Java cdpCheck：通过点击切换 checkbox/radio 状态。
        """
    def cdpClear(self, node: CDPNode) -> bool:
        ...
    def cdpClick(self, node: CDPNode) -> bool:
        ...
    def cdpFocus(self, node: CDPNode) -> bool:
        ...
    def cdpGetAttribute(self, node: CDPNode, attr_name: str) -> str | None:
        ...
    def cdpGetValue(self, node: CDPNode) -> str | None:
        ...
    def cdpHover(self, node: CDPNode) -> bool:
        ...
    def cdpInsertText(self, text: str) -> bool:
        """
        对齐 Java cdpInsertText：Input.insertText 整段插入。
        """
    def cdpIsVisible(self, node: CDPNode) -> bool:
        ...
    def cdpKeyPress(self, key: str, ctrl: bool = False, shift: bool = False) -> bool:
        """
        对齐 Java cdpKeyPress：单键派发，支持 Ctrl/Shift 组合。
        """
    def cdpReload(self) -> None:
        """
        对齐 Java cdpReload：用 CDP Page.reload 而非 location.reload()，规避刷新检测。
        """
    def cdpScreenshot(self, node: CDPNode | None = None) -> str | None:
        """
        
                对齐 Java cdpScreenshot(无参/CDPNode)：
                - 不传 node：截整页
                - 传 node：截元素的可见区域
                返回 Base64 PNG 字符串。
                
        """
    def cdpScrollIntoView(self, node: CDPNode) -> bool:
        ...
    def cdpScrollScreen(self, delta_x: int, delta_y: int, x: int = 0, y: int = 0) -> bool:
        """
        对齐 Java cdpScrollScreen：通过 mouseWheel 事件实现零JS滚动。
        """
    def cdpSelectOption(self, node: CDPNode, value: str) -> bool:
        """
        对齐 Java cdpSelectOption：展开 select → 点击 option 文本。
        """
    def cdpSetAttribute(self, node: CDPNode, attr_name: str, attr_value: str) -> bool:
        ...
    def cdpSetValue(self, node: CDPNode, value: str) -> bool:
        """
        对齐 Java cdpSetValue：聚焦→三击全选→删除→插入新文本，全程零JS。
        """
    def cdpTypeText(self, text: str, interval_ms: int = 0) -> bool:
        """
        对齐 Java cdpTypeText：逐字符 keyDown/keyUp，可触发联想等逐键事件。
        """
    def cdp_call_function_on(self, node: CDPNode, function_js: str, *args: typing.Any) -> typing.Any:
        """
        对齐 Java cdpCallFunctionOn：DOM.resolveNode → Runtime.callFunctionOn。
        """
    def cdp_check(self, node: CDPNode, checked: bool) -> bool:
        """
        对齐 Java cdpCheck：通过点击切换 checkbox/radio 状态。
        """
    def cdp_clear(self, node: CDPNode) -> bool:
        ...
    def cdp_click(self, node: CDPNode) -> bool:
        ...
    def cdp_focus(self, node: CDPNode) -> bool:
        ...
    def cdp_get_attribute(self, node: CDPNode, attr_name: str) -> str | None:
        ...
    def cdp_get_value(self, node: CDPNode) -> str | None:
        ...
    def cdp_hover(self, node: CDPNode) -> bool:
        ...
    def cdp_insert_text(self, text: str) -> bool:
        """
        对齐 Java cdpInsertText：Input.insertText 整段插入。
        """
    def cdp_is_visible(self, node: CDPNode) -> bool:
        ...
    def cdp_key_press(self, key: str, ctrl: bool = False, shift: bool = False) -> bool:
        """
        对齐 Java cdpKeyPress：单键派发，支持 Ctrl/Shift 组合。
        """
    def cdp_reload(self) -> None:
        """
        对齐 Java cdpReload：用 CDP Page.reload 而非 location.reload()，规避刷新检测。
        """
    def cdp_screenshot(self, node: CDPNode | None = None) -> str | None:
        """
        
                对齐 Java cdpScreenshot(无参/CDPNode)：
                - 不传 node：截整页
                - 传 node：截元素的可见区域
                返回 Base64 PNG 字符串。
                
        """
    def cdp_scroll_into_view(self, node: CDPNode) -> bool:
        ...
    def cdp_scroll_screen(self, delta_x: int, delta_y: int, x: int = 0, y: int = 0) -> bool:
        """
        对齐 Java cdpScrollScreen：通过 mouseWheel 事件实现零JS滚动。
        """
    def cdp_select_option(self, node: CDPNode, value: str) -> bool:
        """
        对齐 Java cdpSelectOption：展开 select → 点击 option 文本。
        """
    def cdp_set_attribute(self, node: CDPNode, attr_name: str, attr_value: str) -> bool:
        ...
    def cdp_set_value(self, node: CDPNode, value: str) -> bool:
        """
        对齐 Java cdpSetValue：聚焦→三击全选→删除→插入新文本，全程零JS。
        """
    def cdp_type_text(self, text: str, interval_ms: int = 0) -> bool:
        """
        对齐 Java cdpTypeText：逐字符 keyDown/keyUp，可触发联想等逐键事件。
        """
    def cleanSlate(self) -> None:
        """
        对齐 Java cleanSlate：清缓存 + 清 Cookie，比 deleteAllCookies 更彻底。
        """
    def clean_slate(self) -> None:
        """
        对齐 Java cleanSlate：清缓存 + 清 Cookie，比 deleteAllCookies 更彻底。
        """
    def clearCookie(self) -> None:
        ...
    def clear_cookie(self) -> None:
        ...
    def clickText(self, text: str, delay_ms: int = 500) -> None:
        """
        对齐 Java clickText：基于文本匹配点击所有命中元素。
        """
    def click_point_with_templates(self, src: np.ndarray, temp: np.ndarray, loc: tuple, percent_x: float = 0.5, percent_y: float = 0.5, click: bool = True, button_num: int = 0):
        ...
    def click_text(self, text: str, delay_ms: int = 500) -> None:
        """
        对齐 Java clickText：基于文本匹配点击所有命中元素。
        """
    def close(self) -> None:
        ...
    def closeCurrentTabAndSwitch(self) -> None:
        """
        对齐 Java closeCurrentTabAndSwitch：关闭当前标签页并切到剩余标签。
        """
    def close_current_tab_and_switch(self) -> None:
        """
        对齐 Java closeCurrentTabAndSwitch：关闭当前标签页并切到剩余标签。
        """
    def crawlWebsite(self, url: str) -> str | None:
        """
        对齐 Java crawlWebsite：取 body 文本并保留前 1000 字符中的字母，其余替换为空格。
        """
    def crawl_website(self, url: str) -> str | None:
        """
        对齐 Java crawlWebsite：取 body 文本并保留前 1000 字符中的字母，其余替换为空格。
        """
    def findElement(self, by: By, value: str) -> WebElement:
        ...
    def find_element(self, by: By, value: str) -> WebElement:
        ...
    def getCDPDomSnapshot(self) -> CDPNode:
        """
        对齐 Java getCDPDomSnapshot：一次性获取整棵 DOM（穿透 shadow/iframe）。
        """
    def getCurrentUrl(self) -> str:
        ...
    def getWebPageCookie(self) -> str:
        ...
    def getWindowsTabNum(self) -> int:
        ...
    def get_cdp_dom_snapshot(self) -> CDPNode:
        """
        对齐 Java getCDPDomSnapshot：一次性获取整棵 DOM（穿透 shadow/iframe）。
        """
    def get_current_url(self) -> str:
        ...
    def get_web_page_cookie(self) -> str:
        ...
    def get_windows_tab_num(self) -> int:
        ...
    def goUrl(self, url: str = 'https://cg.163.com/#/mobile') -> bool:
        ...
    def go_url(self, url: str = 'https://cg.163.com/#/mobile') -> bool:
        ...
    def isClosed(self) -> bool:
        """
        对齐 Java isClosed：仅 Windows 下检查进程。
        """
    def is_closed(self) -> bool:
        """
        对齐 Java isClosed：仅 Windows 下检查进程。
        """
    def mustClick(self, element: WebElement) -> None:
        ...
    def mustFindClassName(self, class_name: str) -> list[WebElement]:
        ...
    def mustFindElements(self, by: By, value: str) -> list[WebElement]:
        ...
    def must_click(self, element: WebElement) -> None:
        ...
    def must_find_class_name(self, class_name: str) -> list[WebElement]:
        ...
    def must_find_elements(self, by: By, value: str) -> list[WebElement]:
        ...
    def overrideLocation(self) -> None:
        """
        对齐 Java overrideLocation：固定地理坐标/时区/语言。
        """
    def override_location(self) -> None:
        """
        对齐 Java overrideLocation：固定地理坐标/时区/语言。
        """
    def quit(self) -> None:
        ...
    def removeDebugger(self) -> None:
        """
        对齐 Java removeDebugger：注入反反调试脚本并设置跳过所有断点。
        """
    def remove_debugger(self) -> None:
        """
        对齐 Java removeDebugger：注入反反调试脚本并设置跳过所有断点。
        """
    def scrollScreen(self) -> None:
        ...
    def scroll_screen(self) -> None:
        ...
    def setBodyHtmlWithJS(self, body_content: str) -> None:
        ...
    def setExtraHTTPHeaders(self, headers: dict[str, str]) -> None:
        ...
    def set_body_html_with_js(self, body_content: str) -> None:
        ...
    def set_extra_http_headers(self, headers: dict[str, str]) -> None:
        ...
def _append_text_content(node: CDPNode, out: list[str]) -> None:
    ...
def _collect_text_content(node: CDPNode) -> str:
    """
    递归收集 textContent，对齐 Java collectTextContent。
    """
def _contains_all_classes(class_attr: str, targets: list[str]) -> bool:
    ...
def _is_arm() -> bool:
    ...
def _is_windows() -> bool:
    ...
def _not_windows() -> bool:
    ...
def _parse_cdp_node(data: dict[str, typing.Any] | None, parent: CDPNode | None) -> CDPNode | None:
    """
    对齐 Java parseCDPNode：递归解析 DOM.getDocument 返回的 JSON。
    """
def _sleep(ms: int) -> None:
    ...
def base64_to_png_bytes(b64: str) -> bytes:
    """
    CDP 返回的 Page.captureScreenshot data 是裸 base64（无 data:image 前缀）。
    """
def is_port_in_use(port: int, host: str = '127.0.0.1', timeout: float = 1.0) -> bool:
    ...
def is_process_running(process_name: str) -> bool:
    ...
SKIP_TAGS: set = {'script', 'style', 'head'}
TIMEOUT: int = 60
logger: logging.Logger  # value = <Logger PyTools.MyAwesomeTool.MyWebDriver (DEBUG)>
