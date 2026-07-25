from __future__ import annotations  # 使用高级注解器，支持类成员方法返回自身类型
import os.path
import shutil
import time
import uuid
from collections import deque
from typing import Dict, List, TypeVar, Callable, Generic, Any
import pandas as pd
import re
import datetime
import json
import numpy as np
import hashlib
import random
import sys


def generate_uuid():
    # random_uuid = uuid.uuid4()
    random_string = str(random.getrandbits(128))
    return hashlib.md5(random_string.encode('utf-8')).hexdigest()


# 生成一个随机的 UUID
random_uuid = generate_uuid()


def kill():
    raise KeyboardInterrupt('我自己想退出')  # CTRL+C异常


def convert_to_underscore(camel_case):
    under_score = ""
    for char in camel_case:
        if char.isupper():
            under_score += char.lower()
        else:
            under_score += char
    return under_score


def to_sql_query(df: pd.DataFrame, sheet_name: str):
    key = df.keys()
    template = r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})"
    for i in range(0, len(df)):
        sql_code = "insert into " + sheet_name + " values("
        for j in range(0, len(key)):
            temp = str(df[key[j]][i])
            print(temp)
            mat = re.search(template, temp)
            if mat is not None:
                temp = mat.group(1)
                day = datetime.datetime.strptime(temp, '%Y-%m-%d')
                temp = "TO_DATE(\'" + day.strftime('%Y-%m-%d') + "\',\'yyyy-mm-dd\')"
            elif temp.__eq__("NaT"):
                temp = "\'\'"
            else:
                temp = "\'" + temp + "\'"
            sql_code = sql_code + temp
            if j != len(key) - 1:
                sql_code = sql_code + ","
        sql_code = sql_code + ");\n"
        with open(".\\Read_Excel.txt", "a") as f:
            f.write(sql_code)


def iter_convert_date_frame(my_map: Dict[str, Dict[str, Any]] | List[Dict[str, Any]]) -> pd.DataFrame:
    temp_dic: Dict[str, List[Any]] = {}
    aim_list = my_map
    if type(my_map) == dict:
        aim_list = list(my_map.values().__iter__().__reduce__()[1][0])

    for row in aim_list:
        # print(row.keys())
        for key in row.keys():
            if not temp_dic.__contains__(key):
                temp_dic[key] = []
            temp_dic[key].append(row[key])
    df = pd.DataFrame(temp_dic)
    return df


# extract Map from SubExcel limit with MainKey in MainExcel
def extract_map_from_sub_excel(excel_path: str, main_keys: list, main_map: Dict[str, Dict], my_filter=None,
                               sheet_name=0) -> \
        Dict[str, Dict]:
    if my_filter is None:
        my_filter = {}
    now_map = excel_convert_map(excel_path, main_keys, my_filter, sheet_name)
    remove_list = []
    for k in now_map.keys():
        if not main_map.__contains__(k):
            remove_list.append(k)
        else:
            old_row = main_map[k]
            now_map[k].update(old_row)

    for i in range(0, len(remove_list)):
        now_map.pop(remove_list[i])
    return now_map


def combine_key_name(row: Dict[str], main_keys: List[str]) -> str:
    res = ""
    for i in range(0, len(main_keys)):
        key = main_keys[i]
        res = res + str(row[key]) + "|"
    res = res[:-1]
    return res


def contain_dict(src_dict: Dict[str], aim_dict: Dict[str]) -> bool:
    res = True
    if len(aim_dict.keys()) > 0:
        for k in aim_dict.keys():
            if src_dict.__contains__(k) and src_dict[k].__contains__(aim_dict[k]):
                continue
            else:
                return False
    return res


def excel_convert_map(excel_path: str, main_keys: list, aim=None, sheet_name=0, remove_na=False) -> Dict[str, Dict]:
    if aim is None:
        aim = {}
    main_map = {}
    if excel_path.endswith(".csv"):
        try:
            df = pd.read_csv(excel_path, encoding='utf-8')
        except UnicodeDecodeError:
            try:
                df = pd.read_csv(excel_path, encoding='gbk')  # 中文Windows常用
            except UnicodeDecodeError:
                df = pd.read_csv(excel_path, encoding='gb2312')  # 中文编码
    else:
        df: pd.DataFrame = pd.read_excel(excel_path, sheet_name=sheet_name)
    if remove_na:
        df = df.fillna('')
    keys = df.keys()
    # print("主键字段为:")
    # for i in range(0, len(main_keys)):
    #     print(i, main_keys[i])
    # print("按行打印:")
    for i in range(0, df.shape[0]):
        row = dict(df.iloc[i])
        if contain_dict(row, aim):
            map_key = combine_key_name(row, main_keys)
            main_map[map_key] = row

    return main_map


