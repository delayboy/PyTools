import ctypes

import numpy.ctypeslib as npct
import numpy as np
from typing import Callable, Any, Tuple
import win32gui
import win32con
import win32api

from PyTools.MyAwesomeTool.MyLinkHelper import smart_guess_file_or_link
from PyTools.MyAwesomeTool.MyUtil import set_env_var

WM_KEYDOWN = 0x0100
WM_KEYUP = 0x0101
WM_LBUTTONDOWN = 0x0201
WM_LBUTTONUP = 0x0202
WM_RBUTTONDOWN = 0x0204
WM_RBUTTONUP = 0x0205
VK_OEM_3 = 0xC0
VK_F1 = 0x70
SW_RESTORE = 9
HWND_BROADCAST = 0x0ffff


class PyImagePackage(ctypes.Structure):
    _fields_ = [
        ("img_array", ctypes.c_void_p),
        ("height", ctypes.c_uint64),
        ("width", ctypes.c_uint64),
        ("rowPitch", ctypes.c_uint64),
        ("rSize", ctypes.c_uint64),
    ]

    def __init__(self):
        super().__init__(*(), **{})
        self.img_array = ctypes.c_void_p(0)
        self.height = 0
        self.width = 0
        self.rowPitch = 0
        self.rSize = 0
        self.real_img_mat: np.ndarray = None


class PyRect(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]

    def __init__(self, left: int, top: int, right: int, bottom: int):
        super().__init__(*(), **{})
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom
        self.pretty_format()

    def pretty_format(self):
        if self.left > self.right:
            tmp = self.left
            self.left = self.right
            self.right = tmp
        if self.top > self.bottom:
            tmp = self.top
            self.top = self.bottom
            self.bottom = tmp
        return self

    def get_width(self) -> int:
        return self.right - self.left

    def get_height(self) -> int:
        return self.bottom - self.top

    def get_size(self) -> Tuple[int, int]:
        return self.get_width(), self.get_height()

    def get_middle(self) -> Tuple[int, int]:
        return (self.right + self.left) // 2, (self.top + self.bottom) // 2

    def __str__(self):
        x, y = self.get_middle()
        return "(x:%d,y:%d,w:%d,h:%d)left:%d,top:%d,right:%d,bottom:%d" % (
            x, y, self.right - self.left, self.bottom - self.top, self.left, self.top, self.right, self.bottom)

    def to_bounds(self) -> str:
        return '[%d,%d][%d,%d]' % (self.left, self.top, self.right, self.bottom)


class HookPackage(ctypes.Structure):
    _fields_ = [
        ("keyEventType", ctypes.c_bool),
        ("code", ctypes.c_int32),
        ("wParam", ctypes.c_int64),
    ]

    def __init__(self, *args: Any, **kw: Any):
        super().__init__(*args, **kw)
        self.keyEventType = True
        self.code = 0
        self.wParam = 0


