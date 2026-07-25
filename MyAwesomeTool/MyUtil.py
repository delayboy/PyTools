from __future__ import annotations  # 使用高级注解器，支持类成员方法返回自身类型

import subprocess
import threading
import time
from abc import ABC, abstractmethod
import logging
import os
import datetime
from logging.handlers import TimedRotatingFileHandler, RotatingFileHandler
import hashlib
from typing import List, TypeVar, Callable, Generic, Tuple, Any, Dict, Type
import json
import pickle
import functools
import signal
import psutil
import zipfile
from collections import deque
import locale
import sys

this_process = psutil.Process(os.getpid())
# 获取系统默认编码
system_encoding = locale.getpreferredencoding()
# 在Windows上，先切换控制台编码到UTF-8
if sys.platform == 'win32':
    subprocess.run('chcp 65001', shell=True, capture_output=True)


def run_cmd(cmd_str: str, cwd=None):
    if cwd is None:
        cwd = os.getcwd()
    # 设置编码为GBK以正确显示中文
    sub_proc = subprocess.Popen(cmd_str, shell=True, stdin=subprocess.PIPE,  # subprocess.PIPE
                                stdout=sys.stdout,  # 关键修改
                                stderr=sys.stderr, bufsize=1,  # 行缓冲
                                cwd=cwd,  # 设置工作目录
                                universal_newlines=True,  # text=True,
                                encoding=system_encoding,
                                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)  # Windows命令行使用GBK编码

    # Windows 下使用信号处理
    def signal_handler(sig, frame):
        print("\n接收到中断信号，正在终止进程...")
        os.system(f"taskkill /t /f /pid {sub_proc.pid}")
        sub_proc.terminate()  # 发送终止信号

    # 注册 Ctrl+C 信号处理
    signal.signal(signal.SIGINT, signal_handler)
    try:
        while True:
            try:
                # 设置超时时间（单位：秒）
                sub_proc.wait(timeout=1)  # 30秒超时
                break
            except subprocess.TimeoutExpired:
                sys.stdout.flush()
                sys.stderr.flush()
                continue

    except KeyboardInterrupt:
        sub_proc.terminate()
        try:
            sub_proc.wait(timeout=5)  # 给进程5秒时间正常退出
        except subprocess.TimeoutExpired:
            print("进程无法正常终止，强制杀死...")
            sub_proc.kill()  # 强制杀死进程
            sub_proc.wait()  # 等待进程完全退出


class StringClassifier:
    def __init__(self):
        self.state = None
        self.ignored = False

    @staticmethod
    def classify_char_type(input_tuple_c: Tuple[str, str]):  # 字符聚类
        c = input_tuple_c[0]
        if '\u4e00' <= c <= '\u9fff':
            return "is_chinese"
        elif c.isalpha():
            return "is_alpha"
        elif c == ' ':
            return "is_space"
        elif c.isdigit():
            return "is_digit"
        elif c in ['\n', '\r']:
            return "is_div"
        elif c in [':', '：', '.', ',', '。']:
            return "is_symbol"
        else:
            return "is_other"

    def on_pipline(self, input_tuple_c: Tuple[str, str]) -> Any:
        new_state = self.classify_char_type(input_tuple_c)
        self.state = new_state
        return self.state


class TimeStringClassifier(StringClassifier):
    def on_pipline(self, input_tuple_c: Tuple[str, str]) -> Any:
        ch, new_state = input_tuple_c
        self.ignored = False
        if self.state == "is_space":
            self.ignored = True
        if self.state == "is_digit" and new_state == "is_symbol" and ch == ":":
            pass
        else:
            self.state = new_state

        return self.state


