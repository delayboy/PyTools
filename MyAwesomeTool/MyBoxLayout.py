"""轻量布局容器：HBox 横排 / VBox 竖排，带颜色边框"""
from __future__ import annotations  # 使用高级注解器，

import os.path
import tkinter as tk
from tkinter import ttk, filedialog
import re
from typing import Optional, List, TypeVar, Callable, Generic, Dict, Tuple, Sequence, Any, Union
import platform
from PIL import Image, ImageTk  # pillow型图片支持库
import numpy as np
import cv2
import tkinter.messagebox
import threading


class _BorderFrame(tk.Frame):
    """用 Canvas + inner Frame 模拟带颜色边框的容器，
    因为原生 ttk.Frame 不支持自定义边框颜色。"""

    def __init__(self, master: tk.Misc, border_color: str, border_width: int = 2, **kw):
        # 如果 kw 中没有 bg，则使用 master 的背景色
        if "bg" not in kw:
            kw["bg"] = master.cget("bg") if master.master else "SystemButtonFace"

        # 移除 kw 中的 bg（如果存在），避免重复
        bg = kw.pop("bg", master.cget("bg") if master.master else "SystemButtonFace")

        super().__init__(master, bg=border_color, bd=0, highlightthickness=0, **kw)
        self._border_width = border_width
        self._border_color = border_color
        # 内层 Frame，通过 pack 的 padx/pady 向内缩进，露出外层背景色作为边框
        self.inner = tk.Frame(self, bg=bg)
        self.inner.pack(fill=tk.BOTH, expand=True, padx=border_width, pady=border_width)

    @property
    def container(self) -> tk.Frame:
        """子控件应 pack / grid 到 container 上"""
        return self.inner


class HorizonBox(_BorderFrame):
    """横向排列容器，蓝色边框"""

    def __init__(self, master: tk.Misc, border_width: int = 2, spacing: int = 4,
                 border_color: str = "#3399FF", **kw):
        self._spacing = spacing
        super().__init__(master, border_color=border_color, border_width=border_width, **kw)
        self._col = 0
        self.grid(padx=10, pady=10, sticky="ew")

    def add(self, child: tk.Widget, **grid_kw) -> Any:
        """将 child 放入下一列，自动处理列间距"""
        self.container.columnconfigure(self._col, weight=grid_kw.pop("weight", 0))
        child.grid(in_=self.container, row=0, column=self._col, padx=(0 if self._col == 0 else self._spacing, 0),
                   **grid_kw)
        self._col += 1
        return child

    def add_stretch(self, weight: int = 1):
        """插入一个弹性空白列，用于推开后续控件或吸收多余空间"""
        col = self._col
        self.container.columnconfigure(col, weight=weight)
        spacer = tk.Frame(self.container, width=0)
        spacer.grid(in_=self.container, row=0, column=col)
        self._col += 1

    def grid(self, row=0, column=0, cnf=None, **kw) -> HorizonBox:
        self.grid_configure({} if cnf is None else cnf, row=row, column=column, **kw)
        return self


class VerticalBox(_BorderFrame):
    """纵向排列容器，红色边框"""

    def __init__(self, master: tk.Misc, border_width: int = 1, spacing: int = 6,
                 border_color: str = "#FF4444", **kw):
        self._spacing = spacing
        super().__init__(master, border_color=border_color, border_width=border_width, **kw)
        self._row = 0
        self.grid(padx=10, pady=10, sticky="ew")

    def add(self, child: tk.Widget, **grid_kw) -> Any:
        """将 child 放入下一行，自动处理行间距"""
        self.container.rowconfigure(self._row, weight=grid_kw.pop("weight", 0))
        child.grid(in_=self.container, row=self._row, column=0, pady=(0 if self._row == 0 else self._spacing, 0),
                   **grid_kw)
        self._row += 1
        return child

    def add_stretch(self, weight: int = 1):
        """插入一个弹性空行，用于吸收多余垂直空间"""
        row = self._row
        self.container.rowconfigure(row, weight=weight)
        spacer = tk.Frame(self.container, height=0)
        spacer.grid(in_=self.container, row=row, column=0)
        self._row += 1

    def grid(self, row=0, column=0, cnf=None, **kw) -> VerticalBox:
        self.grid_configure({} if cnf is None else cnf, row=row, column=column, **kw)
        return self


