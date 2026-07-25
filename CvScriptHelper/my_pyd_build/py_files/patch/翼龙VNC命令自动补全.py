# -*- coding: utf-8 -*-
import os.path
import threading
import time
import pyaudio
import soundfile
import cv2
import numpy as np
import win32clipboard
from PyTools.MyAwesomeTool.MyDll import HookPackage
import PyTools.MyAwesomeTool.MyDll as MyDll
from PyTools.MyAwesomeTool.PyUseCPlus import WinManager, start_thread, image_to_binary_arr, binary_arr_to_image, Rect, \
    MyOpenCv, AndroidApp
from PyTools.MyAwesomeTool.MyTcpHelper import TcpServer, TcpClient, TcpHandler, PackageHeader, TcpBase
from PyTools.MyAwesomeTool.MyUtil import auto_patch_python, MyFileEditor
from PIL import Image
import matplotlib.pyplot as plt
import locale
import uiautomation as auto
# 强制设置系统默认编码为UTF-8
import soundfile as sf
import pyaudio
import wave
import requests
from datetime import datetime, timedelta
import re
from pypinyin import lazy_pinyin, Style
import ctypes

auto.GetForegroundControl()
# 或者检查locale是否支持UTF-8
locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
USE_SERVER = False
USE_MAX_FUNC = False
VK_CAPITAL = 0x14


def is_caps_lock_on():
    try:
        # 仅适用于 Windows
        hll_dll = ctypes.WinDLL("User32.dll")

        return hll_dll.GetKeyState(VK_CAPITAL) & 0x0001 != 0
    except Exception as e:
        print(f"获取 Caps Lock 状态时出错: {e}")
        return False


class Speaker:
    def __init__(self):
        # 初始化PyAudio
        self.p_audio = pyaudio.PyAudio()
        input_device_name = "麦克风 (3- Realtek High Definition Audio(SST))"
        input_device_index = 0
        # 遍历音频设备
        for i in range(self.p_audio.get_device_count()):
            print(self.p_audio.get_device_info_by_index(i)["name"])
            if self.p_audio.get_device_info_by_index(i)["name"].__contains__(input_device_name):
                input_device_index = i
                break
        sample_width, channels, frame_rate = self.get_wave_arg("audio.wav")
        # 打开麦克风流
        self.stream = self.p_audio.open(
            format=self.p_audio.get_format_from_width(sample_width),
            channels=channels,
            rate=frame_rate,
            input=True,
            output=True,
            # input_device_index=input_device_index,
        )

        self.play_end = True
        self.playing_event = threading.Event()
        self.playing_event.set()

    # 指定要播放的.wav文件
    def play_wave(self, wav_file="output.wav"):
        self.playing_event.clear()
        self.play_end = False
        # 读取.wav文件的数据并播放到麦克风
        waveform, sample_rate = soundfile.read(wav_file)
        # 将音频去归一化从浮点型转回整型
        audio_data = (waveform * 32767).astype(np.int16)
        a = audio_data.tobytes()
        for i in range(0, len(a), 512):
            self.stream.write(a[i:i + 512])
            if self.play_end:
                break
        print("播放完毕")
        self.playing_event.set()

    # 打开.wav文件并读取其参数
    def get_wave_arg(self, wav_file="output.wav"):
        with wave.open(wav_file, 'rb') as wf:
            sample_width = wf.getsampwidth()
            channels = wf.getnchannels()
            frame_rate = wf.getframerate()
        return sample_width, channels, frame_rate

    def close_stream(self):
        # 关闭流和PyAudio
        self.stream.stop_stream()
        self.stream.close()
        self.p_audio.terminate()


def hai_you_str_format(intput_str: str) -> str:
    return intput_str
    if intput_str.__contains__("校园招聘统一考试") and intput_str.__contains__("分 )"):
        beg = end = 0
        if intput_str.__contains__("上一题"):
            beg = intput_str.index("分 )")
            end = intput_str.rindex("上一题")
        elif intput_str.__contains__("下一题"):
            beg = intput_str.index("分 )")
            end = intput_str.rindex("下一题")
        if end > beg:
            return intput_str[beg + len("分 )"):end]
    return intput_str