class MyDll:
    """Z:/Computer/Program/Program_maker/CPlus/MyDll/MyDll/x64/Debug/MyDll.dll"""

    def __init__(self):
        set_env_var("PATH", "Z:/Computer/Program/Program_maker/CPlus/MyDll/MyDll/x64/Debug")
        self.__lib = ctypes.cdll.LoadLibrary(smart_guess_file_or_link("MyDll.dll"))
        self.__lib.registerEventHook.restype = ctypes.c_int64
        self.__lib.registerEventHook.argtypes = [ctypes.c_int, ctypes.c_bool]

        self.PYHOOKPROC = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(HookPackage))
        self.pyhookProc = None
        self.__lib.setPyHookProc.restype = None
        self.__lib.setPyHookProc.argtypes = [self.PYHOOKPROC]

        self.MyFrameArrivedEventHandle = ctypes.CFUNCTYPE(ctypes.c_int64, ctypes.POINTER(PyImagePackage))
        self.myFrameEventHandle = None
        self.__lib.StartCapturewindow.argtypes = [ctypes.c_int64, self.MyFrameArrivedEventHandle]

        self.__lib.MyFindWindow.restype = ctypes.c_int64
        self.__lib.MyFindWindow.argtypes = [ctypes.c_char_p]

        self.__lib.GetProcessIdFromProcessName.restype = ctypes.c_ulong
        self.__lib.GetProcessIdFromProcessName.argtypes = [ctypes.c_char_p]

        self.__lib.MyGetWindowDC.restype = ctypes.c_int64
        self.__lib.MyGetWindowDC.argtypes = [ctypes.c_int64]

        self.__lib.CopyScreenToBitmap.restype = ctypes.c_void_p
        self.__lib.CopyScreenToBitmap.argtypes = [ctypes.c_int64, ctypes.c_int64, ctypes.POINTER(PyRect)]

        self.__lib.GetBmpInfo.argtypes = [ctypes.c_void_p,
                                          npct.ndpointer(dtype=np.int64, ndim=1, shape=(4,), flags="C_CONTIGUOUS")]

        self.__lib.GetBmpInfo.restype = npct.ndpointer(dtype=np.int64, ndim=1, shape=(4,), flags="C_CONTIGUOUS")

        self.__lib.GetBmpData.argtypes = [ctypes.c_void_p, npct.ndpointer(dtype=np.uint8, ndim=1, flags="C_CONTIGUOUS")]

        self.__lib.WaitForKeyCodeEvent.restype = ctypes.c_int32

        self.__lib.MessageLoop.restype = ctypes.c_int32

        self.__lib.GetWinRect.argtypes = [ctypes.c_int64, ctypes.POINTER(PyRect)]  #

        self.__lib.GetWinRect.restype = ctypes.POINTER(PyRect)

        self.__lib.MyMoveWindow.argtypes = [ctypes.c_int64, ctypes.POINTER(PyRect), ctypes.c_bool]

        self.__lib.SimulateMouseMovement.argtypes = [ctypes.c_int32, ctypes.c_int32]
        self.__lib.SendKey.argtypes = [ctypes.c_char_p]
        self.__lib.SendMouseDown.argtypes = [ctypes.c_bool, ctypes.c_int32]
        self.__lib.MySetCursorPos.argtypes = [ctypes.c_int32, ctypes.c_int32]
        self.__lib.MyGetCursorPos.argtypes = [ctypes.POINTER(ctypes.c_int32), ctypes.POINTER(ctypes.c_int32)]
        self.__lib.MySetForegroundWindow.argtypes = [ctypes.c_int64]

        self.__lib.setTop.argtypes = [ctypes.c_int64, ctypes.c_bool]
        self.__lib.SendKeyDown.argtypes = [ctypes.c_bool, ctypes.c_char]
        self.__lib.MyFindWindowByProcessId.argtypes = [ctypes.c_ulong]
        self.__lib.MyFindWindowByProcessId.restype = ctypes.c_int64
        self.__lib.calculateScreenScale.argtypes = [ctypes.POINTER(ctypes.c_double), ctypes.POINTER(ctypes.c_double)]
        self.__lib.ScrollMouse.argtypes = [ctypes.c_int]
        self.PAINT_CALLBACK = ctypes.CFUNCTYPE(ctypes.c_int64, ctypes.c_int64)
        self.py_paint_callback = None
        self.__lib.MySetWindowDisplayAffinity.argtypes = [ctypes.c_int, ctypes.c_int]
        self.__lib.MySetWindowInterceptMode.argtypes = [ctypes.c_int, ctypes.c_bool]
        self.__lib.CreateTransparentWindow.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                                       self.PAINT_CALLBACK]
        self.__lib.CreateTransparentWindow.restype = ctypes.c_int64

        self.__lib.myRedrawWindow.argtypes = [ctypes.c_int, ctypes.POINTER(PyRect)]
        self.__lib.MyUpdateLayeredWindow.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                                     ctypes.c_int]
        self.__lib.Mat2HBitmap.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                           npct.ndpointer(dtype=np.uint8, ndim=1, flags="C_CONTIGUOUS")]

    def mat2hbitmap(self, channels, cols, rows, data: np.ndarray):
        return self.__lib.Mat2HBitmap(channels, cols, rows, data.flatten())

    def my_update_layered_window(self, hwnd, hdc, mdc, width, height):
        self.__lib.MyUpdateLayeredWindow(hwnd, hdc, mdc, width, height)

    def my_redraw_window(self, hwnd, my_rect: PyRect | None):
        if my_rect is None:
            rect = self.get_win_rect(hwnd)
            self.__lib.myRedrawWindow(hwnd, ctypes.byref(rect))
        else:
            self.__lib.myRedrawWindow(hwnd, ctypes.byref(my_rect))

    def set_window_display_affinity(self, hwnd: int, affinity: int):
        self.__lib.MySetWindowDisplayAffinity(hwnd, affinity)

    def set_window_intercept_mode(self, hwnd: int, usr_block: bool):
        self.__lib.MySetWindowInterceptMode(hwnd, usr_block)

    def create_transparent_window(self, x: int, y: int, wight: int, height: int,
                                  callback: Callable[[int], None]) -> int:
        def temp_callback(hdc: int) -> int:
            callback(hdc)
            return 1

        self.py_paint_callback = self.PAINT_CALLBACK(temp_callback)
        return self.__lib.CreateTransparentWindow(int(x), int(y), int(wight), int(height), self.py_paint_callback)

    def start_capture_window(self, hwnd: int, my_frame_event_callback: Callable[[PyImagePackage], int]):
        # 在此处定制img_pk的预处理方案
        def my_pre_frame_event_handle(img_pk: ctypes.POINTER(PyImagePackage)) -> int:
            pk: PyImagePackage = ctypes.cast(img_pk, ctypes.POINTER(PyImagePackage))[0]  # 指针类型转换
            # pk.real_img_mat = np.array([]).reshape((0, 0, 0))
            # 获取指向图像数据的指针
            img_ptr = ctypes.cast(pk.img_array, ctypes.POINTER(ctypes.c_ubyte))
            # 使用 ctypes.cast 将 img_ptr 转换为一个 NumPy 数组, 数据的形状是 (pk.rSize)
            numpy_array = np.array(np.ctypeslib.as_array(img_ptr, shape=(pk.rSize,)))
            # 重新计算图片高度
            pk.width = int(pk.rowPitch / 4)
            # 重组图片维度
            numpy_array = numpy_array.reshape((pk.height, pk.width, 4))
            pk.real_img_mat = numpy_array
            return my_frame_event_callback(pk)

        self.myFrameEventHandle = self.MyFrameArrivedEventHandle(my_pre_frame_event_handle)
        self.__lib.StartCapturewindow(hwnd, self.myFrameEventHandle)

    def scroll_mouse(self, scroll_offset: int):
        self.__lib.ScrollMouse(scroll_offset)

    def calculate_screen_scale(self) -> (float, float):
        horiz_scale, vert_scale = ctypes.c_double(0), ctypes.c_double(0)
        self.__lib.calculateScreenScale(horiz_scale, vert_scale)
        return horiz_scale.value, vert_scale.value

    def my_set_foreground_window(self, hwnd: int):
        self.__lib.MySetForegroundWindow(hwnd)

    def set_top(self, hwnd: int, is_top: int):
        self.__lib.setTop(hwnd, is_top)

    def send_key_down(self, down: bool, key_code: int):
        self.__lib.SendKeyDown(down, key_code)

    def register_event_hook(self, key_hook: int, do_register: bool) -> int:
        return self.__lib.registerEventHook(key_hook, do_register)

    def set_py_hook_proc(self, py_hook_call_back: Callable[[HookPackage], int]):
        def py_hook_func(hook_pk: ctypes.POINTER(HookPackage)) -> int:
            pk = ctypes.cast(hook_pk, ctypes.POINTER(HookPackage))[0]  # 指针类型转换
            # print(f'keyCode:{pk.code} wParam:{pk.wParam}')
            return py_hook_call_back(pk)

        self.pyhookProc = self.PYHOOKPROC(py_hook_func)
        self.__lib.setPyHookProc(self.pyhookProc)

    def my_find_window(self, win_name: str) -> int:
        b = win_name.encode("gbk")
        return self.__lib.MyFindWindow(b)

    @staticmethod
    def post_message(hwnd: int, key_down: bool, key_code: int):
        if key_down:
            win32gui.PostMessage(hwnd, WM_KEYDOWN, key_code, 0)
        else:
            win32gui.PostMessage(hwnd, WM_KEYUP, key_code, 0)

    @staticmethod
    def restore_window(hwnd: int):
        if win32gui.IsIconic(hwnd):  # 如果窗口最小化，则恢复它
            win32gui.ShowWindow(hwnd, SW_RESTORE)
            win32gui.SetForegroundWindow(hwnd)

    @staticmethod
    def my_find_window_with_class_name(class_name: str, win_name: str) -> int:
        return win32gui.FindWindow(class_name, win_name)

    def get_process_id_from_process_name(self, proc_name: str) -> int:
        b = proc_name.encode("gbk")
        return self.__lib.GetProcessIdFromProcessName(b)

    def my_find_window_by_process_id(self, process_id: int) -> int:
        return self.__lib.MyFindWindowByProcessId(process_id)

    def my_get_window_dc(self, hwnd: int) -> int:
        return self.__lib.MyGetWindowDC(hwnd)

    def copy_screen_to_bitmap(self, hwnd, hdc, my_rect: PyRect) -> ctypes.c_void_p:
        return self.__lib.CopyScreenToBitmap(hwnd, hdc, ctypes.byref(my_rect))

    def get_bmp_info(self, h_bmp) -> np.ndarray:
        info = np.array([0, 0, 0, 0], dtype=np.int64)
        pointer = self.__lib.GetBmpInfo(h_bmp, info)
        # *prt equal to mat_data = ctypes.c_longlong.from_address(ptr).value
        # 从指针指向的地址中读取数据，并转为numpy array,且内存与c++内存是隔离的
        np_canny = np.array(np.fromiter(pointer, dtype=np.int64, count=4))
        return info  # width height channel

    def get_bmp_data(self, h_bmp, info: np.ndarray) -> np.ndarray:
        if info[0] < 0 or info[1] < 0 or info[2] < 0:
            return np.array([])
        all_size = info[0] * info[1] * info[2]
        data = np.zeros(all_size, np.uint8)
        self.__lib.GetBmpData(h_bmp, data)
        return data.reshape((info[1], info[0], info[2]))  # height width channel

    def wait_for_key_code_event(self) -> int:
        return self.__lib.WaitForKeyCodeEvent()

    def message_loop(self):
        # 想使用键盘钩子消息循环是必须的
        return self.__lib.MessageLoop()

    def get_win_rect(self, hwnd) -> PyRect:
        # rect = np.array([0, 0, 0, 0], dtype=np.int32)
        rect = PyRect(0, 0, 0, 0)
        pointer = self.__lib.GetWinRect(hwnd, ctypes.byref(rect))
        rect2 = pointer.contents
        return rect

    def my_move_window(self, hwnd, my_rect: PyRect, re_paint: bool):
        self.__lib.MyMoveWindow(hwnd, ctypes.byref(my_rect), re_paint)

    def simulate_mouse_movement(self, delta_x: int, delta_y: int):
        self.__lib.SimulateMouseMovement(delta_x, delta_y)

    def send_key(self, key_str):
        b = key_str.encode("gbk")
        self.__lib.SendKey(b)

    def set_cursor_pos(self, middle_x: int, middle_y: int):
        self.__lib.MySetCursorPos(middle_x, middle_y)

    def get_cursor_pos(self) -> tuple:
        x = ctypes.c_int32(0)
        y = ctypes.c_int32(0)
        self.__lib.MyGetCursorPos(ctypes.byref(x), ctypes.byref(y))
        return x.value, y.value

    def send_mouse_down(self, down: bool, button_num: int = 0):
        self.__lib.SendMouseDown(down, button_num)