class SimpleButton(tk.Button):
    def __init__(self, text: str, master=None, cnf=None, **kw):
        super().__init__(master, {} if cnf is None else cnf, text=text, **kw)

    def set_button_callback(self, callback: Callable) -> SimpleButton:
        self.configure(command=callback)
        return self

    def grid(self, row=0, column=0, cnf=None, **kw) -> SimpleButton:
        self.grid_configure({} if cnf is None else cnf, row=row, column=column, **kw)
        return self

    def set_text(self, text: str):
        self.config(text=text)

    def get_text(self) -> str:
        return self.cget("text")


class SimpleTextView(tk.Text):
    def __init__(self, text: str, master=None, cnf=None, wrap=tk.WORD, height=10, width=50, **kw):
        super().__init__(master, {} if cnf is None else cnf, wrap=wrap, height=height, width=width, **kw)
        self.insert(tk.END, text)
        self.__text_var = tk.StringVar()
        self.__text_var.trace_add("write", self.__update_text_widget)

    def __update_text_widget(self, var_name, unknown, action="write"):
        start_index = self.index("@0,%d" % int(self.winfo_height() / 2))
        self.mark_set("insert", start_index)
        self.config(state=tk.NORMAL)
        self.delete(1.0, tk.END)
        self.insert(tk.END, self.getvar(var_name))
        self.see(start_index)
        self.mark_set("insert", start_index)

    def set_text(self, text: str):
        self.__text_var.set(text)

    def get_text(self) -> str:
        return self.get("1.0", tk.END)

    def grid(self, row=0, column=0, span=4, cnf=None, **kw) -> SimpleTextView:
        self.grid_configure({} if cnf is None else cnf, row=row, column=column, columnspan=span, **kw)
        return self


class XmlTableUI(tk.Frame):
    """Android XML布局树控件，封装Treeview+Scrollbar+节点操作逻辑"""

    def __init__(self, master=None, on_select: Callable[[str, Tuple], None] = None, **kwargs):
        super().__init__(master, **kwargs)
        self.__on_select = on_select

        self.__tree = ttk.Treeview(self, height=14)
        self.__tree.grid(row=0, column=0)

        self.__tree["columns"] = ("Xpath", "Txt", "Bounds")
        self.__tree.column("#0", width=200, anchor="w")
        self.__tree.column("Xpath", width=100)
        self.__tree.column("Txt", width=150)
        self.__tree.column("Bounds", width=150)

        self.__tree.heading("#0", text="ID")
        self.__tree.heading("Xpath", text="xpath")
        self.__tree.heading("Txt", text="文本")
        self.__tree.heading("Bounds", text="坐标")

        self.__tree.bind("<<TreeviewSelect>>", self.__on_item_selected)
        self.__tree.bind("<Control-c>", self.__copy_selected)
        self.__h_scrollbar = ttk.Scrollbar(self, orient=tk.HORIZONTAL, command=self.__tree.xview)
        self.__h_scrollbar.grid(row=1, column=0, sticky=tk.EW)
        self.__v_scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.__tree.yview)
        self.__v_scrollbar.grid(row=0, column=1, sticky=tk.NS)
        self.__tree.configure(xscrollcommand=self.__h_scrollbar.set, yscrollcommand=self.__v_scrollbar.set)

    def __copy_selected(self, event=None):
        """复制所有选中节点的信息到剪贴板（多行文本）"""
        selected_items = self.__tree.selection()
        if not selected_items:
            return

        lines = [f"[ID]\t[Xpath]\t[文本]\t[坐标]"]
        for item in selected_items:
            text = self.__tree.item(item, "text")
            values = self.__tree.item(item, "values")  # (xpath, txt, bounds)
            # 可根据需要调整格式，这里用制表符 \t 分隔，方便粘贴到表格
            lines.append(f"{text}\t{values[0]}\t{values[1]}\t{values[2]}")

        # 用换行符拼接所有行
        content = "\n".join(lines)

        # 写入剪贴板
        self.clipboard_clear()
        self.clipboard_append(content)
        # 可选：打印提示或播放提示音
        # print(f"已复制 {len(selected_items)} 个节点")

    def add_item(self, root_id: str, name: str, xpath: str = "", txt: str = "", bounds: str = "") -> str:
        sub_ele = self.__tree.insert(root_id, "end", text=name, values=(xpath, txt, bounds))
        return sub_ele

    def has_items(self) -> bool:
        return len(self.__tree.get_children()) > 0

    def clear(self):
        for item in self.__tree.get_children():
            self.__tree.delete(item)

    def expand_all(self):
        for item in self.__tree.get_children():
            self.__tree.item(item, open=True)
            self.__expand_children(item)

    def __expand_children(self, parent: str):
        for child in self.__tree.get_children(parent):
            self.__tree.item(child, open=True)
            self.__expand_children(child)

    def __on_item_selected(self, event):
        if self.__on_select is None:
            return
        selected_item = self.__tree.selection()[0]
        item_values = self.__tree.item(selected_item, "values")
        item_text = self.__tree.item(selected_item, "text")
        self.__on_select(item_text, item_values)

    def set_on_select_callback(self, on_select: Callable[[str, Tuple], None]):
        self.__on_select = on_select


