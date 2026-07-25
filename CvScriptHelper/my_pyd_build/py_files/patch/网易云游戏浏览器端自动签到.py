from __future__ import annotations  # 使用高级注解器，

from typing import TypeVar, Callable, Dict, Tuple, List
import datetime
import os
import time
from PyTools.MyAwesomeTool.MyUtil import start_thread, auto_patch_python, build_logger, MyFileEditor

from PyTools.MyAwesomeTool.PyUseCPlus import MainUI, MyOpenCv, WinManager, MyDllLib, Rect
from PyTools.MyAwesomeTool.MyWebDriver import MyWebDriver

logger = build_logger(filename="./log.txt", name=__name__, use_to_debug=True, file_log_debug=False,
                      use_time_rotate=False)

ManyScriptArranger = TypeVar("ManyScriptArranger")


class ScriptToolBox:
    def __init__(self, main_app: MainUI):
        self.main_app = main_app
        self.cache_img = None
        self.my_dll = main_app.my_dll
        self.driver = MyWebDriver()
        time.sleep(1)
        self.driver.go_url()
        self.main_manager = WinManager(self.my_dll, "")
        self.manager = WinManager(self.my_dll, "网易云", False)
        self.manager.set_top(not self.main_app.Pause)
        self.last_py_code = auto_patch_python(globals())
        logger.debug("md5:%s", self.last_py_code)
        self.arranger = ManyScriptArranger(self)

        start_thread(self.script_loop, ())
        self.main_app.set_user_key_code_callback(self.key_code_callback)
        self.my_dll.register_event_hook(1, True)

    def script_loop(self):
        while True:
            if not self.main_app.Pause:
                self.arranger.script_entry_point()
                # try:
                #
                # except Exception as ep:
                #     logger.error("脚本发生致命错误: %s", ep)

            elif self.cache_img is not None:
                # rect = MyOpenCv.get_real_rect_by_percent_rect(self.cache_img, self.main_app.rect)
                # img2 = MyOpenCv.draw_rect(self.cache_img, rect)
                # img2 = MyOpenCv.show_single_match_pic(img, temp, score, loc)
                # self.main_app.show_image(img2, self.main_app.rect.__str__())
                time.sleep(1)

    def key_code_callback(self, key_code: int) -> bool:
        self.arranger.key_code_callback(key_code)
        if key_code == MyDllLib.VK_F1 + 3:
            new_md5 = auto_patch_python(None)
            if not new_md5.__eq__(self.last_py_code):
                self.last_py_code = auto_patch_python(globals())
                self.arranger = ManyScriptArranger(self)
            else:
                logger.debug("md5: (%s,%s)", new_md5, self.last_py_code)
            self.main_app.change_pause_mode()
            self.manager.set_foreground_window()
            self.manager.set_top(not self.main_app.Pause)
            self.main_app.set_top(self.main_app.Pause)
        return False


def main_loop(app: MainUI):
    def button_callback():
        driver = MyWebDriver()
        for ele in driver.get_cdp_dom_snapshot().find_nodes_by_attr("data-umami-event-source", "download"):
            print(ele.get_attr("data-resource-title"))

    app.set_simple_button_callback(button_callback)
    # ScriptToolBox(app)


def main(patch_md5: str = None, patch_path: str = None):
    if patch_md5 is None or patch_md5 == auto_patch_python(None, patch_path=patch_path):
        main_ui = MainUI(main_loop)
        main_ui.my_dll.register_event_hook(1, True)
        main_ui.myloop()
        exit(0)
    else:
        time.sleep(1)
        print("等待正确的MD5 patch")


if __name__ == '__main__':
    main()
    # MainUI(main_loop).myloop()
