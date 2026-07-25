import math
import random

import vgamepad
import time
from threading import Thread
from pygame import joystick, init, event
import tkinter as tk
import threading
from PyTools.MyAwesomeTool.PyUseCPlus import MyDllLib, start_thread, WinManager
from tkinter import simpledialog, messagebox, filedialog
import os.path
import threading

import psutil
import time
import subprocess
from datetime import datetime, timedelta

# 代码段编写者 bilibili：方块味的菠萝酱

# 定义所有的XBox360游戏手柄按键
UP = vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_UP
DOWN = vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_DOWN
LEFT = vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_LEFT
RIGHT = vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_DPAD_RIGHT

START = vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_START
BACK = vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_BACK
GUIDE = vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_GUIDE

LEFT_THUMB = vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_THUMB
RIGHT_THUMB = vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_THUMB
LEFT_SHOULDER = vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_LEFT_SHOULDER
RIGHT_SHOULDER = vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_RIGHT_SHOULDER

A = vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_A
B = vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_B
X = vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_X
Y = vgamepad.XUSB_BUTTON.XUSB_GAMEPAD_Y


# 定义DS4游戏手柄所有的按键
# NONE = vgamepad.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NONE
# NORTHWEST = vgamepad.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTHWEST
# WEST = vgamepad.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_WEST
# SOUTHWEST = vgamepad.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTHWEST
# SOUTH = vgamepad.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTH
# SOUTHEAST = vgamepad.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_SOUTHEAST
# EAST = vgamepad.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_EAST
# NORTHEAST = vgamepad.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTHEAST
# NORTH = vgamepad.DS4_DPAD_DIRECTIONS.DS4_BUTTON_DPAD_NORTH
#
# LEFT_THUMB = vgamepad.DS4_BUTTONS.DS4_BUTTON_THUMB_RIGHT
# RIGHT_THUMB = vgamepad.DS4_BUTTONS.DS4_BUTTON_THUMB_LEFT
# LEFT_SHOULDER = vgamepad.DS4_BUTTONS.DS4_BUTTON_SHOULDER_RIGHT
# RIGHT_SHOULDER = vgamepad.DS4_BUTTONS.DS4_BUTTON_SHOULDER_LEFT
#
# TRIANGLE = vgamepad.DS4_BUTTONS.DS4_BUTTON_TRIANGLE
# CIRCLE = vgamepad.DS4_BUTTONS.DS4_BUTTON_CIRCLE
# CROSS = vgamepad.DS4_BUTTONS.DS4_BUTTON_CROSS
# SQUARE = vgamepad.DS4_BUTTONS.DS4_BUTTON_SQUARE
#
# PS = vgamepad.DS4_SPECIAL_BUTTONS.DS4_SPECIAL_BUTTON_PS
# TOUCHPAD = vgamepad.DS4_SPECIAL_BUTTONS.DS4_SPECIAL_BUTTON_TOUCHPAD
#

class MyGamepadSimulator:
    def __init__(self):
        # 创建一个虚拟XBOX 360手柄
        self.gamepad = vgamepad.VX360Gamepad()
        self.fake_need_update = False

    def only_trigger(self, value, left=True):
        if left:
            self.gamepad.left_trigger_float(value)
        else:
            self.gamepad.right_trigger_float(value)
        # 左扳机轴 value改成0.0到1.0之间的浮点值

    def left_trigger(self, value):
        self.gamepad.left_trigger_float(value)
        # 左扳机轴 value改成0.0到1.0之间的浮点值
        self.update()

    def right_trigger(self, value):
        self.gamepad.right_trigger_float(value)
        # 右扳机轴 value改成0.0到1.0之间的浮点值
        self.update()

    def left_joystick(self, x_value, y_value):
        self.gamepad.left_joystick_float(x_value, y_value)
        # 左摇杆XY轴  x_values和y_values改成-1.0到1.0之间的浮点值
        # self.update()

    def right_joystick(self, x_value, y_value):
        self.gamepad.right_joystick_float(x_value, y_value)
        # 右摇杆XY轴  x_values和y_values改成-1.0到1.0之间的浮点值
        # self.update()

    def press_button(self, key_code):
        self.update_button(key_code, True)
        time.sleep(0.001)
        self.update_button(key_code, False)
        time.sleep(0.001)

    def only_update_button(self, key_code, pressed=True):
        if pressed:
            self.gamepad.press_button(key_code)
        else:
            self.gamepad.release_button(key_code)

    def update_button(self, key_code, pressed=True):
        self.only_update_button(key_code, pressed)
        self.update()

    def update(self):
        self.fake_need_update = True
        self.gamepad.update()

    def real_update(self):
        if self.fake_need_update:
            self.fake_need_update = False
            self.gamepad.update()

    def reset(self):
        self.gamepad.reset()  # 按键扳机摇杆全部重置成初始状态
        self.gamepad.update()


