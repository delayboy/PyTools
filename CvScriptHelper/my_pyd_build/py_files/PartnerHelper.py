from __future__ import annotations  # 使用高级注解器，

import os.path
import random
import threading
import time
from typing import List, Dict, Tuple

import cv2
import numpy as np

from PyTools.MyAwesomeTool.PyUseCPlus import MyOpenCv, Rect, auto_patch_python
from PyTools.MyAwesomeTool.MyUtil import get_file_from_env_path, set_env_var, this_process
from PyTools.MyAwesomeTool.PyUseCPlus import WinManager, MainUI, MyDllLib, AndroidApp, start_thread, build_logger
from WebDriver import main_loop as cloud_main_loop
from LOLHelper import main_loop as lol_main_loop
from MyEasyOcr.train import MyOcrEngine

logger = build_logger(filename="log.log", name=__name__, use_to_debug=True, file_log_debug=True, use_time_rotate=False)
set_env_var("PATH", os.path.abspath("../../MyEasyOcr"))


class Property:
    def __init__(self, name: str, max_skill_time: float, ji_li_weapon: bool):
        self.name = name
        self.max_skill_time = max_skill_time
        self.ji_li_weapon = ji_li_weapon

    def __str__(self):
        return "%s %.2f %d" % (self.name, self.max_skill_time, self.ji_li_weapon)

    @staticmethod
    def get_partner_properties() -> Dict[str, Property]:
        res = {}
        for line in PARTNER_SETTING.split("\n"):
            tuples = line.split("^")
            if len(tuples) > 2:
                proper = Property(tuples[0], float(tuples[1]), tuples[2].__eq__("true"))
                logger.debug(proper.__str__())
                res[proper.name] = proper

        return res


