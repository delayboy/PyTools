from __future__ import annotations

import os
import time
from typing import Dict, List, Tuple, Sequence
import cv2
import numpy as np
import opencc
from PyTools.MyAwesomeTool.PyUseCPlus import MainUI, MyOpenCv, Rect, WinManager
import PyTools.MyAwesomeTool.MyDll as MyDllLib
from PyTools.MyAwesomeTool.MyUtil import BaseScriptArranger, auto_patch_python
from PyTools.MyAwesomeTool.MyOcrEngine import MyPytorchPaddleOCR

# ==============================================================================
# 全局配置
# ==============================================================================

# 模板图片目录（相对脚本所在目录）
TEMPLATE_DIR = os.path.join(os.path.abspath("."), "ba_template_pic") + os.sep

# 目标学生列表（简体中文，按需扩充）
TARGET_STUDENT_NAMES: str = """
洁莉诺
洁莉诺(温泉)
莉央
美祢(偶像)
伊织
芹奈
咏叶
朱音
花子
玛丽
遥香
桃井
菲娜
亚伽里
仁耶
泉
茱莉
一花
美咲
白子(单车)
花绘
桐乃
明日奈
智惠(旗袍)
伊树菜
花凛
喜美
静子
铃美
莲实
咲希
志美子
萌
亚都梨
阳葵(武装)
爱莉
日向
淳子
名草
绫音
小玉
莲华(泳装)
茜香
晴
千夏
绘梨
皐月
椿(导览员)
玛丽娜(旗袍)
朱音(兔女郎)
茱莉(打工)
阳葵
时雨(温泉)
瀬奈(私服)
美奈
咲希(泳装)
爱瑠
贵音
美优
紫
莉央(武装)
泉(正月)
莉
若藻(泳装)
季(兔女郎)
小玉(露营)
羽留奈(体育服)
咏叶(应援团）
菲娜(导览员）
樱子
季(武装)
令女
月夜(礼服)
沙织(礼服)
桔梗(泳装)
海花
沙织
菲娜(导览员)
咏叶(应援团)
"""

# 学生搜索的百分比范围（先随便填，之后自行测量）
STUDENT_SEARCH_PERCENT_RECT = Rect(0.35, 0.20, 0.85, 0.95)

# 学生名 OCR 子图扩展尺寸（以桃信信号 loc 为起点，向左向上扩展）
STUDENT_NAME_RECT_W = 518
STUDENT_NAME_RECT_H = 20

# 列表向上滑动 / 详情右侧向上滑动 的起止百分比（之后自行测量）
LIST_DRAG_FROM_PERCENT = (0.30, 0.65)
LIST_DRAG_TO_PERCENT = (0.30, 0.35)
DETAIL_SWIPE_FROM_PERCENT = (0.85, 0.70)
DETAIL_SWIPE_TO_PERCENT = (0.85, 0.30)

# 保底点击位置（屏幕左上角百分比）
SAFE_CORNER_PERCENT = (0.19, 0.17)

# 模板匹配阈值
SCORE_THRESHOLD = 0.94

# 超时上限
TIMEOUT_LIMIT = 50

# 单轮循环间隔（避免空转占CPU）
LOOP_SLEEP = 0.5


