from __future__ import annotations

import os.path
import threading
import time
from typing import List, Dict

import numpy as np

from PyTools.MyAwesomeTool.PyUseCPlus import MyOpenCv, Rect, auto_patch_python
from PyTools.MyAwesomeTool.MyUtil import get_file_from_env_path, set_env_var, this_process
from PyTools.MyAwesomeTool.PyUseCPlus import WinManager, MainUI, MyDllLib, start_thread, build_logger

logger = build_logger(filename="log_ba.log", name=__name__, use_to_debug=True, file_log_debug=True,
                      use_time_rotate=False)

MAX_SLOT = 6
CAPTURE_RECT = Rect(0.59, 0.70, 1.06, 1.06)
TEMPLATE_DIR = "templates"


class BAProperty:
    def __init__(self, name: str, max_skill_time: float, can_refresh: bool):
        self.name = name
        self.max_skill_time = max_skill_time
        self.can_refresh = can_refresh

    def __str__(self):
        return "%s %.2f %d" % (self.name, self.max_skill_time, self.can_refresh)

    @staticmethod
    def get_partner_properties() -> Dict[str, BAProperty]:
        res = {}
        for line in PARTNER_SETTING.split("\n"):
            tuples = line.split("^")
            if len(tuples) > 2:
                proper = BAProperty(tuples[0], float(tuples[1]), tuples[2].__eq__("true"))
                logger.debug(proper.__str__())
                res[proper.name] = proper
        return res