class BaseScriptArranger(ABC):
    def __init__(self):
        # __agent_long_memory
        self._alm: AgentTreeMemory = AgentTreeMemory()  # 智能体长期记忆，通过触发action动作来手动控制，记忆的清除和写入
        # __agent_shot_memory
        self._asm: AgentTreeMemory = AgentTreeMemory()  # 短期记忆，看一次更新一次，由脚本自动控制生命周期
        self._start_loop = True

    @abstractmethod
    def _clear_cache(self):
        self.__observation_shot_memory_xml_cache = {}
        self._asm.forget_all()

    @staticmethod
    def _default_final_exit(is_final=True):
        if is_final:
            raise OverflowError("满足条件就退出")

    @staticmethod
    def _stack_to_str(stack: List[Any]) -> str:
        res = '['
        for i in stack:
            res = res + f"{i}\t"
        res = res + ']'
        return res

    @abstractmethod
    def loop_entry_point(self):
        self._clear_cache()
        try:
            self.observe_and_do("当前是在微信主页; X题头是微信两个字",
                                "遗忘 当前页面所有微信群名; 点击 左下角微信两个字")
            self.observe_and_do("已经进入微信群聊", "记忆 当前页面所有微信聊天记录")
        except OverflowError:
            pass

    def script_loop(self):
        while self._start_loop:
            try:
                self.loop_entry_point()
            except OverflowError:
                pass

    def start_script_loop(self):
        self._start_loop = True
        start_thread(self.script_loop, ())

    def stop_loop(self):
        self._start_loop = False

    @abstractmethod
    def observation_route(self, *args) -> bool:
        return True

    @abstractmethod
    def action_route(self, *args) -> bool:
        action_alias_name = args[0]
        if action_alias_name.__eq__("记忆"):
            switch_name = args[1]
            self._alm.remember_this_info(self._asm.get_remember_info(switch_name), switch_name)
        elif action_alias_name.__eq__("遗忘"):
            self._alm.forget_this_info(args[1])
        return True

    def observe_and_do(self, observe_cmd: str, action_cmd: str, is_final=True):
        ob_i = CommandInterpreter(observe_cmd, self.observation_route)
        if ob_i.run():
            a_i = CommandInterpreter(action_cmd, self.action_route)
            if a_i.run():
                logger.debug(f"观察成功:({observe_cmd})执行动作成功:({action_cmd})")
                self._default_final_exit(is_final)


class WxStringClassifier(StringClassifier):
    def on_pipline(self, input_tuple_c: Tuple[str, str]) -> Any:
        ch, new_state = input_tuple_c
        self.ignored = False
        if self.state in ["is_space", "is_symbol", "is_@"]:  # "is_div",
            self.ignored = True
        if ch == ' ':
            new_state = "is_space"
        elif ch in [':', '：']:
            new_state = "is_symbol"
        elif ch in ['\n', '\r']:
            new_state = "is_div"
        elif ch == '@':
            new_state = 'is_@'
        else:
            new_state = "is_text"

        if self.state == "is_text" and new_state == "is_space":
            pass
        elif self.state == "is_@" and new_state == "is_text":  # @后不更新状态
            pass
        else:

            self.state = new_state
        return self.state


def bfs_traverse_directory(dir_path, callback: Callable[[str, bool, str], bool]) -> str:
    queue = deque([dir_path])

    while len(queue) > 0:
        current_path = queue.popleft()

        items = os.listdir(current_path)
        for item in items:
            absolute_path = os.path.join(current_path, item)
            is_dir = os.path.isdir(absolute_path)

            if is_dir:
                queue.append(absolute_path)
                res = callback(current_path, is_dir, item)
            else:
                res = callback(current_path, is_dir, item)
            if res:
                return absolute_path
    return ""


