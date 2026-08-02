from __future__ import annotations  # 使用高级注解器，支持类成员方法返回自身类型

import abc
import os
import threading
import time
from typing import List, TypeVar, Callable, Generic, Tuple, Any, Dict, Type
import uiautomator2 as u2
from uiautomator2 import _BaseClient
import cv2
import ctypes
import adbutils

import numpy as np
from lxml.etree import _Element as MyXmlElement
from PyTools.MyAwesomeTool.PyUseCPlus import Rect, PyRect, MainUI, MyOpenCv, start_thread, build_logger
from PyTools.MyAwesomeTool.MyUtil import group_str_pipline, TimeStringClassifier, StringClassifier, BaseScriptArranger
import re
from datetime import datetime, timedelta
import pdb
from PyTools.MyAwesomeTool.MyUtil import auto_patch_python
import hashlib
from lxml import etree

logger = build_logger(filename="log.log", name=__name__, use_to_debug=True, file_log_debug=True, use_time_rotate=False)
"""
weditor 通过JavaScript的 findNodesByPosition 函数排序找到最小节点面积，来到合适的node节点
"""
test_input = """
经销商简称:徐州华莲
客户姓名: 徐作伍
电话:18361200676
车型:2024款哪吒S猎装 增程300 Pro
期数:60期
费率: 0.417%     25%
开票价：151200
贷款金额:100000
还款方式：等本等息
贴息方案：否 
工作单位:贾汪区张仰双餐饮店
营业执照码:92320305MA27P2E83P
岗位:店长
工作年限: 2年
居住年限: 6年
现住址:江苏省徐州市云龙区润金城二期D8-502室
紧急联系人:渠翠翠
联系电话:14752182260
上牌城市：徐州 @aasd
麻烦处理:

"""


class WxStringClassifier(StringClassifier):
    def on_pipline(self, input_tuple_c: Tuple[str, str]) -> Any:
        ch, new_state = input_tuple_c
        self.ignored = False
        if self.state in ["is_space", "is_symbol", "is_@"]:  # "is_div",
            self.ignored = True
        if ch == ' ':
            new_state = "is_space"
        elif ch in [':', '：']:
            new_state = "is_symbol"
        elif ch in ['\n', '\r']:
            new_state = "is_div"
        elif ch == '@':
            new_state = 'is_@'
        else:
            new_state = "is_text"

        if self.state == "is_text" and new_state == "is_space":
            pass
        elif self.state == "is_@" and new_state == "is_text":  # @后不更新状态
            pass
        else:

            self.state = new_state
        return self.state


class HookDevice(u2.Device):
    def _setup_jar(self):
        jar_path = os.path.abspath("./assets/u2.jar")

        target_path = "/data/local/tmp/u2.jar"
        if self._check_device_file_hash(jar_path, target_path):
            logger.debug("file u2.jar already pushed")
        else:
            logger.debug("push %s -> %s", jar_path, target_path)
            self._dev.sync.push(jar_path, target_path, check=True)


def str_to_md5(input_str: str):
    return hashlib.md5(input_str.encode("utf-8")).hexdigest()


def analyze_wx_time(input_str: str):
    # time_strings = ["2020年2月22日 上午09:59", "10月12日 晚上21:33", "昨天 晚上9:55", "下午3:32"]
    ch_list = group_str_pipline(input_str, [None, TimeStringClassifier])
    now = datetime.now()
    month = now.month
    day = now.day
    year = now.year
    time_part = "00:00"
    yesterday = False
    period = False
    for i, (ch, ch_type) in enumerate(ch_list):
        if ch == "月":
            month = ch_list[i - 1][0]
        elif ch == "年":
            year = ch_list[i - 1][0]
        elif ch == "日":
            day = ch_list[i - 1][0]
        elif ch.__contains__(":"):
            time_part = ch
        elif ch == "昨天":
            yesterday = True
        elif ch in ["晚上", "下午"]:
            period = True

    ret = datetime.strptime(f"{year}-{month}-{day} {time_part}", "%Y-%m-%d %H:%M")  # %I:%M"

    # 根据"晚上"或"下午"来处理24小时制
    if period:
        ret = ret + timedelta(hours=12) if ret.hour < 12 else ret

    if yesterday:
        ret = ret - timedelta(hours=24)
    return ret


