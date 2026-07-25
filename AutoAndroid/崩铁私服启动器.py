# coding=utf8
import tkinter as tk  # 窗口控件支持库
from tkinter import filedialog  # 文件选择弹窗
import threading  # 子进程调用库f
import sys  # 控制台管理与切换支持库
import io  # 二进制读写库
import codecs  # 二进制UTF-8读写支持库
import subprocess  # cmd命令运行库，负责发送adb命令，运行插件中的命令行工具
import signal  # cmd Ctrl+C终结指令信号发送支持库
import time  # 延时函数支持库
import ctypes
import os  # 绝对路径获取支持库


def start_thread(target, args: tuple = ()):
    # 子线程启动函数，用于开启一个子线程，target为需要运行目标方法
    threading.Thread(target=target, args=args).start()


class InteractiveCmd:
    def __init__(self, cmd: str, user_input_mode=False, show_detail=True):
        print(cmd)
        self.__cmd = cmd
        self.__show_detail = show_detail
        # 用于线程同步的事件对象
        self.__event = threading.Event()
        self.__event.clear()
        # 不指定编码格式和文本encoding='utf-8'
        if show_detail:
            self.__sub_proc = subprocess.Popen(self.__cmd, shell=True, stdin=subprocess.PIPE,
                                               stdout=sys.stdout,
                                               stderr=sys.stderr, text=False, bufsize=512)
        else:
            self.__sub_proc = subprocess.Popen(self.__cmd, shell=True, stdin=subprocess.PIPE,
                                               stdout=subprocess.PIPE,
                                               stderr=subprocess.PIPE, text=False, bufsize=512)
        # self.__read_output_thread = threading.Thread(target=self.read_output, args=())
        # self.__write_input_thread = threading.Thread(target=self.write_input, args=())
        # self.__read_output_thread.start()
        # if user_input_mode:
        #     self.__write_input_thread.start()
        self.__output_str_collector: bytes = b''
        self.__running = True
        if self.__show_detail:
            print(self.__cmd)

    def wait(self):
        try:
            self.__sub_proc.wait()
            self.__running = False
        except KeyboardInterrupt:
            self.__sub_proc.terminate()
            self.__sub_proc.wait()
            print("用户主动退出")  # 捕获 Ctrl+C 以允许用户中断命令

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

    def output_chunk_callback(self, output_chunk: bytes):

        if self.__show_detail:
            send_once_already = False

            while not send_once_already:
                try:
                    result = output_chunk.decode('utf-8')
                    print(result, end='', flush=True)  # 输出字符，不换行，立即刷新
                    send_once_already = True
                except UnicodeDecodeError as e:
                    b_array = bytearray(output_chunk)
                    for i in range(e.start, e.end):
                        b_array[i] = 0x20  # 错误字符串替换为空格
                    output_chunk = bytes(b_array)
        # self.__output_str_collector += output_chunk

    def output_timeout_and_wait_input_callback(self) -> str:
        print("线程1等待超时，未收到信号，等待用户输入")
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
        print("[read_output thread exit]")

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
        print("[write_input thread exit]")


class StdoutReDirector(tk.Text):
    """由tk.Text改装的控制台输出管线"""

    def __init__(self, master=None, cnf={}, **kw):
        # 调用父类的Text控件初始化方法
        tk.Text.__init__(self, master, cnf, **kw)

    def write(self, s):
        # 控制台调用print函数时会调用该函数进行写操作，再次实现该函数，达到调用print时将结果输出到TextField的效果
        self.insert("end", s)

    def flush(self):
        # 实现一下flush函数u2库好像调用了该函数，不声明会报错
        self.delete("1.0", "end")