class BaScriptArranger(BaseScriptArranger):
    """Blue Archive 好感度剧情自动播放智能体脚手架。"""

    def __init__(self, main_ui: MainUI):
        super().__init__()
        self.main_ui = main_ui
        # 蔚蓝档案 Unity 窗口
        self.mainManager = WinManager(main_ui.my_dll, "")  # "Blue Archive", class_name="UnityWndClass"
        # OCR：繁中识别 + 繁转简
        self.ocr_engine = MyPytorchPaddleOCR(lang="ch_lite")
        self.ch_converter = opencc.OpenCC('t2s.json')
        # 当前帧缓存（一轮内观察链截图一次，动作链按需复用，避免重复截图）
        self.__cache_img: np.ndarray = None
        # 防止脚本内部模拟按键被全局 hook 误判为用户按键
        self.is_sending_key = False
        # 主循环启停标志（独立于父类 _start_loop，便于外部读取）
        self.running_flag = False
        self.__is_debug = False
        self.student_debug_name = {}
        self.statistic_all_student = True
        print("加载完毕")

    # ==========================================================================
    # 框架接口
    # ==========================================================================
    def _clear_cache(self):
        """每轮循环开始时清空短期缓存；长期记忆 _alm 不在这里清。"""
        self.__cache_img = None
        self._asm.forget_all()

    # ==========================================================================
    # 长期记忆 _alm 语义封装（key 命名集中在这里，方便未来扩充）
    # ==========================================================================
    # _alm 结构：
    #   "学生名"   -> {name: (x, y)}     当前命中的目标学生，只保留一个
    #   "超时次数" -> int                 连续未推进的轮数，超过 TIMEOUT_LIMIT 触发兜底
    def _remember_student(self, name: str, coord: Tuple[int, int]):
        self._alm.remember_this_info({name: coord}, "学生名")

    def _forget_student(self):
        self._alm.forget_this_info("学生名")

    def _has_student(self) -> bool:
        d = self._alm.get_remember_info("学生名")
        return isinstance(d, dict) and len(d) > 0

    def _get_student(self):
        """返回 (name, coord) 或 None。"""
        d = self._alm.get_remember_info("学生名")
        if not isinstance(d, dict) or not d:
            return None
        for name, coord in d.items():
            return name, coord
        return None

    def _incr_timeout(self, delta=1):
        cur = self._alm.get_remember_info("超时次数") or 0
        self._alm.remember_this_info(cur + delta, "超时次数")

    def _reset_timeout(self):
        self._alm.forget_this_info("超时次数")

    def _is_timeout_over(self) -> bool:
        cur = self._alm.get_remember_info("超时次数") or 0
        return cur > TIMEOUT_LIMIT

    # ==========================================================================
    # 通用工具
    # ==========================================================================
    def capture(self) -> np.ndarray:
        if self.__is_debug:
            self.__cache_img = self.load_template("测试桌面截图/monoTalk学生列表.png")
            return self.__cache_img
        time.sleep(0.5)
        self.__cache_img = MyOpenCv.extract_rgb(self.mainManager.capture_window(None))
        return self.__cache_img

    def get_img(self) -> np.ndarray:
        if self.__cache_img is None:
            self.capture()
        return self.__cache_img

    def show_debug(self, text: str, img: np.ndarray = None):
        if not self.__is_debug:
            return
        if img is None:
            img = self.get_img()
        try:
            # self.main_ui.show_image(img, text)
            cv2.imshow("img", img)
            cv2.waitKey()
            # self.main_ui.wait_pause_signal()
        except Exception:
            pass

    def show_mouse_debug(self, text: str, x: int, y: int):
        if not self.__is_debug:
            return
        debug_img = MyOpenCv.draw_rect(self.get_img(), Rect(x, y, x + 50, y + 50))
        self.show_debug(text, debug_img)

    @staticmethod
    def load_template(name: str) -> np.ndarray:
        return MyOpenCv.cv_imread(TEMPLATE_DIR + name, cv2.IMREAD_UNCHANGED)

    def find_template(self, name: str, img: np.ndarray = None) -> Tuple[float, Tuple[int, int]]:
        if img is None:
            img = self.get_img()
        temp = self.load_template(name)
        score, loc = MyOpenCv.match_single_score_and_pos(img, temp)
        # self.show_debug("find_template", MyOpenCv.show_single_match_pic(img, temp, score, tuple(loc)))
        return score, (loc[0], loc[1])

    def find_sub_template(self, name: str, percent_rect: Rect,
                          img: np.ndarray = None) -> Tuple[float, Tuple[int, int]]:
        if img is None:
            img = self.get_img()
        temp = self.load_template(name)
        sub, rect = MyOpenCv.cut_picture_with_percent(img, percent_rect)
        score, loc = MyOpenCv.match_single_score_and_pos(sub, temp)
        # self.show_debug("find_sub_template", MyOpenCv.show_single_match_pic(img, temp, score, tuple(loc)))
        return score, (int(loc[0] + rect.left), int(loc[1] + rect.top))

    def click_absolute(self, loc_in_window: Tuple[int, int]):
        """loc_in_window 是相对 BA 窗口左上角的像素坐标。"""
        rect = self.mainManager.get_rect()
        dll = self.mainManager.myDll
        x = int(rect.left + loc_in_window[0])
        y = int(rect.top + loc_in_window[1])
        dll.set_cursor_pos(x, y)
        self.show_mouse_debug("click_absolute", x, y)
        dll.send_mouse_down(True)
        time.sleep(0.01)
        dll.send_mouse_down(False)
        time.sleep(0.01)

    def click_percent(self, percent: Tuple[float, float]):
        rect = self.mainManager.get_rect()
        dll = self.mainManager.myDll
        x = int(rect.left + rect.get_width() * percent[0])
        y = int(rect.top + rect.get_height() * percent[1])
        dll.set_cursor_pos(x, y)
        self.show_mouse_debug("click_percent", x, y)
        dll.send_mouse_down(True)
        time.sleep(0.01)
        dll.send_mouse_down(False)
        time.sleep(0.01)

    def drag_by_percent(self, from_p: Tuple[float, float], to_p: Tuple[float, float], div_num=20):
        rect = self.mainManager.get_rect()
        fx = int(rect.left + rect.get_width() * from_p[0])
        fy = int(rect.top + rect.get_height() * from_p[1])
        tx = int(rect.left + rect.get_width() * to_p[0])
        ty = int(rect.top + rect.get_height() * to_p[1])
        dll = self.mainManager.myDll
        dll.set_cursor_pos(fx, fy)
        self.show_mouse_debug("drag_by_percent", fx, fy)
        self.show_mouse_debug("drag_by_percent", tx, ty)
        time.sleep(0.05)
        dll.send_mouse_down(True)
        time.sleep(0.01)
        for i in range(1, div_num + 1):
            dll.set_cursor_pos(
                fx + int((tx - fx) * i / div_num),
                fy + int((ty - fy) * i / div_num),
            )
            time.sleep(0.01)
        dll.send_mouse_down(False)
        time.sleep(0.05)

    def press_key(self, key_code: int):
        self.is_sending_key = True
        try:
            self.show_mouse_debug(f"press_key:[{chr(key_code)}]", 0, 0)
            self.mainManager.send_key_code(True, key_code)
            time.sleep(0.05)
            self.mainManager.send_key_code(False, key_code)
            time.sleep(0.05)
        finally:
            self.is_sending_key = False

    # ==========================================================================
    # 观察链
    # ==========================================================================
    def observation_route(self, *args) -> bool:
        ob = args[0]
        if ob == "默认观察":
            return True
        try:
            if ob == "在主页":
                return self.find_sub_template("主页图标.png", Rect(0.82, 0.01, 1.0, 0.21))[0] > SCORE_THRESHOLD
            if ob == "找到桃信图标":
                return self.find_sub_template("桃信.png", Rect(0.03, 0.02, 0.19, 0.30))[0] > SCORE_THRESHOLD
            if ob == "学生通信列表亮":
                if self.statistic_all_student:
                    return self.find_template("消息气泡-亮.png")[0] > SCORE_THRESHOLD
                return self.find_template("学生通信列表-亮.png")[0] > SCORE_THRESHOLD
            if ob == "消息气泡亮":
                if self.statistic_all_student:
                    return self.find_template("学生通信列表-亮.png")[0] > SCORE_THRESHOLD
                return self.find_template("消息气泡-亮.png")[0] > SCORE_THRESHOLD
            if ob == "有学生名记忆":
                return self._has_student()
            if ob == "找到桃信信号":
                return self.has_signal_in_search_area()
            if ob == "找到菜单按钮":
                return self.find_template("菜单.png")[0] > SCORE_THRESHOLD
            if ob == "找到确认按钮":
                return self.find_template("确认.png")[0] > SCORE_THRESHOLD
            if ob == "超时次数大于50":
                return self._is_timeout_over()
        except Exception as e:
            print(f"[BA观察链异常] {ob}: {e}")
        return False

    def has_signal_in_search_area(self) -> bool:
        if self.statistic_all_student:
            return self.find_template("学生好感爱心.png")[0] > SCORE_THRESHOLD
        s1, _ = self.find_sub_template("桃信信号1.png", STUDENT_SEARCH_PERCENT_RECT)
        s2, _ = self.find_sub_template("桃信信号2.png", STUDENT_SEARCH_PERCENT_RECT)
        return s1 > SCORE_THRESHOLD or s2 > SCORE_THRESHOLD

    # ==========================================================================
    # 动作链
    # ==========================================================================
    def action_route(self, *args) -> bool:
        action = args[0]
        try:
            if action == "点击":
                return self.action_click(args[1])
            if action == "学生搜索":
                return self.action_student_search()
            if action == "向上滑动列表":
                self.drag_by_percent(LIST_DRAG_FROM_PERCENT, LIST_DRAG_TO_PERCENT)
                return True
            if action == "向上滑动右侧":
                self.drag_by_percent(DETAIL_SWIPE_FROM_PERCENT, DETAIL_SWIPE_TO_PERCENT)
                return True
            if action == "按1和空格":
                self.press_key(ord("1"))  # 主键盘 1，不是数字小键盘
                self.press_key(0x20)  # VK_SPACE
                return True
            if action == "按ESC":
                self.press_key(0x1B)  # VK_ESCAPE
                return True
            if action == "点击左上角保底":
                self.click_percent(SAFE_CORNER_PERCENT)
                return True
            if action == "超时加1":
                self._incr_timeout()
                return True
            if action == "超时加4":
                self._incr_timeout(4)
                return True
            if action == "遗忘超时次数":
                self._reset_timeout()
                return True
            if action == "遗忘学生名":
                self._forget_student()
                return True
        except Exception as e:
            print(f"[BA动作链异常] {action}: {e}")
        return False

    def action_click(self, target: str) -> bool:
        # 特殊：学生名坐标来自长期记忆
        if target == "学生名坐标":
            student = self._get_student()
            if student is None:
                return False
            _, coord = student
            self.click_absolute(coord)
            return True
        # 其他目标基于模板匹配点击
        template_name = target if target.endswith(".png") else target + ".png"
        temp = self.load_template(template_name)
        score, loc = self.find_template(template_name)
        if score < SCORE_THRESHOLD:
            return False
        click_loc = (int(loc[0]), int(loc[1]))
        # 特殊：学生通信列表-亮 需要点击 Y 底部 + 15px
        if target == "学生通信列表-亮":
            _, h = MyOpenCv.get_image_size(temp)
            click_loc = (click_loc[0], click_loc[1] + h + 15)
        self.show_mouse_debug("click_absolute", click_loc[0], click_loc[1])
        self.mainManager.click_point_with_templates(temp, click_loc, 0.5, 0.5, True)
        return True

    def action_student_search(self) -> bool:
        """
        桃信信号多目标匹配 + OCR 识别学生名。

        步骤：
        1. 在固定百分比 rect 内最多 6 次匹配【桃信信号1/2】，每次取两者得分更高且 >0.9 的那个，
           涂黑后继续匹配（参考 PartnerHelper.number_ocr 的循环涂黑写法）。
        2. 对每个匹配点 loc，向左向上扩展 50x20 子图做 easyocr 识别，繁转简。
        3. 与 TARGET_STUDENT_NAMES 比对，命中即长期记忆 {学生名: 屏幕坐标}。
        始终返回 False（动作不完整，让本轮动作链继续往后执行）。
        """
        img = self.capture()
        # 切出搜索区域
        src, area_rect = MyOpenCv.cut_picture_with_percent(img, STUDENT_SEARCH_PERCENT_RECT)
        temp1 = self.load_template("桃信信号1.png")
        temp2 = self.load_template("桃信信号2.png")
        if self.statistic_all_student:
            temp1 = self.load_template("学生好感爱心.png")
            temp2 = self.load_template("学生好感爱心.png")

        # 1. 多目标匹配，最多 6 次
        src_with_black = src.copy()
        signal_locs: List[Tuple[int, int]] = []
        debug_img = src.copy()
        for _ in range(6):
            if self.statistic_all_student:
                s1, l1 = MyOpenCv.match_single_alpha_score_and_pos(src_with_black, temp1)
                s2, l2 = s1, l1
            else:
                s1, l1 = MyOpenCv.match_single_score_and_pos(src_with_black, temp1)
                s2, l2 = MyOpenCv.match_single_score_and_pos(src_with_black, temp2)
            chosen_score, chosen_loc, chosen_temp = 0.0, None, None
            if s1 > SCORE_THRESHOLD and s1 >= s2:
                chosen_score, chosen_loc, chosen_temp = s1, l1, temp1
            elif s2 > SCORE_THRESHOLD:
                chosen_score, chosen_loc, chosen_temp = s2, l2, temp2
            if chosen_loc is None:
                break
            signal_locs.append((int(chosen_loc[0]), int(chosen_loc[1])))
            w, h = MyOpenCv.get_image_size(chosen_temp)
            fill_rect = Rect(chosen_loc[0], chosen_loc[1], chosen_loc[0] + w, chosen_loc[1] + h)
            src_with_black = MyOpenCv.fill_black_to_src(src_with_black, fill_rect)
            debug_img = MyOpenCv.draw_rect(debug_img, fill_rect, (0, 0, 255, 255))
            print(f"[学生搜索] match #{len(signal_locs)} score={chosen_score:.3f} loc={chosen_loc}")
        self.show_debug(f"signals={len(signal_locs)}", debug_img)

        # 2. 对每个匹配点 OCR 学生名
        for loc_in_sub in signal_locs:
            abs_x = int(area_rect.left + loc_in_sub[0])
            abs_y = int(area_rect.top + loc_in_sub[1])
            offset = 0
            if self.statistic_all_student:
                offset = 30
            ocr_rect = Rect(
                abs_x - STUDENT_NAME_RECT_W + offset,
                abs_y - STUDENT_NAME_RECT_H,
                abs_x - offset,
                abs_y + 25,
            )
            try:
                name_img = MyOpenCv.cut_picture(img, ocr_rect)
            except Exception:
                continue
            ocr_debug = MyOpenCv.draw_rect(img, ocr_rect, (255, 0, 0, 255))
            self.show_debug(f"OCR @({abs_x},{abs_y})", ocr_debug)
            try:
                result = self.ocr_engine.ocr(name_img, det=True, rec=True)
            except Exception as e:
                print(f"[学生搜索] OCR 异常: {e}")
                continue
            text = "".join([text for lvl, box, text, score in result])
            text = self.ch_converter.convert(text).strip().replace("(", "(")
            print(f"[学生搜索] OCR='{text}' @({abs_x},{abs_y})")
            # 3. 命中目标学生即记忆，匹配到一个就结束
            student_names = self.main_ui.get_text().split("\n")
            self.student_debug_name[text.replace(" ", "")] = 1
            for target_name in student_names:
                text = text.replace(" ", "")
                if text.__eq__(""):
                    continue
                if text.__eq__(target_name.replace(" ", "")):
                    self._remember_student(target_name, (abs_x, abs_y))
                    print(f"[学生搜索] 命中目标: {target_name} @ ({abs_x},{abs_y})")
                    return False
        return False

    # ==========================================================================
    # 主循环入口（动作优先级用户会自行调整，无需担心）
    # ==========================================================================
    def loop_entry_point(self):
        time.sleep(LOOP_SLEEP)
        self._clear_cache()
        try:
            # 8. 超时 > 50：按 ESC，遗忘超时，遗忘学生名
            self.observe_and_do("超时次数大于50", "按ESC; 遗忘超时次数; 遗忘学生名")
            # 6. 看到菜单按钮：进入好感度剧情，按 ESC 跳过，遗忘超时
            self.observe_and_do("找到菜单按钮", "按ESC; 遗忘超时次数")
            # 7. 看到确认按钮：点击确认跳过，遗忘学生名
            self.observe_and_do("找到确认按钮", "点击 确认; 遗忘学生名")
            # 1. 主页 + 桃信图标：点击桃信
            self.observe_and_do("在主页; 找到桃信图标", "点击 桃信")
            # 2. 学生通信列表亮：点击图片底部 + 15px 激活消息气泡
            self.observe_and_do("学生通信列表亮", "点击 学生通信列表-亮")
            # 3. 消息气泡亮 且 无学生名记忆：执行学生搜索（动作始终返回 False，链继续）
            self.observe_and_do("消息气泡亮; X有学生名记忆", "学生搜索")
            # 4. 未发现桃信信号 且 无学生名记忆：向上滑动列表，超时 +1
            self.observe_and_do("X有学生名记忆", "向上滑动列表; 超时加1; 点击左上角保底")
            # 5. 有学生名记忆：点击坐标 + 右侧向上滑动 + 按1和空格 + 超时 +1
            self.observe_and_do("有学生名记忆",
                                "点击 学生名坐标; 向上滑动右侧; 按1和空格; 超时加4")
            # 9. 保底：点击左上角固定位置
            self.observe_and_do("默认观察", "点击左上角保底")
        except OverflowError:
            pass