def find_all_excel_sheet(excel_path: str):
    return pd.ExcelFile(excel_path).sheet_names


def write_csv(df: pd.DataFrame, csv_path: str):
    df.to_csv(csv_path)
    print("finish")


def write_excel_dic(df_dic: Dict[str, pd.DataFrame], output_xls_path: str):
    with pd.ExcelWriter(output_xls_path) as writer:  # doctest: +SKIP
        for sheet_name in df_dic.keys():
            df_dic[sheet_name].to_excel(writer, sheet_name=sheet_name)
    print("finish")


def write_excel(data_frame: pd.DataFrame, output_xls_path: str):
    if output_xls_path.endswith(".csv"):
        data_frame.to_csv(output_xls_path, index=False)  # 不将DataFrame的索引写入文件

    else:
        with pd.ExcelWriter(output_xls_path) as writer:  # doctest: +SKIP
            data_frame.to_excel(writer, sheet_name="Default")
    print("finish")


def read_txt(filename: str, read_all=False) -> List[str]:
    res = []
    if read_all:
        with open(filename, 'r', encoding='UTF-8') as f:
            return [f.read()]
    else:
        with open(filename, 'r', encoding='UTF-8') as f:
            lines = f.readlines()
            for each_line in lines:
                res.append(each_line.strip())
    return res


def write_to_txt(filename: str, content: str, option='w'):  # 'a+'
    with open(filename, option, encoding='UTF-8') as file_object:
        file_object.write(content)


class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.bool_):
            return bool(obj)
        return super().default(obj)


def write_to_json(filename: str, content):
    with open(filename, 'w', encoding='UTF-8') as file_object:
        json.dump(content, file_object, indent=4, ensure_ascii=False, cls=NumpyEncoder)


def read_json(filename: str):
    with open(filename, "r", encoding="utf-8") as f:
        json_txt = json.load(f)
        return json_txt


def example():
    Output_Path = "C:\\Users\\14094\\Downloads\\表格.xlsx"
    mainKey = ["id"]
    mainKeyMap = excel_convert_map("D:/收藏夹2.xlsx", mainKey)
    subKeyMap = excel_convert_map("D:/收藏夹.xlsx", mainKey)
    outKeyMap = {}
    for k2 in mainKeyMap:
        mainKeyMap[k2]['created'] = str(mainKeyMap[k2]['created'])
        outKeyMap[k2] = mainKeyMap[k2]
        if not subKeyMap.keys().__contains__(k2):
            print('mainKeyHas', mainKeyMap[k2]['title'])
    for k2 in subKeyMap:
        if not mainKeyMap.keys().__contains__(k2):
            print('subKeyHas', subKeyMap[k2]['title'])
            subKeyMap[k2]['created'] = str(subKeyMap[k2]['created'])
            outKeyMap[k2] = subKeyMap[k2]

    ddf2 = iter_convert_date_frame(outKeyMap)
    write_excel(ddf2, "D:/o.xls")


def my_find_all(pattern: str, content: str) -> List[tuple]:
    matches = re.finditer(pattern, content)
    res = []
    for match in matches:
        if match:
            res.append(match.groups())  # (1)
    return res


# 自定义函数
def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


if __name__ == '__main__':
    config_map = excel_convert_map("C:/Users/Benson/Desktop/ClaudeCodemcp/隐患排查结果总表.xls",
                                   ["分类", "隐患场景", "子场景"], remove_na=True)  # "序号",
    for key in config_map.keys():
        if config_map[key]["说明"].__contains__("已阅") or config_map[key]["说明"].__contains__("已知"):
            filename = key.replace("|", "-").replace("/", "_")
            print(filename)
            shutil.copy2("C:/Users/Benson/Desktop/ClaudeCodemcp/应用功能不足-弹性不足-组件依赖-未读写分离.docx",
                         f"C:/Users/Benson/Desktop/ClaudeCodemcp/screenshot/{filename}.docx")
    # write_to_json("C:/Users/Benson/Desktop/ClaudeCodemcp/隐患排查结果总表2.json", config_map)
    # jso = read_json("C:/Users/Benson/Desktop/ClaudeCodemcp/隐患排查结果总表.json")
    #
    # write_excel(iter_convert_date_frame(jso), "C:/Users/Benson/Desktop/ClaudeCodemcp/text.xlsx")
