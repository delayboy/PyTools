from __future__ import annotations  # 使用高级注解器，
import os
from collections import deque
from typing import List, TypeVar, Callable, Generic, Dict, Tuple, Sequence
import re
import tkinter as tk
from tkinter import ttk
from abc import ABC, abstractmethod
import shutil
from PyTools.MyAwesomeTool.MyUtil import InteractiveCmd


class MyTableUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Simple Table")
        # 创建表格
        tree = ttk.Treeview(self, columns=('Name', 'Count'), show='headings')
        tree.heading('Name', text='Name')
        tree.heading('Count', text='Count')

        # 插入数据
        tree.insert('', 'end', values=('aaa', 2))
        tree.insert('', 'end', values=('bbb', 4))
        for id_str in tree.get_children():
            print(id_str)
            print(tree.item(id_str))
        # 将表格放到窗口中
        tree.pack()
        # 运行主循环
        self.mainloop()


class SyncScrollTreeview(tk.Tk):
    def __init__(self, left_engine: FileEngine, right_engine: FileEngine, left_path: str, right_path: str):
        self.left_engine = left_engine
        self.right_engine = right_engine
        self.left_path = left_path
        self.right_path = right_path
        super().__init__()
        self.title("同步滚动的Treeview")

        # 创建主框架容器
        main_frame = tk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # 创建滚动条
        self.scrollbar = ttk.Scrollbar(main_frame, orient="vertical")
        self.scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # 左侧面板
        left_panel = tk.Frame(main_frame)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 左侧路径输入框
        left_path_frame = tk.Frame(left_panel)
        left_path_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

        tk.Label(left_path_frame, text="左侧路径:").pack(side=tk.LEFT)
        self.left_path_entry = tk.Entry(left_path_frame)
        self.left_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.left_path_entry.insert(0, self.left_path)

        # 左侧Treeview
        self.left_tree = ttk.Treeview(
            left_panel,
            columns=('Value',),
            show='tree headings',
            yscrollcommand=self.sync_scroll
        )
        self.left_tree.heading('#0', text='Path')
        self.left_tree.heading('Value', text='Value')

        self.left_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        # 定义不同的颜色标签
        self.left_tree.tag_configure('red', foreground='red')
        self.left_tree.tag_configure('blue', foreground='blue')
        self.left_tree.tag_configure('green', foreground='green')

        # 右侧面板
        right_panel = tk.Frame(main_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # 右侧路径输入框
        right_path_frame = tk.Frame(right_panel)
        right_path_frame.pack(fill=tk.X, padx=5, pady=(0, 5))

        tk.Label(right_path_frame, text="右侧路径:").pack(side=tk.LEFT)
        self.right_path_entry = tk.Entry(right_path_frame)
        self.right_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.right_path_entry.insert(0, self.right_path)

        # 右侧Treeview
        self.right_tree = ttk.Treeview(
            right_panel,
            columns=('Value',),
            show='tree headings',
            yscrollcommand=self.sync_scroll
        )
        self.right_tree.heading('#0', text='Path')
        self.right_tree.heading('Value', text='Value')

        self.right_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        # 定义不同的颜色标签
        self.right_tree.tag_configure('red', foreground='red')
        self.right_tree.tag_configure('blue', foreground='blue')
        self.right_tree.tag_configure('green', foreground='green')
        # 配置滚动条
        self.scrollbar.config(command=self.sync_scroll_command)

        # 底部同步按钮
        bottom_frame = tk.Frame(self)
        bottom_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        enum_button = tk.Button(bottom_frame, text="遍历", command=self.enum_button_callback)
        enum_button.pack(side=tk.LEFT, expand=True, fill=tk.X, pady=5)

        sync_button = tk.Button(bottom_frame, text="同步", command=self.sync_button_callback)
        sync_button.pack(side=tk.LEFT, expand=True, fill=tk.X, pady=5)

        # 绑定鼠标滚轮事件
        self.bind_mouse_wheel()

    def delete_all_tree(self):
        for item in self.left_tree.get_children():
            self.left_tree.delete(item)
        for item in self.right_tree.get_children():
            self.right_tree.delete(item)

    def bind_mouse_wheel(self):
        """绑定鼠标滚轮事件"""
        self.left_tree.bind("<MouseWheel>", self.on_mouse_wheel)
        self.right_tree.bind("<MouseWheel>", self.on_mouse_wheel)

    def on_mouse_wheel(self, event):
        """处理鼠标滚轮事件"""
        # 确定滚动的方向
        delta = -1 if event.delta > 0 else 1

        # 获取当前Treeview的可见行数
        tree = event.widget
        visible_rows = len(tree.get_children()) - int(tree.configure("height")[4])

        # 计算新的位置
        first_visible = tree.yview()[0]
        new_position = max(0.0, min(1.0, first_visible + delta * 0.1))

        # 同步滚动两个Treeview
        self.left_tree.yview_moveto(new_position)
        self.right_tree.yview_moveto(new_position)

        return "break"  # 阻止默认滚动行为

    def sync_scroll(self, *args):
        """同步滚动条位置"""
        # 更新滚动条
        self.scrollbar.set(*args)

        # # 同步两个Treeview的视图
        # self.left_tree.yview(*args)
        # self.right_tree.yview(*args)

    def sync_scroll_command(self, *args):
        """处理滚动条命令"""
        # 同步两个Treeview的视图
        self.left_tree.yview(*args)
        self.right_tree.yview(*args)

    @abstractmethod
    def enum_button_callback(self):
        pass

    @abstractmethod
    def sync_button_callback(self):
        """同步按钮的回调函数"""
        print("Hello World!")
        print(f"左侧路径: {self.left_path_entry.get()}")
        print(f"右侧路径: {self.right_path_entry.get()}")


class FileStructBase:
    def __init__(self, is_dir: bool, name: str, absolute_path: str, size: int):
        self.is_dir = is_dir
        self.name = name
        self.absolute_path = absolute_path
        self.size = size

    def __str__(self):
        return "[{}]<{}>({}){}".format(self.name, self.is_dir, self.size, self.absolute_path)


class AdbFileStruct(FileStructBase):
    def __init__(self, cmd_response_unit: str):
        super().__init__(False, "", "", 0)

        # 定义正则表达式，匹配回显字符串，示例 “-rw-rw---- 1 u0_a182 media_rw  9126366 2024-01-23 18:26 Adele - Rolling in the Deep.mp3”
        pattern = r"(\S+\s+\d+\s+\S+\s+\S+\s+\d+\s+\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2})\s+(.*)"
        # 使用正则表达式进行匹配
        match = re.match(pattern, cmd_response_unit)
        if match:
            # 获取匹配的前面的部分和文件名部分
            info = match.group(1)
            filename = match.group(2)
        else:
            raise RuntimeError("cmd回显模板匹配失败，请手动检查:\n{}\r\n".format(cmd_response_unit))
        r_list = re.split(r'\s+', info)
        r_list.append(filename)
        if len(r_list) == 8:
            self.type = r_list[0]
            self.is_dir = self.type.__contains__("dr")
            self.count = r_list[1]
            self.user = r_list[2]
            self.permission = r_list[3]
            self.size = int(r_list[4])
            self.date = r_list[5]
            self.time = r_list[6]
            self.name = r_list[7]
            self.absolute_path = self.name
        else:
            raise RuntimeError("cmd回显单元是{}个请手动检查:\n{}\r\n".format(len(r_list), cmd_response_unit))

    @staticmethod
    def extract_file_info_from_cmd_output(cmd_response: str) -> List[AdbFileStruct]:
        cmd_units = re.split(r'[\r\n]+', cmd_response)
        result = []
        for cmd_unit in cmd_units[1:len(cmd_units) - 1]:  # 跳过第一行和最后一行，没有用
            result.append(AdbFileStruct(cmd_unit))

        return result


class FileEngine(ABC):
    @abstractmethod
    def map_dir(self, path: str = "/sdcard/Music/download") -> Dict[str, FileStructBase]:
        pass

    @abstractmethod
    def upload(self, from_path: str, aim_path: str):
        pass

    @abstractmethod
    def remove(self, aim_path):
        pass


class AdbEngine(FileEngine):
    def __init__(self):
        self.__plugin_root = os.path.abspath("../CvScriptHelper/scrcpy-win64-v2.1.1")
        self.__adb = os.path.join(self.__plugin_root, "adb.exe")
        cmd_str = "\"{}\" devices".format(self.__adb)
        output = InteractiveCmd(cmd_str, show_detail=True).get_collect_output()
        print(output)

    def list_dir(self, path: str = "/sdcard/Music/download", show_detail=False) -> List[AdbFileStruct]:
        cmd_str = "\"{}\" shell \"ls -l \\\"{}\\\"\"".format(self.__adb, path)
        print("CMD_USE_PATH:", path)
        output = InteractiveCmd(cmd_str, show_detail=show_detail).get_collect_output()
        return AdbFileStruct.extract_file_info_from_cmd_output(output)

    def map_dir(self, path: str = "/sdcard/Music/download") -> Dict[str, FileStructBase]:
        info_list = self.list_dir(path)
        result = {}
        for file_struct in info_list:
            file_struct.absolute_path = path + "/" + file_struct.name
            result[file_struct.name] = file_struct
        return result

    def upload(self, from_path: str, aim_path: str):
        cmd_str = "\"{}\" push \"{}\" \"{}\"".format(self.__adb, from_path, aim_path)
        output = InteractiveCmd(cmd_str).get_collect_output()
        print(output)

    def remove(self, aim_path):
        cmd_str = "\"{}\" shell \"rm -r \\\"{}\\\"\"".format(self.__adb, aim_path)
        output = InteractiveCmd(cmd_str).get_collect_output()
        print(output)


class OsEngine(FileEngine):
    @staticmethod
    def os_map_dir(current_path: str) -> Dict[str, FileStructBase]:
        result = {}
        # List all the files and directories in the current directory
        try:
            items = os.listdir(current_path)
            for item in items:
                absolute_path = current_path + "/" + item
                is_dir = os.path.isdir(absolute_path)
                size = os.path.getsize(absolute_path)
                result[item] = FileStructBase(is_dir, item, absolute_path, size)
            return result
        except PermissionError:
            # If we do not have permission to access the directory, skip it
            raise RuntimeError("访问{}的权限不足", current_path)

    def map_dir(self, path: str = "/sdcard/Music/download") -> Dict[str, FileStructBase]:
        return self.os_map_dir(path)

    def upload(self, from_path: str, aim_path: str):
        """
             复制文件或文件夹到目标位置
             :param from_path: 源路径(文件或文件夹)
             :param aim_path: 目标路径
             """
        try:
            if os.path.isfile(from_path):
                # 如果是文件，确保目标目录存在
                os.makedirs(os.path.dirname(aim_path), exist_ok=True)
                shutil.copy2(from_path, aim_path)
            elif os.path.isdir(from_path):
                # 如果是文件夹，使用copytree
                shutil.copytree(from_path, aim_path, dirs_exist_ok=True)
            else:
                raise FileNotFoundError(f"Source path not found: {from_path}")
            print(f"Successfully copied from {from_path} to {aim_path}")
        except Exception as e:
            print(f"Error during upload: {str(e)}")

    def remove(self, target_path):
        """
               删除文件或文件夹
               :param target_path: 要删除的路径(文件或文件夹)
               """
        try:
            if os.path.isfile(target_path):
                os.remove(target_path)
            elif os.path.isdir(target_path):
                shutil.rmtree(target_path)
            else:
                raise FileNotFoundError(f"Target path not found: {target_path}")
            print(f"Successfully removed: {target_path}")
        except Exception as e:
            print(f"Error during removal: {str(e)}")


class SyncToolBox(SyncScrollTreeview):

    def expand_all(self, treeview: ttk.Treeview):
        # 遍历所有节点，并展开它们
        for item in treeview.get_children():
            treeview.item(item, open=True)
            # 递归展开子节点
            self.expand_children(treeview, item)

    # 递归展开子节点的辅助函数
    def expand_children(self, treeview: ttk.Treeview, parent: str):
        # 获取当前节点的子节点
        children = treeview.get_children(parent)
        for child in children:
            treeview.item(child, open=True)  # 展开该子节点
            self.expand_children(treeview, child)  # 递归展开子节点的子节点

    def __init__(self, left_engine: FileEngine, right_engine: FileEngine, left_path: str, right_path: str):

        super().__init__(left_engine, right_engine, left_path, right_path)
        self.s_list = []
        self.mainloop()

    def enum_button_callback(self):
        self.s_list = self.bfs_sync_directory(self.left_path_entry.get(), self.right_path_entry.get())

    def sync_button_callback(self):
        """同步按钮的回调函数"""
        print(f"左侧路径: {self.left_path_entry.get()}")
        print(f"右侧路径: {self.right_path_entry.get()}")
        self.show_sync_list(self.s_list)
        self.delete_all_tree()

    def print_tree_contents(self, tree, tree_name):
        """打印树内容到控制台(用于调试)"""
        print(f"\nContents of {tree_name}:")
        for id_str in tree.get_children():
            print(f"ID: {id_str}, Values: {tree.item(id_str)['values']}")

    def show_sync_list(self, sync_list: List[Tuple[str, FileStructBase, FileStructBase]]):
        right_engine = self.right_engine
        for error_reason, left_item, right_item in sync_list:
            print(error_reason, left_item, "<->", right_item)
            if error_reason.__contains__("Left 404"):
                right_engine.remove(right_item.absolute_path)
            elif error_reason.__contains__("Right 404"):
                right_engine.upload(left_item.absolute_path, right_item.absolute_path)
            elif error_reason.__contains__("Diff"):
                right_engine.remove(right_item.absolute_path)
                right_engine.upload(left_item.absolute_path, right_item.absolute_path)

    def bfs_sync_directory(self, left_dir_path: str, right_dir_path: str) -> List[
        Tuple[str, FileStructBase, FileStructBase]]:
        right_engine = self.right_engine
        left_engine = self.left_engine
        queue = deque([""])
        right_tree_root = ''
        left_tree_root = ''
        self.delete_all_tree()
        # List to store the result of BFS traversal
        result = []
        while queue:
            # Pop the first element from the queue
            current_path = queue.popleft()

            left_current_path = left_dir_path + current_path
            left_items = left_engine.map_dir(left_current_path)
            right_current_path = right_dir_path + current_path
            right_items = right_engine.map_dir(right_current_path)

            right_tree_root = self.right_tree.insert("", 'end', text=current_path, values=(right_current_path,))
            self.right_tree.item(right_tree_root, tags=('black',))
            left_tree_root = self.left_tree.insert("", 'end', text=current_path, values=(left_current_path,))
            self.left_tree.item(left_tree_root, tags=('black',))

            already_check = {}
            for file_name, left_info in left_items.items():
                already_check[file_name] = 1  # 标记一下这个文件已经被检查过了
                if not right_items.__contains__(file_name):  # 两个文件夹或文件都不等，直接放入列表中
                    aim_path = right_current_path + "/" + file_name
                    result.append(("Right 404", left_info, FileStructBase(left_info.is_dir, file_name, aim_path, 0)))
                    tag = 'red'
                    self.left_tree.insert(left_tree_root, 'end', text=file_name, values=("",), tags=(tag,))
                    self.right_tree.insert(right_tree_root, 'end', text="No Found", values=("",), tags=(tag,))
                    continue

                if left_info.is_dir:
                    if right_items[file_name].is_dir:  # 两个文件夹相等，所以压入队列
                        queue.append(current_path + "/" + file_name)
                else:

                    if right_items[file_name].size == left_info.size:  # 两个文件相等，什么都不做
                        # tag = 'green'
                        # self.right_tree.insert(right_tree_root, 'end', text=file_name, values=("",), tags=(tag,))
                        # self.left_tree.insert(left_tree_root, 'end', text=file_name, values=("",), tags=(tag,))
                        continue
                    else:  # 两个文件大小不等，放入列表中
                        result.append(("L Diff With R", left_info, right_items[file_name]))
                        tag = 'blue'
                        self.right_tree.insert(right_tree_root, 'end', text=file_name, values=("",), tags=(tag,))
                        self.left_tree.insert(left_tree_root, 'end', text=file_name, values=("",), tags=(tag,))

            for file_name, right_info in right_items.items():  # 这里就不用检查left中已有的项目了
                if already_check.__contains__(file_name):
                    continue

                if not left_items.__contains__(file_name):  # 两个文件夹或文件都不等，直接放入列表中
                    aim_path = left_current_path + "/" + file_name
                    result.append(("Left 404", FileStructBase(right_info.is_dir, file_name, aim_path, 0), right_info))
                    tag = 'red'
                    self.right_tree.insert(right_tree_root, 'end', text=file_name, values=("",), tags=(tag,))
                    self.left_tree.insert(left_tree_root, 'end', text="No Found", values=("",), tags=(tag,))
                    continue

        self.expand_all(self.left_tree)
        self.expand_all(self.right_tree)

        return result


def bfs_traverse_directory(dir_path):
    # Initialize the queue with the root directory
    queue = deque([dir_path])
    # List to store the result of BFS traversal
    result = []
    file_engine = OsEngine()

    while queue:
        # Pop the first element from the queue
        current_path = queue.popleft()
        result.append(current_path)
        items = file_engine.map_dir(current_path)
        for info_struct in items.values():

            if info_struct.is_dir:
                # If the item is a directory, add it to the queue
                queue.append(info_struct.absolute_path)
            else:
                # If the item is a file, add it to the result
                result.append(info_struct.name)

    return result


def example_use():
    # Example usage
    dir_path = "Z:\\Resource\\Media\\Music\\download"
    bfs_result = bfs_traverse_directory(dir_path)
    for path in bfs_result:
        print(path)


if __name__ == '__main__':
    SyncToolBox(OsEngine(), AdbEngine(), "Z:/Resource/Media/Music/download", "/sdcard/Music/download")
    # SyncToolBox(OsEngine(), OsEngine(), "Z:/Resource/Media/Music/download/纯音乐舒缓", "C:/Users/Benson/Desktop/纯音乐")
    pass
