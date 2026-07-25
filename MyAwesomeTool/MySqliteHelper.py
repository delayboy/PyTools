import sqlite3
import time
from PyTools.MyAwesomeTool.MyGptHelper import ChatGLM
from typing import List, Tuple, TypeVar, Callable, Generic


def format_str(s: str) -> str:
    escape_dict = {
        '\n': '\n',
        '\t': '\t',
        '\r': '\r',
        '\\': '\\',
        '\'': "''",
        '\"': '\"'
    }
    return ''.join(escape_dict.get(c, c) for c in s)


def concat_key(keys: list) -> str:
    res = ''
    for param in keys:
        res += param + ','
    res = res[:-1]
    return res


def concat_pairs(dic: dict, div: str, main_key_list: list | None = None) -> str:
    res = ''
    index = 1
    div_str = " {} ".format(div)
    if main_key_list is None:
        main_key_list = dic.keys()
    for key in main_key_list:
        value = dic[key]
        if value is not None:
            res += key + "="
            res += "'{}'".format(format_str(value)) + div_str
    if len(res) > 1:
        res = res[:-len(div_str)]
    return res


def concat_value(keys: list) -> str:
    res = "('"
    for param in keys:
        if param is not None:
            res += format_str(param) + "','"
        else:
            res += "','"
    if len(res) > 3:
        res = res[:-3]
    res = res + "')"
    return res


def select_sql_str(db_name: str, keys: list) -> str:
    key_str = concat_key(keys)
    sql = f'SELECT {key_str} FROM {db_name}'
    return sql


def insert_sql_str(db_name: str, dic: dict) -> str:
    key_list = []
    value_list = []
    for key in dic.keys():
        key_list.append(key)
        value_list.append(dic[key])

    params = concat_key(key_list)
    values = concat_value(value_list)
    sql = f'INSERT INTO {db_name} ({params}) VALUES {values}'
    return sql


def update_sql_str(db_name: str, dic: dict, main_keys: list) -> str:
    pairs = concat_pairs(dic, ",")
    where_pairs = concat_pairs(dic, "and", main_keys)
    sql = f'UPDATE {db_name} SET {pairs} WHERE {where_pairs}'
    return sql


class MySqliteHelper:
    def __init__(self, file_path: str):
        self.filePath = file_path
        self.conn = sqlite3.connect(file_path)  # 连接数据库

        self.col_names = self.get_has_what_table_dic()

    def get_has_what_table_dic(self) -> dict:
        sql = "SELECT * FROM sqlite_master WHERE type = 'table';"  # SQLite语句（查询数据）
        rows = self.execute(sql)
        table_name = [row[1] for row in rows]
        # 获取表的列名（字段名），保存在col_names列表,每个表的字段名集为一个元组
        col_names = {}
        for single_table_name in table_name:
            col_name = self.execute('PRAGMA table_info({})'.format(single_table_name))
            col_name = [x[1] for x in col_name]
            col_names[single_table_name] = col_name
        return col_names

    def insert(self, db_name: str, dic: dict):
        sql = insert_sql_str(db_name, dic)
        return self.execute(sql, False)

    def update(self, db_name: str, dic: dict, main_keys: list):
        sql = update_sql_str(db_name, dic, main_keys)
        return self.execute(sql, False)

    def select(self, db_name: str, keys: list) -> List[dict]:
        sql = select_sql_str(db_name, keys)
        col_name = self.col_names[db_name]
        rows = self.execute(sql)
        res = []
        for line in rows:
            dic = {}
            for i in range(len(line)):
                dic[col_name[i]] = line[i]
            res.append(dic)
        return res

    def execute(self, sql: str, read: bool = True) -> list:
        print(sql)
        cur = self.conn.execute(sql)  # 创建游标
        if read:
            rows = cur.fetchall()
            cur.close()
            return rows
        else:
            self.conn.commit()
            cur.close()
            return [None]

    def close(self):

        self.conn.close()  # 关闭连接


if __name__ == '__main__':

    fileDB = './table_and_key.db'  # 数据库文件
    helper = MySqliteHelper(fileDB)
    d = helper.get_has_what_table_dic()
    tableNames = ['keys', 'tables']
    glm = ChatGLM()
    for tableName in tableNames:
        rawData = helper.select(tableName, d[tableName])
        for line in rawData:
            if line['gpt_description'] is None or line['gpt_description'] == '':

                name = str(line['name'])
                desc = line['description']
                if name.__contains__("("):
                    typeEnum = "某个字段"
                    typeEnum2 = "字段"
                    prompt = "我将给出有关数据库某个字段的[简单描述]，请根据这些描述，串写一段的话来描述该字段。\n例如：\"{字段名称:etl_time}{字段类型:string}{字段中文名:etl时间}{对应源表:dcs_maintenpkgrtnodr_di}\"可被描述为\"这是一个字符串类型的字段，该字段存储在dcs_maintenpkgrtnodr_di这张表中，字段的名称为etl_time，其中文含义为etl时间\" \n那么请写出[简单描述]:\"" + desc + "\"所对应的描述"
                else:
                    typeEnum = "某张表"
                    typeEnum2 = "表"
                    prompt = "我将给出有关数据库某张表的[简单描述]，请根据这些描述，串写一段的话来描述该表。\n例如：\"{对应源库:idk_base}{快速跳转链接:herf_db}{表名:device_info}{表注释:设备信息表}{对应源表:mobile_device}\"可被描述为\"这是一张设备信息表，存储在idk_base数据库下，其表名为device_info，对应的源表为mobile_device\" \n那么请写出[简单描述]:\"" + desc + "\"所对应的描述"

                print("提问:")
                print(prompt)

                print("GPT的回答:")
                gpt_desc = glm.chat_with_glm(prompt)
                line['gpt_description'] = gpt_desc
                helper.update(tableName, line, main_keys=['name'])
                # time.sleep(20)
