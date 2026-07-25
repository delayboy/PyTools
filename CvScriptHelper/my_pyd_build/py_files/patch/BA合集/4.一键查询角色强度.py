from PyTools.MyAwesomeTool.Read_Excel import excel_convert_map, read_json, iter_convert_date_frame, write_excel
import requests
from PyTools.MyAwesomeTool.PyUseCPlus import cv2, MyOpenCv, Rect, MainUI, auto_patch_python
import numpy as np
import easyocr
import os
import re


def extract_digits_from_image(reader, cut_img):
    """
    从 cut_img 中 OCR 识别并提取唯一的连续多位数字。
    :return: 字符串形式的数字；识别失败时返回 ""
    """
    print("正在进行 OCR 识别...")
    result = reader.readtext(cut_img)
    if not result:
        print("未识别到任何文本。")
        return ""
    # 调试日志：打印全部识别内容
    print("\n========== 识别结果 ==========")
    for (bbox, text, prob) in result:
        print(f"文本: {text} \t(置信度: {prob:.4f})")
    print("==============================")
    all_text = "".join(item[1] for item in result)
    all_text = all_text.replace("O", "0").replace("o", "0").replace("h", "1")
    matches = re.findall(r"\d+\([A-Za-z]+\)", all_text)

    if not matches:
        return ""

    # 优先选最长的连续数字片段
    digits_str = max(matches, key=len)
    print(f"最终提取数字: {digits_str}")
    return digits_str


def download_image(url: str):
    # 构造请求头，添加 Referer 和 User-Agent 防止防盗链拦截
    headers = {
        "Referer": "https://www.gamekee.com/",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    print("正在下载图片数据...")
    try:
        # 1. 获取图片数据到内存
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()  # 检查是否请求成功 (200)

        # 2. 将二进制数据转换为 OpenCV 图像格式 (不落地存本地)
        # np.frombuffer 将字节流转为 numpy 数组
        # cv2.imdecode 从内存中的图像数据解码图像
        image_array = np.frombuffer(response.content, np.uint8)
        image = cv2.imdecode(image_array, cv2.IMREAD_COLOR)
        return image
    except Exception as e:
        raise e


def ocr_image_from_url(url: str, reader):
    try:
        image = download_image(url)
        if image is None:
            print("图片解码失败，可能是图片格式损坏或被拦截。")
            return
        cut_img, _ = MyOpenCv.cut_picture_with_percent(image, Rect(0.8, 0.0, 1.0, 0.2))
        res = extract_digits_from_image(reader, cut_img)
        if res.__eq__(""):
            cut_img, _ = MyOpenCv.cut_picture_with_percent(image, Rect(0.6, 0.0, 0.9, 0.2))
            res = extract_digits_from_image(reader, cut_img)
        if res.__eq__(""):
            cv2.imshow("im", cut_img)
            cv2.waitKey()
            cv2.imshow("im", image)
            cv2.waitKey()
            res = str(input("警告：未提取到任何数字字符！请手动输入匹配结果:"))
        return res

    except requests.exceptions.RequestException as e:
        print(f"网络请求失败，发生错误: {e}")
    except Exception as e:
        print(f"发生未知错误: {e}")


def download_student_score():
    print("正在加载 OCR 模型 (首次运行需下载模型，请耐心等待)...")
    ocr_reader = easyocr.Reader(['en'], gpu=True, model_storage_directory=os.path.abspath("./EasyOcr"))
    student_map = read_json("学生评分视图.json")
    out_dic = {}
    for i, student_name in enumerate(student_map.keys()):
        # if not student_name.__eq__("小玉"):
        #     continue
        src_link = student_map[student_name]
        score = ocr_image_from_url(src_link, ocr_reader)
        print(i, student_name, score, src_link)
        # 优先选最长的连续数字片段
        score_num = max(re.findall(r"\d+", score), key=len)
        score_level = score.replace(score_num, "")
        student_name = student_name.replace("（", "(").replace("）", ")").replace(" ", "")
        out_dic[student_name] = {"学生": student_name, "评分": int(score_num),
                                 "评级": score_level}
        # break

    write_excel(iter_convert_date_frame(out_dic), "学生评分表.xlsx")


def merge_score_to_equipment_table():
    score_map = excel_convert_map("学生评分表.xlsx", ["学生"])
    res_map = excel_convert_map("蔚蓝档案装备刷图升级规划计算V6.3-260416.xlsx", ["学生"], sheet_name="原始-学生数据")
    name_map = {"庚": "鹿江", "丽": "莱伊", "茜": "朱音", "茜(兔女郎)": "朱音(兔女郎)", "桃": "桃井",
                "桃(女仆)": "桃井(女仆)", "茜(制服)": "朱音(制服)", "瞬(小)": "瞬(幼女)"}
    for i, student_dic in enumerate(res_map.values()):
        student_name = str(student_dic['学生']).replace("邦妮", "兔女郎") \
            .replace("武装", "临战").replace("露营", "野营").replace("新年", "正月").replace("便服", "私服")
        student_name = student_name.replace("真里奈", "玛丽娜").replace("爱露", "阿露").replace("纯子", "淳子") \
            .replace("爱理", "爱莉").replace("风香", "枫香").replace("花江", "花绘").replace("芽瑠", "梅露").replace(
            "绮罗罗", "绮良良").replace("春香", "遥香").replace("瑠海", "瑠美").replace(
            "丽奈", "蕾娜")
        student_name = student_name.replace("（", "(").replace("）", ")").replace(" ", "")
        if name_map.__contains__(student_name):
            student_name = name_map[student_name]
        if not score_map.__contains__(student_name):
            print(i, student_name, student_dic)
        else:
            student_dic['评分'] = score_map[student_name]['评分']
            student_dic['评级'] = score_map[student_name]['评级']
            score_map.pop(student_name)
    write_excel(iter_convert_date_frame(res_map), "学生装备表.xlsx")
    print(score_map)


def main_loop(app: MainUI):
    stu_map = read_json("学生评分视图.json")
    stu_map = {key.replace("（", "(").replace("）", ")").replace(" ", ""): stu_map[key] for key in stu_map.keys()}
    stu_list_str = '\n'.join([key for key in stu_map.keys()])
    def button_callback():
        stu_name = app.get_text().split("\n")[0].replace(" ", "")
        if stu_map.__contains__(stu_name):
            print(stu_name)
            stu_link = stu_map[stu_name]
            stu_img = download_image(stu_link)
            app.show_image(stu_img)
    app.show_text(stu_list_str)
    app.set_simple_button_callback(button_callback)
    app.show_message_box("点击【测试】按钮获取角色评分版")

def main(patch_md5: str = None, patch_path: str = None):
    if patch_md5 is None or patch_md5 == auto_patch_python(None, patch_path=patch_path):
        MainUI(main_loop).myloop()
        exit(0)
    else:
        time.sleep(1)
        print("等待正确的MD5 patch")

if __name__ == '__main__':
    MainUI(main_loop).myloop()