class ImageMultiCanvas(tk.Frame):
    """多图显示控件，封装Canvas+Scrollbar+图像缩放显示逻辑，支持鼠标滚轮缩放和拖拽（仅row=0）"""

    def __init__(self, master, width=600, height=700, **kwargs):
        super().__init__(master, **kwargs)
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self.__mouse_in_canvas = False
        self.__width = width
        self.__height = height

        # 固定标题 Label
        self.__title_label = tk.Label(self, text="Image Panel", anchor="w",
                                      font=("微软雅黑", 18))
        self.__title_label.grid(row=0, column=0, sticky="ew")

        self.__canvas = tk.Canvas(self, width=width, height=height, highlightthickness=0)
        self.__canvas.grid(row=1, column=0, sticky="nsew")

        self.__scrollbar = tk.Scrollbar(self, orient=tk.VERTICAL, command=self.__canvas.yview)
        self.__scrollbar.grid(row=1, column=1, sticky=tk.NS)
        self.__canvas.config(yscrollcommand=self.__scrollbar.set)

        # row=0 缩放专用状态
        self.__canvas_image_id = None
        self.__photo0: ImageTk.PhotoImage | None = None
        self.__original_pil: Image.Image | None = None

        # row>=1 使用 LabelFrame 承载
        self.__img_frame = tk.LabelFrame(self.__canvas, text='')
        self.__frame_window_id = self.__canvas.create_window((0, 0), window=self.__img_frame, anchor="nw")
        self.__photos_tail: List[ImageTk.PhotoImage] = []
        self.__image_labels: List[tk.Label] = []

        # 鼠标滚轮绑定
        if platform.system() == "Windows":
            self.__canvas.bind("<MouseWheel>", self.__on_mouse_wheel)
        elif platform.system() == "Darwin":
            self.__canvas.bind("<MouseWheel>", self.__on_mouse_wheel)
        else:
            self.__canvas.bind("<Button-4>", lambda e: self.__on_mouse_wheel(e, 1))
            self.__canvas.bind("<Button-5>", lambda e: self.__on_mouse_wheel(e, -1))

        self.__canvas.bind("<Enter>", self.__on_enter)
        self.__canvas.bind("<Leave>", self.__on_leave)

        # 拖拽绑定
        self.__canvas.bind("<ButtonPress-1>", self.__start_pan)
        self.__canvas.bind("<B1-Motion>", self.__pan_image)

    # ── 公开接口 ──

    def show_image(self, img_array: np.ndarray, show_text: str = "", row=0):
        """显示图像到指定行；row=0 支持滚轮缩放和拖拽"""
        title_text = "Image Panel:{}".format(show_text)
        pil_image = self.__array_to_pil(img_array)

        if row == 0:
            self.__title_label.config(text=title_text)
            self.__photo0 = ImageTk.PhotoImage(pil_image)
            if self.__canvas_image_id is not None:
                self.__canvas.delete(self.__canvas_image_id)
            self.__canvas_image_id = self.__canvas.create_image(0, 0, anchor="nw", image=self.__photo0)
            # 确保 canvas image 在 LabelFrame 之下（z-order）
            if len(self.__image_labels) > 0:
                self.__canvas.tag_lower(self.__canvas_image_id)
            # LabelFrame 紧跟图片下方
            img_h = pil_image.size[1]
            self.__canvas.coords(self.__frame_window_id, 0, img_h)
        else:
            self.__title_label.config(text=title_text)
            while len(self.__image_labels) < row - 1 + 1:
                idx = len(self.__image_labels)
                label = tk.Label(self.__img_frame)
                label.grid(row=idx, column=0)
                self.__image_labels.append(label)
                self.__photos_tail.append(None)

            label_idx = row - 1
            photo = ImageTk.PhotoImage(pil_image)
            self.__image_labels[label_idx].__setitem__("imag", photo)
            self.__photos_tail[label_idx] = photo

        self.__update_scroll()

    # ── 图像预处理 ──
    @staticmethod
    def __get_channel_num(img: np.ndarray):
        if img.shape.__len__() == 3:
            channel = img.shape[2]
            return channel
        else:
            return 1

    def __array_to_pil(self, img_array: np.ndarray) -> Image.Image:
        """np.ndarray -> PIL.Image，自动缩放到 600 以内"""
        h, w = img_array.shape[0:2]
        zoom_scale_h = zoom_scale_w = 1.0
        if w > self.__width:
            zoom_scale_w = self.__width / w
        if h > self.__width:
            zoom_scale_h = self.__height / h
        zoom_scale = min(zoom_scale_h, zoom_scale_w)

        if self.__get_channel_num(img_array) >= 3:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
        y, x = img_array.shape[0:2]
        zoom_image = cv2.resize(img_array, (int(x * zoom_scale), int(y * zoom_scale)))
        self.__original_pil = Image.fromarray(img_array)
        return Image.fromarray(zoom_image)

    # ── 滚轮缩放（仅 row=0） ──

    def __on_mouse_wheel(self, event, direction=None):
        if not self.__mouse_in_canvas:
            return

        if self.__canvas_image_id is None or self.__original_pil is None:
            self.__scroll_canvas(event)
            return

        x = self.__canvas.canvasx(event.x)
        y = self.__canvas.canvasy(event.y)

        factor = 1.1
        is_zoom_out = (event.delta < 0) if platform.system() in ("Windows", "Darwin") \
            else (direction is not None and direction < 0)
        if is_zoom_out:
            factor = 1 / factor

        bbox = self.__canvas.bbox(self.__canvas_image_id)
        if not bbox:
            return

        img_x1, img_y1, img_x2, img_y2 = bbox
        new_w = (img_x2 - img_x1) * factor
        new_h = (img_y2 - img_y1) * factor
        if new_w < 50 or new_h < 50:
            return
        self.__width = new_w

        resized_pil = self.__original_pil.resize((int(new_w), int(new_h)), Image.Resampling.LANCZOS)
        self.__photo0 = ImageTk.PhotoImage(resized_pil)
        self.__canvas.itemconfig(self.__canvas_image_id, image=self.__photo0)
        self.__canvas.scale(self.__canvas_image_id, x, y, factor, factor)
        # 缩放后更新滚动区域，否则横向拖拽无法生效
        self.__update_scroll()

    def __scroll_canvas(self, event):
        min_line, max_line = self.__canvas.yview()
        if abs(max_line - min_line) < 1:
            self.__canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    # ── 拖拽平移 ──

    def __start_pan(self, event):
        self.__canvas.scan_mark(event.x, event.y)

    def __pan_image(self, event):
        self.__canvas.scan_dragto(event.x, event.y, gain=1)

    # ── 内部工具 ──

    def __update_scroll(self):
        self.__img_frame.update_idletasks()
        self.__canvas.config(scrollregion=self.__canvas.bbox("all"))

    def __on_enter(self, event):
        self.__mouse_in_canvas = True

    def __on_leave(self, event):
        self.__mouse_in_canvas = False


