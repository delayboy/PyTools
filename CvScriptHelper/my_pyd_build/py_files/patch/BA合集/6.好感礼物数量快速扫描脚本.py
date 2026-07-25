import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
from PIL import Image, ImageDraw, ImageFont, ImageTk
import numpy as np
import threading
import time
import csv
import os
import platform
import re
from ultralytics import YOLO
import easyocr
import requests
import json
from PyTools.MyAwesomeTool.pack_icons import IconStore, IconStoreSQLite

YOLO_MODEL_PATH = "yolo_model/best.pt"
ICON_ZIP = "icons.zip"
SCHALE_DATA_PATH = "data/"
CONFIDENCE_THRESHOLD = 0.2

DICT_RANK = {
    1: 0, 2: 15, 3: 45, 4: 75, 5: 110, 6: 145, 7: 180, 8: 220, 9: 260, 10: 300, 11: 360, 12: 450, 13: 555,
    14: 675, 15: 815, 16: 975, 17: 1155, 18: 1360, 19: 1590, 20: 1845, 21: 2130, 22: 2445, 23: 2790,
    24: 3165, 25: 3575, 26: 4020, 27: 4500, 28: 5020, 29: 5580, 30: 6180, 31: 6825, 32: 7515, 33: 8250,
    34: 9030, 35: 9860, 36: 10740, 37: 11670, 38: 12655, 39: 13695, 40: 14790, 41: 15945, 42: 17160,
    43: 18435, 44: 19770, 45: 21170, 46: 22635, 47: 24165, 48: 25765, 49: 27435, 50: 29175, 51: 30990,
    52: 32880, 53: 34845, 54: 36885, 55: 39005, 56: 41205, 57: 43485, 58: 45850, 59: 48300, 60: 50835,
    61: 53460, 62: 56175, 63: 58980, 64: 61875, 65: 64865, 66: 67950, 67: 71130, 68: 74410, 69: 77790,
    70: 81270, 71: 84855, 72: 88545, 73: 92340, 74: 96240, 75: 100250, 76: 104370, 77: 108600, 78: 112945,
    79: 117405, 80: 121980, 81: 126675, 82: 131490, 83: 136425, 84: 141480, 85: 146660, 86: 151965,
    87: 157395, 88: 162955, 89: 168645, 90: 174465, 91: 180420, 92: 186510, 93: 192735, 94: 199095,
    95: 205595, 96: 212235, 97: 219015, 98: 225940, 99: 233010, 100: 240225
}
ICON_SIZE = (40, 40)
SPECIAL_GIFT_NAME = "item_icon_favor_selection"
SPECIAL_GIFT_EXP = 60


