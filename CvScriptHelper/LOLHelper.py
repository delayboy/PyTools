from __future__ import annotations  # 使用高级注解器，
from PyTools.MyAwesomeTool.MyUtil import start_thread, auto_patch_python, build_logger

from PyTools.MyAwesomeTool.PyUseCPlus import MainUI, MyOpenCv, WinManager, MyDllLib, Rect
import time
import random


class LOLBox:
    def __init__(self, main_app: MainUI):
        self.main_app = main_app
        self.cache_img = None
        self.my_dll = main_app.my_dll
        self.main_app.set_user_key_code_callback(self.key_code_callback)

    def key_code_callback(self, key_code: int) -> bool:
        r0 = random.uniform(0.025, 0.121)
        r1 = random.uniform(0.009, 0.023)
        r2 = random.uniform(0.121, 0.184)
        r3 = random.uniform(0.003, 0.015)
        r4 = random.uniform(0, 1)

        time.sleep(r0)
        if key_code == 220:  # \
            self.my_dll.send_key_down(True, 87)  # w
            time.sleep(r1)
            self.my_dll.send_key_down(True, 81)  # q
            time.sleep(r2)
            if r4 > 0.5:
                self.my_dll.send_key_down(False, 81)  # q
                time.sleep(r3)
                self.my_dll.send_key_down(False, 87)  # w
            else:
                self.my_dll.send_key_down(False, 81)  # w
                time.sleep(r3)
                self.my_dll.send_key_down(False, 87)  # q

            print("宏")
        return False


def main_loop(app: MainUI):
    LOLBox(app)
