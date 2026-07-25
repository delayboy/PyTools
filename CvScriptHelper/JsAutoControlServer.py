from __future__ import annotations  # 使用高级注解器，

from typing import TypeVar, Callable, Dict, Tuple, List
import datetime
import os
import time
import base64
import numpy as np
import cv2
import pdb
import win32clipboard
from PyTools.MyAwesomeTool.MyUtil import start_thread, auto_patch_python, build_logger, MyFileEditor

from PyTools.MyAwesomeTool.PyUseCPlus import MainUI, MyOpenCv, WinManager, MyDllLib, Rect
from PyTools.MyAwesomeTool.MyWebSocketServer import WebSocketHandler, start_websocket_server_loop

logger = build_logger(filename="./log.txt", name=__name__, use_to_debug=True, file_log_debug=False,
                      use_time_rotate=False)


class JsAutoControlServer:
    def __init__(self, app: MainUI):
        self.manager = WinManager(app.my_dll, "")
        self.main_app = app
        self.main_app.set_user_key_code_callback(self.key_code_callback)
        self.temp_file_path = os.path.abspath("./templates") + "/"  # 获取临时文件夹在电脑上的绝对路径
        app.my_dll.register_event_hook(1, True)

    def default_action_route(self, src_mat: np.ndarray, temp: np.ndarray, loc: tuple, action_alias_name: str):
        self.manager.click_point_with_templates(temp, loc)

    @staticmethod
    def __default_final_exit(is_final=True):
        if is_final:
            raise OverflowError("满足条件就退出")

    def _match_sub_pos_and_do(self, temp_path: str, src_mat: np.ndarray, percent_rect: Rect, threshold: float = 0.85,
                              sleep_time: int = 1,
                              is_final: bool = False,
                              call_back: Callable[[np.ndarray, Tuple[float, float], str], None] = None,
                              action_alias_name: str = None) -> bool:
        if call_back is None:
            call_back = self.default_action_route
        if action_alias_name is None:
            action_alias_name = temp_path
        if percent_rect.right > 1 or percent_rect.left > 1 or percent_rect.top > 1 or percent_rect.bottom > 1:
            rect = percent_rect
            src_sub_mat = MyOpenCv.cut_picture(src_mat, rect)
            MyOpenCv.cv_im_write("剪裁后的.png", src_sub_mat)
        else:
            src_sub_mat, rect = MyOpenCv.cut_picture_with_percent(src_mat, percent_rect)

        temp = MyOpenCv.cv_imread(self.temp_file_path + temp_path, cv2.IMREAD_UNCHANGED)
        score, loc = MyOpenCv.match_single_score_and_pos(src_sub_mat, temp)
        loc = (loc[0] + int(rect.left), loc[1] + int(rect.top))
        logger.debug(rect.__str__())
        img = MyOpenCv.draw_rect(src_mat, rect)
        img = MyOpenCv.show_single_match_pic(img, temp, score, loc)
        now = datetime.datetime.now()
        large_than = '>' if score > threshold else '<'
        log_text = "[%s]--[%.2f %s %.2f]--%s" % (now, score, large_than, threshold, action_alias_name)
        logger.debug(log_text)
        self.main_app.show_image(img, log_text)
        if score > threshold:
            # self.vmManager.clickPointWithTemplates(temp, loc, 0.5, 0.5)
            call_back(src_mat, temp, loc, action_alias_name)
            time.sleep(sleep_time)
            self.__default_final_exit(is_final)
            return True
        return False

    def _match_pos_and_do(self, temp_path: str, src_mat: np.ndarray, threshold: float = 0.85, sleep_time: int = 1,
                          is_final: bool = False,
                          call_back: Callable[[np.ndarray, Tuple[float, float], str], None] = None,
                          action_alias_name: str = None) -> bool:

        return self._match_sub_pos_and_do(temp_path, src_mat, Rect(0, 0, 1, 1), threshold, sleep_time, is_final,
                                          call_back, action_alias_name)

    @staticmethod
    def copy_to_clipboard(text_content):
        try:
            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text_content)
            win32clipboard.CloseClipboard()
        except Exception as e:
            print(e)

    def paste_str(self):
        self.manager.send_key_code(True, 162)  # 先取消ctrl
        time.sleep(0.01)
        self.manager.send_key_code(True, ord("A"))  # A
        time.sleep(0.01)
        self.manager.send_key_code(False, ord("A"))  # A
        time.sleep(0.01)
        self.manager.send_key_code(True, 8)  # back
        time.sleep(0.01)
        self.manager.send_key_code(False, 8)
        time.sleep(0.01)
        self.manager.send_key_code(True, ord("V"))  # V
        time.sleep(0.01)
        self.manager.send_key_code(False, ord("V"))  # V
        time.sleep(0.01)
        self.manager.send_key_code(False, 162)  # 先取消ctrl
        time.sleep(0.5)

    def script_entry_point(self, aim_url: str = "目标url"):
        try:
            self.manager.click_point_with_wnd_percent(0.4, 0.4)
            self.copy_to_clipboard(aim_url)
            self.paste_str()

            img = self.manager.capture_window(None)
            self._match_pos_and_do("youtube视频下载搜索按钮.png", img)
            time.sleep(0.5)

            img = self.manager.capture_window(None)
            while not self._match_pos_and_do("youtube视频文件夹预览按钮.png", img):
                img = self.manager.capture_window(None)
                time.sleep(1)

            time.sleep(2)

            self.copy_to_clipboard("C:\\Users\\Benson\\Downloads\\qfsm")
            self.paste_str()

            img = self.manager.capture_window(None)
            self._match_pos_and_do("youtube视频选择文件夹按钮.png", img)
            time.sleep(0.5)

            img = self.manager.capture_window(None)
            self._match_pos_and_do("youtube视频确认可编辑文件夹按钮.png", img)
            time.sleep(0.5)

        except OverflowError:
            pass

    def script_loop(self):
        while True:
            if not self.main_app.Pause:
                self.script_entry_point()
            else:
                time.sleep(1)

    def key_code_callback(self, key_code: int) -> bool:
        print("call")
        if key_code == MyDllLib.VK_OEM_3:
            self.main_app.change_pause_mode()
            self.script_entry_point()
        return False


class JsAutoControlServerHandler(WebSocketHandler):
    def __init__(self, application, request, **kwargs):
        super().__init__(application, request, **kwargs)
        self.js_auto_server: JsAutoControlServer = self.extra_param

    def on_message(self, message):
        print(f"Received message: {message}")
        self.js_auto_server.script_entry_point(message)
        self.write_message("python say hello")


def main_loop(app: MainUI):
    server = JsAutoControlServer(app)
    start_thread(start_websocket_server_loop, (JsAutoControlServerHandler, server))


if __name__ == '__main__':
    # driver = MyWebDriver()
    # driver.go_url("https://chatgpt.com/")
    # w = input()
    # driver.gpt_prompt()
    MainUI(main_loop).myloop()

# 现在您可以使用driver进行网页操作