def check_process_exists(process_name, terminate=False):
    # 遍历系统中的所有进程，检查是否有指定名称的进程
    try:
        for proc in psutil.process_iter(['name']):
            if proc.info['name'].__contains__(process_name):
                if terminate:
                    proc.terminate()  # 终止进程
                return True
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        pass

    return False


def start_process(executable_path):
    # 使用subprocess启动进程
    # 使用 DETACHED_PROCESS 启动进程，保证 Python 脚本退出后进程仍在运行
    # subprocess.Popen([executable_path], creationflags=subprocess.CREATE_NEW_CONSOLE | subprocess.DETACHED_PROCESS,
    #                  close_fds=True)
    subprocess.Popen(f'start cmd /c {executable_path}', shell=True)


class MyD4KeyHelper:
    def __init__(self, my_dll: MyDllLib.MyDll):
        self.on_ctrl = False
        self.process_name = "pyd_main.exe"
        # executable_path =
        # "Z:/Computer/Program/Program_maker/python3/PyTools/CvScriptHelper/my_pyd_build/py_files/dist/pyd_main/pyd_main.exe"
        # 将此路径替换为实际的pyd_main.exe路径
        self.executable_path = os.path.abspath("./pyd_main.exe")
        self.myDll = my_dll
        self.myDll.register_event_hook(1, True)
        self.myDll.register_event_hook(0, True)
        self.key_event = threading.Event()
        self.key_event.clear()
        self.button_event = threading.Event()
        self.button_event.clear()
        self.keep_flash = False
        self.keep_click: bool = False
        self.mouse_down = -1
        self.use_large_switch = False
        self.myDll.set_py_hook_proc(self.key_hook_callback)
        start_thread(self.button_loop, ())
        start_thread(self.do_script_loop, ())

    def press_key(self, key_num):
        self.myDll.send_key_down(True, key_num)
        time.sleep(0.001)
        self.myDll.send_key_down(False, key_num)

    def button_loop(self):
        while True:
            self.button_event.wait()
            self.button_event.clear()
            time.sleep(1)  # 每隔1秒检测一次
            while self.keep_flash:
                self.press_key(ord("B"))
                time.sleep(0.01)

    def check_reboot_loop(self):
        while True:
            if not check_process_exists(self.process_name):
                print(f"{self.process_name} 未找到，正在启动...")
                start_process(self.executable_path)
            else:
                print(f"{datetime.now()}  {self.process_name} 正在运行中...")

            time.sleep(1)  # 每隔1秒检测一次

    def start_message_loop(self):

        self.myDll.message_loop()

    def do_script_loop(self):
        while True:

            self.key_event.wait()
            self.key_event.clear()
            while self.keep_click:
                # print("do_script")
                if self.mouse_down == 1:
                    self.myDll.send_key_down(True, ord("9"))
                    time.sleep(0.1)
                elif self.mouse_down == 0:
                    self.mouse_down = -1
                    self.myDll.send_key_down(False, ord("9"))
                    time.sleep(0.1)
                if self.mouse_down == 2:
                    self.myDll.send_key_down(False, ord("9"))
                    time.sleep(0.1)
                else:
                    # self.press_key(ord("A"))
                    self.press_key(ord("E"))
                    self.press_key(ord("Q"))
                    self.press_key(ord("W"))
                    self.press_key(ord("D"))
                    self.press_key(ord("R"))
                    self.press_key(ord("D"))
                    if self.use_large_switch:
                        self.press_key(ord("F"))

            time.sleep(0.001)

            # press_key(ord("N"))
            # press_key(win32con.VK_RETURN)
            #
            # press_key(win32con.VK_UP)
            #
            # press_key(win32con.VK_UP)
            #
            # press_key(win32con.VK_RETURN)
            # time.sleep(1)
            # press_key(win32con.VK_RETURN)
            # press_key(win32con.VK_RETURN)
            # time.sleep(0.5)
            # press_key(win32con.VK_RETURN)
            # press_key(win32con.VK_RETURN)
            # time.sleep(1)
            # press_key(ord("M"))
            # press_key(ord("M"))
            # press_key(ord("M"))

    def key_hook_callback(self, pk: MyDllLib.HookPackage):
        if pk.keyEventType == 0:
            if pk.wParam == MyDllLib.WM_LBUTTONDOWN:
                self.mouse_down = 1 if self.mouse_down == 0 else self.mouse_down
            elif pk.wParam == MyDllLib.WM_LBUTTONUP:
                self.mouse_down = 0 if self.mouse_down == 1 else self.mouse_down
            elif pk.wParam == MyDllLib.WM_RBUTTONUP:
                self.mouse_down = 0
            elif pk.wParam == MyDllLib.WM_RBUTTONDOWN:
                self.mouse_down = 2
        else:

            if pk.wParam == MyDllLib.WM_KEYDOWN:
                if pk.code == 162:  # ctrl
                    self.on_ctrl = True

                elif self.on_ctrl and pk.code == MyDllLib.VK_OEM_3:
                    check_process_exists(self.process_name, True)
                elif pk.code == MyDllLib.VK_OEM_3:
                    self.use_large_switch = not self.use_large_switch
                elif pk.code == 20:  # 大小写切换
                    self.keep_click = not self.keep_click
                    self.key_event.set()
                elif pk.code == ord(" "):
                    self.keep_flash = True
                    self.button_event.set()

            else:
                if pk.code == 162:  # ctrl
                    self.on_ctrl = False
                elif pk.code == ord(" "):
                    self.keep_flash = False
        return 0


