"""
Python 版 MyWebDriver，对齐 Java 端 MyWebDriver + CDPNode 的 CDP 体系。

设计要点：
- 全程通过 CDP（execute_cdp_cmd）完成 DOM 解析、坐标计算、鼠标/键盘派发，零 JS 注入
- DOM.getDocument 一次性拉取整棵树（含 shadow / iframe），本地内存遍历，避开逐元素 round-trip
- 鼠标/键盘走 Input.dispatchMouseEvent / Input.dispatchKeyEvent / Input.insertText
- 跨 iframe 可用：依赖 backendNodeId，不需要 switchTo()

依赖：selenium>=4.28（与 Java 端 selenium 4.28 对齐），psutil
"""

from __future__ import annotations

import base64
import socket
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
import os
import psutil
from selenium import webdriver
from selenium.common import NoAlertPresentException
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import cv2
import numpy as np

try:
    from PyTools.MyAwesomeTool.MyUtil import build_logger

    logger = build_logger(filename="./log.txt", name=__name__, use_to_debug=True,
                          file_log_debug=False, use_time_rotate=False)
except Exception:  # 兜底，独立运行也能用
    import logging

    logger = logging.getLogger("MyWebDriver")
    logger.addHandler(logging.StreamHandler())
    logger.setLevel(logging.INFO)

TIMEOUT = 60
SKIP_TAGS = {"script", "style", "head"}


# ============================ 工具函数 ============================

def is_port_in_use(port: int, host: str = "127.0.0.1", timeout: float = 1.0) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            return s.connect_ex((host, port)) == 0
    except OSError:
        return False


def is_process_running(process_name: str) -> bool:
    for p in psutil.process_iter(attrs=["name"]):
        try:
            if p.info["name"] and process_name.lower() in p.info["name"].lower():
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def base64_to_png_bytes(b64: str) -> bytes:
    """CDP 返回的 Page.captureScreenshot data 是裸 base64（无 data:image 前缀）。"""
    return base64.b64decode(b64)


def _sleep(ms: int) -> None:
    if ms > 0:
        time.sleep(ms / 1000.0)


# ============================ 键盘虚拟键码 ============================

class KeyEventCodes:
    """按键名 → Windows 虚拟键码映射，对齐 Java 端 KeyEventCodes。"""

    CODES: Dict[str, int] = {}

    @classmethod
    def _init(cls):
        if cls.CODES:
            return
        named = {
            "Enter": 13, "Tab": 9, "Escape": 27, "Backspace": 8, "Delete": 46,
            "Space": 32,
            "ArrowUp": 38, "ArrowDown": 40, "ArrowLeft": 37, "ArrowRight": 39,
            "Home": 36, "End": 35, "PageUp": 33, "PageDown": 34,
            "F1": 112, "F2": 113, "F3": 114, "F4": 115, "F5": 116, "F6": 117,
            "F7": 118, "F8": 119, "F9": 120, "F10": 121, "F11": 122, "F12": 123,
        }
        cls.CODES.update(named)
        for c in range(ord("A"), ord("Z") + 1):
            ch = chr(c)
            cls.CODES[ch] = c
            cls.CODES[ch.lower()] = c
        for c in range(ord("0"), ord("9") + 1):
            cls.CODES[chr(c)] = c

    @classmethod
    def get_code(cls, key: str) -> int:
        cls._init()
        return cls.CODES.get(key, 0)


# ============================ CDPNode ============================

