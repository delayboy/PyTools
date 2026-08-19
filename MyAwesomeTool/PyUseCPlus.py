from __future__ import annotations  # 使用高级注解器，

import random
import base64
from typing import List, TypeVar, Callable, Generic, Dict, Tuple, Sequence
import ctypes
import numpy as np
import threading
import time
import os
import cv2
import adbutils
import datetime

import PyTools.MyAwesomeTool.MyProcessHelper as procHelper
from PyTools.MyAwesomeTool.MyLinkHelper import smart_guess_file_or_link
import PyTools.MyAwesomeTool.MyDll as MyDllLib
from PyTools.MyAwesomeTool.MyDll import PyRect, PyImagePackage
from PyTools.MyAwesomeTool.MyUtil import MyFileEditor, start_thread, InteractiveCmd, build_logger, auto_patch_python, \
    this_process
from PyTools.MyAwesomeTool.MyTcpHelper import TcpClient, PackageHeader, DefaultTcpClientHandler
from PyTools.MyAwesomeTool.MyBoxLayout import MainUIBase


def image_to_base64(image: np.ndarray):  # 图片转base64字符串
    image = cv2.imencode('.png', image)[1]

    base64_data = str(base64.b64encode(image))[2:-1]
    return base64_data


def base64_to_image(base64_string: str) -> np.ndarray:
    # 要解码的base64字符串

    # 从base64字符串中提取编码的图像数据部分
    image_data = base64_string.split(',')[1]

    # 将base64数据解码为字节数组
    image_bytes = base64.b64decode(image_data)

    # 将字节数组转换为NumPy数组
    image_np = np.frombuffer(image_bytes, np.uint8)

    # 解码为OpenCV图像
    image = cv2.imdecode(image_np, cv2.IMREAD_COLOR)
    return image


def image_to_binary_arr(image: np.ndarray) -> np.ndarray:
    return cv2.imencode('.png', image)[1]


def binary_arr_to_image(b_array: np.ndarray) -> np.ndarray:
    return cv2.imdecode(b_array, cv2.IMREAD_COLOR)


def image_to_binary(image: np.ndarray) -> bytes:
    return image_to_binary_arr(image).tobytes()


def binary_to_image(b_array: bytes) -> np.ndarray:
    return binary_arr_to_image(np.frombuffer(b_array, np.uint8))


class Rect:
    Rect = TypeVar('Rect', bound='Rect')

    def __init__(self, left: float, top: float, right: float, bottom: float):
        self.left = left
        self.top = top
        self.right = right
        self.bottom = bottom

    @classmethod
    def percent_rect(cls, left: float, top: float, right: float, bottom: float):
        if 0 <= left < right <= 1 and 0 <= top < bottom <= 1:
            return cls(left, top, right, bottom)
        else:
            raise Exception("PercentRect越界")

    @classmethod
    def from_array(cls, my_rect: PyRect):
        # return cls(myRect[0], myRect[1], myRect[2], myRect[3])
        return cls(my_rect.left, my_rect.top, my_rect.right, my_rect.bottom)

    @classmethod
    def from_percent(cls, w: float, h: float, percent_rect: Rect):
        left = percent_rect.left
        top = percent_rect.top
        right = percent_rect.right
        bottom = percent_rect.bottom
        left = float(w * left)
        top = float(h * top)
        right = float(w * right)
        bottom = float(h * bottom)
        return cls(left, top, right, bottom)

    @classmethod
    def from_percent_use_position_rect(cls, position_rect: Rect, percent_rect: Rect):
        w, h = position_rect.get_size()
        temp_rect = cls.from_percent(w, h, percent_rect)
        temp_rect.left += position_rect.left
        temp_rect.right += position_rect.left
        temp_rect.top += position_rect.top
        temp_rect.bottom += position_rect.top
        return temp_rect

    def to_array(self) -> PyRect:
        # return np.array([self.left, self.top, self.right, self.bottom], dtype=np.int32)
        return PyRect(int(self.left), int(self.top), int(self.right), int(self.bottom))

    def get_width(self):
        return self.right - self.left

    def get_height(self):
        return self.bottom - self.top

    def get_size(self) -> Tuple[float, float]:
        return self.get_width(), self.get_height()

    def get_middle(self) -> Tuple[float, float]:
        return (self.right + self.left) / 2, (self.top + self.bottom) / 2

    def copy(self):
        return Rect(self.left, self.top, self.right, self.bottom)

    def __str__(self):
        return "(w:%.2f,h:%.2f)left:%.2f,top:%.2f,right:%.2f,bottom:%.2f" % (
            self.right - self.left, self.bottom - self.top, self.left, self.top, self.right, self.bottom)

    @staticmethod
    def change_item_in_range(num, range_min=0, range_max=1) -> float:
        if num < range_min:
            return range_min
        elif num > range_max:
            return range_max
        return num

    def move_offset(self, offset_x=0.0, offset_y=0.0):
        w, h = self.get_size()
        self.top = self.change_item_in_range(self.top + offset_y)
        self.bottom = self.change_item_in_range(self.top + h)
        self.left = self.change_item_in_range(self.left + offset_x)
        self.right = self.change_item_in_range(self.left + w)

    def zoom(self, offset_x=0.0, offset_y=0.0):
        w, h = self.get_size()
        w = w + offset_x
        h = h + offset_y
        self.top = self.change_item_in_range(self.bottom - h)
        self.left = self.change_item_in_range(self.right - w)