class PartnerHelper:
    def __init__(self, main_app: MainUI):
        self.main_app = main_app
        self.mainManager = WinManager(self.main_app.my_dll, "")

        self.genShenManager = WinManager(self.main_app.my_dll, "原神", class_name="UnityWndClass")

        self.android_app = AndroidApp(True, ANDROID_DEVICE_NAME)
        self.main_app.set_user_key_code_callback(self.user_key_code)
        self.main_app.set_user_key_code_realtime_callback(self.user_realtime_key_code)
        self.ocr_engine = MyOcrEngine()
        self.partner_properties = Property.get_partner_properties()
        self.skills_cd = [0.0, 0.0, 0.0, 0.0, 0.0]
        self.now_index = 0
        self.rotation_limit = 0  # 帮助草神正好转一圈
        self.ship_names = self.get_default_names()
        self.isPartnerShipLocked = False
        self.auto_click = False
        self.on_buff = False
        self.fill_cd_flag = False
        self.exchange_partner_ship_flag = False
        self.pre_partner_index = 0
        self.keep_rotation = False
        self.last_fishing_mean = 50  # 上一次识别到的目标钓鱼位置
        rect = self.mainManager.get_rect()
        w, h = rect.get_size()
        t_hwnd = self.main_app.my_dll.create_transparent_window(rect.left, rect.top, w, h, self.paint_callback)
        self.drawManager = WinManager(self.main_app.my_dll, t_hwnd)
        self.skip_paint = False
        if self.genShenManager.hwnd == 0:
            self.genShenManager = WinManager(self.main_app.my_dll, "崩坏：星穹铁道", class_name="UnityWndClass")
            logger.debug(f"使用崩铁替代原神窗口: {self.genShenManager.hwnd}")
            self.skip_paint = True
        else:
            start_thread(self.record_gui_screen_loop, ())
            start_thread(self.skills_cd_loop, ())
            start_thread(self.ocr_loop, ())
        self.main_app.my_dll.register_event_hook(1, True)

    def paint_callback(self, hdc):
        pass
        if self.skip_paint:
            return
        for i in range(4):
            name = self.ship_names[i]
            text_color = (255, 255, 255) if i == self.now_index else (25, 25, 25)
            bk_color = (255, 0, 0) if self.skills_cd[i] > 0 else (0, 255, 0)
            div_str = ">" if self.isPartnerShipLocked else ":"
            y_pos = Y_POS_0 + i * Y_DELTA
            cd = self.skills_cd[i]
            if cd < 0.1:
                cd = 0
            show_text = "%.1f%s%s" % (cd, div_str, name)
            self.drawManager.draw_text(Rect(0.88, y_pos, 1, y_pos + 0.06), show_text, text_color, bk_color, hdc=hdc)
            self.buff_cd(name, text_color)

    def rotation_loop(self, loop_num=1, delay=0):
        if not self.keep_rotation:
            self.keep_rotation = True
        if delay > 0:
            time.sleep(delay)
        num = 0
        while self.keep_rotation:
            for i in range(10):
                self.genShenManager.simulate_mouse_movement()
                time.sleep(0.01)
            num += 1
            if num >= loop_num:
                break

    def clear_sills_cd(self):
        for i in range(4):
            self.skills_cd[i] = 0

        self.on_buff = False
        self.skills_cd[4] = 5

    def skills_cd_loop(self):
        while True:
            for i in range(len(self.skills_cd)):
                if self.skills_cd[i] > 0:
                    self.skills_cd[i] -= 0.1
            time.sleep(0.1)
            self.refresh()

    def ocr_loop(self):
        while True:
            if self.auto_click:
                self.isPartnerShipLocked = True
                # time.sleep(0.5)
                try:
                    self.go_fishing()
                except RuntimeError as e:
                    print("我接管了异常", e)

                continue

            now_index = self.select_now_index_match()
            self.now_index = now_index if now_index != -1 else self.now_index

            if self.fill_cd_flag:  # 按了E技能
                self.fill_cd_flag = False
                self.fill_now_partner_cd()  # 设置冷却值
                time.sleep(1)  # 延迟一段时间等待变化以便进行修正
                self.correct_skill_cd_with_ocr()

            if self.exchange_partner_ship_flag:  # 按了F来切换配对
                self.exchange_partner_ship_flag = False
                time.sleep(0.1)
                self.auto_exchange_partner_ship_with_ocr()

            for i in range(4):
                name = self.ship_names[i]
                if not name.__contains__("那维"):
                    continue

                if self.pre_partner_index != self.now_index:
                    if self.now_index == i:
                        self.skills_cd[4] = 10
                        logger.debug("那维-切换到前台")
                    elif self.pre_partner_index == i:
                        self.skills_cd[4] = 105 if self.on_buff else 5
                        logger.debug("那维-切换到后台")

                if self.skills_cd[4] <= 0:  # 如果计时归零时，在前台就取消buff，在后台就上buff
                    self.on_buff = (self.now_index != i)
                break
            if self.pre_partner_index != self.now_index:
                self.refresh()
            self.pre_partner_index = self.now_index
            time.sleep(0.02)

    def refresh(self):
        self.drawManager.refresh_window(Rect(0.88, Y_POS_0, 1, Y_POS_0 + 4 * Y_DELTA))

    def draw_loop(self):

        while True:
            if self.auto_click:
                self.isPartnerShipLocked = True
                time.sleep(0.5)
                continue
            # self.paint_callback(None)
            time.sleep(10)

    def buff_cd(self, name: str, text_color):
        if name.__contains__("那维"):
            bk_color = (0, 255, 0) if self.on_buff else (255, 0, 0)
            show_text = "%.1f%s%s" % (self.skills_cd[4], ":", name)

            self.drawManager.draw_text(Rect(0, 0, 0.12, 0.06), show_text, text_color, bk_color)

    def auto_find_ui_and_click(self, app: AndroidApp, img: np.ndarray, temp_path: str, threshold=0.8,
                               use_app_show_img=False, time_span=0.2) -> bool:
        temp_mat = MyOpenCv.cv_imread(temp_path)
        score, loc = MyOpenCv.match_single_score_and_pos(img, temp_mat)
        if score >= threshold:
            self.genShenManager.send_key_code(True, 164)  # alt
            time.sleep(0.1)
            self.genShenManager.click_point_with_templates(temp_mat, tuple(loc))
            time.sleep(0.1)
            self.genShenManager.send_key_code(False, 164)  # alt
            show_img = MyOpenCv.show_single_match_pic(img, temp_mat, score, tuple(loc))
            if use_app_show_img:
                app.show_image(show_img)
            time.sleep(time_span)
            return True
        return False

    def record_gui_screen_loop(self):
        if self.genShenManager.win_name.__contains__("铁道"):

            def callback(app: AndroidApp, img: np.ndarray):

                if self.auto_find_ui_and_click(app, img, "templates/星铁/再来一次.png", time_span=2):
                    pass
                elif self.auto_find_ui_and_click(app, img, "templates/星铁/零食.png"):
                    self.auto_find_ui_and_click(app, img, "templates/星铁/确认.png")
                    self.auto_find_ui_and_click(app, img, "templates/星铁/确认.png")
                    self.auto_find_ui_and_click(app, img, "templates/星铁/取消.png", time_span=2)
                    pass
                else:
                    pass
                    # click_number = [2, 3, 4]
                    # for i in click_number:
                    #     self.genShenManager.send_key_code(True, ord(str(i)))
                    #     time.sleep(0.01)
                    #     self.genShenManager.send_key_code(False, ord(str(i)))
                app.show_image(img)

                # time.sleep(0.1)  # fps

            self.android_app.play_screen_record_on_phone(self.genShenManager, callback)
        else:
            self.android_app.play_screen_record_on_phone(WinManager(self.main_app.my_dll, EXT_SCREEN_WIN_NAME, False))

    def user_realtime_key_code(self, pk: MyDllLib.HookPackage) -> bool:

        if not pk.keyEventType:
            if pk.wParam == 0x0201:  # WM_LBUTTONDOWN
                if self.main_app.on_ctrl:
                    start_thread(self.rotation_loop, (9999, 0))

            elif pk.wParam == 0x0202:  # WM_LBUTTONUP
                self.keep_rotation = False
            return False

        if pk.code == 69:  # E
            #  name = self.ship_names[self.now_index]
            if pk.wParam == MyDllLib.WM_KEYDOWN:

                if self.main_app.on_ctrl and not self.keep_rotation:  # 只触发一次
                    start_thread(self.rotation_loop, (2, 0.2))

            else:
                self.keep_rotation = False

        if pk.code == 162:  # ctrl
            if pk.wParam == MyDllLib.WM_KEYDOWN:
                if self.main_app.left_button_down:
                    start_thread(self.rotation_loop, (9999, 0))
            else:
                self.keep_rotation = False

        return False

    def user_key_code(self, key_code) -> bool:
        if key_code == MyDllLib.VK_F1:
            mai = WinManager(self.main_app.my_dll, "UnityEnvironment")

        if key_code == MyDllLib.VK_F1 + 3:
            img = self.mainManager.capture_window(None)
            self.main_app.show_image(img)
            for i in range(200):
                aim_path = 'TempCapture/tie_dao_capture{}.png'.format(i)
                if not os.path.exists(aim_path):
                    MyOpenCv.cv_im_write(aim_path, img)
                    break
            # img, _ = MyOpenCv.cut_picture_with_percent(img, Rect(0.36, 0.1, 0.64, 0.12))
        elif key_code == 70:  # F
            self.exchange_partner_ship_flag = True
            # self.mainManager.send_key_code(True, ord("A"))
            # time.sleep(0.25)
            # self.mainManager.send_key_code(False, ord("A"))
        elif key_code == 69:  # E
            time.sleep(0.2)
            self.fill_cd_flag = True

        elif key_code == 48:  # 0
            self.clear_sills_cd()
            # self.mainManager.send_key_code(True, ord("D"))
            # time.sleep(0.25)
            # self.mainManager.send_key_code(False, ord("D"))

        elif key_code == 0x28 or key_code == ord("R"):  # down  orR
            if self.auto_click or self.genShenManager.win_name.__contains__("铁道"):

                self.genShenManager.send_key_code(True, ord("1"))
                ch = random.randint(0, 3)
                if ch == 0:
                    self.genShenManager.click_point_with_wnd_percent(0.74, 0.72)
                elif ch == 3:
                    self.genShenManager.click_point_with_wnd_percent(0.91, 0.20)
                else:
                    self.genShenManager.click_point_with_wnd_percent(0.91, 0.65)
                self.genShenManager.send_key_code(False, ord("1"))
                return True
        elif key_code == MyDllLib.VK_OEM_3:
            self.auto_click = not self.auto_click
            if self.genShenManager.win_name.__contains__("铁道"):
                if self.auto_click:
                    start_thread(self.record_gui_screen_loop, ())
                else:
                    self.android_app.stop_record()
        elif key_code == 72:  # H
            self.isPartnerShipLocked = not self.isPartnerShipLocked
        elif 49 <= key_code <= 52:  # 1--4
            self.correct_skill_cd_with_ocr()

        return False

    def get_default_names(self) -> List[str]:
        res = []
        for key in self.partner_properties.keys():
            res.append(key)
            if len(res) >= 4:
                break

        return res

    def fill_now_partner_cd(self):
        now_index_save = self.now_index
        name = self.ship_names[now_index_save]
        logger.debug("记录角色[%s]的CD", name)
        p = self.partner_properties[name]
        if p.ji_li_weapon:
            self.skills_cd[now_index_save] = p.max_skill_time
        elif self.skills_cd[now_index_save] <= 0:
            self.skills_cd[now_index_save] = p.max_skill_time

    def auto_exchange_partner_ship_with_ocr(self):
        if self.genShenManager.hwnd <= 0 or self.isPartnerShipLocked:
            return
        w, h = self.genShenManager.get_rect().get_size()
        if w < 1000:
            logger.debug("Wrong YuanShen Windows Size!")
            return
        img = self.genShenManager.capture_window(None)
        w, h = MyOpenCv.get_image_size(img)
        if w < 1000:
            logger.debug("Wrong bmp Size!")
            return
        for row in range(4):
            partner_name = self.list_member_match(img, row)
            self.ship_names[row] = partner_name
        self.refresh()

    @staticmethod
    def cut_member_image(screen: np.ndarray, row: int = 0) -> np.ndarray:
        temp_start_h = 0.2038 + row * 0.088565
        img, _ = MyOpenCv.cut_picture_with_percent(screen, Rect(0.85677, temp_start_h, 0.91927, temp_start_h + 0.086))
        img = MyOpenCv.color_to_gray(img)
        img = MyOpenCv.threshold(img, 205, 255)
        return img

    def correct_skill_cd_with_ocr(self):
        now_index_save = self.now_index  # 缓存当前选中角色，防止多线程引起索引变动，放心，截图瞬间NowIndex来不及切换
        if self.skills_cd[now_index_save] > 0:  # 尝试修正当前计时
            cd = self.skill_cd_match()
            if cd >= -0.5:
                logger.debug("number_ocr_cd:%.2f", cd)
                self.skills_cd[now_index_save] = cd
        self.refresh()
        time.sleep(0.2)

    def skill_cd_match(self) -> float:
        if self.genShenManager.hwnd <= 0 or self.auto_click:
            return -1
        w, h = self.genShenManager.get_rect().get_size()
        if w < 1000:
            logger.debug("Wrong YuanShen Windows Size!")
            return -1

        rect = self.genShenManager.from_percent_rect_get_real_rect(Rect(0.80260, 0.8815, 0.908, 0.974))
        src_mat = self.genShenManager.capture_window(rect)
        # self.main_app.show_image(src_mat, "CD截图")
        temp_path = "templates/E.png"
        temp_mat = MyOpenCv.cv_imread(temp_path)
        score, point = MyOpenCv.match_single_score_and_pos(src_mat, temp_mat)
        if score > 0.9 and point[0] > 15 and point[1] > 51:
            x, y = (point[0] - 15, point[1] - 51)
            roi_rect = Rect(x, y, x + 50, y + 30)

            num_mat = MyOpenCv.cut_picture(src_mat, roi_rect)
            num_mat = MyOpenCv.color_to_gray(num_mat)
            num_mat = MyOpenCv.threshold(num_mat, 245, 255)
            v = self.number_ocr(num_mat.copy())
            # self.main_app.show_image(num_mat, "推断:%.2f" % v)
            return v

        else:
            return -1

    def number_ocr(self, num_mat: np.ndarray):
        ocr_cd = 0
        try:
            s_cd = self.ocr_engine.predict(num_mat)
            cd = int(s_cd)
            self.main_app.show_image(num_mat, s_cd + str(num_mat.shape))
            if cd > 0:
                ocr_cd = cd / 10.0
        except ValueError:
            ocr_cd = 0

        match_num_seq = [8, 9, 6, 3, 4, 5, 2, 7, 0, 1]
        max_score = 99
        threshold = 0.77
        round_num = 0
        tuples = (0, 0, 0)
        x_list = []
        num_list = []
        fill_black_rect = Rect(0, 0, 0, 0)
        while max_score >= threshold and round_num < 3:
            round_num += 1
            max_score = 0
            for i in range(10):
                now_num = match_num_seq[i]
                path = "templates/number/%d.png" % now_num
                temp_mat = MyOpenCv.cv_imread(path)
                score, loc = MyOpenCv.match_single_score_and_pos(num_mat, temp_mat)
                # logger.debug("match: (%d):(%.4f)", now_num, score)
                if score >= threshold and score > max_score:
                    max_score = score
                    w, h = MyOpenCv.get_image_size(temp_mat)
                    x, y = loc
                    fill_black_rect = Rect(x, y, x + w, y + h)
                    tuples = (loc[0], loc[1], now_num)

                    break
            if max_score >= threshold:
                num_mat = MyOpenCv.fill_black_to_src(num_mat, fill_black_rect)
                x_list.append(tuples[0])
                num_list.append(tuples[2])
                # logger.debug("get number:(%d)(%.4f)", tuples[2], max_score)

        x_list = np.array(x_list)
        num_list = np.array(num_list)
        index = x_list.argsort()
        num_list = num_list[index]
        k = 0.1
        sum_v = 0.0
        for num in reversed(num_list):
            sum_v += k * num
            k *= 10
        if abs(sum_v - ocr_cd) < 2:  # 两种ocr结果相近就输出，否则输出0
            return ocr_cd
        else:
            return -5
        # return sum_v

    def list_member_match(self, screen: np.ndarray, row: int = 0) -> str:
        src_mat = self.cut_member_image(screen, row)

        for key in self.partner_properties.keys():
            temp_path = "templates/partner/%s.png" % key
            if not os.path.exists(temp_path):
                continue
            temp_mat = MyOpenCv.cv_imread(temp_path)
            score, loc = MyOpenCv.match_single_score_and_pos(src_mat, temp_mat)
            logger.debug("(row:%d)(path:%s) score:(%.4f)", row, temp_path, score)
            if score > 0.8:
                return key

        # 如果没有匹配成功则保存当前截图分片，进行人工分析
        temp_path = "templates/partner/Unknown-Line-%d.png" % row
        if not os.path.exists(temp_path):
            MyOpenCv.cv_im_write(temp_path, src_mat)

        return self.ship_names[row]  # 找不到则不切换角色

    def check_whether_fish_is_coming(self, img: np.ndarray):
        text_img, _ = MyOpenCv.cut_picture_with_percent(img, Rect(0.44, 0.16, 0.54, 0.24))
        text_img = MyOpenCv.threshold(MyOpenCv.color_to_gray(text_img), 205, 255)  # RED channel only
        temp_mat = MyOpenCv.cv_imread("templates/鱼儿上勾啦.png")
        score, loc = MyOpenCv.match_single_score_and_pos(text_img, temp_mat)
        # logger.debug(f"钓鱼按钮:{score}")

        if score > 0.8:
            self.genShenManager.click_point_with_wnd_percent(0.5, 0.5)
            return

    def get_max_green_or_red(self, img_r_or_g: np.ndarray) -> int:
        where_is_green = np.argwhere(img_r_or_g[5, :]).flatten()
        where_is_green_min = 0 if len(where_is_green) < 1 else np.min(where_is_green)
        where_is_max_green = 0
        for i in range(where_is_green_min, len(where_is_green)):
            if i == where_is_green[i]:
                where_is_max_green = i
                continue
            else:
                break
        return where_is_max_green

    def go_fishing(self):
        w, h = self.genShenManager.get_rect().get_size()
        if w < 1000:  # 窗口尺寸不匹配
            return
        img = self.genShenManager.capture_window(None)
        if MyOpenCv.get_image_size(img)[0] < 1000:  # 截图尺寸不匹配
            return

        fishing_img, _ = MyOpenCv.cut_picture_with_percent(img, Rect(0.49, 0.12, 0.51, 0.175))
        fishing_img = MyOpenCv.threshold(MyOpenCv.color_to_gray(fishing_img), 205, 255)
        temp_mat = MyOpenCv.cv_imread("templates/正在钓鱼.png")
        score, loc = MyOpenCv.match_single_score_and_pos(fishing_img, temp_mat)

        if score < 0.8:  # 鱼还没上钩子
            # self.main_app.show_image(fishing_img, f"{score}")
            self.check_whether_fish_is_coming(img)
            time.sleep(0.5)
            return

        img, _ = MyOpenCv.cut_picture_with_percent(img, Rect(0.38, 0.1, 0.62, 0.12))
        img_r = MyOpenCv.threshold(MyOpenCv.color_to_gray(img[:, :, 2]), 200, 255)  # RED channel only
        img_g = MyOpenCv.threshold(MyOpenCv.color_to_gray(img[:, :, 1]), 200, 255)  # GREEN channel only

        # where_is_red_num = len(np.argwhere(img_r[5, :] > 200).flatten())  # 控制条中不应该有太多红色
        where_is_red = np.argwhere(img_r[12, :] > 200).flatten()
        # 如果红色太少，或绿色太少，无法识别出钓鱼目标点，则延用上一次识别到的目标点
        if len(where_is_red) < 10 or len(where_is_red) > 200:
            pass
        else:
            self.last_fishing_mean = np.mean(where_is_red)

        where_is_max_green = self.get_max_green_or_red(img_g)
        where_is_max_red = self.get_max_green_or_red(img_r)
        where_is_max_green = where_is_max_green if where_is_max_green > where_is_max_red else where_is_max_red

        # self.main_app.show_image(img, f"{score} {where_is_max_green} {self.last_fishing_mean}")

        if where_is_max_green < self.last_fishing_mean:  # 未到达游标处按键
            self.main_app.my_dll.send_mouse_down(True)
        else:  # 松键
            self.main_app.my_dll.send_mouse_down(False)

    def select_now_index_match(self):
        if self.genShenManager.hwnd <= 0 or self.auto_click:
            return -1
        w, h = self.genShenManager.get_rect().get_size()
        if w < 1000:
            return -1
        rect = self.genShenManager.from_percent_rect_get_real_rect(Rect(0.90208, 0.2389, 0.91719, 0.5352))
        step = (rect.bottom - rect.top) / 4.0
        # logger.debug(rect.__str__())
        src_mat = self.genShenManager.capture_window(None)
        src_mat, _ = MyOpenCv.cut_picture_with_percent(src_mat, Rect(0.90208, 0.2389, 0.91719, 0.5352))
        src_mat = MyOpenCv.color_to_gray(src_mat)
        src_mat = MyOpenCv.threshold(src_mat, 225, 255)
        temp_path = "templates/select.png"
        temp_mat = MyOpenCv.cv_imread(temp_path)
        score, loc = MyOpenCv.match_single_score_and_pos(src_mat, temp_mat)

        if score < 0.74:
            return -1
        for i in range(4):
            top = i * step
            bottom = top + step
            # log_str = "[%.2f,%d,%d][%.2f,%.2f]" % (score, loc[0], loc[1],top,bottom)
            # logger.debug(log_str)
            if top < loc[1] < bottom:
                # logger.debug("当前选中的角色为:%s %.2f", self.ship_names[i], score)
                # self.main_app.show_image(src_mat, "当前选中的角色为:%s" % self.ship_names[i])
                return i

        return -1