def analyze_wx_info_list(input_str: str) -> Dict[str, str]:
    div_list = group_str_pipline(input_str, [WxStringClassifier])
    total = len(div_list)
    list_builder = []
    res = {}
    for ch, ch_type in div_list:
        if ch_type.__eq__("is_div"):
            if list_builder.__len__() > 1:
                res[list_builder[0]] = list_builder[1]
            elif list_builder.__len__() > 0:
                res[list_builder[0]] = ''
            # res.append(list_builder)
            list_builder = []
        else:
            list_builder.append(ch.strip())
    if list_builder.__len__() > 1:
        if list_builder.__len__() > 1:
            res[list_builder[0]] = list_builder[1]
        elif list_builder.__len__() > 0:
            res[list_builder[0]] = ''
        # res.append(list_builder)
    return res


# 获取当前页面的所有控件
# elements = d.xpath("//*").all()
class XmlElementAnalyzer(u2.xpath.XMLElement):
    def __init__(self, elem: MyXmlElement):
        super().__init__(elem)

    def __str__(self):
        return self.get_xpath()

    def get_ele_xpath(self, strip_index: bool = False):
        root = self.elem.getroottree()
        path = root.getpath(self.elem)
        return os.path.basename(path)

    def get_attrib(self, attr_name="text"):
        if self.elem.attrib.__contains__(attr_name):
            return self.elem.attrib[attr_name]
        else:
            return None

    def get_resource_id(self) -> str:
        return self.get_attrib("resource-id")

    def get_content_desc(self) -> str:
        return self.get_attrib("content-desc")

    def get_rect(self) -> PyRect | None:
        bounds = self.get_attrib("bounds")
        if bounds is None:
            return None
        else:
            return PyRect(*self.bounds)

    def get_text(self):
        return self.get_attrib("text")

    def get_attrib_dic(self):
        return self.elem.attrib