class MyOpenCv:
    @staticmethod
    def color_to_gray(img: np.ndarray):
        channel_num = MyOpenCv.get_channel_num(img)
        if channel_num == 4:
            return cv2.cvtColor(img, cv2.COLOR_RGBA2GRAY)
        elif channel_num == 3:
            return cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
        else:
            return img.copy()

    @staticmethod
    def threshold(img: np.ndarray, thresh=50, max_value=255, option=cv2.THRESH_BINARY):
        value, new_img = cv2.threshold(img, thresh, max_value, option)
        # print(value)
        return new_img

    # 读取带中文的图片，bgr
    @staticmethod
    def cv_imread(file_path: str, flag: int = -1):
        cv_img = cv2.imdecode(np.fromfile(file_path, dtype=np.uint8), flag)
        return cv_img

    # 保存带中文的图片
    @staticmethod
    def cv_im_write(file_path, img: np.ndarray):
        cv2.imencode('.png', img)[1].tofile(file_path)  # 保存带中文的图片，opencv保存的tiff，默认是lzw压缩

    @staticmethod
    def tm_sqdiff_normal(const_src_mat: np.ndarray, const_temp_mat: np.ndarray) -> np.ndarray:
        src_row, src_col = const_src_mat.shape[0:2]
        tmp_row, tmp_col = const_temp_mat.shape[0:2]
        res_row, res_col = (src_row - tmp_row + 1, src_col - tmp_col + 1)
        if res_row <= 0 or res_col <= 0:
            return np.zeros((1, 1))
        res = np.zeros((res_row, res_col))
        for i in range(0, res_row):
            for j in range(0, res_col):
                src_sub = const_src_mat[i:i + tmp_row, j:j + tmp_col]
                mult_res = src_sub - const_temp_mat
                mult_res = mult_res * mult_res
                res[i, j] = np.sum(mult_res)
        return res

    @staticmethod
    def draw_rect(const_src_mat: np.ndarray, rect: Rect, rgb: tuple = (0, 255, 0, 255)) -> np.ndarray:
        src_mat = const_src_mat.copy()
        left_top = (int(rect.left), int(rect.top))
        right_bottom = (int(rect.right), int(rect.bottom))
        cv2.rectangle(src_mat, left_top, right_bottom, rgb, 2, 16)
        return src_mat

    @staticmethod
    def draw_text_loc(const_src_mat: np.ndarray, text: str, loc: Tuple[int, int], color=(0, 0, 0, 0)
                      , font_scale=0.8, thickness=2) -> np.ndarray:
        src_mat = const_src_mat.copy()

        # Get the text size
        text_size, baseline = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
        text_width, text_height = text_size

        # Calculate the bottom-left corner of the text
        x, y = loc
        # Draw black rectangle background
        top_left_corner = (x, y - text_height - baseline)
        bottom_right_corner = (x + text_width, y + baseline)
        cv2.rectangle(src_mat, top_left_corner, bottom_right_corner, color, cv2.FILLED)

        # Draw white text
        cv2.putText(src_mat, text, loc, cv2.FONT_HERSHEY_SIMPLEX, font_scale, (255, 255, 255, 255), thickness)
        return src_mat

    @staticmethod
    def draw_text(const_src_mat: np.ndarray, text: str) -> np.ndarray:
        w, h = MyOpenCv.get_image_size(const_src_mat)
        loc = (0, int(h / 2))
        return MyOpenCv.draw_text_loc(const_src_mat, text, loc)

    @staticmethod
    def overlay_transparent(src: np.ndarray, overlay: np.ndarray, loc: tuple):
        """
        将带透明通道的 overlay 图像叠加到 src 图像的指定位置
        :param src: 3通道 BGR 图像
        :param overlay: 4通道 BGRA 图像
        :param loc: 叠加位置的左上角坐标
        :return: 叠加后的图像（修改 src 的副本或原图）
        """
        x, y = loc
        src = src.copy()
        h, w = overlay.shape[:2]

        # 确保叠加区域不超出 src 边界
        if x + w > src.shape[1] or y + h > src.shape[0]:
            raise ValueError("Overlay region exceeds image boundaries")

        # 提取 ROI
        roi = src[y:y + h, x:x + w]

        # 分离颜色通道和 Alpha 通道
        overlay_bgr = overlay[:, :, :3]  # BGR
        if overlay.shape[2] == 4:
            alpha = overlay[:, :, 3] / 255.0  # Alpha 归一化到 [0,1]
        else:
            alpha = np.ones_like(overlay[:, :, 1], dtype=np.uint8) * 255
            alpha = alpha.astype(np.float32) / 255.0

        # 对每个颜色通道进行混合
        for c in range(3):
            roi[:, :, c] = (1 - alpha) * roi[:, :, c] + alpha * overlay_bgr[:, :, c]

        src[y:y + h, x:x + w] = roi
        return src

    @staticmethod
    def show_single_match_pic(const_src_mat: np.ndarray, const_temp_mat: np.ndarray, score: float,
                              loc: tuple, other_text: str = "score:") -> np.ndarray:
        src_mat = const_src_mat.copy()
        w, h = MyOpenCv.get_image_size(const_temp_mat)
        src_mat = MyOpenCv.overlay_transparent(src_mat, const_temp_mat, loc)
        cv2.rectangle(src_mat, loc, (loc[0] + w, loc[1] + h), (0, 0, 255, 255), 2, 16)
        text = "%s %.2f" % (other_text, score)
        src_mat = MyOpenCv.draw_text_loc(src_mat, text, loc, (0, 0, 255, 255))
        # src_mat = cv2.resize(src_mat, (w, h))
        return src_mat

    @staticmethod
    def get_image_size(img: np.ndarray) -> Tuple[int, int]:
        # 获取图片的宽和高，img存储的宽和高信息是反着的，这个有待研究
        y, x = img.shape[0:2]
        return x, y

    @staticmethod
    def fill_black_to_src_by_percent(img: np.ndarray, input_rect: Rect) -> np.ndarray:
        input_rect = MyOpenCv.get_real_rect_by_percent_rect(img, input_rect)
        return MyOpenCv.fill_black_to_src(img, input_rect)

    @staticmethod
    def fill_black_to_src(img: np.ndarray, input_rect: Rect) -> np.ndarray:
        rect = input_rect.to_array()
        if len(img.shape) >= 3:
            img[rect.top:rect.bottom, rect.left:rect.right, :] = 0
        else:
            img[rect.top:rect.bottom, rect.left:rect.right] = 0
        return img

    @staticmethod
    def get_real_rect_by_percent_rect(img: np.ndarray, percent_rect: Rect) -> Rect:
        w, h = MyOpenCv.get_image_size(img)
        rect = Rect.from_percent(w, h, percent_rect)
        return rect

    @staticmethod
    def cut_picture_with_percent(img: np.ndarray, percent_rect: Rect) -> (np.ndarray, Rect):
        rect = MyOpenCv.get_real_rect_by_percent_rect(img, percent_rect)
        return MyOpenCv.cut_picture(img, rect), rect

    @staticmethod
    def cut_picture(img: np.ndarray, input_rect: Rect) -> np.ndarray:
        rect = input_rect.to_array()
        return img[rect.top:rect.bottom, rect.left:rect.right]

    @staticmethod
    def extract_alpha(img: np.ndarray) -> np.ndarray:
        if MyOpenCv.get_channel_num(img) == 4:
            return img[:, :, 3]
        return img

    @staticmethod
    def extract_rgb(img: np.ndarray) -> np.ndarray:

        if MyOpenCv.get_channel_num(img) == 4:
            return img[:, :, 0:3]
        return img

    @staticmethod
    def get_channel_num(img: np.ndarray):
        if len(img.shape) == 3:
            channel = img.shape[2]
            return channel
        else:
            return 1

    @staticmethod
    def match_multi_pos(src_mat: np.ndarray, temp_mat: np.ndarray, threshold=0.9) -> List[tuple]:

        # res 返回一个长和宽为图片大小的二维矩阵，矩阵中的元素为：模板图片与原图片的匹配度。
        res, match_method = MyOpenCv.match_template(src_mat, temp_mat)
        # loc是两个numpy.ndarray组成的二维tuple，loc[0]可以获取所有x坐标，loc[1]可以获取所有y轴坐标
        if match_method == cv2.TM_SQDIFF_NORMED or match_method == cv2.TM_SQDIFF:
            threshold = 1 - threshold
            loc = np.where(res <= threshold)
        else:
            loc = np.where(res >= threshold)  # 返回满足要求的匹配度所对应的矩阵索引值，也就是图像坐标啦。

        loc_table = list([])  # 存储得到的所有匹配坐标
        # zip可以将tuple里的两个数组一一对应绑定在一起成为一个新的单位tuple组成的数组，每个数组中存储了x坐标和y坐标
        # *号使得生成的数组可以被迭代
        for pt in zip(*loc[::-1]):
            loc_table.append(pt)
        return loc_table

    @staticmethod
    def sobel(src_mat: np.ndarray, rect: Rect = None) -> np.ndarray:
        input_mat = src_mat.copy()
        if rect is not None:
            rect = rect.to_array()
            input_mat = input_mat[rect.top:rect.bottom, rect.left:rect.right]

        sobel_x = cv2.Sobel(input_mat, cv2.CV_16S, 1, 0, ksize=3)
        sobel_y = cv2.Sobel(input_mat, cv2.CV_16S, 0, 1, ksize=3)
        sobel_x = cv2.convertScaleAbs(sobel_x)
        sobel_y = cv2.convertScaleAbs(sobel_y)
        res_mat = cv2.addWeighted(sobel_x, 0.5, sobel_y, 0.5, 0)
        if rect is not None:
            input_mat = src_mat.copy()
            if len(input_mat.shape) >= 3:
                input_mat[rect.top:rect.bottom, rect.left:rect.right, :] = res_mat
            else:
                input_mat[rect.top:rect.bottom, rect.left:rect.right] = res_mat

            return input_mat

        return res_mat

    @staticmethod
    def __inner_match_single_score_and_pos(src_mat: np.ndarray, temp_mat: np.ndarray) -> \
            Tuple[float, Sequence[int, int]]:
        res, match_method = MyOpenCv.match_template(src_mat, temp_mat)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)
        if match_method == cv2.TM_SQDIFF_NORMED or match_method == cv2.TM_SQDIFF:
            return 1 - min_val, min_loc
        else:
            return max_val, max_loc

    @staticmethod
    def match_single_score_and_pos(src_mat: np.ndarray, temp_mat: np.ndarray) -> Tuple[float, Sequence[int, int]]:
        src_channel_num = MyOpenCv.get_channel_num(src_mat)
        temp_channel_num = MyOpenCv.get_channel_num(temp_mat)

        if src_channel_num == 4:
            src_mat = MyOpenCv.extract_rgb(src_mat)
            src_channel_num = 3

        if temp_channel_num == 4 and src_channel_num >= 3:
            score, loc = MyOpenCv.match_single_alpha_score_and_pos(src_mat, temp_mat)
        else:
            score, loc = MyOpenCv.__inner_match_single_score_and_pos(src_mat, temp_mat)
        return score, loc

    @staticmethod
    def match_single_score_and_post_many_times(src_mat: np.ndarray, temp_mat: np.ndarray, max_try_times: int,
                                               threshold: float) -> List[Tuple[float, Sequence[int, int]]]:
        src_with_black = src_mat.copy()
        w, h = MyOpenCv.get_image_size(temp_mat)
        signal_locs: List[Tuple[float, Sequence[int, int]]] = []  # : List[Tuple[int, int]]
        for _ in range(max_try_times):
            chosen_score, chosen_loc = MyOpenCv.match_single_score_and_pos(src_with_black, temp_mat)
            if chosen_score > threshold:
                signal_locs.append((chosen_score, chosen_loc))
                fill_rect = Rect(chosen_loc[0], chosen_loc[1], chosen_loc[0] + w, chosen_loc[1] + h)
                src_with_black = MyOpenCv.fill_black_to_src(src_with_black, fill_rect)
            else:
                break
        return signal_locs

    @staticmethod
    def match_single_alpha_score_and_pos(src_mat: np.ndarray, temp_mat: np.ndarray) -> Tuple[float, Sequence[int, int]]:
        score, loc = MyOpenCv.__inner_match_single_score_and_pos(src_mat, temp_mat)
        x1, y1 = loc
        x, y = MyOpenCv.get_image_size(temp_mat)
        x2 = x1 + x
        y2 = y1 + y
        cut_raw_img = MyOpenCv.cut_picture(src_mat, Rect(x1, y1, x2, y2))
        alpha_mat = MyOpenCv.extract_alpha(temp_mat)
        cut_raw_img = cut_raw_img[:, :, :3]
        alpha = alpha_mat.astype(np.float32) / 255.0
        alpha = np.expand_dims(alpha, axis=2)
        white_bg = np.ones_like(cut_raw_img, dtype=np.uint8) * 255
        cut_raw_img2 = (cut_raw_img.astype(np.float32) * alpha + white_bg.astype(np.float32) * (1 - alpha)).astype(
            np.uint8)
        b, g, r, a = cv2.split(temp_mat)
        zoom_bgr = cv2.merge([b, g, r])
        alpha_z = a.astype(np.float32) / 255.0
        alpha_z = np.expand_dims(alpha_z, axis=2)
        white_bg_z = np.ones_like(zoom_bgr, dtype=np.uint8) * 255
        zoom_image2 = (
                zoom_bgr.astype(np.float32) * alpha_z + white_bg_z.astype(np.float32) * (1 - alpha_z)).astype(
            np.uint8)
        score, _ = MyOpenCv.__inner_match_single_score_and_pos(cut_raw_img2, zoom_image2)
        return score, loc

    @staticmethod
    def match_template(src_mat: np.ndarray, temp_mat: np.ndarray) -> (np.ndarray, int):

        src_channel_num = MyOpenCv.get_channel_num(src_mat)
        temp_channel_num = MyOpenCv.get_channel_num(temp_mat)

        if src_channel_num == 4:
            src_mat = MyOpenCv.extract_rgb(src_mat)
            src_channel_num = 3

        if temp_channel_num == 4 and src_channel_num >= 3:
            '''模板图有4个通道,原始图有3个通道以上，使用mask匹配法'''
            match_method = cv2.TM_SQDIFF_NORMED  # TM_CCORR_NORMED
            alpha_mat = MyOpenCv.extract_alpha(temp_mat)
            temp_mat = MyOpenCv.extract_rgb(temp_mat)
            res = cv2.matchTemplate(src_mat, temp_mat, match_method, mask=np.repeat(alpha_mat[:, :, None], 3, axis=-1))
        elif temp_channel_num == 4 and src_channel_num < 3:
            '''模板图有4个通道,原始图有1个通道，使用mask+RGB2GRAY匹配法'''
            match_method = cv2.TM_SQDIFF_NORMED
            alpha_mat = MyOpenCv.extract_alpha(temp_mat)
            temp_mat = cv2.cvtColor(temp_mat, cv2.COLOR_RGBA2GRAY)
            res = cv2.matchTemplate(src_mat, temp_mat, match_method, mask=alpha_mat)
        elif temp_channel_num == src_channel_num:
            '''模板图有3个通道以下,与原始图通道相等，使用相关性匹配法'''
            match_method = cv2.TM_CCOEFF_NORMED
            res = cv2.matchTemplate(src_mat, temp_mat, match_method, None)
        else:
            '''模板图有3个通道以下,与原始图通道不相等，使用RGB2GRAY+相关性匹配法'''
            match_method = cv2.TM_CCOEFF_NORMED
            if src_channel_num > 1:
                src_mat = cv2.cvtColor(src_mat, cv2.COLOR_RGB2GRAY)
            if temp_channel_num > 1:
                temp_mat = cv2.cvtColor(temp_mat, cv2.COLOR_RGB2GRAY)
            res = cv2.matchTemplate(src_mat, temp_mat, match_method, None)
        return res, match_method

    @staticmethod
    def add_alpha_channel_if_needed(img: np.ndarray) -> np.ndarray:
        # 检查图像的通道数
        if img.shape[2] == 3:  # BGR 图像
            # 生成全不透明的 Alpha 通道 (255 表示完全不透明)
            alpha_channel = np.ones((img.shape[0], img.shape[1]), dtype=img.dtype) * 255

            # 将 BGR 图像和 Alpha 通道合并
            img = cv2.merge((img, alpha_channel))
        return img