class BAHelper:
    def __init__(self, main_app: MainUI):
        self.main_app = main_app
        self.mainManager = WinManager(self.main_app.my_dll, "")
        self.main_app.set_user_key_code_callback(self.user_key_code)
        self.main_app.set_user_key_code_realtime_callback(self.realtime_mouse_callback)
        self.partner_properties = BAProperty.get_partner_properties()
        self.ship_names = self.get_default_names()
        self.member_len = len(self.ship_names)
        self.show_member_index: List[int] = []
        self.need_remove_index: List[int] = []
        self.skills_cd = [0.0] * self.member_len
        self.__late_callback_signal = threading.Event()
        self.key_code_index = 0
        self.cache_index = -1
        self.key_map = ["Q", "W", "E", "R", "D", "F"]
        self.pause = False

        # 记录上一帧每个模板是否存在，用于检测 "出现→消失" 的变化
        self.prev_detected = [False] * self.member_len

        self.screenshot_running = False

        rect = self.mainManager.get_rect()
        w, h = rect.get_size()
        x, y, w, h = int(rect.left), int(rect.top), int(w), int(h)
        t_hwnd = self.main_app.my_dll.create_transparent_window(x, y, w, h, self.paint_callback)
        self.my_dll = self.main_app.my_dll
        self.my_dll.set_window_display_affinity(t_hwnd, 1)
        self.drawManager = WinManager(self.main_app.my_dll, t_hwnd)

        start_thread(self.skills_cd_loop, ())
        self.main_app.my_dll.register_event_hook(1, True)
        self.main_app.my_dll.register_event_hook(0, True)
        main_app.show_text("BAHelper初始化完成，按 ` 键启动/停止截图监控，\n"
                           "按QWER释放对应学生技能，目前只支持4个槽位\n"
                           "星野等角色具体buff持续时间，请在【角色buff冷却值配置.py】文件的PARTNER_SETTING中完成配置，\n"
                           "角色头像模板图需在templates文件夹下配置")

    def paint_callback(self, hdc):
        if not self.screenshot_running:
            self.drawManager.clear_draw(hdc)
            return
        for k in range(min(MAX_SLOT, len(self.show_member_index))):
            i = self.show_member_index[k]
            name = self.ship_names[i]
            text_color = (255, 255, 255)
            bk_color = (255, 0, 0) if self.skills_cd[i] > 0.1 else (0, 255, 0)
            if i == self.cache_index:  # 当前技能释放中则变为蓝色
                bk_color = (0, 0, 255)
            y_pos = Y_POS_0 + k * Y_DELTA
            cd = self.skills_cd[i]
            if cd < 0.1:
                cd = 0
            shot_cut_name = self.key_map[i]
            show_text = "%.1f[%s]:%s" % (cd, shot_cut_name, name)
            draw_rect = Rect(0.88, y_pos, 1, y_pos + 0.06)
            real_draw_rect = self.drawManager.from_percent_rect_get_real_rect(draw_rect)
            self.drawManager.draw_rect(real_draw_rect, (0, 0, 0), hdc, False)
            self.drawManager.draw_text(draw_rect, show_text, text_color, bk_color, hdc=hdc)

    def refresh(self):
        self.drawManager.refresh_window(Rect(0.88, Y_POS_0, 1, Y_POS_0 + MAX_SLOT * Y_DELTA))

    def append_and_pop_show_member_index_if_larger_than_max_slot(self, hit_index: int):
        if hit_index in self.show_member_index:  # 如果已包含该角色，则重新排序角色到队尾
            # self.show_member_index.remove(hit_index)
            # if hit_index in self.need_remove_index:
            #     self.need_remove_index.remove(hit_index)
            # self.show_member_index.append(hit_index)
            return
        while len(self.show_member_index) > MAX_SLOT:  # 是新角色则更新老角色，将老角色排除队列
            if len(self.need_remove_index) > 0:  # 有可以排除的角色，则执行排除
                v = self.need_remove_index.pop()  # left pop 堆栈模式，后进先出，堆栈模式视觉上更稳定
                self.show_member_index.remove(v)
            else:
                self.show_member_index.pop()  # 没有可排除角色，则强制排除末尾角色

        self.show_member_index.append(hit_index)

    def skills_cd_loop(self):
        while True:
            if self.pause:
                time.sleep(0.1)
                self.refresh()
                continue
            for k in range(len(self.show_member_index)):
                i = self.show_member_index[k]
                if self.skills_cd[i] > 0:
                    if not self.cache_index < 0:  # 上次技能还未结算，则开启慢速技能模式
                        self.skills_cd[i] -= 0.02
                    else:
                        self.skills_cd[i] -= 0.1
                    if self.skills_cd[i] < 0:
                        self.skills_cd[i] = 0
                        self.need_remove_index.append(i)
                else:
                    self.need_remove_index.append(i)
            time.sleep(0.1)
            self.refresh()

    def screenshot_loop(self):
        logger.debug("截图监控线程启动")
        reboot_path = os.path.join(TEMPLATE_DIR, "reboot.png")
        reboot_mat = MyOpenCv.cv_imread(reboot_path)
        while self.screenshot_running:
            self.__late_callback_signal.clear()
            self.__late_callback_signal.wait()
            if self.key_code_index < 0:
                self.pause = True
                img = self.mainManager.capture_window(None)
                score, loc = MyOpenCv.match_single_score_and_pos(img, reboot_mat)
                if score > 0.9:  # 已经有重新开始，说明取消了pause
                    self.pause = False
                else:
                    self.pause = True
                continue
            if not self.cache_index < 0:  # 上次技能还未结算，则先不执行
                continue
            i = self.key_code_index
            name = self.ship_names[i]
            prop = self.partner_properties.get(name)
            if prop is None:
                continue

            img = self.mainManager.capture_window(None)
            real_rect = self.mainManager.from_percent_rect_get_real_rect(CAPTURE_RECT)
            cropped, _ = MyOpenCv.cut_picture_with_percent(img, CAPTURE_RECT)
            skip = True
            for j in range(10):
                temp_path = os.path.join(TEMPLATE_DIR, "%s-%d.png" % (name, j))
                if not os.path.exists(temp_path):
                    break
                temp_mat = MyOpenCv.cv_imread(temp_path)
                score, loc = MyOpenCv.match_single_score_and_pos(cropped, temp_mat)
                if score <= 0.8:
                    continue
                else:
                    skip = False
                    break
            if skip:
                continue
            re_loc = (real_rect.left + loc[0], real_rect.top + loc[1])
            save_x, save_y = self.my_dll.get_cursor_pos()  # 记下之前的鼠标位置
            self.mainManager.click_point_with_templates(temp_mat, re_loc, click=False)
            self.my_dll.send_mouse_down(False, 0)  # 先松开左键，防止上一次点击的技能始终激活
            time.sleep(0.01)
            self.my_dll.send_mouse_down(True, 1)  # 按一次右键保证，上一次激活的技能必定取消
            time.sleep(0.01)
            self.my_dll.send_mouse_down(False, 1)  # 按一次右键保证，上一次激活的技能必定取消
            time.sleep(0.01)
            self.my_dll.send_mouse_down(True, 0)  # 按住左键不放，保证技能始终激活
            time.sleep(0.3)
            self.cache_index = i  # 记住当前准备释放的技能，之后松开鼠标后才会真正开始记时
            self.my_dll.set_cursor_pos(save_x, save_y)  # 恢复之前的鼠标位置

            time.sleep(0.01)
        logger.debug("截图监控线程停止")

    def realtime_mouse_callback(self, pk: MyDllLib.HookPackage):
        if not pk.keyEventType:
            if pk.wParam == MyDllLib.WM_LBUTTONUP:
                self.pause = False
                i = self.cache_index
                if i < 0:
                    return True
                name = self.ship_names[i]
                prop = self.partner_properties.get(name)
                if prop.can_refresh:
                    # can_refresh=true: 直接刷新计时
                    self.skills_cd[i] = prop.max_skill_time
                    self.append_and_pop_show_member_index_if_larger_than_max_slot(i)
                    logger.debug("[%s] buff消失，刷新计时 %.1fs", name, prop.max_skill_time)
                else:
                    # can_refresh=false: 只有当前没有在计时才能开始新的计时
                    if self.skills_cd[i] <= 0:
                        self.skills_cd[i] = prop.max_skill_time
                        self.append_and_pop_show_member_index_if_larger_than_max_slot(i)
                        logger.debug("[%s] buff消失，开始计时 %.1fs", name, prop.max_skill_time)
                self.cache_index = -1
                return True
            elif pk.wParam == MyDllLib.WM_RBUTTONDOWN:
                self.cache_index = -1
        return False

    def user_key_code(self, key_code) -> bool:
        if key_code == MyDllLib.VK_OEM_3:  # ` 键
            self.screenshot_running = not self.screenshot_running
            self.key_code_index = 0
            self.__late_callback_signal.set()
            if self.screenshot_running:
                self.show_member_index = [i for i in range(self.member_len)]
                start_thread(self.screenshot_loop, ())
                self.main_app.show_text("BA监控已启动")
            else:
                self.skills_cd = [0.0] * self.member_len
                self.show_member_index.clear()
                self.main_app.show_text("BA监控已停止")
            return True
        elif key_code == ord("Q"):
            self.key_code_index = 0
            self.__late_callback_signal.set()
        elif key_code == ord("W"):
            self.key_code_index = 1
            self.__late_callback_signal.set()
        elif key_code == ord("E"):
            self.key_code_index = 2
            self.__late_callback_signal.set()
        elif key_code == ord("R"):
            self.key_code_index = 3
            self.__late_callback_signal.set()
        elif key_code == ord("D"):
            self.key_code_index = 4
            self.__late_callback_signal.set()
        elif key_code == ord("F"):
            self.key_code_index = 5
            self.__late_callback_signal.set()
        elif key_code == 27:
            self.key_code_index = -1
            self.__late_callback_signal.set()
        return False

    def get_default_names(self) -> List[str]:
        res = []
        for key in self.partner_properties.keys():
            res.append(key)
        return res


Y_POS_0 = 0.24
Y_DELTA = 0.085
PARTNER_SETTING = """
水花子^1^true^
妃咲^15^true^
泳装渚^26^true^
柯伊^25^true^
优香^25^true^
机爱^2^true^
铃莎^22^true^
日奈^10^true
瞬^30^true^
水星野^50^true^
"""


def main_loop(main_ui: MainUI):
    BAHelper(main_ui)


def main(patch_md5: str = None, patch_path: str = None):
    if patch_md5 is None or patch_md5 == auto_patch_python(None, patch_path=patch_path):
        auto_patch_python(globals(), patch_path="./角色buff冷却值配置.py")
        MainUI(main_loop).myloop()
        exit(0)
    else:
        time.sleep(1)
        print("等待正确的MD5 patch")


if __name__ == '__main__':
    main()