class PhoneController:
    def __init__(self, main_ui: MainUI, device_id="QWBILZRGSW7XXCV4"):
        self.main_ui = main_ui
        self.main_ui.set_simple_button_callback(self.__test_button_callback)
        serial = adbutils.adb.device()

        self.__device = HookDevice(serial)  # u2.connect(device_id)  # 通过设备号与手机建立连接

        self.__img = None
        self.__hierarchy_root_xml: MyXmlElement = self.capture_hierarchy_root_xml()
        self.__debug_wait_signal = threading.Event()

    def enter_recent_apps(self):
        # 模拟按下安卓的多任务视图按钮
        self.__device.press("recent")

    def wait_for_debug(self):
        self.__debug_wait_signal.clear()
        self.__debug_wait_signal.wait()

    def __test_button_callback(self):
        self.main_ui.delete_all_tree()
        self.capture_screen()
        self.capture_hierarchy_root_xml()
        self.render_tree()
        self.__debug_wait_signal.set()

    @staticmethod
    def __build_find_callback(find_callback: Callable[[XmlElementAnalyzer], bool]):
        def temp_find_callback(stack: List[int], other_stack: List[Any], element: MyXmlElement):
            ea = XmlElementAnalyzer(element)
            if find_callback(ea) is True:
                return None
            else:
                return ""

        return temp_find_callback

    @staticmethod
    def __build_find_many_callback(res_list: List[XmlElementAnalyzer],
                                   find_callback: Callable[[XmlElementAnalyzer], bool]):
        def temp_find_callback(stack: List[int], other_stack: List[Any], element: MyXmlElement):
            ea = XmlElementAnalyzer(element)
            if find_callback(ea) is True:
                res_list.append(XmlElementAnalyzer(element))
            return ""

        return temp_find_callback

    def __main_ui_tree_render_callback(self, stack: List[int], other_stack: List[Any], element: MyXmlElement) -> str:
        ea = XmlElementAnalyzer(element)
        # print(self.stack_to_str(other_stack), ea.get_xpath())

        return self.main_ui.add_to_tree(other_stack[-1], str(ea.get_ele_xpath()), str(ea.get_attrib_dic()),
                                        str(ea.get_text()),
                                        str(ea.get_attrib("bounds")))

    def foreach_xml_element(self, callback: Callable[[List[int], List[Any], MyXmlElement], Any]) -> \
            Tuple[List[int], List[Any], MyXmlElement | None]:
        stack: List[int] = [-1]
        stack_other: List[Any] = [""]
        # callback([], node)  # 发起回调
        node: MyXmlElement = self.__hierarchy_root_xml
        while stack.__len__() > 0:
            index_now = stack[stack.__len__() - 1] + 1  # 树结构索引栈
            if index_now == 0:
                other_info = callback(stack, stack_other, node)  # 发起回调
                if other_info is None:
                    return stack, stack_other, node
                stack_other.append(other_info)
            # elems = node.xpath(".//*")  # .all()
            if index_now < node.__len__():  # 当前索引超出子列表范围，说明子节点遍历完成
                node = node[index_now]  # 获取子节点
                stack.pop()  # 更新栈顶索引值
                stack.append(index_now)  # 更新栈顶索引值
                stack.append(-1)  # 拥有子节点则深度优先遍历
            else:
                stack.pop()  # 出栈
                stack_other.pop()
                node = node.getparent()  # 树节点回退
        return stack, stack_other, None

    def find_element_by_attr_dic(self, key_and_value: Dict[str, str]) -> XmlElementAnalyzer | None:
        def compare(ea: XmlElementAnalyzer):
            result = True
            for key in key_and_value.keys():
                value = key_and_value[key]
                if ea.get_attrib(key) == value:
                    continue
                else:
                    result = False
                    break
            return result

        find_callback = self.__build_find_callback(lambda ea: compare(ea))
        s1, s2, node = self.foreach_xml_element(find_callback)
        if node is None:
            return None
        return XmlElementAnalyzer(node)

    def find_element_by_resource_id(self, resource_id) -> XmlElementAnalyzer | None:
        return self.find_element_by_attr_dic({"resource-id": resource_id})

    def find_elements_by_attr_dic(self, key_and_value: Dict[str, str]) -> List[XmlElementAnalyzer]:
        def compare(ea: XmlElementAnalyzer):
            result = True
            for key in key_and_value.keys():
                value = key_and_value[key]
                if ea.get_attrib(key) == value:
                    continue
                else:
                    result = False
                    break
            return result

        res = []
        find_callback = self.__build_find_many_callback(res, lambda ea: compare(ea))
        self.foreach_xml_element(find_callback)
        return res

    def find_elements_by_resource_id(self, resource_id) -> List[XmlElementAnalyzer]:

        return self.find_elements_by_attr_dic({"resource-id": resource_id})

    def capture_hierarchy_root_xml(self) -> MyXmlElement:
        # 获取当前界面根节点，对于微信这类有反爬虫设计的APP，需安装hamibot、autox.js等软件启动【无障碍】服务后台才能绕过限制，否则获取不到控件xml
        root = self.__device.xpath("/*").get()
        self.__hierarchy_root_xml = root.elem
        xml_str = etree.tostring(root.elem, encoding='unicode', pretty_print=True)
        self.main_ui.show_text(xml_str)
        return self.__hierarchy_root_xml

    def get_hierarchy_root_xml(self) -> MyXmlElement:
        return self.__hierarchy_root_xml

    def capture_screen(self) -> np.ndarray:
        self.__img = self.__device.screenshot(format="opencv")
        return self.__img
        # width, height = self.device.window_size()
        # cv2.imwrite("1.png", im)
        # cv2.imshow("1", cv2.resize(im, (width // 1, height // 1)))
        #
        # cv2.waitKey()

    def render_tree(self):
        if self.__img is None:
            return
        self.foreach_xml_element(self.__main_ui_tree_render_callback)
        self.main_ui.expend_all_tree()
        self.main_ui.show_image(self.__img)

    def click(self, x, y):
        self.__device.click(x, y)

    # 滑动屏幕
    def swipe(self, opt_str: str = "上"):
        # 获取屏幕的宽度和高度
        width, height = self.__device.window_size()
        # 从屏幕中间向上滑动
        x_from = width // 2
        x_to = width // 2
        y_from = height // 4
        y_to = height // 4
        if opt_str.__contains__("下"):
            y_to = height * 2 // 4
        elif opt_str.__contains__("左"):
            x_to = 0
        elif opt_str.__contains__("右"):
            x_to = width
        else:
            y_from = height * 2 // 4
        # print(x_from, y_from, x_to, y_to)
        self.__device.swipe(x_from, y_from, x_to, y_to, duration=0.05)

    def send_keys(self, text: str, clear: bool = True):
        self.__device.send_keys(text, clear=clear)