class CDPNode:
    """CDP DOM 节点快照，对齐 Java 端 CDPNode。"""

    __slots__ = (
        "node_id", "backend_node_id", "node_type", "node_name", "node_value",
        "local_name", "attributes", "children", "shadow_root_type", "frame_id",
        "parent",
    )

    def __init__(self):
        self.node_id: int = 0
        self.backend_node_id: int = 0
        self.node_type: int = 0  # 1=Element 3=Text 9=Document 11=DocumentFragment
        self.node_name: str = ""
        self.node_value: str = ""
        self.local_name: str = ""
        self.attributes: Optional[List[str]] = None  # 扁平数组 [k,v,k,v,...]
        self.children: Optional[List["CDPNode"]] = None
        self.shadow_root_type: Optional[str] = None
        self.frame_id: Optional[str] = None
        self.parent: Optional["CDPNode"] = None

    # ---- 类型判定 ----
    def is_element(self) -> bool:
        return self.node_type == 1

    def is_text(self) -> bool:
        return self.node_type == 3

    def is_document(self) -> bool:
        return self.node_type == 9

    def is_shadow_root(self) -> bool:
        return self.shadow_root_type is not None

    # ---- 属性 ----
    def get_attr(self, name: str) -> Optional[str]:
        if not self.attributes:
            return None
        for i in range(0, len(self.attributes) - 1, 2):
            if self.attributes[i] == name:
                return self.attributes[i + 1]
        return None

    def get_body(self) -> Optional["CDPNode"]:
        if self.is_element() and self.local_name == "body":
            return self
        if self.children:
            for c in self.children:
                found = c.get_body()
                if found:
                    return found
        return None

    # ---- 全文本聚合 ----
    def crawl_all_element(self) -> str:
        """对齐 Java crawlAllElement：聚合全部可见文本节点内容。"""
        chunks: List[str] = []

        def visitor(node: "CDPNode", depth: int) -> int:
            if node.is_text() and node.node_value:
                chunks.append(node.node_value)
            return 2

        self.walk_cdp_tree(visitor)
        text = " ".join(chunks)
        # 压缩连续空白
        return " ".join(text.split())

    # ---- 查询族 ----
    def find_nodes_by_text(self, text: str, use_equal: bool = False) -> List["CDPNode"]:
        results: List[CDPNode] = []
        seen: set[int] = set()

        def visitor(node: "CDPNode", depth: int) -> int:
            if node.is_text() and node.node_value:
                target = node.node_value.strip() if use_equal else node.node_value
                matched = (target == text) if use_equal else (text in node.node_value)
                if matched and node.parent and node.parent.is_element():
                    if node.parent.backend_node_id not in seen:
                        seen.add(node.parent.backend_node_id)
                        results.append(node.parent)
            return 2

        self.walk_cdp_tree(visitor)
        return results

    def find_nodes_by_tag(self, tag_name: str) -> List["CDPNode"]:
        target = tag_name.lower()
        results: List[CDPNode] = []

        def visitor(node: "CDPNode", depth: int) -> int:
            if node.is_element() and node.local_name == target:
                results.append(node)
            return 2

        self.walk_cdp_tree(visitor)
        return results

    def find_nodes_by_class(self, class_name: str) -> List["CDPNode"]:
        """返回 (node, class_attr原文) 列表，对齐 Java CDPNodesByClassName。"""
        target_classes = [c for c in class_name.strip().split() if c]
        results: List[CDPNode] = []

        def visitor(node: "CDPNode", depth: int) -> int:
            if node.is_element() and node.attributes:
                cls = node.get_attr("class")
                if cls and _contains_all_classes(cls, target_classes):
                    results.append(node)
            return 2

        self.walk_cdp_tree(visitor)
        return results

    def find_node_by_id(self, id_value: str) -> Optional["CDPNode"]:
        holder: List[Optional[CDPNode]] = [None]

        def visitor(node: "CDPNode", depth: int) -> int:
            if node.is_element() and node.get_attr("id") == id_value:
                holder[0] = node
                return 0  # 找到即终止
            return 2

        self.walk_cdp_tree(visitor)
        return holder[0]

    def find_nodes_by_attr(self, attr_key: str, value: str) -> List["CDPNode"]:
        results: List[CDPNode] = []

        def visitor(node: "CDPNode", depth: int) -> int:
            if node.is_element() and node.get_attr(attr_key) == value:
                results.append(node)
            return 2

        self.walk_cdp_tree(visitor)
        return results

    def enum_nodes(self, visitor: Callable[["CDPNode", int], int]) -> bool:
        return self.walk_cdp_tree(visitor)

    # ---- textContent ----
    def get_text_content(self) -> str:
        return _collect_text_content(self).strip()

    # ---- 核心遍历 ----
    def walk_cdp_tree(self, visitor: Callable[["CDPNode", int], int]) -> bool:
        """
        非递归 DOM 树遍历（对齐 Java walkCDPTree）。
        返回 True=visitor 提前终止，False=正常完成。
        visitor 返回：0=终止, 1=跳过子树, 2=继续
        跳过规则：script/style/head 直接跳过；iframe 跳过 visitor 但仍递归 children
        """
        index_stack: List[int] = [-1]
        node_stack: List[CDPNode] = [self]
        current: CDPNode = self

        choice = visitor(self, 0)
        if choice == 0:
            return True
        if choice == 1:
            return False

        while index_stack:
            kids = current.children
            next_index = index_stack[-1] + 1
            if kids:
                while next_index < len(kids):
                    child = kids[next_index]
                    if child.is_element() and child.local_name in SKIP_TAGS:
                        next_index += 1
                        continue
                    break
            index_stack[-1] = next_index

            if kids is None or next_index >= len(kids):
                index_stack.pop()
                node_stack.pop()
                current = node_stack[-1] if node_stack else None
                continue

            child = kids[next_index]
            # iframe 跳过 visitor，但仍进入其 children
            skip_visitor = child.is_element() and child.local_name == "iframe"
            if not skip_visitor:
                child_choice = visitor(child, len(index_stack))
                if child_choice == 0:
                    return True
                if child_choice == 1:
                    continue
            index_stack.append(-1)
            node_stack.append(child)
            current = child

        return False


def _contains_all_classes(class_attr: str, targets: List[str]) -> bool:
    element_classes = set(class_attr.split())
    return all(t in element_classes for t in targets)


def _collect_text_content(node: CDPNode) -> str:
    """递归收集 textContent，对齐 Java collectTextContent。"""
    parts: List[str] = []
    _append_text_content(node, parts)
    return "".join(parts)


def _append_text_content(node: CDPNode, out: List[str]) -> None:
    if node.is_text():
        out.append(node.node_value)
    elif node.is_document():
        if node.children:
            for c in node.children:
                _append_text_content(c, out)
    elif node.is_element():
        if node.local_name in SKIP_TAGS:
            return
        if node.children:
            for c in node.children:
                _append_text_content(c, out)


# ============================ MyWebDriver ============================