class TestRect(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_int64),
        ("top", ctypes.c_int64),
        ("right", ctypes.c_int64),
        ("bottom", ctypes.c_int64),
    ]


# Mat2HBitmap Python版: 将 OpenCV 的 Mat 转换为 HBITMAP
def mat2_h_bitmap(use_my_dll: MyDll, mat):
    height, width = mat.shape[:2]
    n_channels = mat.shape[2] if len(mat.shape) > 2 else 1

    # # 将图像数据传递给 CreateBitmap 的最后一个参数
    # hbitmap = ctypes.windll.gdi32.CreateBitmap(
    #     width, height, 1, n_channels * 8, ctypes.c_void_p(mat.ctypes.data)
    # )
    return use_my_dll.mat2hbitmap(n_channels, width, height, mat)


def clear_screen(hdc: int, tuple_refresh_rect: PyRect):
    h_brush = win32gui.CreateSolidBrush(rgb(0, 0, 0))
    win32gui.FillRect(hdc, (
        tuple_refresh_rect.left, tuple_refresh_rect.top, tuple_refresh_rect.right, tuple_refresh_rect.bottom), h_brush)
    win32gui.DeleteObject(h_brush)


def my_draw_image(use_my_dll: MyDll, hwnd: int, hdc: int, mat: np.ndarray, transparent=False):
    # 将 OpenCV 的 Mat 转换为 HBITMAP
    h_bmp = mat2_h_bitmap(use_my_dll, mat)

    # 创建一个兼容的 DC
    mdc = win32gui.CreateCompatibleDC(hdc)

    # 将位图选择到 DC 中
    h_old_bitmap = win32gui.SelectObject(mdc, h_bmp)

    # 获取图片尺寸
    height, width = mat.shape[:2]
    if transparent:
        use_my_dll.my_update_layered_window(hwnd, hdc, mdc, width, height)
        # 使用 UpdateLayeredWindow 绘制图像到透明窗口
        # win32gui.UpdateLayeredWindow(hwnd, hdc, (0, 0), (width, height), mdc, (0, 0), 0,
        #                              (win32con.AC_SRC_OVER, 0, 255, win32con.AC_SRC_ALPHA), win32con.ULW_ALPHA)

    else:
        # 将内存 DC (mdc) 上的位图绘制到窗口的设备上下文 (hdc) 上
        win32gui.BitBlt(hdc, 0, 0, width, height, mdc, 0, 0, win32con.SRCCOPY)

    # 恢复并清理
    win32gui.SelectObject(mdc, h_old_bitmap)
    win32gui.DeleteDC(mdc)
    win32gui.DeleteObject(h_bmp)