def compress_folder_with_progress(folder_path: str, output_zip_path: str, white_list: set = None,
                                  black_list: set = None):
    """
    压缩文件夹并显示进度

    Args:
        folder_path: 要压缩的文件夹路径
        output_zip_path: 输出的ZIP文件路径
        black_list: 压缩文件黑名单（不进行压缩）
        white_list: 压缩文件白名单（进行压缩）
    """
    # 先统计文件总数
    total_files = []
    if white_list is None:
        white_list = {""}
    if black_list is None:
        black_list = set()

    for path_name in white_list:
        abs_path_name = os.path.join(folder_path, path_name)
        if not os.path.exists(abs_path_name):
            continue
        if os.path.isdir(abs_path_name):
            for root, dirs, files in os.walk(abs_path_name):
                # 从dirs列表中移除要排除的目录，这样os.walk就不会遍历它们
                dirs[:] = [d for d in dirs if os.path.join(root, d) not in black_list]
                for file in files:
                    file_path = os.path.join(root, file)
                    if file_path in black_list:
                        continue
                    else:
                        total_files.append(file_path)
        else:
            total_files.append(abs_path_name)

    processed_files = 0
    total_files_num = len(total_files)
    base_folder_name = os.path.basename(folder_path)
    print(f"找到 {total_files_num} 个文件，开始压缩...")
    with zipfile.ZipFile(output_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for file_path in total_files:
            arcname = os.path.relpath(file_path, folder_path)
            zipf.write(file_path, os.path.join(base_folder_name, arcname))

            processed_files += 1
            progress = (processed_files / total_files_num) * 100
            print(f"\r进度: {processed_files}/{total_files_num} ({progress:.1f}%)", end='')

    print(f"\n压缩完成！文件保存为: {output_zip_path}")


def group_str_pipline(input_str: str, classify_pipline: List[Type[StringClassifier]] = None) -> List[Tuple[str, str]]:
    classify_pipline = [StringClassifier] if classify_pipline is None else classify_pipline

    input_context = [(each_c, '') for each_c in input_str]
    for each_callback in classify_pipline:
        input_context = group_str_by_char_type(input_context, each_callback)
    return input_context
    # 通过字符聚类对输入字符进行分组


def group_str_by_char_type(input_str: List[Tuple[str, str]], classifier: Type[StringClassifier]) -> \
        List[Tuple[str, str]]:
    state = None  # 初始状态机
    str_builder = ""
    res = []
    classifier = StringClassifier if classifier is None else classifier
    classifier = classifier()
    for tuple_c in input_str:
        new_state = classifier.on_pipline(tuple_c)
        if not state == new_state:
            if state is not None:
                if not classifier.ignored:
                    res.append((str_builder, state))
                str_builder = ""
            state = new_state
        str_builder += tuple_c[0]
    if not classifier.ignored:
        res.append((str_builder, state))
    return res


def print_delta_time(diff):
    # diff = day1 - day2
    days = diff.days
    hours, remainder = divmod(diff.seconds, 3600)
    minutes = remainder // 60
    print(f"间隔为: {days}天 {hours}小时 {minutes}分钟")


def time_check(threshold):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            if end_time - start_time > threshold:
                print(f'{func.__name__} longer than{threshold}')
            return result

        return wrapper

    return decorator


def memory_check(check_process: psutil.Process):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            now_process = check_process
            if check_process is None:
                now_process = this_process
            start_use_mb = now_process.memory_full_info().uss
            result = func(*args, **kwargs)
            end_use_mb = now_process.memory_full_info().uss
            add = end_use_mb - start_use_mb
            if add > 0:
                add = add / 1024 / 1024
                print(
                    f'{func.__name__} 为内存增量函数 {end_use_mb / 1024 / 1024}-{start_use_mb / 1024 / 1024}={add} MB')
            return result

        return wrapper

    return decorator


def longest_common_subsequence(seq1: list, seq2: list, calculate_sequence: bool = False) -> Tuple[float, list]:
    m = len(seq1)
    n = len(seq2)

    # 创建一个二维数组来存储子序列长度
    dp = [[0] * (n + 1) for _ in range(m + 1)]

    # 填充数组
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if seq1[i - 1] == seq2[j - 1]:
                dp[i][j] = dp[i - 1][j - 1] + 1
            else:
                dp[i][j] = max(dp[i - 1][j], dp[i][j - 1])

    # 通过 dp 矩阵反推具体的公共子序列
    common_sequence = []
    i, j = m, n
    while calculate_sequence and i > 0 and j > 0:
        if seq1[i - 1] == seq2[j - 1]:
            common_sequence.insert(0, seq1[i - 1])  # 从末尾开始插入到前面去
            i -= 1
            j -= 1
        elif dp[i - 1][j] > dp[i][j - 1]:  # 如果i序列的LCS大于j序列，则减少i
            i -= 1
        else:  # 否则减少j
            j -= 1

    return dp[m][n], common_sequence


def set_global_logging():
    # 配置日志记录器,并设置日志级别为WARNING，输出所有级别的日志消息
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


def build_logger(name: str = None, filename="./log.log", use_to_debug=False, use_time_rotate=True,
                 file_log_debug=False, add_file_handler=True):
    if name is None:
        name = "MyDefault"
    # 创建一个日志记录器

    my_logger = logging.getLogger(name)
    if use_to_debug:
        my_logger.setLevel(level=logging.DEBUG)
    else:
        my_logger.setLevel(level=logging.WARNING)

    fmt = '[%(asctime)s %(name)s  P-%(process)s T-%(thread)s %(levelname)-8s %(funcName)s] %(message)s'

    formatter = logging.Formatter(fmt, '%Y-%m-%d %H:%M:%S')  # 时间格式

    console = logging.StreamHandler()  # 控制台输出日志

    console.setLevel(logging.DEBUG)  # 设置控制台输出日志级别

    console.setFormatter(formatter)  # 设置控制台打印格式

    # 将日志内容传递到相关联的handlers中

    my_logger.addHandler(console)

    if not add_file_handler:
        return my_logger

    if use_time_rotate:

        file_handler = TimedRotatingFileHandler(filename, when='d', interval=1,
                                                backupCount=2, encoding='utf-8')

        # when:h(时)/m(分)/s(秒)/d(天)/midnight(凌晨)等等,  interval:间隔时间, backupCount=0 保存几天的日志

        # file_handler.suffix = '%Y-%m-%d_%M_%S'  # 日志文件后缀
    else:
        file_handler = RotatingFileHandler(filename=filename, mode='a', encoding='UTF-8',
                                           maxBytes=1024 * 100 * 100, backupCount=2)
    if file_log_debug:
        file_handler.setLevel(logging.DEBUG)  # 设置输出到日志文件等级
    else:
        file_handler.setLevel(logging.INFO)  # 设置输出到日志文件等级

    file_handler.setFormatter(formatter)  # 设置写到日志文件格式

    my_logger.addHandler(file_handler)

    return my_logger


logger = build_logger(__name__, use_to_debug=True, add_file_handler=False)


class InteractiveCmd:
    def __init__(self, cmd: str, user_input_mode=False, show_detail=True):
        logger.info(cmd)
        self.__cmd = cmd
        self.__show_detail = show_detail
        # 用于线程同步的事件对象
        self.__event = threading.Event()
        self.__event.clear()
        # 不指定编码格式和文本encoding='utf-8'
        self.__sub_proc = subprocess.Popen(self.__cmd, shell=True, stdin=subprocess.PIPE,
                                           stdout=subprocess.PIPE,
                                           stderr=subprocess.PIPE, text=False, bufsize=512)
        self.__read_output_thread = threading.Thread(target=self.read_output, args=())
        self.__write_input_thread = threading.Thread(target=self.write_input, args=())
        self.__read_output_thread.start()
        if user_input_mode:
            self.__write_input_thread.start()
        self.__output_str_collector: bytes = b''
        self.__running = True
        if self.__show_detail:
            print(self.__cmd)
        try:
            self.__sub_proc.wait()
            self.__running = False
        except KeyboardInterrupt:
            self.__sub_proc.terminate()
            self.__sub_proc.wait()
            logger.warning("用户主动退出")  # 捕获 Ctrl+C 以允许用户中断命令

    @staticmethod
    def kill(proc: subprocess.Popen, use_ctrl=False):
        # 但是录制视频或下载文件时，命令行一般使用流传输，线程比较复杂，因此只能使用ctrl+c进行终结，这种终结方式对所有线程都有效
        # 包括python自己的主窗口线程
        if use_ctrl:
            proc.send_signal(signal.CTRL_C_EVENT)
            # 另一种ctrl+c终结方式：os.kill(proc.pid, signal.CTRL_C_EVENT)
        else:
            # 使用taskKill命令终止cmd命令运行可以避免ctrl+c终止整个python程序的异常
            os.system("taskkill /t /f /pid %s" % proc.pid)
        # 命令行终止后，将子进程对象释放掉(置空），防止之后对空对象操作。
        proc.kill()
        # 使用wait等待子进程指令的回显全部打印完成后才退出。
        proc.wait()

    def force_close(self, use_ctrl=True):
        self.kill(self.__sub_proc, use_ctrl)

    def get_collect_output(self):
        raw_bytes = self.__output_str_collector
        try:
            result = raw_bytes.decode('utf-8')
        except UnicodeDecodeError as e:
            b_error = raw_bytes[e.start]  # 获取异常点
            if b_error == 0xA0:  # 修复已知异常
                b_array = bytearray(raw_bytes)
                b_array[e.start] = 0x20
                result = bytes(b_array).decode('utf-8')
            else:
                raise e
        return result

    @abstractmethod
    def output_chunk_callback(self, output_chunk: bytes):
        if self.__show_detail:
            print(output_chunk, end='', flush=True)  # 输出字符，不换行，立即刷新
        self.__output_str_collector += output_chunk

    @abstractmethod
    def output_timeout_and_wait_input_callback(self) -> str:
        logger.debug("线程1等待超时，未收到信号，等待用户输入")
        # 准备要传递给CMD的用户输入
        user_input = input('')
        return user_input

    def read_output(self):
        # 读取并打印CMD的回显
        while True:
            output_chunk = self.__sub_proc.stdout.read(256)  # 读取一个字符# sub_proc.stdout.readline()
            if len(output_chunk) == 0:  # 没有正常输出的时候，则获取错误输出
                output_chunk = self.__sub_proc.stderr.read(256)
            self.__event.set()  # 发送信号
            if not self.__running:
                # 子进程已结束
                self.__sub_proc.stdin = None
                break
            self.output_chunk_callback(output_chunk)
        logger.debug("[read_output thread exit]")

    def write_input(self):
        while True:
            if not self.__event.wait(2):  # 等待最多1秒
                if self.__sub_proc.stdin is None:
                    break
                user_input = self.output_timeout_and_wait_input_callback()
                if user_input is None:
                    continue
                user_input = user_input + "\n"  # 注意要包括换行符
                # 向CMD发送用户输入
                self.__sub_proc.stdin.write(user_input.encode('utf-8'))
                self.__sub_proc.stdin.flush()  # 刷新stdin以确保输入被发送
            self.__event.clear()
        logger.debug("[write_input thread exit]")


class MyFileEditor:
    def __init__(self, path: str = "C:/share/log.txt"):
        self.path = path

    def log(self, content: str):
        now = datetime.datetime.now()
        log_text = "[%s]%s\n" % (now, content)
        self.write(log_text, True)

    def exists(self):
        return os.path.exists(self.path)

    def write(self, content: str, append: bool = False):
        if not os.path.exists(self.path):
            filepath = os.path.split(self.path)
            if not os.path.exists(filepath[0]):
                os.mkdir(filepath[0])
        if append:
            mode = "a"
        else:
            mode = "w"
        with open(self.path, mode, encoding="utf-8") as f:
            f.write(content)

    def read(self):
        with open(self.path, "r", encoding="utf-8") as f:
            return f.read()


class MyJSONEditor:
    def __init__(self, path: str):
        self.path = path

    def exists(self):
        return os.path.exists(self.path)

    def read(self) -> dict:
        if not os.path.exists(self.path):
            return {}
        with open(self.path, "r", encoding="utf-8") as f:
            content = json.load(f)
            return content

    def write(self, data: dict):
        if not os.path.exists(self.path):
            filepath = os.path.split(self.path)
            if not os.path.exists(filepath[0]):
                os.mkdir(filepath[0])
        with open(self.path, "w", encoding="utf-8") as f:
            content = json.dumps(data, indent=4, ensure_ascii=False)
            f.write(content)


def get_file_from_env_path(file_to_find: str = 'MyDll.dll') -> str:
    # 获取PATH环境变量的值，并使用分号（;）分割成多个路径
    path_dirs = os.environ['PATH'].split(';')
    path_dirs.append(os.path.abspath("."))
    # 要查找的文件名 file_to_find

    # 遍历每个路径，查看文件是否存在
    for path in path_dirs:
        file_path = os.path.join(path, file_to_find)
        if os.path.isfile(file_path):
            logger.debug(f"文件 {file_to_find} 存在于路径: {path}")

            return file_path
        else:
            logger.debug(f"文件[{file_to_find}]未在[{path}]中找到")

    logger.debug(f"文件 {file_to_find} 未在任何路径中找到。")
    return None


def print_all_env():
    logger.debug("当前程序已经加载的环境变量:")
    for key, value in os.environ.items():
        logger.debug(f"{key}: {value}")


def set_env_var(var_name: str, var_value: str):
    if var_name.__contains__("PATH"):  # 如果是路径类型的环境变量，则先提取之前的环境变量
        old_value = os.environ[var_name] if os.environ.__contains__(var_name) else ""
        if old_value.__contains__(var_value):
            logger.debug("需要设置的路径类型环境变量[%s]已存在", var_name)
            return
        else:
            os.environ[var_name] = var_value + ";" + old_value
            logger.debug("需要设置PATH环境变量不存在，已经设置了[%s]=(%s)", var_name, var_value)

    else:  # 否则直接设置就好
        os.environ[var_name] = var_value

    print_all_env()


# 将列表缓存为二进制字节
def any_obj_to_bytes(data: Any) -> bytes:
    return pickle.dumps(data)


# 将二进制自己转回列表
def bytes_to_any_obj(raw_bytes: bytes) -> Any:
    return pickle.loads(raw_bytes)


# 将列表缓存为二进制文件
def cache_obj(filename: str, data: Any):
    with open(filename, 'wb') as f:
        pickle.dump(data, f)


# 从文件中读取并还原列表
def read_obj(filename: str):
    with open(filename, 'rb') as f:
        data = pickle.load(f)
    return data


def get_file_list(dir_path, tail: str = ".py") -> list:
    # 获取目录中所有文件和目录的名称列表
    res = []
    items = os.listdir(dir_path)
    # 遍历所有文件和目录
    for item in items:
        # 获取文件或子目录的完整路径
        item_path = os.path.join(dir_path, item)

        # 判断是否为文件
        if os.path.isfile(item_path) and item.endswith(tail):
            res.append(item_path)

    return res


def auto_patch_python(my_global: dict | None, ret_md5_str: bool = True, patch_path='./patch.py') -> str:
    if os.path.exists(patch_path):
        pycode = open(patch_path, encoding="utf-8").read()
    else:
        pycode = ""
    if my_global is not None:
        exec(pycode, my_global)
    if ret_md5_str:
        return hashlib.md5(pycode.encode("utf-8")).hexdigest()
    else:
        return pycode


def manual_patch_python(my_global: dict, patch_path='./patch'):
    file_list = get_file_list(patch_path)

    file_list.append("直接加载不patch")
    for i, item_path in enumerate(file_list):
        print(i, os.path.basename(item_path))
    num = int(input("选择需要patch的python文件 "))
    if 0 <= num < len(file_list):
        patch_name = file_list[num]
        print("选择了文件:", patch_name)
        if os.path.exists(patch_name):
            pycode = open(patch_name, encoding="utf-8").read()
            os.chdir(patch_path)
            exec(pycode, my_global)

            return True
    return False


def merge_locals_kwargs(my_locals: dict, excludes: list = None, **kwargs):
    excludes_list = ['self', 'kwargs', '__class__']
    if excludes is not None:
        excludes_list.extend(excludes)
    if not kwargs:
        kwargs = dict()
    return merge_dict(dict((k, v) for k, v in list(my_locals.items())
                           if k not in excludes_list), **kwargs)


def merge_dict(d: dict, overwrite=False, inplace=False, **kwargs):
    """
    通配传参示例

    def statisticFreq(values, counts, group, min_per=0.0, max_per=1.0, use_sql_label=False) -> Tuple[List[str], List[Any]]:
        # max_value,min_value 也可以直接通过locals()函数来传参
        rangeList = divValueRange(**merge_locals_kwargs(locals(), max_value=np.max(values), min_value=np.min(values)))
    """
    nd = dict([(k, v) for k, v in d.items()] + [(k, v) for k, v in kwargs.items() if overwrite or k not in d])
    if inplace:
        d.update(nd)
        return d
    return nd


def start_thread(target, args: tuple = ()):
    # 子线程启动函数，用于开启一个子线程，target为需要运行目标方法
    thread_handle = threading.Thread(target=target, args=args)
    thread_handle.start()
    return thread_handle


class CommandInterpreter:
    def __init__(self, many_cmd_str: str, callback: Callable[[Tuple[str]], bool]):
        # self.__rip: int = 0
        self.__cmd_str = many_cmd_str
        self.__code_list = []
        self.__initialize_code_line()
        self.__run_code_callback = callback
        self.__a = callback.__name__
        if self.__a.__contains__("action"):
            self.__a = "动作链"
        else:
            self.__a = "观察链"

    @staticmethod
    def __format_each_command(cmd_str: str = None) -> Tuple[str, bool, List[str], bool]:
        if cmd_str is None:
            return "", False, [], False
        use_not = False
        cmd_list = cmd_str.split(" ")
        alias_name = cmd_list[0]
        has_args = len(cmd_list) > 1

        if alias_name.startswith("X"):
            use_not = True
            alias_name = alias_name[1:]
            cmd_list[0] = alias_name

        return alias_name, has_args, cmd_list, use_not

    def __initialize_code_line(self):
        self.__code_list = [c.strip() for c in self.__cmd_str.split(";")]

    def run(self) -> bool:
        success = True
        for cmd_line in self.__code_list:
            alias_name, has_args, cmd_list, use_not = self.__format_each_command(cmd_line)
            result = self.__run_code_callback(*cmd_list)
            result = not result if use_not else result
            if result:
                continue
            else:
                success = False

                logger.debug(f"---------在执行{self.__a}:({self.__cmd_str})时失败-------具体失败项:({cmd_line})")
                break
        return success


class AgentTreeMemory:
    def __init__(self):
        self.__memory: Dict[str, Any] = {}

    def remember_this_info(self, value: Any, *keys: str):
        now_dic = self.__memory
        for key in keys[:-1]:
            if not now_dic.__contains__(key):
                now_dic[key] = {}
                now_dic = now_dic[key]
            elif type(now_dic[key]) is not dict:
                now_dic[key] = {}
                now_dic = now_dic[key]
            else:
                now_dic = now_dic[key]
        now_dic[keys[-1]] = value

    def if_remember_this_info(self, *keys: str) -> bool:
        return self.get_remember_info(*keys) is not None

    def get_remember_info(self, *keys: str) -> Any:
        now_dic = self.__memory

        for key in keys[:-1]:
            if type(now_dic) == dict and now_dic.__contains__(key):
                now_dic = now_dic[key]

            else:
                return None
        key = keys[-1]
        if type(now_dic) == dict and now_dic.__contains__(key):
            return now_dic[key]
        return None

    def forget_this_info(self, *keys: str):
        # now_dic = self.get_remember_info(*keys)
        # if type(now_dic) == dict:
        #     now_dic.clear()
        now_dic = self.__memory
        for key in keys[:-1]:
            if type(now_dic) == dict and now_dic.__contains__(key):
                now_dic = now_dic[key]

            else:
                return
        key = keys[-1]
        if type(now_dic) == dict and now_dic.__contains__(key):
            now_dic.pop(key)

    def forget_all(self):
        self.__memory.clear()


@memory_check(None)
def test_sleep(a):
    time.sleep(1)
    a.append(1)


# run_cmd("ping www.baidu.com")
if __name__ == '__main__':
    a = []
    test_sleep(a)
    print(a)
    input()
    # while True:
    #     output = InteractiveCmd("ping www.baidu.com")
    #     logger.info("<output_collect>" + output.get_collect_output() + "</output_collect>")