def test(main_ui: MainUI):
    img = MyOpenCv.cv_imread("整机截图2.png")

    if MyOpenCv.get_image_size(img)[0] < 1000:  # 截图尺寸不匹配
        return
    fishing_img, _ = MyOpenCv.cut_picture_with_percent(img, Rect(0.49, 0.14, 0.51, 0.175))
    fishing_img = MyOpenCv.threshold(MyOpenCv.color_to_gray(fishing_img), 205, 255)
    main_ui.show_image(fishing_img)
    temp_mat = MyOpenCv.cv_imread("templates/正在钓鱼.png")
    MyOpenCv.cv_im_write("正在钓鱼.png", fishing_img)
    score, loc = MyOpenCv.match_single_score_and_pos(fishing_img, temp_mat)
    # main_ui.show_image(fishing_img, f"{score}")

    text_img, _ = MyOpenCv.cut_picture_with_percent(img, Rect(0.44, 0.16, 0.54, 0.24))
    text_img = MyOpenCv.threshold(MyOpenCv.color_to_gray(text_img), 205, 255)  # RED channel only
    # MyOpenCv.cv_im_write("鱼儿上勾啦.png", text_img)
    temp_mat = MyOpenCv.cv_imread("templates/鱼儿上勾啦.png")
    score, loc = MyOpenCv.match_single_score_and_pos(text_img, temp_mat)

    img, _ = MyOpenCv.cut_picture_with_percent(img, Rect(0.38, 0.1, 0.62, 0.12))
    img_r = MyOpenCv.threshold(MyOpenCv.color_to_gray(img[:, :, 2]), 200, 255)  # RED channel only
    img_g = MyOpenCv.threshold(MyOpenCv.color_to_gray(img[:, :, 1]), 200, 255)  # GREEN channel only
    main_ui.show_image(img_g, f"{score}")
    where_is_red_num = len(np.argwhere(img_r[5, :] > 200).flatten())  # 控制条中不应该有太多红色
    where_is_red = np.argwhere(img_r[12, :] > 200).flatten()
    if where_is_red_num < 10 or len(where_is_red) < 10:  # 红色太少，未钓鱼所以退出
        time.sleep(0.5)
        return
    where_is_red_mean = np.mean(where_is_red)
    where_is_green = np.argwhere(img_g[5, :]).flatten()
    where_is_green_min = 0 if len(where_is_green) < 1 else np.min(where_is_green)

    where_is_max_green = 0
    for i in range(where_is_green_min, len(where_is_green)):
        if i == where_is_green[i]:
            where_is_max_green = i
            continue
        else:
            break

    print("1")


