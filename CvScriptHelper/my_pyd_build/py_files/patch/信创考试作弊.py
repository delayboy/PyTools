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
import easyocr

auto.GetForegroundControl()
# 或者检查locale是否支持UTF-8
locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
USE_SERVER = False
USE_MAX_FUNC = False


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


class RecordTcpClientHandler(TcpHandler):
    def __init__(self, gpt_client, my_dll: MyDll.MyDll, recv_callback):
        super().__init__()
        self.gpt_client = gpt_client

        self.my_dll = my_dll
        self.recv_callback = recv_callback

    def callback(self, tcp_base: TcpClient, pk: PackageHeader) -> str:
        print('阿里云听写:', pk.get_str_data())
        question = pk.get_str_data()
        # query_dic = {'query': question, 'history': [], 'max_length': 512, 'top_p': 0.98, 'temperature': 0.9}
        # self.gpt_client.send_str(json.dumps(query_dic, ensure_ascii=False))
        # self.gpt_client.gpt_prompt(question)

        self.recv_callback(question)


class AudioRecorder:

    def __init__(self, my_dll: MyDll.MyDll, recv_callback):
        # 参数设置
        self.on_ctrl = False
        self.chunk_size = 1024  # 每个音频段的大小
        self.sample_format = pyaudio.paInt16
        self.channels = 1
        self.sample_rate = 16000
        self.record_seconds = 30  # 音频录制时长
        self.output_file = "output.wav"
        self.recv_callback = recv_callback
        # self.speaker = Speaker()
        # self.gpt_client = TcpClient(GptTcpClientHandler(self.speaker), server_po`rt=5454)
        self.gpt_client = None  # MyWebDriver()
        # self.gpt_client.go_url("https://chatgpt.com/")
        self.client = None
        self.record_speaker = False
        if USE_SERVER and USE_MAX_FUNC:
            self.client = TcpClient(RecordTcpClientHandler(self.gpt_client, my_dll, self.recv_callback), "127.0.0.1",
                                    5454, keep_alive=True)  # , 'gpt.delayboy.cn', 5353
        self.is_record_event = threading.Event()
        self.is_record_event.set()
        # self.model = whisper.load_model("./whisper_model/medium.pt")  # args.whisper_size
        # print("whisper load finish")
        self.is_record = False

    def cal_silence_time(self, times: int):
        return times / self.sample_rate * self.chunk_size

    def do_record(self, speaker=False):
        if self.is_record:
            self.is_record = False
            time.sleep(0.5)
            return
        self.is_record = True
        self.record_speaker = speaker
        if self.client is None:
            return

        self.is_record_event.wait()  # 如果没在录制，则等待上一次录制结束
        start_thread(self.start_record, (speaker,))

    def start_record(self, speaker=False):
        self.is_record = True
        self.is_record_event.clear()
        # 初始化PyAudio
        audio = pyaudio.PyAudio()

        # 获取可用的输入设备列表，找到扬声器设备
        # for i in range(audio.get_device_count()):
        #     device_info = audio.get_device_info_by_index(i)
        #     print(f"设备索引: {i}, 设备名: {device_info['name']}, 输入通道数: {device_info['maxInputChannels']}")
        # audio.get_default_input_device_info()
        speaker_index = None
        device_name = "麦克风 (1080P"
        if speaker:
            device_name = "立体声混音"
        for i in range(audio.get_device_count()):
            device_info = audio.get_device_info_by_index(i)
            if device_info['name'].__contains__("Dubbing"):
                continue
            if device_info['name'].__contains__(device_name):
                speaker_index = i
                break
        # 打开麦克风流
        stream = audio.open(format=self.sample_format, channels=self.channels,
                            rate=self.sample_rate, input=True, input_device_index=speaker_index,
                            frames_per_buffer=self.chunk_size)
        # 初始化存储音频段的列表
        audio_segments = []

        print("录制中...")
        silence_time = 0
        for _ in range(0, int(self.sample_rate / self.chunk_size * self.record_seconds)):
            data = stream.read(self.chunk_size)  # 读取音频数据
            audio_data = np.frombuffer(data, dtype=np.int16)  # 转换为numpy.ndarray
            amplitude = np.max(np.abs(audio_data))
            if amplitude < 800:
                silence_time += 1
            else:
                silence_time = 0

            # print(amplitude)
            self.client.send_array(audio_data)
            audio_segments.append(audio_data)
            # print(audio_segments.__len__())
            # if self.cal_silence_time(silence_time) >= 0.02 and audio_segments.__len__() > 2:
            #     audio_segments.clear()
            #     self.client.send_array(np.array([]), -1)
            if self.cal_silence_time(silence_time) >= 1 or not self.is_record:  #
                break

        self.client.send_array(np.array([]), -1)
        # print("录制完成")
        # 关闭音频流
        stream.stop_stream()
        stream.close()

        # 关闭PyAudio
        audio.terminate()

        # 合并所有音频段
        merged_audio = np.concatenate(audio_segments)
        # options = dict(beam_size=5, best_of=5)
        # transcribe_options = dict(task="transcribe", **options)
        # merged_audio = merged_audio.astype(np.float32) / 32768.0
        # result = self.model.transcribe(merged_audio, word_timestamps=True, initial_prompt="以下是普通话的句子。",
        #                                **transcribe_options)
        # print(result)
        self.is_record_event.set()
        self.is_record = False

    def save_wav(self, merged_audio):
        # 保存为.wav文件
        # with wave.open(output_file, 'wb') as wf:
        #     wf.setnchannels(channels)
        #     wf.setsampwidth(audio.get_sample_size(sample_format))
        #     wf.setframerate(sample_rate)
        #     wf.writeframes(merged_audio.tobytes())

        soundfile.write(self.output_file, merged_audio, self.sample_rate)
        print(f"音频已保存为 {self.output_file}")


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
        self.on_ctrl = False
        self.on_alt = False
        self.on_shift = False
        self.option_code = '0'
        self.cur_x = 0
        self.cur_y = 0
        self.rect = Rect(0, 0, 0, 0)
        self.capture_stage = 0
        self.__img = None
        self.__late_callback_signal = threading.Event()
        self.tcp_handler = DefaultTcpServerHandler(self)
        self.android_app = AndroidApp()
        if USE_SERVER:
            # self.tcp_engine = TcpServer(self.tcp_handler)
            self.tcp_engine = TcpServer(self.tcp_handler, port=9600)  # , host="COM2", port=115200
            self.tcp_engine.start()
        else:
            self.tcp_engine = TcpClient(self.tcp_handler, server_ip="best.delayboy.cn", server_port=8888,
                                        keep_alive=True)
            # self.tcp_engine = TcpClient(self.tcp_handler, "COM6", server_port=115200, keep_alive=True)  # "192.168.1.8"

        self.my_dll: MyDll = MyDll.MyDll()
        self.ar = AudioRecorder(self.my_dll, self.recv_callback)
        self.mainManager = WinManager(self.my_dll, "")
        self.reader = easyocr.Reader(['ch_sim', 'en'], model_storage_directory=os.path.abspath("./EasyOcrModel"))
        rect = self.mainManager.get_rect().to_array()
        w, h = rect.get_size()
        self.drawManager = None
        if USE_MAX_FUNC or not USE_SERVER:
            t_hwnd = self.my_dll.create_transparent_window(rect.left, rect.top, w, h, self.paint_callback)
            self.drawManager = WinManager(self.my_dll, t_hwnd)
        start_thread(self.async_hook_callback, ())
        self.my_dll.set_py_hook_proc(self.real_time_hook_callback)
        self.my_dll.register_event_hook(0, True)
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

    def show_img(self, img: np.ndarray):
        self.__img = img
        # self.img = cv2.cvtColor(self.img, cv2.COLOR_RGBA2BGR)
        # Image.fromarray(self.img).show()

    def refresh_window(self):
        if self.drawManager is not None:
            self.drawManager.refresh_window(None)

    def exit_ocr(self):
        self.capture_stage = 0
        self.rect = Rect(0, 0, 0, 0)
        self.__img = None
        self.option_code = 'exit_ocr'

    def ocr_cut_pic(self):
        if self.__img is not None:
            pic = MyOpenCv.cut_picture(self.__img, self.rect)

            text_result = self.reader.readtext(pic)
            text_res = ""

            text_result = sorted(text_result, key=lambda item: item[0][0][1], reverse=False)  # 按y排序
            div_text_result = []
            pre_y = -100
            for pos, text, threshold in text_result:
                x, y = pos[0]
                gap_y = y - pre_y
                if gap_y > 15:
                    pre_y = y
                    div_text_result.append([])
                div_text_result[-1].append((pos, text, threshold))

            pre_y = -1
            pre_x = 0
            for y_index, sub_list in enumerate(div_text_result):
                sub_list.sort(key=lambda item: item[0][0][0], reverse=False)  # 按X排序

                for pos, text, threshold in sub_list:
                    x, y = pos[0]
                    end_x, _ = pos[1]
                    normalized_end_x = round(end_x / 10)
                    normalized_y = y_index  # 将索引视为y坐标
                    normalized_x = round(x / 10)
                    if pre_y != normalized_y:
                        if pre_y > -1:  # 不是第一次进入换行阶段
                            text_res += "\n"
                        pre_y = normalized_y
                        pre_x = 0

                    gap_num = int(normalized_x - pre_x)

                    pre_x = normalized_end_x
                    gap_str = ""
                    for i in range(gap_num):
                        gap_str += " "

                    text_res += gap_str + text
                    print(x, y, end_x, text)  # 打印坐标
            copy_to_clipboard(text_res)
            MyOpenCv.cv_im_write("OCR截图临时保存.png", pic)
            self.send_clipboard_text_with_tcp(text_res)
        self.exit_ocr()
        self.tcp_engine.send_str("", code=4)

    def send_clipboard_text_with_tcp(self, c: str = None, code_end=1):
        if c is None:
            c = get_from_clipboard()
        if len(c) > 900:
            c_list = split_string(c, 900)
            for i, c in enumerate(c_list):
                # print(i, "/", len(c_list))
                self.tcp_engine.send_str(c, code=0)
            self.tcp_engine.send_str("", code=code_end)
        else:
            self.tcp_engine.send_str(c, code=code_end)

        print("远程剪贴板发送成功")

    def paint_callback(self, hdc):
        if self.drawManager is None:
            return
        if USE_SERVER:  # and False
            if self.ar.is_record:
                bk_color = (0, 255, 0)
                if self.ar.record_speaker:
                    bk_color = (255, 0, 0)
                cur_x, cur_y = self.my_dll.get_cursor_pos()
                self.drawManager.draw_rect(Rect(cur_x + 5, cur_y, cur_x + 5 + 5, cur_y + 5), bk_color, hdc)
                # self.drawManager.draw_text(Rect(0, 0, 0.03, 0.03), "1", bk_color, bk_color, hdc=hdc)
            else:
                self.drawManager.clear_draw(hdc)
            return
        if self.__img is not None:
            self.drawManager.my_draw_image(self.__img, hdc)
        else:
            self.drawManager.clear_draw(hdc)
        self.drawManager.draw_rect(self.rect.copy(), (255, 0, 0), hdc)
        pass

    def async_hook_callback(self):
        while True:
            self.__late_callback_signal.clear()
            self.__late_callback_signal.wait()

            o = self.option_code
            if o.__eq__("left"):
                # ret_alt = False

                # self.mainManager.send_key_code(False, 160)  # 先取消shift
                # if self.on_alt:
                #     ret_alt = True
                # self.mainManager.send_key_code(False, 164)  # 先取消alt
                # self.mainManager.send_key_code(True, 162)  # 先取消ctrl
                # time.sleep(0.01)
                # self.mainManager.send_key_code(True, ord("A"))  # A
                # time.sleep(0.01)
                # self.mainManager.send_key_code(False, 162)  # 先取消ctrl
                # time.sleep(0.01)
                # self.mainManager.send_key_code(True, 8)  # back
                # time.sleep(0.01)
                # self.mainManager.send_key_code(False, 8)
                # if ret_alt:
                #     self.mainManager.send_key_code(True, 164)  # 先取消alt
                self.tcp_engine.send_any_obj({'option': o}, code=-2)
            elif o.__eq__("up"):
                self.my_dll.scroll_mouse(120)
                self.tcp_engine.send_any_obj({'option': o}, code=-2)
            elif o.__eq__('down'):
                self.my_dll.scroll_mouse(-120)
                self.tcp_engine.send_any_obj({'option': o}, code=-2)
            elif o.__eq__("do_enter"):
                # self.mainManager.send_key_code(False, 164)  # 先取消alt
                self.mainManager.send_key_code(False, 162)  # 先取消ctrl
                self.mainManager.send_key_code(False, 160)  # 先取消shift
                self.mainManager.send_key_code(True, 13)
                time.sleep(0.01)
                self.mainManager.send_key_code(False, 13)
                self.tcp_engine.send_any_obj({'key_code': 13, 'option': o}, code=-2)
            elif o.__eq__('q'):
                print("拷贝桌面")
                arr = self.mainManager.capture_window(None)
                arr = image_to_binary_arr(arr)
                self.tcp_engine.send_array(arr, code=2)

            elif o.__eq__("cut_pic"):

                self.ocr_cut_pic()

                self.refresh_window()
            elif o.__eq__('mouse_move'):
                if self.capture_stage == 2:
                    self.rect.left = self.cur_x
                    self.rect.top = self.cur_y
                elif self.capture_stage == 1:
                    self.rect.right = self.cur_x
                    self.rect.bottom = self.cur_y
                # if not self.tcp_engine.is_com_type():
                self.tcp_engine.send_any_obj(self.rect, code=3)
                # time.sleep(0.1)
                self.refresh_window()
            elif o.__eq__("begin_ocr"):
                print("开始OCR截图")
                self.capture_stage = 1

                if not self.tcp_engine.is_com_type():
                    self.tcp_engine.send_array(image_to_binary_arr(self.__img), code=2)
                else:
                    img = cv2.cvtColor(self.__img, cv2.COLOR_RGBA2GRAY)
                    w, h = MyOpenCv.get_image_size(img)
                    img = cv2.resize(img, (w // 4, h // 4))
                    self.tcp_engine.send_array(image_to_binary_arr(img), code=2)
                self.refresh_window()
            elif o.__eq__("exit_ocr"):
                self.tcp_engine.send_str("", code=4)
                self.refresh_window()
            elif o.__eq__("send_char_and_type"):
                self.mainManager.send_key_code(False, 160)  # 先取消shift
                self.mainManager.send_key_code(False, 164)  # 先取消alt
                self.mainManager.send_key_code(False, 162)  # 先取消ctrl
                self.mainManager.send_key_code(False, MyDll.VK_OEM_3)  # 先取消ctrl

                # for line in get_from_clipboard().split("\n"):
                #     self.my_dll.send_key(line)
                #     time.sleep(0.01)
                self.send_clipboard_text_with_tcp(code_end=-1)
                if self.ar.is_record_event.wait(timeout=1):
                    self.refresh_window()
            elif o.__eq__("begin_gui_record"):
                start_thread(self.record_gui_screen_loop, ())
            elif o.__eq__("copy_ui"):
                ui_str = copy_ui(True)
                MyFileEditor("./copy_real_ui.txt").write(ui_str)
                copy_to_clipboard(ui_str)
                self.send_clipboard_text_with_tcp(ui_str)
            elif o.__eq__("copy_real_ui"):
                ui_str = copy_ui(False)
                MyFileEditor("./copy_real_ui.txt").write(ui_str)
                copy_to_clipboard(ui_str)
                self.send_clipboard_text_with_tcp(ui_str)
            else:
                self.send_clipboard_text_with_tcp()

    def real_time_hook_callback(self, pk: HookPackage) -> int:
        # print(pk.code,ord("1"))
        if pk.code == 164:
            if pk.wParam == 260 or pk.wParam == 256:
                self.on_alt = True
            elif pk.wParam == 257:
                self.on_alt = False
        if self.on_alt:
            if pk.wParam == 260 or pk.wParam == MyDll.WM_KEYDOWN:
                if pk.code == ord("W"):  # 上
                    self.option_code = 'up'
                    self.__late_callback_signal.set()
                elif pk.code == ord("S"):  # 下
                    self.option_code = 'down'
                    self.__late_callback_signal.set()
                elif pk.code == ord("A"):  #
                    self.option_code = 'send_char_and_type'
                    self.__late_callback_signal.set()
                elif pk.code == ord("Q"):  #
                    self.option_code = 'left'
                    self.__late_callback_signal.set()
                elif pk.code == ord("Z"):  #
                    self.option_code = 'do_enter'
                    self.__late_callback_signal.set()
                elif pk.code == MyDll.VK_OEM_3:
                    pass
                    self.option_code = "send_char_and_type"  # "begin_gui_record"
                    self.__late_callback_signal.set()

        if pk.wParam == MyDll.WM_KEYDOWN:

            if pk.code == MyDll.VK_F1 and self.on_ctrl:
                self.__img = self.mainManager.capture_window(None)
                self.option_code = 'begin_ocr'
                self.__late_callback_signal.set()
            elif pk.code == 160:  # shift
                self.on_shift = True
            elif pk.code == 162:  # ctrl
                self.on_ctrl = True
            elif pk.code == 81 and self.on_ctrl:  # q
                copy_and_paste_script(self.my_dll)
            elif pk.code == 86 and self.on_ctrl:  # v 在正常逻辑之前运行
                # g_camel_case = get_from_clipboard()
                # underscore = convert_to_underscore(g_camel_case)
                # print("转换为下划线命名法：", underscore)
                # copy_to_clipboard(underscore)
                print("用户粘贴")
            elif self.on_shift and pk.code == 32:  # 空格
                self.ar.do_record(True)
                self.refresh_window()
            elif pk.code == 27:  # esc
                self.exit_ocr()
                self.__late_callback_signal.set()
            elif self.on_ctrl and pk.code == 32:  # 空格
                # self.option_code = 'do_record'
                # self.__late_callback_signal.set()
                if self.on_alt:
                    self.option_code = 'do_enter'
                    self.__late_callback_signal.set()
                else:
                    self.ar.do_record()
                self.refresh_window()
            elif pk.code == 38:  # 上

                self.option_code = 'up'
                # self.__late_callback_signal.set()
            elif pk.code == 40:  # 下
                self.option_code = 'down'
                # self.__late_callback_signal.set()

        elif pk.wParam == MyDll.WM_KEYUP:
            if pk.code == 162:  # ctrl
                self.on_ctrl = False
            elif pk.code == 160:  # shift
                self.on_shift = False
            elif pk.code == 67 and self.on_ctrl:  # c 在正常逻辑之后运行
                # g_camel_case = get_from_clipboard()
                # underscore = convert_to_html(g_camel_case)
                # print("转换为下划线命名法：", underscore)
                # copy_to_clipboard(underscore)
                self.option_code = 'send_char'
                self.__late_callback_signal.set()
                print("用户复制")
            elif pk.code == ord("B") and self.on_ctrl:
                self.option_code = 'copy_ui'
                self.__late_callback_signal.set()
                print("用户复制UI")
            elif pk.code == ord("I") and self.on_ctrl:
                self.option_code = 'copy_real_ui'
                self.__late_callback_signal.set()
                print("用户复制真实UI")
        elif not pk.keyEventType and pk.wParam == MyDll.WM_LBUTTONDOWN:
            if self.capture_stage == 1:
                self.cur_x, self.cur_y = self.my_dll.get_cursor_pos()
                self.rect.right = self.cur_x
                self.rect.bottom = self.cur_y
                self.capture_stage = 2
            elif self.capture_stage == 2:
                self.capture_stage = 0
                self.option_code = 'cut_pic'
                self.__late_callback_signal.set()
        else:
            # print(pk.code, pk.wParam)
            if self.capture_stage > 0:
                self.cur_x, self.cur_y = self.my_dll.get_cursor_pos()
                self.option_code = 'mouse_move'
                self.__late_callback_signal.set()
        return 1

    def loop(self):
        self.my_dll.message_loop()


class DefaultTcpServerHandler(TcpHandler):
    def __init__(self, main_ui: TransparentMainUI):
        super().__init__()
        self.collect_char = ""
        self.mainUi = main_ui

    @staticmethod
    def replace_with_space(string, start, end):
        string_list = list(string)
        for i in range(start, end + 1):
            string_list[i] = ' '

        return ''.join(string_list)

    def safe_send(self, line: str = "Untitled - Personal - Microsoft​ Edge"):

        send = False
        while not send:
            try:
                self.mainUi.my_dll.send_key(line)
                send = True
            except UnicodeEncodeError as e:
                line = self.replace_with_space(line, e.start, e.end)

    def callback(self, tcp_base: TcpBase, pk: PackageHeader) -> str:
        if pk.code == -2:
            key_code = pk.get_any_obj()
            o = key_code["option"]
            if o.__eq__("do_enter"):
                self.mainUi.mainManager.send_key_code(True, key_code["key_code"])
                time.sleep(0.01)
                self.mainUi.mainManager.send_key_code(False, key_code["key_code"])
            if o.__eq__("left"):
                self.mainUi.mainManager.send_key_code(False, 160)  # 先取消shift
                self.mainUi.mainManager.send_key_code(False, 164)  # 先取消alt
                self.mainUi.mainManager.send_key_code(True, 162)  # 先取消ctrl
                time.sleep(0.01)
                self.mainUi.mainManager.send_key_code(True, ord("A"))  # A
                time.sleep(0.01)
                self.mainUi.mainManager.send_key_code(False, 162)  # 先取消ctrl
                time.sleep(0.01)
                self.mainUi.mainManager.send_key_code(True, 8)  # back
                time.sleep(0.01)
                self.mainUi.mainManager.send_key_code(False, 8)
            elif o.__eq__("up"):
                self.mainUi.my_dll.scroll_mouse(120)
            elif o.__eq__('down'):
                self.mainUi.my_dll.scroll_mouse(-120)
        elif pk.code == -1:
            self.collect_char += pk.get_str_data()
            self.collect_char = hai_you_str_format(self.collect_char)
            copy_to_clipboard(self.collect_char)
            num = 0
            for line in self.collect_char.split("\n"):
                self.safe_send(line)
                time.sleep(0.01)
                self.mainUi.mainManager.send_key_code(True, 160)  # 先按shift
                self.mainUi.mainManager.send_key_code(True, 13)
                time.sleep(0.01)
                self.mainUi.mainManager.send_key_code(False, 13)
                self.mainUi.mainManager.send_key_code(False, 160)  # 先取消shift
                num += 1
                if num > 10:
                    break

            self.collect_char = ""
            print("通过TCP网络，设置剪贴板，并使用键盘进行输入")
        elif pk.code == 1:
            self.collect_char += pk.get_str_data()
            self.collect_char = hai_you_str_format(self.collect_char)
            copy_to_clipboard(self.collect_char)
            self.collect_char = ""
            print("通过TCP网络，设置剪贴板")
        elif pk.code == 0:
            self.collect_char += pk.get_str_data()
        elif pk.code == 3:
            rect = pk.get_any_obj()
            self.mainUi.rect = rect
            self.mainUi.refresh_window()
        elif pk.code == 2:
            img = binary_arr_to_image(pk.data)
            if self.mainUi.tcp_engine.is_com_type():
                w, h = MyOpenCv.get_image_size(img)
                img = cv2.resize(img, (w * 4, h * 4))
            img = MyOpenCv.add_alpha_channel_if_needed(img)
            if img is not None:
                self.mainUi.show_img(img)
                self.mainUi.refresh_window()
        elif pk.code == 4:
            self.mainUi.exit_ocr()
            self.mainUi.refresh_window()
        super().callback(tcp_base, pk)

    def wait_for_signal(self):
        self.recv_signal.wait()  # timeout=2


def main(patch_md5: str | None, patch_path: str):
    if patch_md5 is None or patch_md5 == auto_patch_python(None, patch_path=patch_path):

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