class MainUI(MainUIBase):
    """继承tk.Frame的主窗口，master为窗口的父控件"""

    def __init__(self, main_loop_func: Callable[[MainUI], None], button_list=("开始", "播放游戏画面", "清空", "测试")):
        # 初始化Application的Frame部分
        # 设置窗口标题
        super().__init__(button_list)
        self.my_dll = MyDllLib.MyDll()
        self.my_dll.set_py_hook_proc(self.hook_proc)
        self.__key_code = 0
        self.__keyCodeSignal = threading.Event()
        self.__keyCodeSignal.clear()
        self.on_ctrl = False
        self.__on_alt = False
        self.__rect = Rect(0, 0, 0.2, 0.2)
        self.__user_key_code_callback: Callable[[int], bool] = None
        self.__user_key_code_realtime_callback: Callable[[MyDllLib.HookPackage], bool] = None
        self.left_button_down = False

        self.change_pause_mode(True)
        self.change_draw_mode()
        self.__main_loop_func = main_loop_func
        self.set_xml_on_select_callback(self.__on_tree_item_selected)

    def __on_tree_item_selected(self, item_text: str, item_values: Tuple):
        img2 = MyOpenCv.draw_rect(self.get_cache_img(), Rect(*self.format_bounds(item_values[-1])),
                                  rgb=(0, 0, 255, 255))
        self.show_image(img2, use_cache=False)
        self.show_text(f"Selected item: {item_text}, Values: {item_values}")

    def get_win_manager(self):
        return WinManager(self.my_dll, self._win_title, False)

    def set_user_key_code_callback(self, callback: Callable[[int], bool]):
        self.__user_key_code_callback = callback

    def set_user_key_code_realtime_callback(self, callback: Callable[[MyDllLib.HookPackage], bool]):
        self.__user_key_code_realtime_callback = callback

    def hook_proc(self, pk: MyDllLib.HookPackage) -> int:
        if self.__user_key_code_realtime_callback is not None:
            if self.__user_key_code_realtime_callback(pk):
                return 1

        if not pk.keyEventType:
            if pk.wParam == 0x0201:  # WM_LBUTTONDOWN
                self.left_button_down = True

            elif pk.wParam == 0x0202:  # WM_LBUTTONUP
                self.left_button_down = False
        if pk.code == 164:
            self.__on_alt = (pk.wParam == 260)
        elif pk.code == 162:  # ctrl
            self.on_ctrl = (pk.wParam == MyDllLib.WM_KEYDOWN)

        if pk.keyEventType and (pk.wParam == MyDllLib.WM_KEYDOWN or pk.wParam == 260):
            self.__key_code = pk.code
            self.__keyCodeSignal.set()
        return 1

    def key_code_callback_loop(self):
        while True:
            self.__keyCodeSignal.wait()
            self.__keyCodeSignal.clear()
            key_code = self.__key_code
            if self.__user_key_code_callback is not None:
                if self.__user_key_code_callback(key_code):
                    continue
            offset_y = 0
            offset_x = 0
            if self.on_ctrl:
                if key_code == 38:  #
                    offset_y = 0.01
                elif key_code == 37:  # 左
                    offset_x = 0.01
                elif key_code == 39:  # 右
                    offset_x = -0.01
                elif key_code == 40:  # 下
                    offset_y = -0.01
                self.__rect.zoom(offset_x, offset_y)
            else:
                if key_code == 38:  # 上
                    offset_y = -0.01
                elif key_code == 37:  # 左
                    offset_x = -0.01
                elif key_code == 39:  # 右
                    offset_x = 0.01
                elif key_code == 40:  # 下
                    offset_y = 0.01
                self.__rect.move_offset(offset_x, offset_y)

            if self.get_cache_img() is not None and (offset_y != 0 or offset_x != 0):
                rect = MyOpenCv.get_real_rect_by_percent_rect(self.get_cache_img(), self.__rect)
                img2 = MyOpenCv.draw_rect(self.get_cache_img(), rect)
                self.show_image(img2, str(self.__rect) + "\n" + str(rect), use_cache=False)

    def main_loop_entry_point(self):
        self.__main_loop_func(self)
        # self.my_dll.register_event_hook(1, True)
        # self.my_dll.register_event_hook(0, True)

    def myloop(self):
        start_thread(self.key_code_callback_loop, ())
        self.after(100, lambda: self.main_loop_entry_point())  # 创建窗口100毫秒后调用lambda函数模拟on_create窗口事件
        # StartThread(, (self, None))
        # 主循环开始
        while True:
            try:
                # self.my_dll.message_loop()
                self.mainloop()  # 正常主循环会卡在这里
                break  # 正常退出主窗口会跳出死循环
            except KeyboardInterrupt:  # 由于使用ctrl+c终端录屏进程时，主窗口进程也会中断，因此捕捉这个异常，让主循环重新启动
                print("重启UI")  # 捕捉异常时，app=None的代码没有正常运行而被跳过了，因此死循环不退出。
                break