# ==============================================================================
# 入口：MainUI + 全局键盘 hook
# ==============================================================================
def main_loop(app: MainUI):
    arranger = BaScriptArranger(app)
    arranger.running_flag = False
    app.show_text(
        "[BA自动桃信脚本] 进入游戏电脑版主页按键盘左上角 `~ 键启动脚本 / 按TAB键 停止脚本，如果UI识别结果不佳，请修改ba_template_pic文件夹下的模板图片，重新截图\n"
        "请将需要过桃信的学生写在下方，写国际服简体中文即可，没有指定名字的学生不会过桃信（防止不小心过掉老师心爱学生的桃信）：" + TARGET_STUDENT_NAMES)

    def on_user_key(key_code: int) -> bool:
        # VK_OEM_3（`~ 键）：启动 / 暂停切换
        if key_code == MyDllLib.VK_OEM_3:
            if arranger.running_flag:
                arranger.stop_loop()
                arranger.running_flag = False
                msg = "[BA] 已暂停"
            else:
                arranger.start_script_loop()
                arranger.running_flag = True
                msg = "[BA] 已启动"
            print(msg)
            # app.show_text(msg + "  (`~ 切换 / ESC 退出)")
            return True
        # ESC：关闭脚本（排除脚本内部模拟的 ESC）
        if key_code == 9:
            arranger.stop_loop()
            arranger.running_flag = False
            msg = "[BA] ESC 退出"
            print(msg)
            # app.show_text(msg)
            print("临时截图")
            app.show_image(arranger.mainManager.capture_window(None))
            app.delete_all_tree()
            for key in arranger.student_debug_name.keys():
                app.add_to_tree("", key)
            return True
        return False

    app.set_user_key_code_callback(on_user_key)


def main(patch_md5: str = None, patch_path: str = None):
    if patch_md5 is None or patch_md5 == auto_patch_python(None, patch_path=patch_path):
        main_ui = MainUI(main_loop)
        main_ui.my_dll.register_event_hook(1, True)
        main_ui.myloop()
        exit(0)
    else:
        time.sleep(1)
        print("等待正确的MD5 patch")


if __name__ == "__main__":
    main(None, "")