class MyJoyListener(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title("my_title")
        self.geometry("800x600")

        # self.grid()
        label = tk.Label(self, text="一定注意!!!\n先启动此程序，再启动暗黑4，最后再插入手柄"
                                    "\n进入游戏后并按手柄A/B/X/Y任意键激活手柄代理"
                                    "\n启动顺序不对将造成功能异常!!!"
                                    "\n如果游戏内按键无反应，可以使用管理员身份运行本程序", anchor="w")
        label.config(font=("Arial", 12))
        label.pack(side=tk.TOP)
        # label.grid(row=1)
        self.button_list = [A, B, X, Y, LEFT_SHOULDER, RIGHT_SHOULDER, BACK, START, LEFT_THUMB, RIGHT_THUMB, GUIDE]
        self.button_map = {'UP': UP, 'DOWN': DOWN, 'LEFT': LEFT, 'RIGHT': RIGHT}
        self.simulator = MyGamepadSimulator()
        self.action_event = threading.Event()
        self.action_event.clear()
        self.button_event = threading.Event()
        self.button_event.clear()
        self.running = True
        self.prev_button_states = {}
        self.prev_axis_states = {}
        self.prev_pad_axis = (0, 0, 0, 0)
        self.keep_click = False
        self.is_player_moving = False
        self.ignore_click = False
        self.use_flash = False

        self.myDll = MyDllLib.MyDll()
        self.main_win = WinManager(self.myDll, "")
        self.mouse_x, self.mouse_y = self.main_win.get_rect().get_middle()
        print(self.mouse_x, self.mouse_y)
        self.radius = 100
        self.use_large_switch = False
        self.prev_mouse_pos = (None, None)
        messagebox.showwarning("",
                               "")
        self.joystick = None
        self.joy_list = []
        init()
        for i in range(joystick.get_count()):
            joy = joystick.Joystick(i)
            print(i, joy.get_name())
            if joy.get_name().__contains__(
                    "Xbox 360 Controller") and joy.get_guid() == '030003f05e0400008e02000000007200':
                joy.init()
                self.joy_list.append(joy)

        Thread(target=self.joystick_listener, daemon=True).start()
        Thread(target=self.action_loop, daemon=True).start()
        Thread(target=self.button_send_loop, daemon=True).start()
        self.d4keyboard = MyD4KeyHelper(self.myDll)

        #
        # self.action_loop()

    def press_key(self, key_num):
        self.myDll.send_key_down(True, key_num)
        time.sleep(0.001)

        self.myDll.send_key_down(False, key_num)
        # time.sleep(0.5)

    def inner_re_update_all(self, update_mode=1):
        if update_mode % 2 == 0:  # 被2整除，开启按钮热更新
            for key in self.prev_button_states.keys():
                if key == 0:
                    continue
                value = self.prev_button_states[key]
                self.simulator.only_update_button(self.button_list[key], value)

        if update_mode % 3 == 0:  # 被3整除，开启方向键热更新
            for key in self.button_map.keys():
                if self.prev_axis_states.__contains__(key):
                    value = self.prev_axis_states[key]
                    self.simulator.only_update_button(self.button_map[key], value)
        if update_mode % 5 == 0:  # 被5整除，开启触发器热更新
            for axis_idx in [4, 5]:
                if self.prev_axis_states.__contains__(axis_idx):
                    value = self.prev_axis_states[axis_idx]
                    if axis_idx == 4:
                        self.simulator.only_trigger(0.99 if value else -1.0, True)
                    elif axis_idx == 5:
                        self.simulator.only_trigger(0.99 if value else -1.0, False)

        # 默认会同步摇杆
        axis_x, axis_y, right_axis_x, right_axis_y = self.prev_pad_axis
        if not self.keep_click or self.ignore_click:  # 不能一直按摇杆否则会放不出技能
            self.simulator.left_joystick(axis_x, axis_y)
        self.simulator.right_joystick(right_axis_x, right_axis_y)

        self.simulator.update()

    def button_send_loop(self):

        while True:
            self.button_event.wait()
            self.button_event.clear()
            time.sleep(1)  # 长按超过1s了
            while self.use_flash:
                self.simulator.press_button(B)
                time.sleep(0.01)
            while self.ignore_click:  # 长按A 1秒后执行反复点击操作
                self.simulator.press_button(A)
                time.sleep(0.05)

    def listen_pad(self):
        right_axis_x = self.joystick.get_axis(2)
        right_axis_y = self.joystick.get_axis(3)

        axis_x = self.joystick.get_axis(0)
        axis_y = self.joystick.get_axis(1)

        self.prev_pad_axis = (axis_x, -axis_y, right_axis_x, -right_axis_y)
        self.is_player_moving = abs(axis_x) > 0.3 or abs(axis_y) > 0.3
        if abs(axis_x) > 0.5 or abs(axis_y) > 0.5:
            self.is_player_moving = True
            real_radius = self.radius * 3
            x_offset = real_radius * axis_x
            y_offset = real_radius * axis_y
            now_radius = math.sqrt(pow(x_offset, 2) + pow(y_offset, 2))
            if now_radius - real_radius > -10:

                target_x = self.mouse_x + x_offset
                target_y = self.mouse_y + y_offset
                prev_x, prev_y = self.prev_mouse_pos
                if prev_x is None or abs(target_x - prev_x) >= 1 or abs(target_y - prev_y) >= 1:
                    # print(target_x, target_y)
                    # self.myDll.set_cursor_pos(int(target_x), int(target_y))
                    self.prev_mouse_pos = (target_x, target_y)

        else:

            self.prev_mouse_pos = (None, None)

    def do_moving(self):
        axis_x, axis_y, right_axis_x, right_axis_y = self.prev_pad_axis
        if self.is_player_moving:  # 留点时间来执行移动指令
            self.simulator.left_joystick(axis_x, axis_y)
            self.simulator.update()
            time.sleep(0.015)

    def action_loop(self):
        while True:
            self.action_event.wait()
            self.action_event.clear()
            while self.keep_click:
                if self.ignore_click:
                    time.sleep(0.05)
                    self.simulator.press_button(A)
                    continue
                self.do_moving()  # 穿插移动指令，让角色调整朝向
                self.simulator.press_button(LEFT_SHOULDER)
                self.do_moving()  # 穿插移动指令，让角色调整朝向
                self.simulator.left_trigger(0.9999)
                time.sleep(0.01)
                self.simulator.left_trigger(-1)
                self.do_moving()  # 穿插移动指令，让角色调整朝向
                self.simulator.press_button(LEFT_THUMB)
                self.do_moving()  # 穿插移动指令，让角色调整朝向
                self.simulator.press_button(RIGHT_SHOULDER)
                self.do_moving()  # 穿插移动指令，让角色调整朝向
                self.simulator.press_button(X)
                self.do_moving()  # 穿插移动指令，让角色调整朝向
                self.simulator.right_trigger(0.9999)
                time.sleep(0.01)
                self.simulator.right_trigger(-1)
                self.do_moving()  # 穿插移动指令，让角色调整朝向
                self.simulator.press_button(X)

                if self.use_large_switch:
                    self.do_moving()  # 穿插移动指令，让角色调整朝向
                    self.simulator.press_button(Y)
                time.sleep(0.01)

                # self.press_key(ord("A"))
                # self.press_key(ord("E"))
                # self.press_key(ord("Q"))
                # self.press_key(ord("W"))
                # self.press_key(ord("D"))
                # self.press_key(ord("R"))
                # self.press_key(ord("D"))
                # if self.use_large_switch:
                #     self.press_key(ord("F"))
                # time.sleep(0.01)

    def check_direction_state(self, key_name, hats, hat_x, hat_y):
        if hats > 0:
            if key_name == "UP":
                return hat_y == 1
            if key_name == "DOWN":
                return hat_y == -1
            if key_name == "LEFT":
                return hat_x == -1
            if key_name == "RIGHT":
                return hat_x == 1
        else:
            axis_x = self.joystick.get_axis(0) if self.joystick.get_numaxes() > 0 else 0
            axis_y = self.joystick.get_axis(1) if self.joystick.get_numaxes() > 1 else 0
            if key_name == "UP":
                return axis_y < -0.5
            if key_name == "DOWN":
                return axis_y > 0.5
            if key_name == "LEFT":
                return axis_x < -0.5
            if key_name == "RIGHT":
                return axis_x > 0.5
        return False

    def joystick_listener(self):
        need_update = False
        while self.running:
            event.pump()

            if self.joystick:
                update_trigger = 1
                update_direction = 1
                update_button = 1
                for axis_idx in [2, 3]:  # LT 和 RT
                    prev_pressed = self.prev_axis_states.get(axis_idx, False)
                    degree = self.joystick.get_axis(axis_idx)
                    pressed = abs(degree) > 0.2
                    if pressed != prev_pressed:
                        self.prev_axis_states[axis_idx] = pressed
                        print("手柄摇杆", axis_idx, "被使用", "角度为", degree)
                        if axis_idx == 3 and pressed:
                            self.keep_click = degree < 0
                            self.action_event.set()
                            print("开启手柄宏脚本")
                        elif axis_idx == 2 and pressed:
                            self.use_large_switch = degree < 0

                for axis_idx in [4, 5]:  # LT 和 RT
                    prev_pressed = self.prev_axis_states.get(axis_idx, False)
                    degree = self.joystick.get_axis(axis_idx)
                    pressed = degree > 0.5
                    if pressed != prev_pressed:
                        self.prev_axis_states[axis_idx] = pressed
                        print("手柄触发器", axis_idx, "被使用", "角度为", degree)
                        update_trigger = 5

                hats = self.joystick.get_numhats()
                hat_x, hat_y = (0, 0)
                if hats > 0:
                    hat_x, hat_y = self.joystick.get_hat(0)

                for dir_key in ('UP', 'DOWN', 'LEFT', 'RIGHT'):
                    pressed = self.check_direction_state(dir_key, hats, hat_x, hat_y)
                    prev_pressed = self.prev_axis_states.get(dir_key, False)
                    if pressed != prev_pressed:
                        self.prev_axis_states[dir_key] = pressed
                        print("方向键", dir_key, "被按下" if pressed else "被抬起")
                        update_direction = 3

                button_states = {button_i: self.joystick.get_button(button_i) for button_i in
                                 range(self.joystick.get_numbuttons())}
                for button_i, pressed in button_states.items():
                    prev_pressed = self.prev_button_states.get(button_i, False)
                    if pressed != prev_pressed:
                        if button_i == 0:
                            self.simulator.reset()  # 不加这句话[整理储物箱]和[穿装备]的时候会将画面卡死
                            self.keep_click or self.button_event.set()
                            self.ignore_click = pressed
                            self.simulator.update_button(A, pressed)
                        elif button_i == 1:
                            self.button_event.set()
                            self.use_flash = pressed
                        self.prev_button_states[button_i] = pressed
                        print("手柄按键", button_i, "被按下" if pressed else "被抬起")
                        update_button = 2

                self.listen_pad()
                self.inner_re_update_all(update_trigger * update_button * update_direction)
                time.sleep(0.01)  # 不加这句 START按键会把 LT 和 RT 卡死，因为模拟信号有频率限制
                continue
            else:
                # self.simulator.press_button(A)  # 没有找到手柄时疯狂按A
                # time.sleep(0.01)
                for joy in self.joy_list:
                    button_states = {button_i: joy.get_button(button_i) for button_i in
                                     range(joy.get_numbuttons())}
                    for button_i, pressed in button_states.items():
                        if pressed:  # 真实手柄按B进行定位
                            self.joystick = joy
                            print("找到真实手柄")
                    time.sleep(0.01)  # 不加这句 START按键会把 LT 和 RT 卡死，因为模拟信号有频率限制


if __name__ == '__main__':
    app = MyJoyListener()
    app.mainloop()

    # del gamepad
    # print("虚拟手柄已销毁")

def hidden_import():
    import PyTools.MyAwesomeTool.MyDll as MyDllLib
    import PyTools.MyAwesomeTool.MyUtil
    import PyTools.MyAwesomeTool.MyTcpHelper
    import PyTools.MyAwesomeTool.PyUseCPlus
    import PyTools.MyAwesomeTool.MyProcessHelper
    import PyTools.MyAwesomeTool.MyLinkHelper