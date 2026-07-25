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
# from ultralytics import YOLO
import easyocr
import requests
import json
from io import BytesIO
from PyTools.MyAwesomeTool.PyUseCPlus import MyOpenCv, cv2, Rect
from PyTools.MyAwesomeTool.Read_Excel import iter_convert_date_frame, write_csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from PyTools.MyAwesomeTool.pack_icons import IconStore, IconStoreSQLite

YOLO_MODEL_PATH = "best.pt"
ICON_PATH = "icons/"
ICON_ZIP = "icons.zip"
DB_FILE = "icons.db"
SCHALE_DATA_PATH = "data/"
CONFIDENCE_THRESHOLD = 0.921

ICON_SIZE = (40, 40)
SPECIAL_GIFT_NAME = "item_icon_favor_selection"


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
        self.equipment_data = None

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

            # 下载装备数据:   https://schaledb.com/images/equipment/icon/equipment_icon_hairpin_tier10_piece.webp
            url_students = "https://schaledb.com/data/zh/equipment.min.json"
            r_equipment = requests.get(url_students, headers=headers).json()
            with open(os.path.join(SCHALE_DATA_PATH, "equipment.json"), "w", encoding="utf-8") as f:
                json.dump(r_equipment, f, ensure_ascii=False, indent=4)

            for key in r_equipment:
                item = r_equipment[key]
                item_name = item["Icon"]
                item_url = f"https://schaledb.com/images/equipment/icon/{item_name}.webp"
                # 如何下载item_url文件？到os.path.join(ICON_PATH, f"{item_name}.png")下保存成png格式图片
                # 下载 webp 图片
                response = requests.get(item_url, headers=headers)
                response.raise_for_status()  # 检查请求是否成功
                # 用 Pillow 打开图像并转换为 PNG
                img = Image.open(BytesIO(response.content))
                # 保存为 PNG
                save_path = os.path.join(ICON_PATH, f"{item_name}.png")
                img.save(save_path, "PNG")
                print(f"保存图片:{save_path}")

            self.after(0, self._load_schale_data)  # 加载下载好的数据
            self.after(0, lambda: messagebox.showinfo("成功", "SchaleDB数据已下载并加载完毕！"))
        except Exception as e:
            self.after(0, lambda: messagebox.showerror("下载失败", f"无法下载SchaleDB数据：\n{e}"))
            raise e

    def _load_schale_data(self):
        favor_path = os.path.join(SCHALE_DATA_PATH, "favor.json")
        equipment_path = os.path.join(SCHALE_DATA_PATH, "equipment.json")
        if os.path.exists(favor_path) and os.path.exists(equipment_path):
            try:
                with open(favor_path, "r", encoding="utf-8") as f:
                    self.favor_data = json.load(f)
                with open(equipment_path, "r", encoding="utf-8") as f:
                    self.equipment_data = json.load(f)
                return True
            except Exception as e:
                messagebox.showerror("加载错误", f"加载SchaleDB数据文件失败: {e}")
                return False
        return False

    def _get_item_name_by_icon(self, icon: str):
        if icon.startswith("item_"):
            """通过图标文件名获取物品名称"""
            if not self.favor_data:
                return icon
            if icon == SPECIAL_GIFT_NAME:
                return "自选箱"
            for item in self.favor_data:
                if item["Icon"] == icon:
                    return item["Name"]
        elif icon.startswith("equipment_"):
            for key in self.equipment_data:
                item = self.equipment_data[key]
                if item["Icon"] == icon:
                    return f"T-{item['Tier']}-{item['Name']}-{item['Category']}"

        return icon

    def load_models_and_resources(self):
        try:
            # if not os.path.exists(YOLO_MODEL_PATH): raise FileNotFoundError(f"YOLO模型文件未找到: {YOLO_MODEL_PATH}")
            # self.model = YOLO(YOLO_MODEL_PATH)
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

        button_frame = ctk.CTkFrame(top_control_frame)
        button_frame.grid(row=0, column=1, sticky="ns", padx=(10, 0))
        button_frame.grid_rowconfigure((0, 1), weight=1)  # Make buttons fill the height

        self.btn_export = ctk.CTkButton(button_frame, text="导出CSV", command=self.export_to_csv, state="disabled")
        self.btn_export.grid(row=1, column=0, padx=5, pady=(2, 0))

        self.integrated_results_scroll_frame = ctk.CTkScrollableFrame(tab2, label_text="总计结果")
        self.integrated_results_scroll_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self.integrated_results_scroll_frame.grid_columnconfigure(1, weight=1)

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

    def process_item(self, raw_img, key, item):
        item_name = str(item["Icon"])
        if item_name.endswith("_piece"):
            # ✅ 改为从 icon_store 获取 OpenCV 格式图片
            temp_mat = self.icon_store.get_cv(f"{item_name}.png", -1)
            if temp_mat is None:
                return None
            zoom_scale = 1.14
            x, y = MyOpenCv.get_image_size(temp_mat)
            raw_w, raw_h = MyOpenCv.get_image_size(raw_img)
            if raw_w > 2398:  # 说明是手机大屏截图
                zoom_scale = 1.31

            if raw_w > 1900:  # 删除一半冗余截图
                raw_img = MyOpenCv.cut_picture(raw_img, Rect.from_percent(raw_w, raw_h, Rect(0.4, 0, 1.0, 1.0)))
            zoom_image = cv2.resize(temp_mat, (int(x * zoom_scale), int(y * zoom_scale)))
            score, loc = MyOpenCv.match_single_score_and_pos(raw_img, zoom_image)
            x1, y1 = loc
            x, y = MyOpenCv.get_image_size(zoom_image)
            x2 = x1 + x
            y2 = y1 + y
            cut_raw_img = MyOpenCv.cut_picture(raw_img, Rect(x1, y1, x2, y2))
            alpha_mat = MyOpenCv.extract_alpha(zoom_image)
            cut_raw_img = cut_raw_img[:, :, :3]
            alpha = alpha_mat.astype(np.float32) / 255.0
            alpha = np.expand_dims(alpha, axis=2)
            white_bg = np.ones_like(cut_raw_img, dtype=np.uint8) * 255
            cut_raw_img2 = (cut_raw_img.astype(np.float32) * alpha + white_bg.astype(np.float32) * (1 - alpha)).astype(
                np.uint8)
            b, g, r, a = cv2.split(zoom_image)
            zoom_bgr = cv2.merge([b, g, r])
            alpha_z = a.astype(np.float32) / 255.0
            alpha_z = np.expand_dims(alpha_z, axis=2)
            white_bg_z = np.ones_like(zoom_bgr, dtype=np.uint8) * 255
            zoom_image2 = (
                    zoom_bgr.astype(np.float32) * alpha_z + white_bg_z.astype(np.float32) * (1 - alpha_z)).astype(
                np.uint8)
            score, _ = MyOpenCv.match_single_score_and_pos(cut_raw_img2, zoom_image2)
            # cv2.imshow("im", MyOpenCv.show_single_match_pic(raw_img, zoom_image, score, loc))
            # cv2.waitKey()
            return item_name, score, x1, y1, x2, y2
        return None

    def _suppress_overlapping_boxes(self, boxes, overlap_threshold=0.5):
        if not boxes:
            return []

        sorted_boxes = sorted(boxes, key=lambda b: b[1], reverse=True)

        kept = []
        for box in sorted_boxes:
            _, score, x1, y1, x2, y2 = box
            discard = False
            for kept_box in kept:
                _, _, kx1, ky1, kx2, ky2 = kept_box

                ix1 = max(x1, kx1)
                iy1 = max(y1, ky1)
                ix2 = min(x2, kx2)
                iy2 = min(y2, ky2)

                inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
                if inter == 0:
                    continue

                area = (x2 - x1) * (y2 - y1)
                kept_area = (kx2 - kx1) * (ky2 - ky1)
                smaller = min(area, kept_area)
                if inter / smaller > overlap_threshold:
                    discard = True
                    break

            if not discard:
                kept.append(box)

        print(f"NMS: {len(boxes)} -> {len(kept)} boxes (threshold={overlap_threshold})")
        return kept

    def run_analysis(self):
        processed_images_list = []
        per_image_results_dict = {}

        try:
            total_images = len(self.image_paths)
            for i, image_path in enumerate(self.image_paths):
                self.after(0, lambda i=i, total=total_images: self.lbl_status.configure(
                    text=f"正在分析第 {i + 1}/{total} 张图片..."))

                # yolo_resp = self.model.predict(source=image_path, imgsz=640, save=False)[0]

                img = Image.open(image_path).convert("RGB")
                img_raw = img.copy()
                detected_results = []
                raw_img = MyOpenCv.cv_imread(image_path)

                # 使用线程池
                boxes = []
                with ThreadPoolExecutor(max_workers=8) as executor:
                    futures = {executor.submit(self.process_item, raw_img, key, item): key for key, item in
                               self.equipment_data.items()}
                    # futures = {self.process_item(raw_img, key, item): key for key, item in
                    #            self.equipment_data.items()}
                    for future in as_completed(futures):
                        result = future.result()
                        if result is not None:
                            boxes.append(result)
                            print(result[0], result[1])  # print item_name, score

                boxes = self._suppress_overlapping_boxes(boxes)

                raw_w, raw_h = MyOpenCv.get_image_size(raw_img)
                if raw_w > 1900:  # 说明是大屏截图
                    img_raw = Image.fromarray(
                        MyOpenCv.cut_picture(raw_img, Rect.from_percent(raw_w, raw_h, Rect(0.4, 0, 1.0, 1.0))))
                    img = img_raw.copy()
                draw = ImageDraw.Draw(img)
                for box in boxes:
                    name, conf, x1, y1, x2, y2 = box

                    if conf < CONFIDENCE_THRESHOLD: continue
                    label = f"{name}\n{conf:.2f}"
                    draw.rectangle((x1, y1, x2, y2), outline="red", width=3)
                    draw.text((x1, y1 - 25), label, fill="red", font=self.font)

                    tx1, ty1, tx2, ty2 = int(x1 + (x2 - x1) * 0.4), int(y1 + (y2 - y1) * 0.6), int(
                        x1 + (x2 - x1) * 1.1), int(y1 + (y2 - y1) * 1.1)
                    draw.rectangle((tx1, ty1, tx2, ty2), outline="blue", width=2)

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
            self.after(0, self.analysis_failed, str(e))
            raise e

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

        # ──────── 改动点3: UI 图标显示（辅助方法）────────

    def _load_icon_pil(self, icon_name: str):
        """统一加载图标 PIL Image"""
        if self.icon_store and self.icon_store.exists(icon_name):
            return self.icon_store.get_pil(icon_name)
        # 回退：尝试从文件系统读取
        icon_file = os.path.join(ICON_PATH, f"{icon_name}.png")
        if os.path.exists(icon_file):
            try:
                return Image.open(icon_file)
            except Exception:
                return None
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
                except Exception as e:
                    print(e)
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

        # 排序时，确保特殊礼物总是在最前面
        sorted_items = sorted(merged_data.items(),
                              key=lambda item: (
                                  item[0] != SPECIAL_GIFT_NAME,  # False (0) for special gift, True (1) for others
                                  [int(c) if c.isdigit() else c.lower() for c in re.split('([0-9]+)', item[0])]
                              ))

        self.integrated_results = dict(sorted_items)

        self.populate_integrated_results_table()

    def populate_integrated_results_table(self, detailed_results=None):
        for widget in self.integrated_results_scroll_frame.winfo_children():
            widget.destroy()

        # 仅显示基础的整合结果
        ctk.CTkLabel(self.integrated_results_scroll_frame, text="物品", font=ctk.CTkFont(weight="bold")).grid(
            row=0, column=0, padx=5, pady=2, sticky="w")
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
                except Exception as e:
                    print(e)
                    item_widget = ctk.CTkLabel(self.integrated_results_scroll_frame, text=name)
            else:
                item_widget = ctk.CTkLabel(self.integrated_results_scroll_frame, text=name)
            item_widget.grid(row=i + 1, column=0, padx=5, pady=5, sticky="w")
            ctk.CTkLabel(self.integrated_results_scroll_frame, text=str(quantity), anchor="w").grid(
                row=i + 1, column=1, padx=5, pady=5, sticky="ew")

    def export_to_csv(self):
        if not self.integrated_results:
            messagebox.showwarning("无数据", "没有可导出的整合结果。")
            return

        timestamp = time.strftime("%Y%m%d_%H%M%S")

        default_filename = f"inventory_{timestamp}.csv"
        save_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")],
            title="保存整合结果为CSV",
            initialfile=default_filename
        )
        if not save_path: return

        try:
            res_list = [
                {"Tier": "T" + str(i), "_hat_": 0, "_gloves_": 0, "_shoes_": 0, "_bag_": 0, "_badge_": 0,
                 "_hairpin_": 0,
                 "_charm_": 0, "_watch_": 0, "_necklace_": 0} for
                i in range(11)]
            for item_name, quantity in self.integrated_results.items():
                name = self._get_item_name_by_icon(item_name)
                top_which = 1
                type_name = ""
                for i in range(2, 11):
                    if name.__contains__("T-" + str(i) + "-"):
                        top_which = i
                        break
                for type_n in ["_hat_", "_gloves_", "_shoes_", "_bag_", "_badge_", "_hairpin_", "_charm_", "_watch_",
                               "_necklace_"]:
                    if item_name.__contains__(type_n):
                        type_name = type_n
                        break
                if type_n.__eq__(""):
                    print("未找到合适的匹配项", item_name)
                res_list[top_which][type_name] = quantity

            ddf2 = iter_convert_date_frame(res_list)
            write_csv(ddf2, save_path)
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