def main_loop(main_ui: MainUI):
    # test(main_ui)
    PartnerHelper(main_ui)


GAME_MODE = "GenShin"
Y_POS_0 = 0.24
Y_DELTA = 0.085
ANDROID_DEVICE_NAME = "QWBILZRGSW7XXCV4"
EXT_SCREEN_WIN_NAME = "python黑客工具箱"
PARTNER_SETTING = """
胡桃^16^false^
宵宫^18^false^
雷神^10^false^
草神^6^true^
夜兰^10^false^
神里^10^-false^
甘雨^10^false^
魈^10^false^
钟离^12^false^
辛炎^18^false^
迪奥娜^15^true^
温迪^6^true^
七七^30^false^
刻晴^7^false^
莫娜^12^false^
迪卢克^10^false^
琴^6^false^
砂糖^15^true^
重云^15^false^
女仆^24^false^
心海^20^false^
班尼特^5^false^
皇女^25^false^
那维^12^false^
凝光^12^false^
行秋^21^true^
北斗^8^false^
罗莎^6^false^
万叶^10^false^
香菱^12^false^
雷泽^10^false^
早柚^11^false^
九条^10^false^
芭芭拉^32^false^
"""


def main():
    auto_patch_python(globals(), patch_path="./settings.py")
    if GAME_MODE.__contains__("LOL"):
        MainUI(lol_main_loop).myloop()
    elif GAME_MODE.__contains__("Script"):
        MainUI(cloud_main_loop).myloop()
    else:
        MainUI(main_loop).myloop()


if __name__ == '__main__':
    main()