# 定义递归函数来枚举窗口中的所有控件
def enumerate_controls(text_list: list, control, mask: bool, depth=0):
    indent = '  ' * depth
    # 获取当前控件的 LegacyIAccessible.Name（如果有的话）
    # legacy_name = control.GetLegacyIAccessiblePattern().Name if control.GetLegacyIAccessiblePattern() else None
    print(f"{indent}控件类型: {control.ControlTypeName}, 名称: {control.Name}")
    text = f"{indent}控件类型: {control.ControlTypeName}, 名称: {control.Name},FrameWork: {control.FrameworkId},Class:{control.ClassName}"
    text = f"{control.Name}"
    if mask:
        if control.ControlTypeName.__eq__("TextControl"):
            text_list.append(text)
    else:
        text_list.append(text)
    # 递归遍历子控件
    for child in control.GetChildren():
        enumerate_controls(text_list, child, mask, depth + 1)


def copy_ui(mask: bool) -> str:
    # time.sleep(2)
    # 获取当前活动窗口
    current_window = auto.GetForegroundControl()

    # 打印窗口的标题和类型
    # print(f"窗口标题: {current_window.Name}, 窗口类型: {current_window.ControlTypeName}")
    t_list = []
    # 枚举当前窗口的所有控件
    enumerate_controls(t_list, current_window, mask)
    # print(t_list)
    res = ""
    for line in t_list:
        if not line == "":
            res += line + "\n"
    return res


def split_string(s, chunk_size):
    return [s[i:i + chunk_size] for i in range(0, len(s), chunk_size)]


def copy_to_clipboard(text_content):
    try:
        win32clipboard.OpenClipboard()
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(win32clipboard.CF_UNICODETEXT, text_content)
        win32clipboard.CloseClipboard()
    except Exception as e:
        print(e)


def get_from_clipboard() -> str:
    try:
        win32clipboard.OpenClipboard()
        clipboard_content = ""  # 确保剪贴板获取字符格式为utf-8格式
        if win32clipboard.IsClipboardFormatAvailable(win32clipboard.CF_UNICODETEXT):  # win32clipboard.CF_TEXT
            clipboard_content = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
        win32clipboard.CloseClipboard()
        return str(clipboard_content)
    except Exception as e:
        print(e)
        return ""


def convert_to_html(camel_case):
    return "<center>" + camel_case + "</center>"


def convert_to_underscore(camel_case):
    under_score = ""
    index = 0
    for char in camel_case:
        if char.isupper():
            if index == 0:
                under_score += char.lower()
            else:
                under_score += "_" + char.lower()
        else:
            under_score += char
        index += 1
    return under_score


def copy_and_paste_script(m_dll: MyDll.MyDll):
    # m_dll.send_key_down(True, 162)  # ctrl
    m_dll.send_key_down(True, 67)
    time.sleep(0.02)
    m_dll.send_key_down(False, 67)
    g_camel_case = get_from_clipboard()
    underscore = convert_to_underscore(g_camel_case)
    print("转换为下划线命名法：", underscore)
    copy_to_clipboard(underscore)
    m_dll.send_key_down(True, 86)
    time.sleep(0.02)
    m_dll.send_key_down(False, 86)
    # m_dll.send_key_down(False, 162) 并不需要松开和按下ctrl这个过程用户帮做完了


def custom_sort_key(item):
    y = item[0][0][1]
    x = item[0][0][0]
    # 将 x[0][0] 向下取整到每 10 的倍数，认为是“相等”的范围，因此如果差异在 -10 到 +10 之间，结果被视为相等。
    normalized_y = round(y / 10)  # round(y / 10)  # * 5
    return normalized_y, x  # 优先按左上角Y坐标排序，其次按横坐标排