class MainUI(tk.Tk):
    """继承tk.Frame的主窗口，master为窗口的父控件"""

    def close_window(self):
        # 当窗口被关闭时，调用这个方法
        self.ProxyProc.force_close()

        # self.MongoDbProc.force_close()
        # self.destroy()  # 销毁窗口控件总容器
        # sys.stdout = self.console  # 将控制台管道切换回原始状态

    def __init__(self):
        # 初始化Application的Frame部分

        super().__init__()
        self.title('python黑客工具箱')
        # 设置窗体大小
        self.geometry('1000x600')
        # 在最顶层的父类窗口中可以截取窗口关闭事件，以运行窗口退出时希望实现的方法closeWindow
        self.protocol('WM_DELETE_WINDOW', self.close_window)
        self.option_add("*Font", "微软雅黑")

        self.RecordProc = None  # 记录ScrCpy的录屏进程，方便进程终止与重启
        self.CastScreenProc = None  # 记录ScrCpy的投屏进程，方便进程终止与重启
        self.console = sys.stdout  # 保存原始控制台方便切换
        self.SwitchConsole = True  # 检测当前是否为改装控制台

        # 一套输入控件
        self.InputLabel = tk.Label(self, text="设备号")  # 输入框提示标签
        self.InputField = tk.Entry(self, textvariable="input", width='100')  # 输入框
        self.InputField.bind("<Return>", self.RunCmd)  # 对输入框绑定enter监听事件，回车回运行cmd命令
        self.connectButton = tk.Button(self, text="抓抓", command=lambda: print("抓抓"))
        # 一套输出控件
        self.OutputLabel = tk.Label(self, text="控制台")  # 控制台输出面板提示标签
        self.OutputField = StdoutReDirector(self, width='100', height='10')  # 负责显示控制台打印输出
        self.ConsoleButton = tk.Button(self, text="切换命令行显示通道", command=self.ChangeConsole)
        self.ImageLabel = tk.Label(self)  # 负责显示OpenCv处理和识别后的结果图
        self.Photo = None  # 负责暂存ImageLabel中要显示的图片，如果不用指针存储显示图片，图片会自动销毁
        self.ImageSize = (500, 300)  # 设置ImageLabel的显示比例

        # 其他工具控件
        self.subFrame = tk.Frame(self)  # 创建一个子面板作为工具箱
        self.AutoButton = tk.Button(self.subFrame, text="安卓自动化", command=lambda: print("安卓自动化"))
        self.AutoGetCards = tk.Button(self.subFrame, text="自动抽卡", command=lambda: print("自动抽卡"))
        self.Base64Button = tk.Button(self.subFrame, text="转Base64", command=lambda: print("转Base64"))
        self.RecordMovie = tk.Button(self.subFrame, text="录制视频",
                                     command=lambda: print("录制视频"))
        self.CastScreen = tk.Button(self.subFrame, text="投屏", command=lambda: print("投屏"))
        self.OpenCVButton = tk.Button(self.subFrame, text="图像分析",
                                      command=lambda: print("图像分析"))  # 临时测试OpenCV识别效果

        self.createLayout()  # 初始化各个控件的布局
        # self.ChangeConsole()  # 初始化时改变输出管线

        self.ProxyProc = self.run_cmd_thread(
            "mitmdump.exe -s ./miniproxy/proxy.py -p 7070 -k --set connection_strategy=lazy --set upstream_cert=false",
            True)
        # self.MongoDbProc = self.run_cmd_thread(".\Database\mongod.exe --dbpath .\Database\data --port 27017", True)
        # os.system("start .\Database\mongod.exe --dbpath .\Database\data --port 27017")
        os.system("Start.bat")

    def run_cmd_thread(self, cmd: str, show_detail=True):
        p = InteractiveCmd(cmd, show_detail=show_detail)
        start_thread(p.wait, ())
        return p

    def createLayout(self):
        # 显示窗口，并使用grid布局
        self.grid()
        # 初始化输入框内文字
        self.InputField.delete(0, "end")
        self.InputField.insert(0,
                               "mitmdump.exe -s ./miniproxy/proxy.py -p 7070 -k --set connection_strategy=lazy --set upstream_cert=false")
        # 输入控件布局
        self.connectButton.grid(row=0, column=2)
        self.InputLabel.grid(row=0, column=0, sticky=tk.E)
        self.InputField.grid(row=0, column=1)
        # 输出控件布局
        self.OutputLabel.grid(row=1, column=0, sticky=tk.E)
        self.OutputField.grid(row=1, column=1)
        self.ConsoleButton.grid(row=2, column=1)
        self.ImageLabel.grid(row=3, column=1)
        # 边栏工具按钮
        self.subFrame.grid(row=1, column=3)
        self.OpenCVButton.grid(row=1, column=0, sticky=tk.E)  # 设这些控件靠东(east)也就是靠右
        self.AutoButton.grid(row=2, column=0, sticky=tk.E)
        self.AutoGetCards.grid(row=3, column=0, sticky=tk.E)
        self.Base64Button.grid(row=1, column=1, sticky=tk.W)  # 设这些控件靠西(west)也就是靠左
        self.RecordMovie.grid(row=2, column=1, sticky=tk.W)
        self.CastScreen.grid(row=3, column=1, sticky=tk.W)

    def RunCmd(self, event):
        if type(event) is not str:  # 如果不是字符说明是键盘响应事件调用的RunCmd，因此要从输入框获取cmd命令
            # print(event.char) # event记录了用户点击的按键的各种属性，event.char对应的是按键所对应的字符串
            cmd = self.InputField.get()
        else:
            cmd = event  # 如果是字符，说明event本身就是cmd命令，可以直接运行
        P = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        # command_output = P.stdout.read().decode('utf-8') 使用utf-8格式对输出有很多限制，因此弃用该方法
        print(P.stdout.read())  # 打印控制台输出

    def ChangeConsole(self):
        self.OutputField.delete("1.0", "end")  # 切换控制台管道时，历史记录
        if self.SwitchConsole:  # 控制台输出切换扳机，True，False无所谓其实
            sys.stdout = self.OutputField
        else:
            sys.stdout = self.console
        self.SwitchConsole = not self.SwitchConsole  # 切换扳机反向


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


if __name__ == '__main__':
    if not is_admin():
        if sys.version_info[0] == 3:
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, __file__, None, 1)
    else:
        # 初始化主窗口控件
        app = MainUI()
        # 主循环开始
        try:
            app.mainloop()  # 正常主循环会卡在这里
        except KeyboardInterrupt as e:
            os.system("taskkill /f /im mongod.exe")
            os.system("taskkill /f /im java.exe")
        os.system("taskkill /f /im mongod.exe")
        os.system("taskkill /f /im java.exe")