def my_draw_rect(hdc: int, tuple_rect: PyRect, color: Tuple[int, int, int], transparent=True):
    # 创建红色画笔
    red_pen = win32gui.CreatePen(win32con.PS_SOLID, 5, win32api.RGB(*color))
    old_pen = win32gui.SelectObject(hdc, red_pen)
    if transparent:
        # 绘制矩形边框，不填充背景
        win32gui.FrameRect(hdc, (tuple_rect.left, tuple_rect.top, tuple_rect.right, tuple_rect.bottom), red_pen)
    else:
        # 非透明模式：必须提供有效画刷。创建一个纯色画刷。
        solid_brush = win32gui.CreateSolidBrush(win32api.RGB(*color))
        # old_brush = win32gui.SelectObject(hdc, solid_brush)
        win32gui.FillRect(hdc, (tuple_rect.left, tuple_rect.top, tuple_rect.right, tuple_rect.bottom), solid_brush)
        # win32gui.Rectangle(hdc, tuple_rect.left, tuple_rect.top, tuple_rect.right, tuple_rect.bottom)
        win32gui.DeleteObject(solid_brush)

    # 释放画笔并释放设备上下文
    win32gui.SelectObject(hdc, old_pen)
    win32gui.DeleteObject(red_pen)


def my_draw_text(hdc: int, tuple_rect: PyRect, lp_str: str, text_color: int, back_color: int):
    font = win32gui.LOGFONT()
    font.lfHeight = 30  # 字体的高度
    font.lfWeight = 900  # 字体的粗细
    font.lfFaceName = "黑体"
    h_font = win32gui.CreateFontIndirect(font)
    old_font = win32gui.SelectObject(hdc, h_font)
    # h_brush = win32gui.CreateSolidBrush(rgb(0, 0, 0))
    # win32gui.FillRect(hdc, (tuple_rect.left, tuple_rect.top, tuple_rect.right, tuple_rect.bottom), h_brush)
    # win32gui.DeleteObject(h_brush)
    # win32gui.SetBkMode(hdc, 1)
    win32gui.SetBkColor(hdc, back_color)
    win32gui.SetTextColor(hdc, text_color)
    win32gui.DrawText(hdc, lp_str, -1, (tuple_rect.left, tuple_rect.top, tuple_rect.right, tuple_rect.bottom), 0x1)

    un_use_font = win32gui.SelectObject(hdc, old_font)
    win32gui.DeleteObject(un_use_font)