class MyWebDriver:
    """对齐 Java MyWebDriver：CDP 驱动的浏览器自动化封装。"""

    def __init__(self, edge: bool = True):
        self.edge_path = "/Edge/Application/"
        self.chrome_path = "/Chrome/Application/"
        self.driver: Optional[webdriver.Remote] = None
        self.console_listener = None

        user_dir = os.getcwd()  # 与 Java System.getProperty("user.dir") 对应：Python 端由调用方设置 cwd
        if _not_windows():
            edge = False  # Linux 强制 Chrome

        if edge:
            self._init_edge(user_dir)
        else:
            self._init_chrome(user_dir)

        self.driver.set_window_size(1000, 800)
        self.driver.set_window_position(0, 0)

    # ---- 浏览器启动 ----
    def _init_edge(self, user_dir: str) -> None:
        opts = EdgeOptions()
        user = os.getcwd()  # 获取当前工作目录
        # 设置EdgeDriver路径
        driver_path = user + self.edge_path + "msedgedriver.exe"
        # 使用os.environ来设置环境变量
        os.environ["webdriver.edge.driver"] = driver_path
        os.environ["PATH"] = user + self.edge_path + ";" + os.environ["PATH"]
        if is_port_in_use(3326):
            connect = EdgeOptions()
            connect.add_experimental_option("debuggerAddress", "127.0.0.1:3326")
            self.driver = webdriver.Edge(options=connect)
            logger.info("已连接到现有Edge浏览器实例(端口3326)")
            return

        prefs = {
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
            "profile.default_content_settings.popups": 0,
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_setting_values.automatic_downloads": 1,
        }
        opts.add_experimental_option("prefs", prefs)
        opts.add_experimental_option("useAutomationExtension", False)
        opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        opts.add_argument("disable-gpu")
        opts.add_argument("start-maximized")
        opts.add_argument("--remote-debugging-port=3326")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument("--disable-features=VizDisplayCompositor")
        opts.add_argument("--disable-background-timer-throttling")
        opts.add_argument("--disable-renderer-backgrounding")
        opts.add_argument("--disable-backgrounding-occluded-windows")
        opts.add_argument(f"user-data-dir={user_dir}/Edge/UserData")
        opts.add_argument("profile-directory=Profile 1")
        if user_dir:
            opts.binary_location = f"{user_dir}{self.edge_path}msedge.exe"
        opts.set_capability("unhandledPromptBehavior", "ignore")
        opts.page_load_strategy = "normal"
        logger.warning(opts.to_capabilities().__str__())
        self.driver = webdriver.Edge(options=opts)

    def _init_chrome(self, user_dir: str) -> None:
        opts = ChromeOptions()
        tail = ".exe" if _is_windows() else ""
        driver_path = user_dir + self.chrome_path + "chromedriver" + tail
        # 使用os.environ来设置环境变量
        os.environ["webdriver.chrome.driver"] = driver_path
        os.environ["PATH"] = user_dir + self.chrome_path + ";" + os.environ["PATH"]
        if is_port_in_use(9222):
            connect = ChromeOptions()
            connect.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
            self.driver = webdriver.Chrome(options=connect)
            logger.info("已连接到现有Chrome浏览器实例(端口9222)")
            return

        prefs = {
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
            "profile.default_content_settings.popups": 0,
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_setting_values.automatic_downloads": 1,
        }
        opts.add_experimental_option("prefs", prefs)
        opts.add_experimental_option("useAutomationExtension", False)
        opts.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        opts.add_argument("disable-gpu")
        opts.add_argument("start-maximized")
        opts.add_argument("--remote-debugging-port=9222")
        opts.add_argument("--remote-allow-origins=*")
        opts.add_argument("--disable-dev-shm-usage")
        opts.add_argument("--no-sandbox")
        opts.add_argument("--disable-blink-features=AutomationControlled")
        opts.add_argument("--disable-features=VizDisplayCompositor")
        opts.add_argument("--disable-background-timer-throttling")
        opts.add_argument("--disable-renderer-backgrounding")
        opts.add_argument("--disable-backgrounding-occluded-windows")
        opts.add_argument(f"user-data-dir={user_dir}/Chrome/UserData")
        opts.add_argument("profile-directory=Profile 1")
        if user_dir and not _is_arm():
            opts.binary_location = f"{user_dir}{self.chrome_path}chrome{tail}"
        elif user_dir:
            opts.binary_location = f"{user_dir}{self.chrome_path}chromium-browser{tail}"
        opts.set_capability("unhandledPromptBehavior", "ignore")
        opts.page_load_strategy = "normal"
        self.driver = webdriver.Chrome(options=opts)

    # ==================== 基础导航/状态 ====================

    def go_url(self, url: str = "https://cg.163.com/#/mobile") -> bool:
        try:
            self.driver.get(url)
            return True
        except Exception as e:
            logger.error(f"Can't Reach Website {{{url}}}: {e}")
            return False

    def cdp_reload(self) -> None:
        """对齐 Java cdpReload：用 CDP Page.reload 而非 location.reload()，规避刷新检测。"""
        self._cdp("Page.reload", {})

    def get_current_url(self) -> str:
        return self.driver.current_url

    def get_windows_tab_num(self) -> int:
        return len(self.driver.window_handles)

    def close(self) -> None:
        if self.driver is not None:
            self.driver.close()

    def quit(self) -> None:
        if self.driver is not None:
            self.driver.quit()

    def is_closed(self) -> bool:
        """对齐 Java isClosed：仅 Windows 下检查进程。"""
        if not _is_windows():
            return False
        if is_process_running("msedge.exe"):
            logger.info("浏览器未关闭")
            return False
        logger.info("浏览器已关闭")
        return True

    # ==================== 弹窗/Cookie/JS ====================

    def cancel_alert(self) -> None:
        try:
            self.driver.switch_to.alert.accept()
            _sleep(1000)
        except NoAlertPresentException:
            pass
        except Exception:
            pass

    def clear_cookie(self) -> None:
        self.driver.delete_all_cookies()

    def add_cookie(self, cookie: Dict[str, Any]) -> None:
        self.driver.add_cookie(cookie)

    def get_web_page_cookie(self) -> str:
        return self.driver.execute_script("return document.cookie;")

    def set_body_html_with_js(self, body_content: str) -> None:
        self.driver.execute_script("document.body.innerHTML=arguments[0];", body_content)

    def scroll_screen(self) -> None:
        self.driver.execute_script("window.scrollBy(0, 500)")

    def must_click(self, element: WebElement) -> None:
        try:
            ActionChains(self.driver).move_to_element(element).click().perform()
        except Exception as e:
            logger.info(f"selenium用户模拟点击[mustClick]与网页元素交互失败: {e}")

    def remove_debugger(self) -> None:
        """对齐 Java removeDebugger：注入反反调试脚本并设置跳过所有断点。"""
        anti_debug = r"""
        (function() {
            window.debugger = function() {};
            const originalFunction = Function;
            Function = function(...args) {
                if (args.length > 0 && typeof args[0] === 'string' && args[0].includes('debugger')) {
                    return function() { console.log('debugger blocked'); };
                }
                return originalFunction(...args);
            };
            Function.prototype = originalFunction.prototype;
            const originalEval = window.eval;
            window.eval = function(code) {
                if (typeof code === 'string' && code.includes('debugger')) return undefined;
                return originalEval.call(this, code);
            };
            const originalNow = performance.now;
            performance.now = function() { return Date.now(); };
            console.debug = function() {};
            console.log('Anti-debug protection disabled');
        })();
        """
        self._cdp("Page.addScriptToEvaluateOnNewDocument", {"source": anti_debug})
        self._cdp("Debugger.enable", {})
        self._cdp("Debugger.setSkipAllPauses", {"skip": True})

    def override_location(self) -> None:
        """对齐 Java overrideLocation：固定地理坐标/时区/语言。"""
        self._cdp("Emulation.setGeolocationOverride", {
            "latitude": 40.061513671875,
            "longitude": 116.421068250869,
            "accuracy": 1,
        })
        self._cdp("Emulation.setTimezoneOverride", {"timezoneId": "Asia/Shanghai"})
        self._cdp("Emulation.setLocaleOverride", {"locale": "zh-Hans-CN"})

    def set_extra_http_headers(self, headers: Dict[str, str]) -> None:
        self._cdp("Network.setExtraHTTPHeaders", {"headers": headers})

    def clean_slate(self) -> None:
        """对齐 Java cleanSlate：清缓存 + 清 Cookie，比 deleteAllCookies 更彻底。"""
        self._cdp("Network.clearBrowserCache", {})
        self._cdp("Network.clearBrowserCookies", {})

    def capture_page_with_driver(self) -> np.ndarray:
        # 截图并保存为NumPy数组
        screenshot = self.driver.get_screenshot_as_png()
        screenshot_np = np.frombuffer(screenshot, np.uint8)
        image = cv2.imdecode(screenshot_np, cv2.IMREAD_COLOR)

        return image

    # ==================== CDP 截图 ====================

    def cdp_screenshot(self, node: Optional[CDPNode] = None) -> Optional[str]:
        """
        对齐 Java cdpScreenshot(无参/CDPNode)：
        - 不传 node：截整页
        - 传 node：截元素的可见区域
        返回 Base64 PNG 字符串。
        """
        params: Dict[str, Any] = {"format": "png", "fromSurface": True}
        if node is not None:
            clip = self._node_clip_box(node)
            if clip is None:
                return None
            params["clip"] = clip
        try:
            result = self._cdp("Page.captureScreenshot", params)
            return result.get("data")
        except Exception as e:
            logger.error(f"CDP截图失败 backendNodeId={getattr(node, 'backend_node_id', None)}: {e}")
            return None

    def _node_clip_box(self, node: CDPNode) -> Optional[Dict[str, Any]]:
        try:
            res = self._cdp("DOM.getBoxModel", {"backendNodeId": node.backend_node_id})
            model = res.get("model")
            if not model:
                return None
            content = model.get("content")
            if not content or len(content) < 8:
                return None
            x = float(content[0])
            y = float(content[1])
            width = float(content[2]) - x
            height = float(content[5]) - y
            return {
                "x": x, "y": y,
                "width": max(width, 1),
                "height": max(height, 1),
                "scale": 1,
            }
        except Exception as e:
            logger.error(f"DOM.getBoxModel失败 backendNodeId={node.backend_node_id}: {e}")
            return None

    # ==================== CDP DOM 快照 ====================

    def get_cdp_dom_snapshot(self) -> CDPNode:
        """对齐 Java getCDPDomSnapshot：一次性获取整棵 DOM（穿透 shadow/iframe）。"""
        result = self._cdp("DOM.getDocument", {"depth": -1, "pierce": True})
        return _parse_cdp_node(result.get("root"), None)

    def click_text(self, text: str, delay_ms: int = 500) -> None:
        """对齐 Java clickText：基于文本匹配点击所有命中元素。"""
        body = self.get_cdp_dom_snapshot().get_body()
        if body is None:
            return
        for node in body.find_nodes_by_text(text, use_equal=True):
            self.cdp_click(node)
            _sleep(abs(delay_ms))

    def crawl_website(self, url: str) -> Optional[str]:
        """对齐 Java crawlWebsite：取 body 文本并保留前 1000 字符中的字母，其余替换为空格。"""
        try:
            if not self.go_url(url):
                return None
            body = self.get_cdp_dom_snapshot().get_body()
            if body is None:
                return None
            raw = body.crawl_all_element()
            out = []
            for i, ch in enumerate(raw[:1000]):
                out.append(ch if ch.isalpha() else " ")
            return "".join(out)
        except Exception as e:
            logger.error(f"crawl_website error: {e}")
            return None

    # ==================== CDP 鼠标交互 ====================

    def click_point_with_templates(self, src: np.ndarray, temp: np.ndarray, loc: tuple, percent_x: float = 0.5,
                                   percent_y: float = 0.5,
                                   click: bool = True, button_num: int = 0):
        y, x = src.shape[0:2]
        src_shape = (x, y)
        y, x = temp.shape[0:2]
        temp_shape = (x, y)
        rec = self.driver.get_window_size()
        w, h = (rec["width"], rec["height"])
        middle_x = (loc[0] + temp_shape[0] * percent_x) / src_shape[0] * w
        middle_y = (loc[1] + temp_shape[1] * percent_y) / src_shape[1] * h
        logger.debug('x:%.2f y:%.2f', middle_x, middle_y)
        # 获取当前窗口大小
        window_width = self.driver.execute_script("return window.innerWidth;")
        window_height = self.driver.execute_script("return window.innerHeight;")
        logger.debug("window_width: %.2f, window_height: %.2f", window_width, window_height)
        actions = ActionChains(self.driver)
        # 进行重置坐标
        actions.reset_actions()
        # 将鼠标移动到指定的坐标位置
        actions.move_by_offset(middle_x, middle_y)

        # 执行点击操作
        actions.click().perform()

    def cdp_click(self, node: CDPNode) -> bool:
        center = self._cdp_get_center(node)
        if center is None:
            return False
        return self._cdp_dispatch_mouse_click(center[0], center[1])

    def cdp_hover(self, node: CDPNode) -> bool:
        center = self._cdp_get_center(node)
        if center is None:
            return False
        try:
            self._cdp("Input.dispatchMouseEvent", {
                "type": "mouseMoved", "x": center[0], "y": center[1],
            })
            return True
        except Exception as e:
            logger.debug(f"CDP鼠标悬停失败: {e}")
            return False

    def cdp_focus(self, node: CDPNode) -> bool:
        if node is None or node.backend_node_id == 0:
            return False
        try:
            self._cdp("DOM.focus", {"backendNodeId": node.backend_node_id})
            return True
        except Exception as e:
            logger.info(f"CDP聚焦失败 backendNodeId={node.backend_node_id}: {e}")
            return False

    def cdp_scroll_into_view(self, node: CDPNode) -> bool:
        if node is None or node.backend_node_id == 0:
            return False
        try:
            self._cdp("DOM.scrollIntoViewIfNeeded", {"backendNodeId": node.backend_node_id})
            return True
        except Exception as e:
            logger.debug(f"CDP滚动到可视区域失败 backendNodeId={node.backend_node_id}: {e}")
            return False

    def cdp_scroll_screen(self, delta_x: int, delta_y: int, x: int = 0, y: int = 0) -> bool:
        """对齐 Java cdpScrollScreen：通过 mouseWheel 事件实现零JS滚动。"""
        try:
            self._cdp("Input.dispatchMouseEvent", {
                "type": "mouseWheel", "x": x, "y": y,
                "deltaX": delta_x, "deltaY": delta_y,
            })
            return True
        except Exception as e:
            logger.debug(f"CDP页面滚动失败: {e}")
            return False

    def cdp_set_value(self, node: CDPNode, value: str) -> bool:
        """对齐 Java cdpSetValue：聚焦→三击全选→删除→插入新文本，全程零JS。"""
        self._cdp_triple_click(node)
        self.cdp_key_press("Backspace", False, False)
        if value:
            return self.cdp_insert_text(value)
        return True

    def cdp_clear(self, node: CDPNode) -> bool:
        return self.cdp_set_value(node, "")

    def cdp_check(self, node: CDPNode, checked: bool) -> bool:
        """对齐 Java cdpCheck：通过点击切换 checkbox/radio 状态。"""
        current = self.cdp_get_attribute(node, "checked")
        is_checked = current is not None
        if is_checked == checked:
            return True
        return self.cdp_click(node)

    def cdp_select_option(self, node: CDPNode, value: str) -> bool:
        """对齐 Java cdpSelectOption：展开 select → 点击 option 文本。"""
        if not self.cdp_click(node):
            return False
        _sleep(300)
        self.click_text(value)
        return False

    # ---- 鼠标内部工具 ----
    def _cdp_get_center(self, node: CDPNode) -> Optional[Tuple[float, float]]:
        if node is None or node.backend_node_id == 0:
            return None
        try:
            result = self._cdp("DOM.getBoxModel", {"backendNodeId": node.backend_node_id})
            model = result.get("model")
            if not model:
                return None
            quad = model.get("border")
            if not quad or len(quad) < 8:
                return None
            x = sum(float(quad[i * 2]) for i in range(4)) / 4
            y = sum(float(quad[i * 2 + 1]) for i in range(4)) / 4
            return x, y
        except Exception as e:
            logger.debug(f"CDP获取坐标失败 backendNodeId={node.backend_node_id}: {e}")
            return None

    def _cdp_dispatch_mouse_click(self, x: float, y: float) -> bool:
        try:
            self._cdp("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
            self._cdp("Input.dispatchMouseEvent", {
                "type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 1,
            })
            self._cdp("Input.dispatchMouseEvent", {
                "type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 1,
            })
            return True
        except Exception as e:
            logger.debug(f"CDP鼠标事件派发失败: {e}")
            return False

    def _cdp_triple_click(self, node: CDPNode) -> bool:
        """对齐 Java cdpTripleClick：clickCount=3 的 press+release 全选。"""
        center = self._cdp_get_center(node)
        if center is None:
            return False
        x, y = center
        try:
            self._cdp("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y})
            self._cdp("Input.dispatchMouseEvent", {
                "type": "mousePressed", "x": x, "y": y, "button": "left", "clickCount": 3,
            })
            self._cdp("Input.dispatchMouseEvent", {
                "type": "mouseReleased", "x": x, "y": y, "button": "left", "clickCount": 3,
            })
            return True
        except Exception as e:
            logger.debug(f"CDP三击失败: {e}")
            return False

    # ==================== CDP 键盘交互 ====================

    def cdp_insert_text(self, text: str) -> bool:
        """对齐 Java cdpInsertText：Input.insertText 整段插入。"""
        if text is None:
            return False
        try:
            self._cdp("Input.insertText", {"text": text})
            return True
        except Exception as e:
            logger.debug(f"CDP插入文本失败: {e}")
            return False

    def cdp_type_text(self, text: str, interval_ms: int = 0) -> bool:
        """对齐 Java cdpTypeText：逐字符 keyDown/keyUp，可触发联想等逐键事件。"""
        if text is None:
            return False
        try:
            for ch in text:
                key_code = KeyEventCodes.get_code(ch)
                down: Dict[str, Any] = {
                    "type": "keyDown", "text": ch, "key": ch,
                    "code": f"Key{ch.upper()}",
                }
                if key_code > 0:
                    down["windowsVirtualKeyCode"] = key_code
                self._cdp("Input.dispatchKeyEvent", down)

                up: Dict[str, Any] = {
                    "type": "keyUp", "key": ch,
                    "code": f"Key{ch.upper()}",
                }
                if key_code > 0:
                    up["windowsVirtualKeyCode"] = key_code
                self._cdp("Input.dispatchKeyEvent", up)

                if interval_ms > 0:
                    _sleep(interval_ms)
            return True
        except Exception as e:
            logger.debug(f"CDP逐键输入失败: {e}")
            return False

    def cdp_key_press(self, key: str, ctrl: bool = False, shift: bool = False) -> bool:
        """对齐 Java cdpKeyPress：单键派发，支持 Ctrl/Shift 组合。"""
        key_code = KeyEventCodes.get_code(key)
        try:
            if ctrl:
                self._cdp("Input.dispatchKeyEvent", {
                    "type": "keyDown", "key": "Control", "code": "ControlLeft",
                    "windowsVirtualKeyCode": 162,
                })
                if shift:
                    self._cdp("Input.dispatchKeyEvent", {
                        "type": "keyDown", "key": "Shift", "code": "ShiftLeft",
                        "windowsVirtualKeyCode": 160,
                    })
            modifiers = 0
            if ctrl:
                modifiers |= 2
            if shift:
                modifiers |= 1

            down: Dict[str, Any] = {
                "type": "keyDown", "key": key,
                "code": f"Key{key}" if key_code > 0 else key,
            }
            if key_code > 0:
                down["windowsVirtualKeyCode"] = key_code
            if modifiers:
                down["modifiers"] = modifiers
            self._cdp("Input.dispatchKeyEvent", down)

            up: Dict[str, Any] = {"type": "keyUp", "key": key}
            if key_code > 0:
                up["windowsVirtualKeyCode"] = key_code
            if modifiers:
                up["modifiers"] = modifiers
            self._cdp("Input.dispatchKeyEvent", up)

            if ctrl:
                if shift:
                    self._cdp("Input.dispatchKeyEvent", {
                        "type": "keyUp", "key": "Shift", "code": "ShiftLeft",
                        "windowsVirtualKeyCode": 160,
                    })
                self._cdp("Input.dispatchKeyEvent", {
                    "type": "keyUp", "key": "Control", "code": "ControlLeft",
                    "windowsVirtualKeyCode": 162,
                })
            return True
        except Exception as e:
            logger.debug(f"CDP按键失败 key={key}: {e}")
            return False

    # ==================== CDP JS 查询（同源 iframe 可用） ====================

    def cdp_call_function_on(self, node: CDPNode, function_js: str,
                             *args: Any) -> Any:
        """对齐 Java cdpCallFunctionOn：DOM.resolveNode → Runtime.callFunctionOn。"""
        object_id = self._cdp_resolve_node_id(node)
        if object_id is None:
            return None
        try:
            params: Dict[str, Any] = {
                "objectId": object_id,
                "functionDeclaration": function_js,
                "returnByValue": True,
            }
            if args:
                params["arguments"] = [{"value": a} for a in args]
            result = self._cdp("Runtime.callFunctionOn", params)
            remote_obj = result.get("result")
            if remote_obj is not None:
                return remote_obj.get("value")
        except Exception as e:
            logger.debug(f"CDP调用函数失败: {e}")
        return None

    def cdp_get_value(self, node: CDPNode) -> Optional[str]:
        ret = self.cdp_call_function_on(node, "function() { return this.value; }")
        return None if ret is None else str(ret)

    def cdp_get_attribute(self, node: CDPNode, attr_name: str) -> Optional[str]:
        ret = self.cdp_call_function_on(node,
                                        "function(name) { return this.getAttribute(name); }",
                                        attr_name)
        return None if ret is None else str(ret)

    def cdp_set_attribute(self, node: CDPNode, attr_name: str, attr_value: str) -> bool:
        ret = self.cdp_call_function_on(node,
                                        "function(n,v) { this.setAttribute(n,v); return true; }",
                                        attr_name, attr_value)
        return ret is True

    def cdp_is_visible(self, node: CDPNode) -> bool:
        ret = self.cdp_call_function_on(node, """
            function() {
                if (this.offsetParent === null && this.tagName !== 'BODY') return false;
                var s = window.getComputedStyle(this);
                return s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
            }
        """)
        return ret is True

    def _cdp_resolve_node_id(self, node: CDPNode) -> Optional[str]:
        if node is None or node.backend_node_id == 0:
            return None
        try:
            result = self._cdp("DOM.resolveNode", {"backendNodeId": node.backend_node_id})
            remote_obj = result.get("object")
            if remote_obj is not None:
                return remote_obj.get("objectId")
        except Exception as e:
            logger.debug(f"CDP解析节点失败 backendNodeId={node.backend_node_id}: {e}")
        return None

    # ==================== Selenium 兼容接口 ====================

    def find_element(self, by: By, value: str) -> WebElement:
        return self.driver.find_element(by, value)

    def must_find_elements(self, by: By, value: str) -> List[WebElement]:
        self._wait(by, value, TIMEOUT)
        return self.driver.find_elements(by, value)

    def must_find_class_name(self, class_name: str) -> List[WebElement]:
        return self.must_find_elements(By.CSS_SELECTOR, f'[class="{class_name}"]')

    def close_current_tab_and_switch(self) -> None:
        """对齐 Java closeCurrentTabAndSwitch：关闭当前标签页并切到剩余标签。"""
        if len(self.driver.window_handles) > 1:
            self.driver.close()
        handles = self.driver.window_handles
        if handles:
            self.driver.switch_to.window(handles[0])

    # ==================== 内部工具 ====================

    def _cdp(self, cmd: str, params: Dict[str, Any]) -> Dict[str, Any]:
        return self.driver.execute_cdp_cmd(cmd, params)

    def _wait(self, by: By, value: str, timeout_seconds: int) -> None:
        WebDriverWait(self.driver, timeout_seconds).until(
            EC.presence_of_element_located((by, value))
        )


# ============================ 解析 CDP DOM JSON ============================

def _parse_cdp_node(data: Optional[Dict[str, Any]], parent: Optional[CDPNode]) -> Optional[CDPNode]:
    """对齐 Java parseCDPNode：递归解析 DOM.getDocument 返回的 JSON。"""
    if data is None:
        return None
    node = CDPNode()
    node.parent = parent
    node.node_id = int(data.get("nodeId", 0) or 0)
    node.backend_node_id = int(data.get("backendNodeId", 0) or 0)
    node.node_type = int(data.get("nodeType", 0) or 0)
    node.node_name = data.get("nodeName", "") or ""
    node.node_value = data.get("nodeValue", "") or ""
    node.local_name = data.get("localName", "") or ""
    node.shadow_root_type = data.get("shadowRootType")
    node.frame_id = data.get("frameId")

    raw_attrs = data.get("attributes")
    if raw_attrs:
        node.attributes = [str(a) for a in raw_attrs]

    raw_children = data.get("children")
    if raw_children:
        node.children = []
        for c in raw_children:
            child = _parse_cdp_node(c, node)
            if child is not None:
                node.children.append(child)

    # CDP 对 iframe 节点，内部文档放在 contentDocument 而非 children
    content_doc = data.get("contentDocument")
    if content_doc:
        if node.children is None:
            node.children = []
        cd_node = _parse_cdp_node(content_doc, node)
        if cd_node is not None:
            node.children.append(cd_node)
    return node


# ============================ 平台判定 ============================

def _is_windows() -> bool:
    import sys
    return sys.platform == "win32"


def _not_windows() -> bool:
    return not _is_windows()


def _is_arm() -> bool:
    import platform
    machine = platform.machine().lower()
    return machine in ("aarch64", "arm64", "armv7l", "armv8l")


# ============================ 兼容 Java 端命名（snake↔camel） ============================

# 为方便从 Java 端逐字翻译脚本调用，挂上 camelCase 别名
MyWebDriver.getCDPDomSnapshot = MyWebDriver.get_cdp_dom_snapshot  # type: ignore[attr-defined]
MyWebDriver.cdpClick = MyWebDriver.cdp_click  # type: ignore[attr-defined]
MyWebDriver.cdpHover = MyWebDriver.cdp_hover  # type: ignore[attr-defined]
MyWebDriver.cdpFocus = MyWebDriver.cdp_focus  # type: ignore[attr-defined]
MyWebDriver.cdpScrollIntoView = MyWebDriver.cdp_scroll_into_view  # type: ignore[attr-defined]
MyWebDriver.cdpScrollScreen = MyWebDriver.cdp_scroll_screen  # type: ignore[attr-defined]
MyWebDriver.cdpSetValue = MyWebDriver.cdp_set_value  # type: ignore[attr-defined]
MyWebDriver.cdpClear = MyWebDriver.cdp_clear  # type: ignore[attr-defined]
MyWebDriver.cdpCheck = MyWebDriver.cdp_check  # type: ignore[attr-defined]
MyWebDriver.cdpSelectOption = MyWebDriver.cdp_select_option  # type: ignore[attr-defined]
MyWebDriver.cdpInsertText = MyWebDriver.cdp_insert_text  # type: ignore[attr-defined]
MyWebDriver.cdpTypeText = MyWebDriver.cdp_type_text  # type: ignore[attr-defined]
MyWebDriver.cdpKeyPress = MyWebDriver.cdp_key_press  # type: ignore[attr-defined]
MyWebDriver.cdpCallFunctionOn = MyWebDriver.cdp_call_function_on  # type: ignore[attr-defined]
MyWebDriver.cdpGetValue = MyWebDriver.cdp_get_value  # type: ignore[attr-defined]
MyWebDriver.cdpGetAttribute = MyWebDriver.cdp_get_attribute  # type: ignore[attr-defined]
MyWebDriver.cdpSetAttribute = MyWebDriver.cdp_set_attribute  # type: ignore[attr-defined]
MyWebDriver.cdpIsVisible = MyWebDriver.cdp_is_visible  # type: ignore[attr-defined]
MyWebDriver.cdpScreenshot = MyWebDriver.cdp_screenshot  # type: ignore[attr-defined]
MyWebDriver.cdpReload = MyWebDriver.cdp_reload  # type: ignore[attr-defined]
MyWebDriver.clickText = MyWebDriver.click_text  # type: ignore[attr-defined]
MyWebDriver.crawlWebsite = MyWebDriver.crawl_website  # type: ignore[attr-defined]
MyWebDriver.getCurrentUrl = MyWebDriver.get_current_url  # type: ignore[attr-defined]
MyWebDriver.getWindowsTabNum = MyWebDriver.get_windows_tab_num  # type: ignore[attr-defined]
MyWebDriver.goUrl = MyWebDriver.go_url  # type: ignore[attr-defined]
MyWebDriver.closeCurrentTabAndSwitch = MyWebDriver.close_current_tab_and_switch  # type: ignore[attr-defined]
MyWebDriver.mustClick = MyWebDriver.must_click  # type: ignore[attr-defined]
MyWebDriver.removeDebugger = MyWebDriver.remove_debugger  # type: ignore[attr-defined]
MyWebDriver.overrideLocation = MyWebDriver.override_location  # type: ignore[attr-defined]
MyWebDriver.setExtraHTTPHeaders = MyWebDriver.set_extra_http_headers  # type: ignore[attr-defined]
MyWebDriver.cleanSlate = MyWebDriver.clean_slate  # type: ignore[attr-defined]
MyWebDriver.isClosed = MyWebDriver.is_closed  # type: ignore[attr-defined]
MyWebDriver.cancelAlert = MyWebDriver.cancel_alert  # type: ignore[attr-defined]
MyWebDriver.clearCookie = MyWebDriver.clear_cookie  # type: ignore[attr-defined]
MyWebDriver.addCookie = MyWebDriver.add_cookie  # type: ignore[attr-defined]
MyWebDriver.getWebPageCookie = MyWebDriver.get_web_page_cookie  # type: ignore[attr-defined]
MyWebDriver.setBodyHtmlWithJS = MyWebDriver.set_body_html_with_js  # type: ignore[attr-defined]
MyWebDriver.scrollScreen = MyWebDriver.scroll_screen  # type: ignore[attr-defined]
MyWebDriver.findElement = MyWebDriver.find_element  # type: ignore[attr-defined]
MyWebDriver.mustFindElements = MyWebDriver.must_find_elements  # type: ignore[attr-defined]
MyWebDriver.mustFindClassName = MyWebDriver.must_find_class_name  # type: ignore[attr-defined]
CDPNode.crawlAllElement = CDPNode.crawl_all_element  # type: ignore[attr-defined]
CDPNode.getBody = CDPNode.get_body  # type: ignore[attr-defined]
CDPNode.getAttr = CDPNode.get_attr  # type: ignore[attr-defined]
CDPNode.findCDPNodesByText = CDPNode.find_nodes_by_text  # type: ignore[attr-defined]
CDPNode.findCDPNodesByTagName = CDPNode.find_nodes_by_tag  # type: ignore[attr-defined]
CDPNode.findCDPNodesByClassName = CDPNode.find_nodes_by_class  # type: ignore[attr-defined]
CDPNode.findCDPNodeById = CDPNode.find_node_by_id  # type: ignore[attr-defined]
CDPNode.findCDPNodesByAttr = CDPNode.find_nodes_by_attr  # type: ignore[attr-defined]
CDPNode.cdpGetTextContent = CDPNode.get_text_content  # type: ignore[attr-defined]
CDPNode.enumCDPNodes = CDPNode.enum_nodes  # type: ignore[attr-defined]
CDPNode.isElement = CDPNode.is_element  # type: ignore[attr-defined]
CDPNode.isText = CDPNode.is_text  # type: ignore[attr-defined]
CDPNode.isDocument = CDPNode.is_document  # type: ignore[attr-defined]
CDPNode.isShadowRoot = CDPNode.is_shadow_root  # type: ignore[attr-defined]