class TransparentMainUI:
    def __init__(self):
        self.option_code = '0'
        self.rect = Rect(0, 0, 0, 0)
        self.capture_stage = 0
        self.__img = None
        self.__late_callback_signal = threading.Event()
        self.my_dll: MyDll = MyDll.MyDll()
        self.on_click_loop = False
        self.pre_click_hour = -1
        self.sp = Speaker()
        self.mainManager = WinManager(self.my_dll, "")

        rect = self.mainManager.get_rect().to_array()
        w, h = rect.get_size()
        self.drawManager = None
        # if USE_MAX_FUNC or not USE_SERVER:
        t_hwnd = self.my_dll.create_transparent_window(rect.left, rect.top, w, h, self.paint_callback)
        self.drawManager = WinManager(self.my_dll, t_hwnd)
        start_thread(self.async_hook_callback, ())
        self.my_dll.set_py_hook_proc(self.real_time_hook_callback)
        # self.my_dll.register_event_hook(0, True)
        self.my_dll.register_event_hook(1, True)

    def record_gui_screen_loop(self):
        if self.android_app.isRun:
            self.android_app.stop_record()
            return

        def callback(app: AndroidApp, img: np.ndarray):
            if self.tcp_engine.is_connect():
                self.tcp_engine.send_array(image_to_binary_arr(img), code=2)
            else:
                app.isRun = False
            # time.sleep(0.1)  # fps

        self.android_app.play_screen_record_on_phone(
            WinManager(self.my_dll, "python黑客工具"), callback)

    def auto_find_ui_and_click(self, img: np.ndarray, temp_path: str, threshold=0.8,
                               time_span=0.2, click=False) -> bool:
        temp_mat = MyOpenCv.cv_imread(temp_path)

        score, loc = MyOpenCv.match_single_score_and_pos(img, temp_mat)
        if score >= threshold:
            if click:
                self.mainManager.click_point_with_templates(temp_mat, tuple(loc))
                time.sleep(time_span)
            return True
        return False

    def recv_callback(self, question):
        self.my_dll.send_key(question)
        self.option_code = 'send_char_and_type'
        copy_to_clipboard(question)
        self.__late_callback_signal.set()

    def refresh_window(self):
        if self.drawManager is not None:
            self.drawManager.refresh_window(None)

    def click_loop(self):
        while self.on_click_loop:
            now = datetime.now()

            temp_mat = MyOpenCv.cv_imread("OCR截图临时保存.png")
            img = self.mainManager.capture_window(None)
            score, loc = MyOpenCv.match_single_score_and_pos(img, temp_mat)
            try:
                res = requests.request(url="https://www.baidu.com", method="get")
                is_connect = res.status_code == 200
            except Exception as e:
                is_connect = False

            if score < 0.95 or not is_connect:
                print("钉钉页面异常报警")
                self.sp.play_wave()
            else:
                print("上次填表时间为：", now.hour, "脚本执行中", now)

                if not now.hour == self.pre_click_hour:
                    print("时间更新执行填表脚本")
                    self.pre_click_hour = now.hour
                    self.my_dll.send_key_down(True, 39)
                    time.sleep(0.5)
                    self.my_dll.send_key_down(False, 39)
                    self.my_dll.send_key("无异常")
                    time.sleep(0.5)
                    self.my_dll.send_key_down(True, 39)  # left
                    time.sleep(0.5)
                    self.my_dll.send_key_down(False, 39)
                    self.my_dll.send_key("赵云浩")
                    time.sleep(0.5)
                    self.my_dll.send_key_down(True, 162)  # left
                    time.sleep(0.1)
                    self.my_dll.send_key_down(True, ord("S"))  # left
                    time.sleep(0.1)
                    self.my_dll.send_key_down(False, ord("S"))  # left
                    time.sleep(0.1)
                    self.my_dll.send_key_down(False, 162)
            time.sleep(5)

    def paint_callback(self, hdc):
        if self.drawManager is None:
            return
        if self.on_click_loop:
            bk_color = (0, 255, 0)
            cur_x, cur_y = self.my_dll.get_cursor_pos()
            self.drawManager.draw_rect(Rect(cur_x + 5, cur_y, cur_x + 5 + 5, cur_y + 5), bk_color, hdc)

        else:
            self.drawManager.clear_draw(hdc)

    @staticmethod
    def needs_shift_detailed(char):
        # 美式键盘布局中需要Shift键的字符映射
        # 键: 正常按键, 值: 需要Shift时输出的字符
        keyboard_layout = {
            '`': '~', '1': '!', '2': '@', '3': '#', '4': '$', '5': '%',
            '6': '^', '7': '&', '8': '*', '9': '(', '0': ')', '-': '_',
            '=': '+', '[': '{', ']': '}', '\\': '|', ';': ':', "'": '"',
            ',': '<', '.': '>', '/': '?'
        }

        # 检查字符是否在需要Shift的符号中
        return char in keyboard_layout.values()

    @staticmethod
    def is_chinese_char(text):

        chinese_regex = re.compile(u'[\u4e00-\u9fff]')
        return chinese_regex.search(text) is not None

    @staticmethod
    def chinese_to_pinyin(chinese_char):
        # 单个字符
        result = lazy_pinyin(chinese_char, style=Style.NORMAL)
        return result[0].capitalize() if result else ""

    def sub_send_key(self, input_str: str):
        time.sleep(0.01)
        if is_caps_lock_on():
            self.mainManager.send_key_code(True, 20)
            time.sleep(0.01)
            self.mainManager.send_key_code(False, 20)
            time.sleep(0.01)
        for c in input_str:
            if not self.on_click_loop:
                break
            if self.needs_shift_detailed(c):
                self.mainManager.send_key_code(True, 160)
                time.sleep(0.01)
                self.my_dll.send_key(c)
                time.sleep(0.01)
                self.mainManager.send_key_code(False, 160)
                time.sleep(0.01)
            # 如果是大写字母，需要Shift
            elif c.isalpha() and c.isupper():
                self.mainManager.send_key_code(True, 160)
                time.sleep(0.01)
                self.my_dll.send_key(c)
                time.sleep(0.01)
                self.mainManager.send_key_code(False, 160)
                time.sleep(0.01)
            elif c.__eq__("\n"):
                self.mainManager.send_key_code(True, 13)
                time.sleep(0.01)
                self.mainManager.send_key_code(False, 13)
            elif self.is_chinese_char(c):
                self.sub_send_key(self.chinese_to_pinyin(c))
            else:
                self.my_dll.send_key(c)
                time.sleep(0.01)

    def send_key_with_simulate_shift(self):
        all_str = get_from_clipboard()
        self.sub_send_key(all_str)

    def async_hook_callback(self):
        while True:
            self.__late_callback_signal.clear()
            self.__late_callback_signal.wait()
            if self.on_click_loop:
                self.send_key_with_simulate_shift()
            # o = self.option_code

            # if self.on_click_loop:
            #     self.on_click_loop = False
            # else:
            #     print("start loop")
            #     self.on_click_loop = True
            #     start_thread(self.click_loop,())

    def real_time_hook_callback(self, pk: HookPackage) -> int:
        print(pk.code)
        if pk.wParam == MyDll.WM_KEYUP:
            if pk.code == 20:  # MyDll.VK_F1
                self.option_code = 'begin_loop'
                self.__late_callback_signal.set()
        elif pk.wParam == MyDll.WM_KEYDOWN:
            if pk.code == 27: # esc
                self.on_click_loop = not self.on_click_loop
                self.refresh_window()

        return 1

    def loop(self):
        self.my_dll.message_loop()


def main(patch_md5: str, patch_path: str):
    if patch_md5 is None or patch_md5 == auto_patch_python(None, patch_path=patch_path):
        print("111")
        if patch_md5 is not None and USE_SERVER and USE_MAX_FUNC:
            pass
            from PyTools.MyAwesomeTool.KeDaSoundToText import ke_da_main
            start_thread(ke_da_main, ())
        TransparentMainUI().loop()
        exit(0)
    else:
        time.sleep(1)
        print("等待正确的MD5 patch")

# if __name__ == '__main__':
#     TransparentMainUI().loop()