def rgb(r, g, b):
    return (r & 0xFF) | ((g & 0xFF) << 8) | ((b & 0xFF) << 16)


def get_key_code_ascii_by_str(key: str):
    return ord(key)


if __name__ == '__main__':
    print("kais")
"""
    myDll = MyDll()


    def replace_with_space(string, start, end):
        string_list = list(string)
        for i in range(start, end + 1):
            string_list[i] = ' '

        return ''.join(string_list)


    def safe_send(line: str = "Untitled - Personal - Microsoft​ Edge"):

        send = False
        while not send:
            try:
                myDll.send_key(line)
                send = True
            except UnicodeEncodeError as e:
                line = replace_with_space(line, e.start, e.end)


    exit(0)
    mat2 = cv2.imread("test.png", -1)


    def callback(hdc):
        mat2_h_bitmap(myDll, mat2)


    hh = myDll.create_transparent_window(0, 0, 300, 200, callback)
    hd = myDll.my_get_window_dc(hh)
    myDll.message_loop()

    # desktop = myDll.my_find_window("")
    # hdc2 = myDll.my_get_window_dc(desktop)
    # while True:
    #     my_draw_text(hdc2, 0, 0, "测试", rgb(0, 0, 0), rgb(255, 0, 0))
    #     time.sleep(0.1)
    #
    # exit(0)
    # time.sleep(2)

    # 模拟向下滚动鼠标滚轮
    # myDll.scroll_mouse(-120)
    myDll.register_event_hook(1, True)
    # myDll.register_event_hook(0, True)
    myDll.set_py_hook_proc(lambda pk: print(f'eventType:{pk.keyEventType} keyCode:{pk.code} wParam:{pk.wParam}'))
    myDll.message_loop()

    # hw = myDll.my_find_window_by_process_name("msedge.exe")
    # mHdc = myDll.my_get_window_dc(hw)
    # hBmp = myDll.copy_screen_to_bitmap(hw, mHdc,myDll.get_win_rect(hw))
    # myDll.get_bmp_info(hBmp)
    # rec = myDll.get_win_rect(hw)
    # print(rec)
    info2 = np.array([1, 2, 3, 4], dtype=np.int64)
    # rect = TestRect.from_buffer(info2)
"""
