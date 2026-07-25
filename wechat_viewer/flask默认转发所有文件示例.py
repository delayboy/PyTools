import json
from flask import Flask, render_template, send_file, abort, Response
from pathlib import Path
import os
import html
import re
from datetime import datetime
import pandas as pd
from urllib.parse import unquote
from flask import render_template_string

app = Flask(__name__)

# 定义文件类型与MIME类型的映射
MIME_TYPES = {
    '.html': 'text/html',
    '.htm': 'text/html',
    '.json': 'application/json',
    '.js': 'application/javascript',
    '.css': 'text/css',
    '.txt': 'text/plain',
    '.md': 'text/markdown',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.webp': 'image/webp',
    '.ico': 'image/x-icon',
    '.pdf': 'application/pdf',
    '.xml': 'application/xml',
    '.csv': 'text/csv',
}

# 应该内联显示的文件扩展名（不设置为附件）
INLINE_EXTENSIONS = {'.html', '.htm', '.json', '.js', '.css', '.txt', '.md',
                     '.jpg', '.jpeg', '.png', '.gif', '.svg', '.webp',
                     '.xml', '.csv'}

# 应该强制下载的文件扩展名
DOWNLOAD_EXTENSIONS = {'.exe', '.zip', '.rar', '.7z', '.doc', '.docx',
                       '.xls', '.xlsx', '.pdf'}  # pdf可以选择内联或下载


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def download_file(path):
    # 解码URL路径
    path = unquote(path)

    if path == "chat":
        return index()

    # 构建文件路径
    file_path = f"./templates/{path}"

    if os.path.exists(file_path) and os.path.isfile(file_path):
        # 获取文件扩展名
        file_ext = os.path.splitext(file_path)[1].lower()

        # 获取MIME类型
        mime_type = MIME_TYPES.get(file_ext, 'application/octet-stream')

        # 决定是否作为附件下载
        if file_ext in DOWNLOAD_EXTENSIONS:
            # 强制下载
            return send_file(file_path, as_attachment=True, mimetype=mime_type)
        elif file_ext in INLINE_EXTENSIONS:
            # 内联显示
            return send_file(file_path, as_attachment=False, mimetype=mime_type)
        else:
            # 其他类型默认内联显示，但可以设置Content-Disposition
            response = send_file(file_path, as_attachment=False, mimetype=mime_type)
            # 对于未知类型，让浏览器决定如何处理
            return response
    else:
        return abort(404)


@app.route('/')
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <title>文件服务器</title>
        <style>
            body { font-family: Arial, sans-serif; margin: 40px; }
            .file-list { list-style: none; padding: 0; }
            .file-list li { padding: 8px; border-bottom: 1px solid #eee; }
            .file-list a { text-decoration: none; color: #0066cc; }
            .file-list a:hover { text-decoration: underline; }
            .file-size { color: #666; font-size: 0.9em; margin-left: 10px; }
            .file-date { color: #999; font-size: 0.8em; margin-left: 10px; }
        </style>
    </head>
    <body>
        <h1>文件列表</h1>
        <ul class="file-list">
            {% for file in files %}
            <li>
                <a href="{{ file.path }}">{{ file.name }}</a>
                <span class="file-size">({{ file.size }})</span>
                <span class="file-date">{{ file.date }}</span>
            </li>
            {% endfor %}
        </ul>
    </body>
    </html>
    """, files=get_file_list())


def get_file_list():
    """获取templates目录下的文件列表"""
    files = []
    templates_dir = "./templates"

    if os.path.exists(templates_dir):
        for item in os.listdir(templates_dir):
            item_path = os.path.join(templates_dir, item)
            if os.path.isfile(item_path):
                stat = os.stat(item_path)
                files.append({
                    'name': item,
                    'path': item,
                    'size': format_size(stat.st_size),
                    'date': datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                })

    return sorted(files, key=lambda x: x['name'])


def format_size(size):
    """格式化文件大小"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f}{unit}"
        size /= 1024.0
    return f"{size:.1f}TB"


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)