class WinManager:
    WinManager = TypeVar('WinManager', bound='WinManager')

    def __init__(self, my_dll: MyDllLib.MyDll, win_name: str | int = "", use_process_name: bool = False,
                 class_name=None):
        self.myDll = my_dll

        self.width_scale, self.height_scale = self.myDll.calculate_screen_scale()
        if type(win_name) == int:
            hwnd = win_name
            self.win_name = ""
            self.myDll = my_dll
            self.hwnd = hwnd
            self.hdc = my_dll.my_get_window_dc(hwnd)

            return

        if class_name is not None:
            self.hwnd = my_dll.my_find_window_with_class_name(class_name, win_name)
        else:

            if use_process_name:
                if type(win_name) == str:
                    pid = my_dll.get_process_id_from_process_name(win_name)
                    print("pid:", pid)
                else:
                    pid = win_name
                self.hwnd = my_dll.my_find_window_by_process_id(pid)
            else:
                self.hwnd = my_dll.my_find_window(win_name)  # "sokit -- F1获取帮助"

        print("get hwnd", self.hwnd)
        if self.hwnd != 0:
            self.win_name = win_name
            self.hdc = my_dll.my_get_window_dc(self.hwnd)
        else:
            self.win_name = ""
            self.hdc = 0

    def refresh_window(self, percent_rect: Rect):
        if percent_rect is None:
            self.myDll.my_redraw_window(self.hwnd, None)
            return
        my_rect = self.from_percent_rect_get_real_rect(percent_rect)
        my_rect = self.scale_rect(my_rect)
        self.myDll.my_redraw_window(self.hwnd, my_rect.to_array())

    def start_capture_window(self, my_frame_event_callback: Callable[[PyImagePackage], int]):

        self.myDll.start_capture_window(self.hwnd, my_frame_event_callback)

    def set_foreground_window(self):
        self.myDll.my_set_foreground_window(self.hwnd)

    def set_top(self, is_top: bool):
        is_top_int = 1 if is_top else 0
        self.myDll.set_top(self.hwnd, is_top_int)

    def send_key_code(self, down: bool, key_code: int):
        self.myDll.send_key_down(down, key_code)

    def capture_window_with_other_manager(self, main_manager: WinManager) -> np.ndarray:
        return main_manager.capture_window(self.get_rect())

    def is_horizon_screen(self) -> bool:
        rect = self.get_rect()
        w, h = rect.get_size()
        return w > h

    def get_rect(self) -> Rect:
        rect_array = self.myDll.get_win_rect(self.hwnd)
        return Rect.from_array(rect_array)

    def move_window(self, rect: Rect, re_paint: bool = True):
        self.myDll.my_move_window(self.hwnd, rect.to_array(), re_paint)

    def capture_window(self, my_rect: Rect | None) -> np.ndarray:
        if my_rect is None:
            my_rect = self.get_rect()
            w, h = my_rect.get_size()
            my_rect = Rect(0, 0, w, h)
        h_bmp = self.myDll.copy_screen_to_bitmap(self.hwnd, self.hdc, my_rect.to_array())
        if h_bmp == 0:
            return np.zeros((800, 800, 4), dtype=ctypes.c_uint8)
        info = self.myDll.get_bmp_info(h_bmp)
        data = self.myDll.get_bmp_data(h_bmp, info)
        if data.shape[0] > 3:
            # data = cv2.cvtColor(data, cv2.COLOR_RGBA2BGRA)
            return data
        return np.zeros((800, 800, 4), dtype=ctypes.c_uint8)

    def click_point_with_wnd_percent(self, percent_x: float, percent_y: float, click: bool = True):
        rect = self.get_rect()
        middle_x = int(rect.left + rect.get_width() * percent_x)
        middle_y = int(rect.top + rect.get_height() * percent_y)
        self.myDll.set_cursor_pos(middle_x, middle_y)
        if click:
            self.myDll.send_mouse_down(True)
            time.sleep(0.01)
            self.myDll.send_mouse_down(False)
            time.sleep(0.01)

    def click_point_with_templates(self, temp: np.ndarray, loc: tuple, percent_x: float = 0.5, percent_y: float = 0.5,
                                   click: bool = True, button_num: int = 0, **kwargs):
        rect = self.get_rect()
        temp_shape = MyOpenCv.get_image_size(temp)
        middle_x = int(rect.left + loc[0] + temp_shape[0] * percent_x)
        middle_y = int(rect.top + loc[1] + temp_shape[1] * percent_y)
        self.myDll.set_cursor_pos(middle_x, middle_y)
        if click:
            self.myDll.send_mouse_down(True, button_num)
            time.sleep(0.01)
            self.myDll.send_mouse_down(False, button_num)
            time.sleep(0.01)

    def drag_mouse(self, delta_x: int, delta_y: int, div_num=20):
        self.myDll.send_mouse_down(True)
        time.sleep(0.01)
        x, y = self.myDll.get_cursor_pos()
        for i in range(div_num):
            self.myDll.set_cursor_pos(x + int(i * delta_x / div_num), y + int(i * delta_y / div_num))
            time.sleep(0.01)

        time.sleep(0.01)
        self.myDll.send_mouse_down(False)
        time.sleep(0.01)

    def from_percent_rect_get_real_rect(self, percent_rect: Rect):
        real_rect = Rect.from_percent_use_position_rect(self.get_rect(), percent_rect)
        return real_rect

    def scale_rect(self, rect: Rect) -> Rect:
        rect.left = rect.left / self.width_scale
        rect.right = rect.right / self.width_scale
        rect.top = rect.top / self.height_scale
        rect.bottom = rect.bottom / self.height_scale
        return rect

    def draw_text(self, percent_rect: Rect, lp_str, text_color: Tuple[int, int, int], back_color: Tuple[int, int, int],
                  hdc=None):
        if hdc is None:
            hdc = self.hdc
        real_rect = self.from_percent_rect_get_real_rect(percent_rect)
        real_rect = self.scale_rect(real_rect)
        MyDllLib.my_draw_text(hdc, real_rect.to_array(), lp_str, MyDllLib.rgb(*text_color),
                              MyDllLib.rgb(*back_color))

    def clear_draw(self, hdc=None):
        if hdc is None:
            hdc = self.hdc
        MyDllLib.clear_screen(hdc, self.get_rect().to_array())

    def my_draw_image(self, img: np.ndarray, hdc=None):
        if hdc is None:
            hdc = self.hdc

        height, width = img.shape[:2]
        img = cv2.resize(img, (int(width / self.width_scale), int(height / self.height_scale)))
        # image_bgra = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
        MyDllLib.my_draw_image(self.myDll, self.hwnd, hdc, img)

    def draw_rect(self, real_rect: Rect, color: Tuple[int, int, int], hdc=None, transparent=True):
        if hdc is None:
            hdc = self.hdc
        real_rect = self.scale_rect(real_rect)
        MyDllLib.my_draw_rect(hdc, real_rect.to_array(), color, transparent)

    def simulate_mouse_movement(self, delta_x: int = 500, deta_y: int = 0):
        self.myDll.simulate_mouse_movement(delta_x, deta_y)