class ScriptArranger(BaseScriptArranger):
    def __init__(self, main_ui: MainUI):
        super().__init__()
        self.pc = PhoneController(main_ui)
        self.__observation_shot_memory_xml_cache: Dict[str, bool] = {}  # 短期记忆，看一次更新一次，由脚本自动控制生命周期
        self._alm.remember_this_info("数智", "[搜索文本]")

    def _clear_cache(self):
        self.__observation_shot_memory_xml_cache = {}
        self._asm.forget_all()

    def __print_callback(self, stack: List[int], other_stack: List[Any], element: MyXmlElement) -> str:
        # print("-" * 30)
        ea = XmlElementAnalyzer(element)
        # print(self.stack_to_str(stack), ea.get_xpath())
        text = ea.get_text()
        if text is not None and ea.get_resource_id().__eq__("com.tencent.mm:id/kbq"):
            print(self._stack_to_str(stack), ea.get_xpath())
            print("控件文字", text)
            print("bounds", ea.get_rect())
            print("控件信息", ea.get_attrib_dic())
        return ""

    def loop_entry_point(self):
        # self.pc.capture_screen()
        # self.pc.capture_hierarchy_root_xml()
        self.pc.wait_for_debug()
        self._clear_cache()
        try:
            self.observe_and_do("当前是在微信主页; X题头是微信两个字",
                                "遗忘 当前页面所有微信群名; 点击 左下角微信两个字")
            self.observe_and_do("当前是在微信主页; X有_搜索放大镜", "向下滑动")
            self.observe_and_do("当前是在微信主页; 题头是微信两个字; 有_搜索放大镜", "点击 搜索放大镜")
            self.observe_and_do("手机控件有提示 搜索本地或网络结果; X手机控件有文本 [搜索文本]",
                                "点击 搜索本地或网络结果; 输入 [搜索文本]")
            self.observe_and_do(
                "手机控件有提示 搜索本地或网络结果; 手机控件有文本 [搜索文本]; X手机控件有文本 更多群聊", "向上滑动")
            self.observe_and_do("手机控件有提示 搜索本地或网络结果; 手机控件有文本 [搜索文本]; 手机控件有文本 更多群聊",
                                "点击 更多群聊")
            self.observe_and_do("X手机控件有提示 搜索本地或网络结果; 手机控件有文本 [搜索文本]; ",
                                "记忆 当前页面所有微信群名")
            self.observe_and_do("X手机控件有提示 搜索本地或网络结果; 手机控件有文本 [搜索文本]; X找到了目标群聊",
                                "向上滑动")
            self.observe_and_do("X手机控件有提示 搜索本地或网络结果; 手机控件有文本 [搜索文本]; 找到了目标群聊",
                                "点击 目标群聊")
            self.observe_and_do("已经进入微信群聊; 手机控件有描述 更多信息", "点击 更多信息; 遗忘 当前页面所有微信群名")
            self.observe_and_do("手机控件有文本 查找聊天记录; X手机控件有文本 退出群聊", "向上滑动")
            self.observe_and_do("手机控件有文本 查找聊天记录; 手机控件有文本 退出群聊", "点击 退出群聊")
            self.observe_and_do("手机控件有文本 退出后其他群成员不会收到通知; 手机控件有文本 取消", "点击 取消")
            self.observe_and_do("当前在手机主页; 找到微信APP", "遗忘 当前页面所有微信群名; 点击 微信APP")
            self.observe_and_do("当前在手机主页; X找到微信APP", "遗忘 当前页面所有微信群名; 向右滑动")
        except OverflowError:
            pass

    def is_wechat_title(self):
        title = self.pc.find_element_by_resource_id("android:id/text1")
        if title is None:
            return False
        if title.get_text().__contains__("微信"):
            return True
        return False

    def is_wechat_search(self):
        search = self.pc.find_element_by_attr_dic({'NAF': 'true', 'resource-id': 'com.tencent.mm:id/meb'})
        if search is None:
            return False
        self._asm.remember_this_info(search.get_rect().get_middle(), "搜索放大镜")
        return True

    def is_phone_xml_has_text(self, text: str, key: str):
        if text.__eq__("[搜索文本]"):
            text = self._alm.get_remember_info(text)
        if key.__eq__("提示"):
            key = 'hint'
        elif key.__eq__("描述"):
            key = 'content-desc'
        else:
            key = 'text'
        search = self.pc.find_element_by_attr_dic({key: text})
        if search is None:
            return False
        print(search.get_attrib_dic())
        self._asm.remember_this_info(search.get_rect().get_middle(), text)
        return True

    def is_in_wechat_homepage(self):
        ele_list = [ele for ele in self.pc.find_elements_by_resource_id("com.tencent.mm:id/icon_tv")]
        text_list = [ele.get_text() for ele in ele_list]
        # print(text_list)
        navigation = ["微信", "通讯录", "发现", "我"]
        in_wechat = True
        for ne in navigation:
            if ne in text_list:
                continue
            else:
                in_wechat = False
                break
        if in_wechat:
            for i, text in enumerate(text_list):
                if text == "微信":
                    self._asm.remember_this_info(ele_list[i].get_rect().get_middle(), "左下角微信两个字")
        return in_wechat

    def is_wechat_find_aim_group(self):
        result = False
        if self._alm.if_remember_this_info("当前页面所有微信群名"):
            res_dic: Dict[str, PyRect] = self._alm.get_remember_info("当前页面所有微信群名")
            for aim_text in ["跟进"]:
                for group_name in res_dic.keys():
                    if group_name.__contains__(aim_text):
                        rect: PyRect = res_dic[group_name]
                        result = (2400 - rect.top) > 50  # 保证目标群聊按钮落在屏幕中间
                        self._asm.remember_this_info((rect.left, rect.top), "目标群聊")
                        break
                if result:
                    break
        return result

    def is_wechat_has_2_days_chat_history(self):
        ui = [ele.get_text() for ele in self.pc.find_elements_by_resource_id("com.tencent.mm:id/br1")]
        now_day = datetime.now()
        result = False
        for text in ui:
            if text is not None:
                if now_day - analyze_wx_time(text) > timedelta(days=4):
                    result = True
                    break
        return result

    def action_route(self, *args) -> bool:
        action_alias_name = args[0]
        if action_alias_name.__eq__("记忆"):
            switch_name = args[1]
            if switch_name.__eq__("当前页面所有微信群名"):
                save_at_least_one = False  # 至少多存了一个群名称，说明操作成功了，否则可能是屏幕卡住了
                for ele in self.pc.find_elements_by_resource_id("com.tencent.mm:id/odf"):
                    text = ele.get_text()
                    if not self._alm.if_remember_this_info(switch_name, text):
                        save_at_least_one = True
                    self._alm.remember_this_info(ele.get_rect(), switch_name, text)

                return save_at_least_one
            elif switch_name.__eq__("当前页面所有微信聊天记录"):
                save_at_least_one = False  # 至少多存了一个群名称，说明操作成功了，否则可能是屏幕卡住了
                for ele in self.pc.find_elements_by_resource_id("com.tencent.mm:id/bkl"):
                    text = ele.get_text()
                    text_dic = analyze_wx_info_list(text)
                    if text_dic.__contains__("客户姓名"):
                        text_md5 = str_to_md5(text_dic["客户姓名"] + text_dic["电话"] + text_dic["贷款金额"])
                        if not self._alm.if_remember_this_info(switch_name, text_md5):
                            self._alm.remember_this_info(text_dic, switch_name, text_md5)
                            now_order_num = len(self._alm.get_remember_info(switch_name).keys())
                            logger.debug(f"当前一共找到{now_order_num}个订单,新加入的订单信息为:{text_dic}")
                            save_at_least_one = True
                return save_at_least_one
        elif action_alias_name.__contains__("滑动"):
            self.pc.swipe(action_alias_name)
        elif action_alias_name.__eq__("打开后台视图"):
            self.pc.enter_recent_apps()
        elif action_alias_name.__eq__("什么都不做"):
            pass
        elif action_alias_name.__eq__("点击"):
            observation_alias_name = args[1]
            x, y = self._asm.get_remember_info(observation_alias_name)
            self.pc.click(x, y)
            print("click aa")
        elif action_alias_name.__eq__("输入"):
            self.pc.send_keys(self._alm.get_remember_info(args[1]) if args[1].__eq__("[搜索文本]") else args[1])
        elif action_alias_name.__eq__("遗忘"):
            self._alm.forget_this_info(args[1])

        return True

    def observation_route(self, *args) -> bool:
        result = True
        observation_alias_name: str = args[0]
        if observation_alias_name.startswith("手机控件有"):
            text = args[1]
            result = self.is_phone_xml_has_text(text, observation_alias_name.replace("手机控件有", ""))
            return result
        if self.__observation_shot_memory_xml_cache.__contains__(observation_alias_name):
            result = self.__observation_shot_memory_xml_cache[observation_alias_name]
            return result
        if observation_alias_name.__eq__("默认观察"):
            self.pc.foreach_xml_element(self.__print_callback)
        elif observation_alias_name.__eq__("渲染树状图"):
            self.pc.render_tree()
        elif observation_alias_name.__eq__("当前是在微信主页"):
            result = self.is_in_wechat_homepage()
        elif observation_alias_name.__eq__("有_搜索放大镜"):
            result = self.is_wechat_search()
        elif observation_alias_name.__eq__("保存的群名包含文件传输助手"):
            result = self._alm.if_remember_this_info("当前页面所有微信群名", "文件传输助手")
        elif observation_alias_name.__eq__("题头是微信两个字"):
            result = self.is_wechat_title()
        elif observation_alias_name.__eq__("找到了目标群聊"):
            result = self.is_wechat_find_aim_group()
        elif observation_alias_name.__eq__("已经进入微信群聊"):
            ui = [ele.get_content_desc() for ele in self.pc.find_elements_by_resource_id("com.tencent.mm:id/bjz")]
            result = "更多功能按钮，已折叠" in ui
        elif observation_alias_name.__eq__("当前在手机主页"):
            find_pattern = {'package': 'com.miui.home', "content-desc": "相机"}
            node = self.pc.find_element_by_attr_dic(find_pattern)
            result = node is not None
        elif observation_alias_name.__eq__("找到微信APP"):
            find_pattern = {'package': 'com.miui.home', "content-desc": "微信"}
            node = self.pc.find_element_by_attr_dic(find_pattern)
            result = node is not None
            if result:
                self._asm.remember_this_info(node.get_rect().get_middle(), "微信APP")
        elif observation_alias_name.__eq__("当前聊天存在2天前的信息"):
            result = self.is_wechat_has_2_days_chat_history()

        else:
            pass
        self.__observation_shot_memory_xml_cache[observation_alias_name] = result
        return result


def main_loop(main_ui: MainUI):
    # 遍历并输出控件信息
    sa = ScriptArranger(main_ui)
    sa.start_script_loop()
    # pc.observation_xml("渲染树状图")
    return


def main(patch_md5: str = None, patch_path: str = None):
    if patch_md5 is None or patch_md5 == auto_patch_python(None, patch_path=patch_path):
        MainUI(main_loop).myloop()
    else:
        time.sleep(1)
        print("等待正确的MD5 patch")


# d.click(52, 146) 点击对应坐标
if __name__ == '__main__':
    # bbb = analyze_wx_info_list(test_input)
    # res = []
    # for s in time_strings:
    #     res.append(print(analyze_wx_time(s)))
    #     # print(s, )
    main(None)
# for s in time_strings:

# c = analyze_wx_info_list(test_input)
# print(c)