class ImageCanvas(ctk.CTkFrame):
    def __init__(self, master):
        super().__init__(master, corner_radius=0)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.canvas.grid(row=0, column=0, sticky="nsew")

        self.pil_image = None
        self.ctk_image = None
        self.image_on_canvas = None

        self.canvas.bind("<ButtonPress-1>", self.start_pan)
        self.canvas.bind("<B1-Motion>", self.pan_image)
        if platform.system() == "Windows":
            self.canvas.bind("<MouseWheel>", self.zoom_image)
        elif platform.system() == "Darwin":  # macOS
            self.canvas.bind("<MouseWheel>", self.zoom_image)
        else:  # Linux
            self.canvas.bind("<Button-4>", lambda e: self.zoom_image(e, 1))
            self.canvas.bind("<Button-5>", lambda e: self.zoom_image(e, -1))

    def load_image(self, pil_image):
        self.pil_image = pil_image
        self.fit_image_to_canvas()

    def fit_image_to_canvas(self):
        if self.pil_image is None:
            return

        canvas_width = self.winfo_width()
        canvas_height = self.winfo_height()

        if canvas_width <= 1 or canvas_height <= 1:
            self.after(50, self.fit_image_to_canvas)
            return

        img_w, img_h = self.pil_image.size

        w_ratio = canvas_width / img_w
        h_ratio = canvas_height / img_h
        scale = min(w_ratio, h_ratio)

        new_w = int(img_w * scale)
        new_h = int(img_h * scale)

        self.display_image(self.pil_image.resize((new_w, new_h), Image.Resampling.LANCZOS))

    def display_image(self, resized_pil_image):
        self.canvas.delete("all")
        self.ctk_image = ImageTk.PhotoImage(resized_pil_image)

        canvas_width = self.winfo_width()
        canvas_height = self.winfo_height()

        x = (canvas_width - self.ctk_image.width()) // 2
        y = (canvas_height - self.ctk_image.height()) // 2

        self.image_on_canvas = self.canvas.create_image(x, y, anchor="nw", image=self.ctk_image)

    def start_pan(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def pan_image(self, event):
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    def zoom_image(self, event, direction=None):
        x = self.canvas.canvasx(event.x)
        y = self.canvas.canvasy(event.y)

        factor = 1.1
        if (event.delta < 0 if platform.system() in ["Windows", "Darwin"] else direction < 0):
            factor = 1 / factor

        bbox = self.canvas.bbox(self.image_on_canvas)
        if not bbox: return

        img_x1, img_y1, img_x2, img_y2 = bbox
        img_w = img_x2 - img_x1
        img_h = img_y2 - img_y1

        new_w = img_w * factor
        new_h = img_h * factor

        if new_w < 50 or new_h < 50:
            return

        resized_pil = self.pil_image.resize((int(new_w), int(new_h)), Image.Resampling.LANCZOS)
        self.ctk_image = ImageTk.PhotoImage(resized_pil)
        self.canvas.itemconfig(self.image_on_canvas, image=self.ctk_image)

        self.canvas.scale(self.image_on_canvas, x, y, factor, factor)


class InventoryAnalyzerApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.model = None
        self.reader = None
        self.font = None
        self.count_font = None
        self.load_models_and_resources()

        self.title("FavorInventory")
        self.geometry("1400x850")
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.image_paths = []
        self.processed_images = []
        self.all_analysis_results = {}
        self.integrated_results = {}
        self.current_image_index = 0

        # SchaleDB 数据
        self.favor_data = None
        self.students_data = None
        self.full_student_list = []  # 新增：用于存储完整的学生列表

        # ✅ 新增：初始化图标存储（一次性加载）
        if os.path.exists(ICON_ZIP):
            self.icon_store = IconStore(ICON_ZIP)
            # print(f"使用 ZIP 图标库: {self.icon_store.count} 个图标")
        else:
            self.icon_store = None
            print(f"警告: 未找到 {ICON_ZIP}，将回退到文件系统读取")

        self.create_widgets()
        if not self._load_schale_data():
            if messagebox.askyesno("数据缺失", "未找到SchaleDB数据文件。是否立即下载？"):
                threading.Thread(target=self._download_schale_data, daemon=True).start()
            return

    def _get_level_by_rank(self, value: int) -> tuple:
        for level in sorted(DICT_RANK.keys(), reverse=True):
            rank = DICT_RANK[level]
            if value >= rank:
                return level, value - rank
        return 0, 0

    def _download_schale_data(self):
        try:
            os.makedirs(SCHALE_DATA_PATH, exist_ok=True)
            headers = {"Accept-Language": "zh-CN,zh;q=0.9"}

            # 下载好感度物品数据
            url_items = "https://schaledb.com/data/zh/items.min.json"
            r_items = requests.get(url_items, headers=headers).json()
            favor = [item for item in r_items.values() if item["Category"] == "Favor"]
            with open(os.path.join(SCHALE_DATA_PATH, "favor.json"), "w", encoding="utf-8") as f:
                json.dump(favor, f, ensure_ascii=False, indent=4)

            # 下载学生数据
            url_students = "https://schaledb.com/data/zh/students.min.json"
            r_students = requests.get(url_students, headers=headers).json()
            with open(os.path.join(SCHALE_DATA_PATH, "students.json"), "w", encoding="utf-8") as f:
                json.dump(r_students, f, ensure_ascii=False, indent=4)

            self.after(0, self._load_schale_data)  # 加载下载好的数据
            self.after(0, lambda: messagebox.showinfo("成功", "SchaleDB数据已下载并加载完毕！"))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("下载失败", f"无法下载SchaleDB数据：\n{e}"))

    def _load_schale_data(self):
        favor_path = os.path.join(SCHALE_DATA_PATH, "favor.json")
        students_path = os.path.join(SCHALE_DATA_PATH, "students.json")
        if os.path.exists(favor_path) and os.path.exists(students_path):
            try:
                with open(favor_path, "r", encoding="utf-8") as f:
                    self.favor_data = json.load(f)
                with open(students_path, "r", encoding="utf-8") as f:
                    self.students_data = json.load(f)

                self.after(0, self._populate_student_combobox)  # 加载成功后填充下拉框
                return True
            except Exception as e:
                messagebox.showerror("加载错误", f"加载SchaleDB数据文件失败: {e}")
                return False
        return False

    def _populate_student_combobox(self):
        """填充学生选择下拉框"""
        if not self.students_data:
            return

        try:
            # 存储完整列表
            self.full_student_list = [f"{s['Name']} ({s['Id']})" for s in self.students_data.values()]
            self.full_student_list.sort()  # 按名称排序

            # 初始化下拉框
            self.combo_stu_select.configure(values=self.full_student_list, state="normal")

            # 尝试设置默认值
            default_student = "未花（泳装） (10122)"
            if default_student in self.full_student_list:
                self.combo_stu_select.set(default_student)
            elif self.full_student_list:
                self.combo_stu_select.set(self.full_student_list[0])

        except Exception as e:
            messagebox.showerror("错误", f"填充学生列表时出错: {e}")
            self.combo_stu_select.configure(state="disabled")

    def _filter_student_combobox(self, event=None):
        """根据输入过滤学生下拉框的选项"""
        try:
            current_text = self.combo_stu_select.get().lower()

            if not current_text:
                filtered_list = self.full_student_list
            else:
                filtered_list = [s for s in self.full_student_list if current_text in s.lower()]

            # 更新下拉列表，同时保留输入框的文本
            self.combo_stu_select.configure(values=filtered_list)
        except Exception:
            # 避免在UI销毁等过程中出现意外错误
            pass

    def _get_item_name_by_icon(self, icon: str):
        """通过图标文件名获取物品名称"""
        if not self.favor_data:
            return icon
        if icon == SPECIAL_GIFT_NAME:
            return "自选箱"
        for item in self.favor_data:
            if item["Icon"] == icon:
                return item["Name"]
        return icon

    def _calc_favor_exp_for_student(self, stu_id: str):
        """为指定学生计算所有好感度物品的EXP值"""
        if not self.favor_data or not self.students_data:
            return None

        student = self.students_data.get(str(stu_id))
        if not student:
            return None

        favor_item_tags = student.get("FavorItemTags", [])
        favor_item_unique_tags = student.get("FavorItemUniqueTags", [])

        # 返回一个字典，键是物品图标名(icon)，值是计算出的EXP
        exp_map = {}
        for item in self.favor_data:
            g = ["BC", "Bc", "ew"]  # 通用加成标签
            tags = item.get("Tags", [])
            stu_tags = set(favor_item_tags + favor_item_unique_tags + g)
            score = min(sum(1 for tag in tags if tag in stu_tags), 3)
            exp = item.get("ExpValue", 0) * (1 + score)
            exp_map[item["Icon"]] = exp
        return exp_map

    def load_models_and_resources(self):
        try:
            if not os.path.exists(YOLO_MODEL_PATH): raise FileNotFoundError(f"YOLO模型文件未找到: {YOLO_MODEL_PATH}")

            self.model = YOLO(YOLO_MODEL_PATH)
            self.reader = easyocr.Reader(['en'], gpu=True, model_storage_directory=os.path.abspath("./EasyOcrModel"))
            self.font = ImageFont.truetype("arial.ttf", 24)
            self.count_font = ImageFont.truetype("arial.ttf", 56)
        except Exception as e:
            messagebox.showerror("初始化失败", f"加载模型或资源时出错: {e}")
            self.destroy()

    def create_widgets(self):
        self.main_paned_window = tk.PanedWindow(self, orient=tk.HORIZONTAL, sashwidth=8, bg=self._apply_appearance_mode(
            ctk.ThemeManager.theme["CTkFrame"]["fg_color"]))
        self.main_paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        left_frame = ctk.CTkFrame(self.main_paned_window, fg_color="transparent")
        left_frame.grid_rowconfigure(1, weight=1)
        left_frame.grid_columnconfigure(0, weight=1)

        control_panel = ctk.CTkFrame(left_frame)
        control_panel.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 0))

        self.btn_select_image = ctk.CTkButton(control_panel, text="选择图片(可多选)", command=self.select_images)
        self.btn_select_image.pack(side="left", padx=5, pady=5)
        self.lbl_image_path = ctk.CTkLabel(control_panel, text="尚未选择图片", text_color="gray", wraplength=400)
        self.lbl_image_path.pack(side="left", padx=5, pady=5, expand=True, fill="x")
        self.btn_analyze = ctk.CTkButton(control_panel, text="开始分析", command=self.start_analysis_thread,
                                         state="disabled")
        self.btn_analyze.pack(side="left", padx=5, pady=5)

        image_container = ctk.CTkFrame(left_frame)
        image_container.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.image_canvas = ImageCanvas(image_container)
        self.image_canvas.pack(fill="both", expand=True)

        status_nav_bar = ctk.CTkFrame(left_frame)
        status_nav_bar.grid(row=2, column=0, sticky="ew", padx=10, pady=(0, 10))
        self.lbl_status = ctk.CTkLabel(status_nav_bar, text="准备就绪")
        self.lbl_status.pack(side="left", padx=10)
        self.progress_bar = ctk.CTkProgressBar(status_nav_bar, mode="indeterminate")
        self.btn_next_img = ctk.CTkButton(status_nav_bar, text="下一张 >", command=self.next_image, state="disabled",
                                          width=80)
        self.btn_next_img.pack(side="right", padx=5, pady=5)
        self.btn_prev_img = ctk.CTkButton(status_nav_bar, text="< 上一张", command=self.prev_image, state="disabled",
                                          width=80)
        self.btn_prev_img.pack(side="right", padx=5, pady=5)

        self.main_paned_window.add(left_frame, minsize=400, width=1300)

        right_frame = ctk.CTkFrame(self.main_paned_window, fg_color="transparent")
        self.main_paned_window.add(right_frame, minsize=300)

        self.tab_view = ctk.CTkTabview(right_frame)
        self.tab_view.pack(fill="both", expand=True, padx=10, pady=10)
        self.tab_view.add("当前图片结果")
        self.tab_view.add("整合统计结果")
        self.tab_view.set("当前图片结果")

        tab1 = self.tab_view.tab("当前图片结果")
        tab1.grid_rowconfigure(0, weight=1)
        tab1.grid_columnconfigure(0, weight=1)
        self.results_scroll_frame = ctk.CTkScrollableFrame(tab1, label_text="物品列表")
        self.results_scroll_frame.grid(row=0, column=0, sticky="nsew")
        self.results_scroll_frame.grid_columnconfigure(1, weight=1)

        tab2 = self.tab_view.tab("整合统计结果")
        tab2.grid_rowconfigure(2, weight=1)
        tab2.grid_columnconfigure(0, weight=1)

        top_control_frame = ctk.CTkFrame(tab2)
        top_control_frame.grid(row=0, column=0, rowspan=2, sticky="ew", padx=10, pady=10)
        top_control_frame.grid_columnconfigure(0, weight=1)

        input_frame = ctk.CTkFrame(top_control_frame, fg_color="transparent")
        input_frame.grid(row=0, column=0, sticky="nsew")
        input_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(input_frame, text="选择学生:").grid(row=0, column=0, padx=(0, 5), pady=(0, 5), sticky="w")
        self.combo_stu_select = ctk.CTkComboBox(input_frame, values=[], state="disabled")
        self.combo_stu_select.grid(row=0, column=1, padx=5, pady=(0, 5), sticky="ew")
        self.combo_stu_select.bind("<KeyRelease>", self._filter_student_combobox)

        ctk.CTkLabel(input_frame, text="自选箱数量:").grid(row=1, column=0, padx=(0, 5), pady=(5, 0), sticky="w")
        self.entry_special_gift = ctk.CTkEntry(input_frame)
        self.entry_special_gift.insert(0, "0")
        self.entry_special_gift.grid(row=1, column=1, padx=5, pady=(5, 0), sticky="ew")
        self.entry_special_gift.bind("<Return>", lambda e: self.recalculate_integrated_results())
        self.entry_special_gift.bind("<FocusOut>", lambda e: self.recalculate_integrated_results())

        button_frame = ctk.CTkFrame(top_control_frame)
        button_frame.grid(row=0, column=1, sticky="ns", padx=(10, 0))
        button_frame.grid_rowconfigure((0, 1), weight=1)  # Make buttons fill the height

        self.btn_calc_exp = ctk.CTkButton(button_frame, text="计算好感经验", command=self.run_exp_calculation,
                                          state="disabled")
        self.btn_calc_exp.grid(row=0, column=0, padx=5, pady=(0, 2))
        self.btn_export = ctk.CTkButton(button_frame, text="导出CSV", command=self.export_to_csv, state="disabled")
        self.btn_export.grid(row=1, column=0, padx=5, pady=(2, 0))

        self.integrated_results_scroll_frame = ctk.CTkScrollableFrame(tab2, label_text="总计结果")
        self.integrated_results_scroll_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.integrated_results_scroll_frame.grid_columnconfigure(1, weight=1)

        self.lbl_total_exp = ctk.CTkLabel(tab2, text="", font=ctk.CTkFont(size=16, weight="bold"))
        self.lbl_total_exp.grid(row=3, column=0, sticky="ew", padx=10, pady=10)

    def select_images(self):
        paths = filedialog.askopenfilenames(filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp")])
        if not paths: return

        self.image_paths = list(paths)
        self.lbl_image_path.configure(text=f"已选择 {len(self.image_paths)} 张图片")
        self.btn_analyze.configure(state="normal")
        self.btn_export.configure(state="disabled")

        self.clear_all_views()
        self.image_canvas.load_image(Image.open(self.image_paths[0]))

    def start_analysis_thread(self):
        if not self.image_paths: return
        self.btn_analyze.configure(state="disabled")
        self.btn_select_image.configure(state="disabled")
        self.btn_prev_img.configure(state="disabled")
        self.btn_next_img.configure(state="disabled")

        self.lbl_status.configure(text="准备开始分析...")
        self.progress_bar.pack(side="right", padx=10, fill="x", expand=True)
        self.progress_bar.start()

        threading.Thread(target=self.run_analysis, daemon=True).start()

    def run_analysis(self):
        processed_images_list = []
        per_image_results_dict = {}

        try:
            total_images = len(self.image_paths)
            for i, image_path in enumerate(self.image_paths):
                self.after(0, lambda i=i, total=total_images: self.lbl_status.configure(
                    text=f"正在分析第 {i + 1}/{total} 张图片..."))

                yolo_resp = self.model.predict(source=image_path, imgsz=640, save=False)[0]
                img = Image.open(image_path).convert("RGB")
                img_raw = img.copy()
                draw = ImageDraw.Draw(img)
                detected_results = []

                for box in yolo_resp.boxes:
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])
                    if conf < CONFIDENCE_THRESHOLD: continue

                    name = yolo_resp.names[cls]
                    label = f"{name}\n{conf:.2f}"
                    draw.rectangle([x1, y1, x2, y2], outline="red", width=3)
                    draw.text((x1, y1 - 25), label, fill="red", font=self.font)

                    tx1, ty1, tx2, ty2 = int(x1 + (x2 - x1) * 0.4), int(y1 + (y2 - y1) * 0.6), int(
                        x1 + (x2 - x1) * 1.1), int(y1 + (y2 - y1) * 1.1)
                    draw.rectangle([tx1, ty1, tx2, ty2], outline="blue", width=2)

                    img_crop = img_raw.crop((tx1, ty1, tx2, ty2))
                    number_text = self.perform_ocr(img_crop)

                    draw.text((tx2 - 70, ty1 - 30), number_text, fill="blue", font=self.count_font)
                    if number_text == "N/A":
                        continue
                    detected_results.append([name, number_text])

                processed_images_list.append(img)
                per_image_results_dict[image_path] = detected_results

            self.after(0, self.display_full_analysis_results, processed_images_list, per_image_results_dict)
        except Exception as e:
            import torch
            import torchvision
            print(f"PyTorch: {torch.__version__}")
            print(f"TorchVision: {torchvision.__version__}")
            print(f"CUDA available: {torch.cuda.is_available()}")
            print(f"CUDA version: {torch.version.cuda}")
            print(dir(torchvision.ops))  # 查看是否有 nms
            print(torchvision.ops.nms)   # 查看 nms 的信息
            # 测试简单的 NMS
            boxes = torch.tensor([[0, 0, 10, 10], [5, 5, 15, 15]], dtype=torch.float32).cuda()
            scores = torch.tensor([0.9, 0.8], dtype=torch.float32).cuda()

            try:
                indices = torchvision.ops.nms(boxes, scores, 0.5)
                print("NMS on GPU works!")
                print(indices)
            except Exception as e2:
                raise e2
           
            raise e
            self.after(0, self.analysis_failed, str(e))

    def perform_ocr(self, img_crop):
        result = self.reader.readtext(np.array(img_crop), allowlist='0123456789x')
        if result:
            for r in result:
                if r[1] and r[1].lower().startswith('x'): return r[1]
            return result[0][1]
        return "N/A"

    def display_full_analysis_results(self, processed_images, per_image_results):
        self.lbl_status.configure(text="分析完成！")
        self.progress_bar.stop()
        self.progress_bar.pack_forget()

        self.processed_images = processed_images
        self.all_analysis_results = per_image_results
        self.current_image_index = 0

        self.recalculate_integrated_results()
        self.show_image_and_results(self.current_image_index)

        self.btn_analyze.configure(state="normal")
        self.btn_select_image.configure(state="normal")
        if self.integrated_results:
            self.btn_export.configure(state="normal")
            self.btn_calc_exp.configure(state="normal")

    def analysis_failed(self, error_message):
        self.lbl_status.configure(text="分析失败。")
        self.progress_bar.stop()
        self.progress_bar.pack_forget()
        messagebox.showerror("分析错误", f"处理图像时发生错误:\n{error_message}")
        self.btn_analyze.configure(state="normal")
        self.btn_select_image.configure(state="normal")

    def clear_all_views(self):
        for widget in self.results_scroll_frame.winfo_children():
            widget.destroy()
        for widget in self.integrated_results_scroll_frame.winfo_children():
            widget.destroy()

        self.image_canvas.canvas.delete("all")
        self.processed_images.clear()
        self.all_analysis_results.clear()
        self.integrated_results.clear()
        self.lbl_total_exp.configure(text="")
        self.entry_special_gift.delete(0, 'end')
        self.entry_special_gift.insert(0, "0")
        self.btn_calc_exp.configure(state="disabled")

    def show_image_and_results(self, index):
        if not self.processed_images or not (0 <= index < len(self.processed_images)):
            return

        self.image_canvas.load_image(self.processed_images[index])
        self.lbl_image_path.configure(text=f"图片 {index + 1}/{len(self.image_paths)}")

        current_image_path = self.image_paths[index]
        results_for_current_image = self.all_analysis_results.get(current_image_path, [])
        self.populate_results_table(results_for_current_image)

        self.btn_prev_img.configure(state="normal" if index > 0 else "disabled")
        self.btn_next_img.configure(state="normal" if index < len(self.processed_images) - 1 else "disabled")

        self.current_image_index = index

    def next_image(self):
        if self.current_image_index < len(self.processed_images) - 1:
            self.show_image_and_results(self.current_image_index + 1)

    def prev_image(self):
        if self.current_image_index > 0:
            self.show_image_and_results(self.current_image_index - 1)

    def _load_icon_pil(self, icon_name: str):
        """统一加载图标 PIL Image"""
        if self.icon_store and self.icon_store.exists(icon_name):
            return self.icon_store.get_pil(icon_name)

        return None

    def populate_results_table(self, results):
        for widget in self.results_scroll_frame.winfo_children():
            widget.destroy()

        ctk.CTkLabel(self.results_scroll_frame, text="物品", font=ctk.CTkFont(weight="bold")).grid(row=0, column=0,
                                                                                                   padx=5, pady=2,
                                                                                                   sticky="w")
        ctk.CTkLabel(self.results_scroll_frame, text="数量", font=ctk.CTkFont(weight="bold")).grid(row=0, column=1,
                                                                                                   padx=5, pady=2,
                                                                                                   sticky="w")

        results.sort(key=lambda x: [int(c) if c.isdigit() else c.lower() for c in re.split('([0-9]+)', x[0])])

        for i, (original_name, quantity) in enumerate(results):
            icon_img_pil = self._load_icon_pil(original_name)
            display_name = self._get_item_name_by_icon(original_name)
            if icon_img_pil:
                try:
                    icon_img = ctk.CTkImage(icon_img_pil, size=ICON_SIZE)
                    item_widget = ctk.CTkLabel(self.results_scroll_frame, image=icon_img, text=display_name,
                                               compound="left", padx=5)
                except Exception:
                    item_widget = ctk.CTkLabel(self.results_scroll_frame, text=display_name)
            else:
                item_widget = ctk.CTkLabel(self.results_scroll_frame, text=display_name)

            item_widget.grid(row=i + 1, column=0, padx=5, pady=5, sticky="w")

            quantity_entry = ctk.CTkEntry(self.results_scroll_frame)
            quantity_entry.insert(0, quantity)
            quantity_entry.grid(row=i + 1, column=1, padx=5, pady=5, sticky="ew")

            quantity_entry.bind("<KeyRelease>",
                                lambda event, item_name=original_name, entry=quantity_entry: self.on_quantity_edited(
                                    item_name, entry))

    def on_quantity_edited(self, item_name, quantity_entry):
        new_quantity_str = quantity_entry.get()
        current_image_path = self.image_paths[self.current_image_index]

        results_list = self.all_analysis_results.get(current_image_path, [])
        for i, (name, _) in enumerate(results_list):
            if name == item_name:
                results_list[i][1] = new_quantity_str
                break

        self.recalculate_integrated_results()

    def recalculate_integrated_results(self):

        merged_data = {}
        for results_list in self.all_analysis_results.values():
            for name, quantity_str in results_list:
                try:
                    quantity = int(re.sub(r'\D', '', quantity_str))
                    current_max = merged_data.get(name, 0)
                    merged_data[name] = max(current_max, quantity)
                except (ValueError, TypeError):
                    continue

        try:
            special_gift_quantity = int(self.entry_special_gift.get())
        except (ValueError, AttributeError):
            special_gift_quantity = 0

        # 将特殊礼物添加到整合结果中，以便导出
        if special_gift_quantity > 0:
            merged_data[SPECIAL_GIFT_NAME] = special_gift_quantity

        # 排序时，确保特殊礼物总是在最前面
        sorted_items = sorted(merged_data.items(),
                              key=lambda item: (
                                  item[0] != SPECIAL_GIFT_NAME,  # False (0) for special gift, True (1) for others
                                  [int(c) if c.isdigit() else c.lower() for c in re.split('([0-9]+)', item[0])]
                              ))

        self.integrated_results = dict(sorted_items)

        self.populate_integrated_results_table()
        self.lbl_total_exp.configure(text="")  # 清空之前的计算结果

    def run_exp_calculation(self):
        """按钮点击后执行的函数，用于计算并显示EXP"""

        selected_student = self.combo_stu_select.get().strip()
        if not selected_student:
            messagebox.showwarning("输入错误", "请选择一名学生。")
            return

        # 从 "Name (Id)" 格式中提取ID
        match = re.search(r'\((\d+)\)$', selected_student)
        if not match:
            messagebox.showwarning("输入错误", "无效的学生选择格式。请从列表中选择。")
            return
        stu_id = match.group(1)

        exp_map = self._calc_favor_exp_for_student(stu_id)
        if exp_map is None:
            messagebox.showerror("错误", f"未找到学生ID: {stu_id}，请检查ID是否正确。")
            return

        detailed_results = []
        total_exp = 0

        # 首先处理特殊礼物
        try:
            special_gift_quantity = int(self.entry_special_gift.get())
        except ValueError:
            special_gift_quantity = 0

        if special_gift_quantity > 0:
            special_gift_total_exp = special_gift_quantity * SPECIAL_GIFT_EXP
            total_exp += special_gift_total_exp
            detailed_results.append({
                "name": SPECIAL_GIFT_NAME,
                "quantity": special_gift_quantity,
                "per_item_exp": SPECIAL_GIFT_EXP,
                "total_exp": special_gift_total_exp
            })

        # 然后处理其他礼物
        for name, quantity in self.integrated_results.items():
            if name == SPECIAL_GIFT_NAME:  # 跳过已处理的特殊礼物
                continue
            per_item_exp = exp_map.get(name, 0)  # name 应该是图标文件名
            item_total_exp = int(per_item_exp * quantity)
            total_exp += item_total_exp
            detailed_results.append({
                "name": name,
                "quantity": quantity,
                "per_item_exp": per_item_exp,
                "total_exp": item_total_exp
            })

        level, remain_exp = self._get_level_by_rank(total_exp)
        self.lbl_total_exp.configure(text=f"总经验值: {total_exp}  |  可达到: {level}级 + {remain_exp} EXP")

        self.populate_integrated_results_table(detailed_results)

    def populate_integrated_results_table(self, detailed_results=None):
        for widget in self.integrated_results_scroll_frame.winfo_children():
            widget.destroy()

        if detailed_results:
            # 显示详细计算结果
            ctk.CTkLabel(self.integrated_results_scroll_frame, text="物品", font=ctk.CTkFont(weight="bold")).grid(row=0,
                                                                                                                  column=0,
                                                                                                                  padx=5,
                                                                                                                  pady=2,
                                                                                                                  sticky="w")
            ctk.CTkLabel(self.integrated_results_scroll_frame, text="数量", font=ctk.CTkFont(weight="bold")).grid(row=0,
                                                                                                                  column=1,
                                                                                                                  padx=5,
                                                                                                                  pady=2,
                                                                                                                  sticky="w")
            ctk.CTkLabel(self.integrated_results_scroll_frame, text="单件EXP", font=ctk.CTkFont(weight="bold")).grid(
                row=0, column=2, padx=5, pady=2, sticky="w")
            ctk.CTkLabel(self.integrated_results_scroll_frame, text="总EXP", font=ctk.CTkFont(weight="bold")).grid(
                row=0, column=3, padx=5, pady=2, sticky="w")

            for i, result in enumerate(detailed_results):
                name = result["name"]
                icon_img_pil = self._load_icon_pil(name)
                name = self._get_item_name_by_icon(result["name"])
                if icon_img_pil:
                    try:
                        icon_img = ctk.CTkImage(icon_img_pil, size=ICON_SIZE)
                        item_widget = ctk.CTkLabel(self.integrated_results_scroll_frame, image=icon_img, text=name,
                                                   compound="left", padx=5)
                    except Exception:
                        item_widget = ctk.CTkLabel(self.integrated_results_scroll_frame, text=name)
                else:
                    item_widget = ctk.CTkLabel(self.integrated_results_scroll_frame, text=name)
                item_widget.grid(row=i + 1, column=0, padx=5, pady=5, sticky="w")

                ctk.CTkLabel(self.integrated_results_scroll_frame, text=str(result["quantity"])).grid(row=i + 1,
                                                                                                      column=1, padx=5,
                                                                                                      pady=5,
                                                                                                      sticky="w")
                ctk.CTkLabel(self.integrated_results_scroll_frame, text=f'{result["per_item_exp"]:.0f}').grid(row=i + 1,
                                                                                                              column=2,
                                                                                                              padx=5,
                                                                                                              pady=5,
                                                                                                              sticky="w")
                ctk.CTkLabel(self.integrated_results_scroll_frame, text=str(result["total_exp"])).grid(row=i + 1,
                                                                                                       column=3, padx=5,
                                                                                                       pady=5,
                                                                                                       sticky="w")

        else:
            # 仅显示基础的整合结果
            ctk.CTkLabel(self.integrated_results_scroll_frame, text="物品", font=ctk.CTkFont(weight="bold")).grid(row=0,
                                                                                                                  column=0,
                                                                                                                  padx=5,
                                                                                                                  pady=2,
                                                                                                                  sticky="w")
            ctk.CTkLabel(self.integrated_results_scroll_frame, text="最大数量", font=ctk.CTkFont(weight="bold")).grid(
                row=0, column=1, padx=5, pady=2, sticky="w")
            for i, (name, quantity) in enumerate(self.integrated_results.items()):
                icon_img_pil = self._load_icon_pil(name)
                name = self._get_item_name_by_icon(name)
                if icon_img_pil:
                    try:
                        icon_img = ctk.CTkImage(icon_img_pil, size=ICON_SIZE)
                        item_widget = ctk.CTkLabel(self.integrated_results_scroll_frame, image=icon_img, text=name,
                                                   compound="left", padx=5)
                    except Exception:
                        item_widget = ctk.CTkLabel(self.integrated_results_scroll_frame, text=name)
                else:
                    item_widget = ctk.CTkLabel(self.integrated_results_scroll_frame, text=name)
                item_widget.grid(row=i + 1, column=0, padx=5, pady=5, sticky="w")
                ctk.CTkLabel(self.integrated_results_scroll_frame, text=str(quantity), anchor="w").grid(row=i + 1,
                                                                                                        column=1,
                                                                                                        padx=5, pady=5,
                                                                                                        sticky="ew")

    def export_to_csv(self):
        if not self.integrated_results:
            messagebox.showwarning("无数据", "没有可导出的整合结果。")
            return

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        total_exp = self.lbl_total_exp.cget("text").replace("总经验值: ", "").split("  |  ")[
            0] if self.lbl_total_exp.cget("text") else "0"
        default_filename = f"inventory_{total_exp}_{timestamp}.csv"
        save_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            title="保存整合结果为CSV",
            initialfile=default_filename
        )
        if not save_path: return

        try:
            with open(save_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["item_name", "quantity"])
                for item_name, quantity in self.integrated_results.items():
                    writer.writerow([item_name, quantity])
            messagebox.showinfo("成功", f"整合结果已成功导出到:\n{save_path}")
        except Exception as e:
            messagebox.showerror("导出失败", f"无法写入CSV文件:\n{e}")


def main(patch_md5: str = None, patch_path: str = None):
    from PyTools.MyAwesomeTool.MyUtil import BaseScriptArranger, auto_patch_python
    if patch_md5 is None or patch_md5 == auto_patch_python(None, patch_path=patch_path):
        app = InventoryAnalyzerApp()
        app.mainloop()
        exit(0)
    else:
        time.sleep(1)
        print("等待正确的MD5 patch")

if __name__ == "__main__":
    app = InventoryAnalyzerApp()
    app.mainloop()