class AndroidApp:
    def __init__(self, use_client: bool = False, device_name: str = "df044cd3"):
        self.client = None
        self.isRun = False
        self.use_client = use_client
        self.try_reconnect_client()
        self.now_index = 0

    def client_is_alive(self):
        return self.client is not None and self.client.running

    def try_reconnect_client(self):
        if self.use_client and (not self.client_is_alive()):
            self.client = None
            try:
                adb_device = adbutils.adb.device()
                adb = adbutils.adb_path()  # os.path.join(plugin_root, "adb.exe")
                cmd_str = "\"{}\" devices".format(adb)
                print(InteractiveCmd(cmd_str).get_collect_output())
                adb_device.forward("tcp:80", "tcp:9999")
                # 查看所有转发的端口
                forwards = adb_device.forward_list()
                print(f"当前转发列表: {forwards}")
                # 判断转发是否成功
                if any('tcp' in str(f) for f in forwards):
                    self.client = TcpClient(DefaultTcpClientHandler(), server_port=80)
                    print("tcp服务成功开启")
                else:
                    print("端口转发失败")
            except adbutils.AdbError as e:
                print(f"AndroidApp连接失败: {e}")

    def show_text(self, text: str):
        if self.client is not None:
            pk = PackageHeader.init_str_header(text, 1)
            self.client.async_queue_send_pk(pk)

    def show_image(self, img: np.ndarray, text: str = "default"):
        if self.client is not None:
            if text != "":
                img = MyOpenCv.draw_text(img, text)
            pk = PackageHeader.init_binary_header(image_to_binary(img))
            self.client.async_queue_send_pk(pk)
            # self.client.send_str(text)

    def stop_record(self):
        self.isRun = False
        time.sleep(2)

    def play_screen_record_on_phone(self, manager: WinManager,
                                    callback: Callable[[AndroidApp, np.ndarray], None] | None = None,
                                    use_win32=False):
        self.isRun = True
        if self.client is None and callback is None:  # 用户没有定义自己的回调函数，手机扩展屏没连上的时候直接退出
            return
        if use_win32:
            while self.isRun:
                img2 = manager.capture_window(None)
                self.show_image(img2)
                time.sleep(0.1)
        else:
            def default_callback(app: AndroidApp, img: np.ndarray):
                app.show_image(img)

            if callback is None:
                callback = default_callback

            def frame_arrive(pk: PyImagePackage) -> int:
                callback(self, pk.real_img_mat)
                return 1 if self.isRun else 0

            manager.start_capture_window(frame_arrive)