class MainUIBase(tk.Tk):
    """顶部工具栏控件：按钮组 + 文本显示区"""

    def __init__(self, button_list=("开始", "播放游戏画面", "清空", "测试")):
        # 初始化Application的Frame部分
        # 设置窗口标题
        super().__init__()
        # self.columnconfigure(4, weight=1)  # 意思是「窗口多余的水平空间全部交给第 4 列去吸收」
        self._win_title = 'python黑客工具箱'
        self.title(self._win_title)
        self.Pause = True  # change to False Auto
        self.Render = False
        # 设置窗体大小
        self.geometry('1200x700+850+0')
        # 在最顶层的父类窗口中可以截取窗口关闭事件，以运行窗口退出时希望实现的方法closeWindow
        self.protocol('WM_DELETE_WINDOW', self.close_window)
        self.option_add("*Font", "微软雅黑")
        self.grid()
        self.__simple_button_dic: Dict[str, SimpleButton] = {}
        # sticky="ew"表示让控件在东西向水平方向上拉伸
        top_hbox = HorizonBox(self, border_width=1).grid(row=0, column=0, padx=10, pady=10, sticky="ew")
        vbox = top_hbox.add(VerticalBox(self))
        # 创建顶部工具栏
        hbox = vbox.add(HorizonBox(self, border_width=0))
        hbox.add_stretch()  # 插入空白保持美观
        for button_name in button_list:
            self.__simple_button_dic[button_name] = hbox.add(SimpleButton(text=button_name))
        self.set_simple_button_callback(self.change_pause_mode, "开始")
        self.set_simple_button_callback(self.change_draw_mode, "播放游戏画面")
        self.set_simple_button_callback(self.delete_all_tree, "清空")
        hbox.add_stretch()  # 插入空白保持美观

        self.__text_view = vbox.add(SimpleTextView("这是一个很长的文字注释，可以滚动查看..."))
        # 创建XML布局树控件
        self.__xml_table = vbox.add(XmlTableUI())

        # 创建多图显示控件
        self.__image_canvas: ImageMultiCanvas = top_hbox.add(ImageMultiCanvas(self, width=1200, height=700))

        self.__cache_img: np.ndarray = None
        self.__pauseSignal = threading.Event()
        self.__pauseSignal.clear()

    def set_simple_button_callback(self, callback: Callable[[], None], button_name: str = "测试"):
        self.get_simple_button(button_name).set_button_callback(callback)

    def get_simple_button(self, button_name: str) -> SimpleButton:
        if not self.__simple_button_dic.__contains__(button_name):
            self.__simple_button_dic[button_name] = SimpleButton(button_name)
        return self.__simple_button_dic[button_name]

    def show_text(self, text: str):
        self.__text_view.set_text(text)

    def get_text(self) -> str:
        return self.__text_view.get_text()

    def close_window(self):
        # 当窗口被关闭时，调用这个方法
        self.destroy()  # 销毁窗口控件总容器
        print("windows close")
        # raise KeyboardInterrupt("windows close")
        # exit(-1)

    def change_pause_mode(self, value: bool = None):
        if value is None:
            self.Pause = not self.Pause
        else:
            self.Pause = value
        self.get_simple_button("开始").set_text("开始" if self.Pause else "暂停")
        print(f"Change Pause {self.Pause}")
        self.__pauseSignal.set()

    def wait_pause_signal(self):
        self.__pauseSignal.clear()
        self.__pauseSignal.wait()

    def change_draw_mode(self):
        self.Render = not self.Render
        self.get_simple_button("播放游戏画面").set_text("暂停游戏画面" if self.Render else "播放游戏画面")
        print(f"Change Render {self.Render}")
        self.__pauseSignal.set()

    def set_xml_on_select_callback(self, on_select: Callable[[str, Tuple], None]):
        self.__xml_table.set_on_select_callback(on_select)

    def delete_all_tree(self):
        self.__xml_table.clear()

    def expend_all_tree(self):
        self.__xml_table.expand_all()

    def add_to_tree(self, root_id: str, name: str, xpath: str = "", txt: str = "", bounds: str = "") -> str:
        return self.__xml_table.add_item(root_id, name, xpath, txt, bounds)

    def show_image(self, img_array: np.ndarray, show_text: str = "", row=0, use_cache=True, add_to_summery=False):
        if use_cache:
            self.__cache_img = img_array
        self.__image_canvas.show_image(img_array, show_text, row)

    def get_cache_img(self) -> np.ndarray:
        return self.__cache_img

    def set_top(self, is_top: bool):
        if is_top:
            self.attributes('-topmost', 1)  # 将窗口置顶
        else:
            self.attributes('-topmost', 0)  # 将窗口置顶

    """参考Python指导文档：Tk图形用户界面(GUI) » tkinter.messagebox"""

    @staticmethod
    def show_message_box(text="Are you sure"):
        # tkinter.messagebox.askquestion(title=None, message=None, *, type=YESNO, **options)
        # tkinter.messagebox.askokcancel(title=None, message=None, **options)
        # tkinter.messagebox.askretrycancel(title=None, message=None, **options)
        # tkinter.messagebox.askyesno(title=None, message=None, **options)
        # tkinter.messagebox.askyesnocancel(title=None, message=None, **options)
        return tk.messagebox.askyesno("黑客工具箱确认框", text)

    @staticmethod
    def format_bounds(bounds) -> Tuple[int, int, int, int]:
        if not bounds or not bounds.__contains__("["):
            return 0, 0, 0, 0
        lx, ly, rx, ry = map(int, re.findall(r"\d+", bounds))
        return lx, ly, rx, ry

    @staticmethod
    def ask_file_path(is_dir: bool = False, save: bool = False) -> Union[Tuple[str, ...], str]:
        if is_dir:
            file_path = filedialog.askdirectory(initialdir=os.path.abspath("./"))  # 获取输出文件夹啊的路径
        else:
            if save:
                file_path = filedialog.asksaveasfilename(defaultextension=".txt",
                                                         filetypes=[('文本文件', '*.txt'), ("All Files", "*.*")])
            else:
                file_path = filedialog.askopenfilenames(
                    filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp"), ("All Files", "*.*")])
        return file_path


def ask_choice(title: str, message: str, options: list[str], default: str = None) -> str | None:
    """弹出带下拉选择的确认框，返回选中的值；点取消返回 None。"""
    root = tk.Tk()
    # root.withdraw()  # 隐藏主窗口
    dialog = tk.Toplevel()
    dialog.title(title)
    dialog.resizable(False, False)
    dialog.grab_set()  # 模态：阻塞父窗口

    result = None

    tk.Label(dialog, text=message, font=("微软雅黑", 12)).pack(padx=20, pady=(15, 10))

    var = tk.StringVar(value=default or (options[0] if options else ""))
    combo = ttk.Combobox(dialog, textvariable=var, values=options, state="readonly", width=30)
    combo.pack(padx=20, pady=5)

    def on_ok():
        nonlocal result
        result = var.get()
        dialog.destroy()
        root.destroy()

    def on_cancel():
        dialog.destroy()

    btn_frame = tk.Frame(dialog)
    btn_frame.pack(pady=(10, 15))
    tk.Button(btn_frame, text="确定", width=8, command=on_ok).pack(side=tk.LEFT, padx=5)
    tk.Button(btn_frame, text="取消", width=8, command=on_cancel).pack(side=tk.LEFT, padx=5)

    dialog.protocol("WM_DELETE_WINDOW", on_cancel)
    # 居中于父窗口
    dialog.transient(dialog.master)
    dialog.wait_window()

    return result


def example():
    root = tk.Tk()
    root.title("Box Layout Demo")
    root.geometry("400x300")

    # 修改这里：gap -> spacing, padding -> border_width
    hbox = HorizonBox(root, spacing=6, border_width=1)
    hbox.grid(row=0, column=0, padx=10, pady=10, sticky="ew")

    for text in ["开始", "暂停", "清空", "测试"]:
        hbox.add(tk.Button(hbox, text=text))

    # 修改这里：gap -> spacing, padding -> border_width
    vbox = VerticalBox(root, spacing=6, border_width=6)
    vbox.grid(row=1, column=0, padx=10, pady=10, sticky="ew")

    for text in ["上", "中", "下"]:
        vbox.add(tk.Button(vbox, text=text))

    root.mainloop()


if __name__ == '__main__':
    print(MainUIBase.ask_file_path(False, True))
