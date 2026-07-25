"""DeepSeek Viewer by HTML V2
This script provides a web interface to view DeepSeek chat conversations.
It loads conversation data from a JSON file, processes it, and renders it using Flask and Jinja2 templates.
NOTE:template.html should be created in the templates directory with appropriate HTML structure, because Flask will defautly look for it there.
   You can change  the default template directory by setting the `template_folder` parameter in the Flask app initialization. Flask(__name__, template_folder='your_template_directory')
"""
import json
from flask import Flask, render_template, send_file, abort
from markdown import markdown
from markdown.extensions.codehilite import CodeHiliteExtension
from pathlib import Path
import os
import html
import re
from PyTools.MyAwesomeTool.Read_Excel import excel_convert_map
from datetime import datetime
import pandas as pd

app = Flask(__name__)


def data_time_format2(time_stamp: pd.Timestamp):
    # 字符串转datetime对象
    dt = datetime.strptime(time_stamp.strftime('%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S')

    # 转换为正常日期字符串
    normal_date = dt.strftime('%Y-%m-%d %H:%M')  # 输出: '2025-08-17'

    # 计算星期几（返回数字，0=周一，6=周日）
    weekday_num = dt.weekday()  # 返回: 6（因为2025-08-17是周日）

    # 或者获取星期几的名称
    weekday_name = dt.strftime('%A')  # 输出: 'Sunday'（英文）
    weekday_name_cn = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日'][weekday_num]
    return normal_date + "  " + weekday_name_cn


def data_time_format(time_stamp: pd.Timestamp):
    # 字符串转datetime对象
    dt = datetime.strptime(time_stamp.strftime('%Y-%m-%d %H:%M:%S'), '%Y-%m-%d %H:%M:%S')

    # 转换为正常日期字符串
    normal_date = dt.strftime('%Y-%m-%d')  # 输出: '2025-08-17'

    # 计算星期几（返回数字，0=周一，6=周日）
    weekday_num = dt.weekday()  # 返回: 6（因为2025-08-17是周日）

    # 或者获取星期几的名称
    weekday_name = dt.strftime('%A')  # 输出: 'Sunday'（英文）
    weekday_name_cn = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日'][weekday_num]
    return normal_date + "  " + weekday_name_cn


def load_chat_data(file_path):
    """加载JSON聊天数据"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def preprocess_md(content):
    # 匹配 ```代码块``` 并移除每行前的缩进
    content = re.sub(r'^(\s*)```', '```', content, flags=re.MULTILINE)
    return content


def process_wechat_data(wechat_dic: dict):
    """处理聊天数据，提取对话信息"""
    processed = []
    pre_date = ""
    for key in wechat_dic.keys():
        value = wechat_dic[key]
        date_value = data_time_format(value['日期'])
        real_date_value = data_time_format2(value['日期'])
        if not date_value.__eq__(pre_date):
            pre_date = date_value
            # 提取对话基本信息
            conv_info = {
                'id': str(value['序号']),
                'title': real_date_value,
                'inserted_at': real_date_value,
                'messages': []
            }
            processed.append(conv_info)

        message = {'files': [], 'search_results': None, 'model': 'deepseek-chat',
                   'reasoning_content': None, 'content': value['内容'],
                   'inserted_at': real_date_value, 'id': str(value['序号']), 'is_user': True,
                   'content_html': markdown(f"分类:{value['分类']}\n\n字数:{value['字数']}\n\n---\n\n" + value['内容'])}
        conv_info['messages'].append(message)

    return processed


def process_chat_data(chat_data):
    """处理聊天数据，提取对话信息"""
    processed = []
    for conversation in chat_data:
        # 提取对话基本信息
        conv_info = {
            'id': conversation['id'],
            'title': conversation['title'],
            'inserted_at': conversation['inserted_at'],
            'messages': []
        }

        # 提取对话消息
        # 从根节点开始
        # 初始化栈，存储(节点ID, 子节点索引)

        root_id = conversation['mapping']['root']
        stack = [('root', -1)]
        num_conv = 0
        while len(stack) > 0:
            current_id, child_index = stack[-1]
            current_node = conversation['mapping'][current_id]

            if child_index == -1:  # 首次访问该节点
                # 更新栈顶，准备处理子节点
                stack[-1] = (current_id, 0)  # 将索引设为0，准备处理第一个子节点
            elif child_index < len(current_node['children']):  # 还有子节点待处理
                # 获取下一个子节点ID
                next_child_id = current_node['children'][child_index]
                # 更新栈顶索引
                stack[-1] = (current_id, child_index + 1)
                # 压入子节点，初始索引为-1
                stack.append((next_child_id, -1))

            else:  # 所有子节点处理完成
                if len(current_node['children']) < 1:  # 是真正的叶子节点
                    for i in range(len(stack)):
                        node_id, idx = stack[i]
                        curr_node = conversation['mapping'][node_id]
                        # 处理当前节点的消息
                        if curr_node['message']:
                            message = curr_node['message']
                            message['id'] = int(node_id)
                            is_user = message['id'] % 2 == 1
                            message['is_user'] = is_user
                            content = message['content'] if message['content'] else ""
                            content = preprocess_md(content)
                            # <pre>标签会: 保留所有空格和换行  使用等宽字体显示  但不自动转义HTML特殊字符
                            md_content = f"<pre style=\"background-color: rgba(255, 255, 255, 0);\">{html.escape(content)}</pre>" if \
                                is_user else markdown(content,
                                                      extensions=['toc', 'extra', 'tables', 'fenced_code', 'nl2br',
                                                                  'codehilite',
                                                                  CodeHiliteExtension(noclasses=True,
                                                                                      linenums=False,
                                                                                      use_pygments=True)])
                            message['content_html'] = md_content
                            if content.__contains__("额外优化"):
                                pass
                            conv_info['messages'].append(message)
                        elif node_id == "root":
                            pass
                            # conv_info['messages'].append(message)
                    num_conv += 1
                    message = {'files': [], 'search_results': None, 'model': 'deepseek-chat',
                               'reasoning_content': None, 'content': '',
                               'inserted_at': '2025-07-14T09:06:29.721000+08:00', 'id': -1, 'is_user': True,
                               'content_html': markdown(f"===========第{num_conv}段对话结束===========\n-----")}
                    conv_info['messages'].append(message)
                stack.pop()  # 弹出当前节点

        processed.append(conv_info)

    return processed


def initialize_data():
    final_processed_data = []
    for root, dirs, files in os.walk(Path(__file__).parent, topdown=False):
        for name in files:
            file_path = os.path.join(root, name)
            if name.endswith(".xlsx"):
                wechat_message_dic = excel_convert_map(file_path, ["序号"])
                processed_data = process_wechat_data(wechat_message_dic)
                final_processed_data.extend(processed_data)
            elif name.endswith(".json"):
                chat_data = load_chat_data(file_path)
                processed_data = process_chat_data(chat_data)
                final_processed_data.extend(processed_data)
    return final_processed_data


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def download_file(path):
    if path == "chat":
        return index()
    else:
        if os.path.exists(f"./templates/{path}") and os.path.isfile(f"./templates/{path}"):
            return send_file(f"./templates/{path}", as_attachment=True)
        else:
            return abort(404)


@app.route('/')
def index():
    return render_template('template.html', conversations=initialize_data())


if __name__ == '__main__':
    initialize_data()
    app.run(host='0.0.0.0', port=8080, debug=True)