def main_loop(app: MainUI):
    app.show_image(WinManager(app.my_dll, "").capture_window(None))

    def temp():
        while True:
            res = ""
            max_size = random.randint(55, 70)
            for line in [f"{i}>超长文本:{random.randint(0, 100)}\n" for i in range(max_size)]:
                res += line
            app.show_text(res)
            time.sleep(1)

    start_thread(temp, ())
    return
    my_dll = app.my_dll
    MyFileEditor().log("脚本启动")
    WinManager(my_dll).get_rect()
    WinManager(my_dll).get_rect()
    # import VMPhonePatch
    # listener = VMPhonePatch.KeyCodeHookEventListener(app, my_dll)
    # listener.start()
    # myDll.MessageLoop()


if __name__ == '__main__':
    # MainUI(main_loop).myloop()

    def default_callback2(app: AndroidApp, img: np.ndarray):
        app.show_image(img)
        time.sleep(0.1)


    myDll = MyDllLib.MyDll()
    mat = WinManager(myDll, "").capture_window(None)

    # def callback(hdc):
    #     MyDllLib.mat2_h_bitmap(myDll, mat)
    #
    #
    # hh = myDll.create_transparent_window(0, 0, 300, 200, callback)
    # hd = myDll.my_get_window_dc(hh)
    # myDll.message_loop()
    wm = WinManager(myDll, "Blue Archive", class_name="UnityWndClass")  # "「空荧酒馆」原神地图" "云游戏辅助"
    # wm = WinManager(myDll, "Task Manager")
    print(wm.win_name)
    # mm = wm.capture_window(None)
    # cv2.imshow("", mm)
    # cv2.waitKey()
    # print(wm.get_rect())
    app2 = AndroidApp(True)
    app2.play_screen_record_on_phone(wm, default_callback2)
    myDll.message_loop()
