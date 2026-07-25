# coding=utf8
import tkinter as tk  # 窗口控件支持库
from tkinter import filedialog  # 文件选择弹窗
import threading  # 子进程调用库f
import sys  # 控制台管理与切换支持库
import io  # 二进制读写库
import codecs  # 二进制UTF-8读写支持库
import uiautomator2 as u2  # 手机控制与连接库(点击、截图、识别手机控件等)
import subprocess  # cmd命令运行库，负责发送adb命令，运行插件中的命令行工具
import signal  # cmd Ctrl+C终结指令信号发送支持库
from PIL import Image, ImageTk  # pillow型图片支持库
import cv2  # OpenCV图像识别支持库
import time  # 延时函数支持库
import numpy  # 矩阵运算支持库
import os  # 绝对路径获取支持库

TempFilePath = os.path.dirname(os.path.abspath(".\\Temp")) + "\\Temp\\"  # 获取临时文件夹在电脑上的绝对路径
TempLateFilePath = os.path.dirname(os.path.abspath(".\\Template")) + "\\Template\\"  # 获取模板文件夹在电脑上的绝对路径
PluginPath = os.path.dirname(os.path.abspath(".\\plugin")) + "\\plugin\\"  # 获取插件文件夹在电脑上的绝对路径


def TestImage(img: numpy.ndarray):
    # 临时展示OpenCV的图像，专门用于测试
    cv2.imshow('MyOpenCV', img)
    cv2.waitKey(0)  # 进程阻塞在此处，等待键盘按键
    cv2.destroyAllWindows()  # 按键结束后销毁所有图像窗口


def StartThread(target, args: tuple = ()):
    # 子线程启动函数，用于开启一个子线程，target为需要运行目标方法
    threading.Thread(target=target, args=args).start()


def kill(proc: subprocess.Popen, useCtrl=False):
    # 但是录制视频或下载文件时，命令行一般使用流传输，线程比较复杂，因此只能使用ctrl+c进行终结，这种终结方式对所有线程都有效
    # 包括python自己的主窗口线程
    if useCtrl:
        proc.send_signal(signal.CTRL_C_EVENT)
        # 另一种ctrl+c终结方式：os.kill(proc.pid, signal.CTRL_C_EVENT)
    else:
        # 使用taskKill命令终止cmd命令运行可以避免ctrl+c终止整个python程序的异常
        os.system("taskkill /t /f /pid %s" % proc.pid)
    # 命令行终止后，将子进程对象释放掉(置空），防止之后对空对象操作。
    proc.kill()
    # 使用wait等待子进程指令的回显全部打印完成后才退出。
    proc.wait()


def WriteFile(path, content):
    # 将图片信息写入对应路径
    file_handle = codecs.open(path, 'w', "utf-8")
    file_handle.write(content)


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

    def closeWindow(self):
        # 当窗口被关闭时，调用这个方法
        sys.stdout = self.console  # 将控制台管道切换回原始状态
        self.master.destroy()  # 销毁窗口控件总容器
        if self.CastScreenProc is not None:
            kill(self.CastScreenProc)  # 如果在投屏，结束投屏
        if self.RecordProc is not None:
            kill(self.RecordProc, useCtrl=True)  # 如果在录像，结束录像并报错

    def __init__(self):
        # 初始化Application的Frame部分

        super().__init__()
        self.title('python黑客工具箱')
        # 设置窗体大小
        self.geometry('1000x600')
        # 在最顶层的父类窗口中可以截取窗口关闭事件，以运行窗口退出时希望实现的方法closeWindow
        self.protocol('WM_DELETE_WINDOW', self.closeWindow)
        self.option_add("*Font", "微软雅黑")
        
        self.device: u2.Device = None  # 全局手机设备存储变量，只在第一次调用初始化方法时绑定手机，绑定后不再更改
        self.RecordProc = None  # 记录ScrCpy的录屏进程，方便进程终止与重启
        self.CastScreenProc = None  # 记录ScrCpy的投屏进程，方便进程终止与重启

        self.console = sys.stdout  # 保存原始控制台方便切换
        self.SwitchConsole = True  # 检测当前是否为改装控制台

        # 一套输入控件
        self.InputLabel = tk.Label(self, text="设备号")  # 输入框提示标签
        self.InputField = tk.Entry(self, textvariable="input", width='100')  # 输入框
        self.InputField.bind("<Return>", self.RunCmd)  # 对输入框绑定enter监听事件，回车回运行cmd命令
        self.connectButton = tk.Button(self, text="抓抓", command=lambda: StartThread(self.Capture()))
        # 一套输出控件
        self.OutputLabel = tk.Label(self, text="控制台")  # 控制台输出面板提示标签
        self.OutputField = StdoutReDirector(self, width='100', height='10')  # 负责显示控制台打印输出
        self.ConsoleButton = tk.Button(self, text="切换命令行显示通道", command=self.ChangeConsole)
        self.ImageLabel = tk.Label(self)  # 负责显示OpenCv处理和识别后的结果图
        self.Photo = None  # 负责暂存ImageLabel中要显示的图片，如果不用指针存储显示图片，图片会自动销毁
        self.ImageSize = (500, 300)  # 设置ImageLabel的显示比例

        # 其他工具控件
        self.subFrame = tk.Frame(self)  # 创建一个子面板作为工具箱
        self.AutoButton = tk.Button(self.subFrame, text="安卓自动化", command=lambda: StartThread(self.AutoAndroid))
        self.AutoGetCards = tk.Button(self.subFrame, text="自动抽卡", command=lambda: StartThread(self.AutoCards))
        self.Base64Button = tk.Button(self.subFrame, text="转Base64", command=lambda: StartThread(self.Base64Change))
        self.RecordMovie = tk.Button(self.subFrame, text="录制视频", command=lambda: StartThread(self.ScreenCpy, (True,)))
        self.CastScreen = tk.Button(self.subFrame, text="投屏", command=lambda: StartThread(self.ScreenCpy))
        self.OpenCVButton = tk.Button(self.subFrame, text="图像分析",
                                      command=lambda: StartThread(MyOpenCV(self).GetLogOut))  # 临时测试OpenCV识别效果

        self.createLayout()  # 初始化各个控件的布局
        self.ChangeConsole()  # 初始化时改变输出管线
        self.RunCmd("adb devices")  # 初始化时运行cmd命令

    def createLayout(self):
        # 显示窗口，并使用grid布局
        self.grid()
        # 初始化输入框内文字
        self.InputField.delete(0, "end")
        self.InputField.insert(0, "38ae6a45")
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

    def Base64Change(self):
        path = tk.filedialog.askopenfile()  # 获取图片路径
        self.OutputField.delete("1.0", "end")  # 清空控制台输出
        import base64
        with open(path.name, 'rb') as f:
            base64_data = base64.b64encode(f.read())  # 读取文件并使用base64编码
            s = base64_data.decode()  # base64转为字符
            print('data:image/jpeg;base64,%s' % s)  # 串接字符生成“字符串”图片

    def ScreenCpy(self, record: bool = False):
        # scrCpy插件调用函数，支持投屏与录制两种模式（两种功能可以并发，但不能多开）
        if record:
            Proc = self.RecordProc  # 获取之前保存的录屏进程
            if Proc is not None:  # 如果正在录屏，就结束录屏进程，实现的效果：第二次点击停止录屏
                kill(Proc, useCtrl=True)  # 使用ctrl+c的方式结束进程，否则录制的视频文件不正常
                self.RecordProc = None
            else:
                # 调用srcCpy插件，-N启用静默模式，禁止录屏过程中投屏，-r 指定输出到临时文件夹中文件用Output.mp4命名
                cmd = PluginPath + "scrcpy.exe" + " -N " + " -r " + TempFilePath + "Output.mp4"
                # 运行cmd命令，shell=True设置使用系统自带的cmd窗口，不使用自带的cmd工具，录制的视频文件会出现错误。
                Proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT)
                self.RecordProc = Proc  # 用全局进程指针保存当前正在运行的子进程
                print(cmd)
                print(Proc.stdout.read())  # 由于录制视频时程序不退出，进程会卡在这里一直读取
                # 通过启动另一个子线程，对Proc进行结束操作，Proc才会停止读取和打印操作
        else:
            Proc = self.CastScreenProc  # 获取之前保存的投屏进程
            if Proc is not None:  # 如果正在投屏，就结束投屏进程，实现的效果：第二次点击停止投屏
                kill(Proc)  # 使用正常的强制kill方法结束投屏进程，如果使用ctrl+c终止进程，投屏进程关闭时会导致录屏进程也关闭
                self.CastScreenProc = None
            else:
                cmd = PluginPath + "scrcpy.exe"  # 直接运行插件即可，所有参数均为默认值
                Proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT)
                self.CastScreenProc = Proc  # 用全局进程指针保存当前正在运行的子进程
                print(cmd)
                print(Proc.stdout.read())  # 由于投屏时程序不退出，进程会卡在这里一直读取
                # 通过启动另一个子线程，对Proc进行结束操作，Proc才会停止读取和打印操作

    def opUiObject(self, d: u2.UiObject, text: str):
        if d.exists:
            if text.__eq__("click"):
                d.click()
                time.sleep(1)
            else:
                d.click()
                time.sleep(1)
                d.set_text(text)
                time.sleep(1)
                self.InitializeDevice().click(1005, 1504)  # 点击屏幕中间收起键盘
                time.sleep(1)
        print(text)

    def mustFind(self, **kwargs) -> u2.UiObject:
        d = self.InitializeDevice()
        device = d(**kwargs)
        while not device.exists:
            self.device.swipe(520, 1894, 500, 1794)
            device = d(**kwargs)
            if kwargs.get("text") is None:
                print(kwargs.get("textContains"))
            else:
                print(kwargs.get("text"))
        return device

    def AutoCards(self):
        print("cards")
        d = self.InitializeDevice()
        self.opUiObject(d(textContains="在籍本科生", instance=0), "click")
        self.opUiObject(d(text="否", instance=0), "click")
        self.opUiObject(d(text="否", instance=1), "click")
        self.opUiObject(d(text="否", instance=2), "click")
        self.opUiObject(d(text="否", instance=3), "click")
        self.opUiObject(d(text="否", instance=4), "click")
        print("cards over")

    def AutoAndroid(self):
        print("Auto")
        # StartThread(self.ScreenCpy)  # 启动投屏进程
        d = self.InitializeDevice()
        d.implicitly_wait(2.0)
        self.opUiObject(d(textContains="正确输入学号", instance=0), "18026202")
        self.opUiObject(d(textContains="正确输入本人姓名", instance=0), "吕泊伸")
        self.opUiObject(d(textContains="正确输入手机号", instance=0), "13716616824")
        self.opUiObject(d(text="学生类型", instance=0), "click")
        self.opUiObject(d(text="本科生", instance=0), "click")
        self.opUiObject(d(text="确定", instance=0), "click")
        self.opUiObject(self.mustFind(text="入校类型", instance=0), "click")
        self.opUiObject(d(text="确定", instance=0), "click")
        self.opUiObject(d(textContains="出入中蓝公寓", instance=0), "click")
        self.opUiObject(d(text="确定", instance=0), "click")
        self.opUiObject(d(textContains="出入校本部西区", instance=0), "click")
        self.opUiObject(d(text="是", instance=0), "click")
        self.opUiObject(d(text="确定", instance=0), "click")
        self.opUiObject(self.mustFind(textContains="出入通州校区", instance=0), "click")
        self.opUiObject(d.xpath("//android.widget.TextView[@text=\"确定\"]"), "click")
        self.opUiObject(d.xpath("//*[contains(@text, '是否离京')]"), "click")
        self.opUiObject(d.xpath("//android.widget.TextView[@text=\"确定\"]"), "click")
        self.opUiObject(d.xpath("//*[contains(@text, '是否去过中高风险地区')]"), "click")
        self.opUiObject(d.xpath("//android.widget.TextView[@text=\"确定\"]"), "click")
        self.opUiObject(d(textContains="地区风险等级", instance=0), "click")
        self.opUiObject(d(text="低风险地区", instance=0), "click")
        self.opUiObject(d(text="确定", instance=0), "click")
        self.opUiObject(d.xpath("//*[contains(@text, '填写详细地址')]"), "北京昌平区天通苑四区25号楼五单元402")
        self.opUiObject(self.mustFind(textContains="目前所在位置", instance=0), "click")
        d(text="确定").wait(timeout=10.0)
        self.opUiObject(d(text="确定", instance=0), "click")
        self.opUiObject(self.mustFind(text="自测体温", instance=0), "click")
        self.opUiObject(d.xpath("//android.widget.TextView[@text=\"确定\"]"), "click")
        self.opUiObject(d(text="健康码", instance=0), "click")
        self.opUiObject(d.xpath("//android.widget.TextView[@text=\"确定\"]"), "click")
        self.opUiObject(d(text="行程码", instance=0), "click")
        self.opUiObject(d.xpath("//android.widget.TextView[@text=\"确定\"]"), "click")
        self.opUiObject(d(textContains="内核酸检测结果", instance=0), "click")
        self.opUiObject(d.xpath("//android.widget.TextView[@text=\"确定\"]"), "click")
        self.opUiObject(d(textContains="抵京当日核酸检测结果", instance=0), "click")
        self.opUiObject(d.xpath("//android.widget.TextView[@text=\"确定\"]"), "click")
        self.opUiObject(d.xpath(
            '//*[@text="wx403094a4d093a136:pages/create/create.html:VISIBLE"]/android.view.View[6]/android.view.View[2]/android.view.View[3]'),
            "click")
        self.opUiObject(d.xpath("//*[@text=\"请输入\"]"), "秦素琦")
        self.opUiObject(d(textContains="个人承诺", instance=0), "click")
        self.opUiObject(d.xpath("//android.widget.TextView[@text=\"确定\"]"), "click")
        print("finish")

    def RunCmd(self, event):
        if type(event) is not str:  # 如果不是字符说明是键盘响应事件调用的RunCmd，因此要从输入框获取cmd命令
            # print(event.char) # event记录了用户点击的按键的各种属性，event.char对应的是按键所对应的字符串
            cmd = self.InputField.get()
        else:
            cmd = event  # 如果是字符，说明event本身就是cmd命令，可以直接运行
        P = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        # command_output = P.stdout.read().decode('utf-8') 使用utf-8格式对输出有很多限制，因此弃用该方法
        print(P.stdout.read())  # 打印控制台输出

    def Capture(self):
        # 抓抓
        d = self.InitializeDevice()  # 与手机建立绑定关系
        print(d.info)  # 打印绑定信息
        path = filedialog.askdirectory(initialdir="D:\\Tempfile")  # 获取输出文件夹啊的路径
        print(path)
        image = BytesToImage(TakeScreenShot(d), d.window_size())  # 使用高精度截图方便分析
        print(d.window_size())  # 打印当前手机状态
        image.save(path + "\\test.png")  # 存储截图
        DUMP = d.dump_hierarchy()  # 获取手机控件解析文件
        WriteFile(path + "\\test.uix", DUMP)  # 存储解析文件
        MyOpenCV(self).ShowImage()  # 所有工作都完成后，在窗口上显示图片

    def ChangeConsole(self):
        self.OutputField.delete("1.0", "end")  # 切换控制台管道时，历史记录
        if self.SwitchConsole:  # 控制台输出切换扳机，True，False无所谓其实
            sys.stdout = self.OutputField
        else:
            sys.stdout = self.console
        self.SwitchConsole = not self.SwitchConsole  # 切换扳机反向

    """想要建立连接必须先运行cmd命令：uiautomator2 init"""

    def InitializeDevice(self) -> u2.Device:
        # 与手机建立绑定的设备初始化函数
        if self.device is not None:
            d = self.device  # 如果之前已经建立过绑定，就使用之前的绑定
        else:
            DeviceNum = self.InputField.get()  # 获取输入框内的设备号
            d = u2.connect(str(DeviceNum))  # 通过设备号与手机建立连接
            self.device = d  # 用全局指针，存储绑定好的设备变量，避免二次绑定，提高程序效率
        return d


class MyOpenCV:
    """OpenCV图像识别工具类，负责识别游戏中的图形按钮"""

    # 只有类传递的的是地址，因此必须传递窗口主类
    def __init__(self, mainUI: MainUI):
        # 实测OpenCv背景透明的图片是没有用的！！！
        # 因为在匹配前矩阵会做去色处理，是不会保留Alpha通道的，最后还是会被自动分配白色或者黑色
        # 因此不如使用具有强烈对比色的黑或白作为背景，效果要好很多
        # 至于具体选择白色还是黑色根据实际效果来定，基本原则是根据周边像素的冷暖色来定，冷色用黑，暖色用白
        # 最一劳永逸的方式还是使用方形图片进行识别
        self.mainUI = mainUI  # 获取主窗口控件类，方便在主窗口显示图片识别和标注结果。
        self.Path = TempLateFilePath  # 模板文件夹
        self.WelfareOver = self.Path + "WelfareOver.png"  # 已领取模板
        self.PaiMan = self.Path + "PaiMan.png"  # 派蒙模板
        self.GripEveryDay = self.Path + "GripEveryDay.png"  # 把握每日按钮
        self.CloseTemplate = self.Path + "close2.png"  # 关闭按钮
        self.OkButton = self.Path + "OKButton.png"  # 确定按钮
        self.LogOut = self.Path + "LOGOUT.png"  # 退出登陆按钮
        self.Activity = self.Path + "Activity.png"  # 游戏主页活动栏按钮
        self.img = cv2.imread(TempFilePath + "temp.png")  # 从临时文件夹内获取手机屏幕截图

    """单图识别:获取各种模板的识别结果，以tuple型坐标作为返回值"""

    def GetActivity(self) -> tuple:
        return self.GetTemplate(self.Activity, 0.5, (1513, 21), (2083, 102))

    def GetLogOut(self) -> tuple:
        return self.GetTemplate(self.LogOut, 0.99, (2097, 919), (2180, 988))

    def GetOkButton(self) -> tuple:
        return self.GetTemplate(self.OkButton, 0.99)

    def GetCloseButton(self) -> tuple:
        return self.GetTemplate(self.CloseTemplate, 0.8, (2095, 5), (2207, 94))

    def GetGripEveryDay(self) -> tuple:
        return self.GetTemplate(self.GripEveryDay, 0.9, (185, 161), (600, 877))

    def GetPaiMan(self) -> tuple:
        return self.GetTemplate(self.PaiMan, 0.4, (100, 0), (213, 104))

    def GetTemplate(self, Template, threshold=0.9, Top_Left: tuple = None, Bottom_Right: tuple = None):
        im_gray = cv2.cvtColor(self.img, cv2.COLOR_BGR2GRAY)  # 对游戏界面截图进行去色处理
        Template = cv2.imread(Template, 0)  # 以灰度(无色)模式读取模板图片
        # 用模板对游戏截图进行单图匹配计算，设置预期的匹配度threshold，返回匹配到的图片所在坐标
        loc = self.GetMatchSingle(im_gray, Template, threshold)
        # 检测是匹配到了模板图片，并且对目标图片的位置进行“矩形”约束，要求返回的坐标点必须在某个矩形范围内，不在范围内也会返回坐标为空
        if loc is not None and self.PosInRange(loc, Top_Left, Bottom_Right):
            return self.DrawSingleMatchResult(loc, Template)
        else:
            return None

    def DrawSingleMatchResult(self, loc, Template) -> tuple:
        self.DrawRect(self.img, loc, Template)  # 标注识别到的模板图片的位置
        w, h = self.GetImageSize(Template)  # 获取模板图片的宽和高
        Aim = tuple((int(loc[0] + w / 2), int(loc[1] + h / 2)))  # 取模板图片中心点，作为点击目标(标记像素点必须为整数)
        cv2.rectangle(self.img, Aim, (Aim[0] + w, Aim[1] + h), (0, 255, 0), 10)  # 使用绿色标注要手机即将点击的坐标
        self.ShowImage()  # 在主窗口展示图片
        return Aim  # 返回计算好的点击的坐标

    @staticmethod
    def PosInRange(pos, top_left, bottom_right) -> bool:
        # 对匹配到的坐标结果进行矩形约束，要求识别出的坐标结果一定要在一个矩形范围内
        # top_left为矩形左上点，bottom_right为矩形右下点
        # 如果没有设置矩形范围，就认为不想使用约束，直接返回真
        if top_left is None or bottom_right is None:
            return True
        # 否则要求目标坐标必须在矩形范围内才返回真
        inRange = False
        if top_left[0] < pos[0] < bottom_right[0]:
            if top_left[1] < pos[1] < bottom_right[1]:
                inRange = True
        return inRange

    @staticmethod
    def GetMatchSingle(im_gray: numpy.ndarray, template: numpy.ndarray, threshold=0.9):
        res = cv2.matchTemplate(im_gray, template, cv2.TM_CCOEFF_NORMED)  # 使用TM_CCOEFF相关系数匹配法 1表示完美的匹配；-1表示最差的匹配。
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)  # 获取矩阵的最大特征值和最小特征值所在的位置，和对应的图片坐标
        if max_val >= threshold:
            return max_loc
        else:
            return None

    """多图识别:获取米友社模板图的匹配结果，以tuple型坐标返回需要点击的坐标"""

    def GetWelfare(self) -> list:
        img = self.img  # 获取游戏截图
        Template = cv2.imread(self.WelfareOver, 0)  # 使用无色模式读取模板图

        loc = self.GetMatchMat(img, Template, 0.5)  # 获取多图匹配结果，匹配度大于0.5即可保留
        if loc.__len__() <= 0:
            return None  # 没有匹配结果，返回空
        else:
            # 通过特殊算法获取所有已领取图片构成的矩形范围，top为左上点，bottom为右下点
            Top, Bottom = self.GetWelfareRange(loc)
            Aim = self.GetWelfareAimPoint(Bottom)  # 沿着右下点对坐标进行偏移计算，即可获取到希望点击的图片坐标
            self.GetMatchResultImage(img, loc, Template)  # 绘制匹配到的结果图
            cv2.rectangle(img, Top, Bottom, (0, 255, 0), 10)  # 标注特殊算法计算出的矩形范围
            self.DrawRect(img, tuple(Aim), Template, (255, 0, 0))  # 标注希望点击的位置坐标
            self.ShowImage()  # 在主窗口内展示控件
            return Aim  # 返回希望点击的坐标位置

    def GetGripEveryDayPoints(self) -> list:
        Template = cv2.imread(self.GripEveryDay, 0)  # 随便获取一个模板图的属性方便画图
        re = list([])  # 坐标输出列表
        a = (1363, 475)  # 第一行第一个奖励坐标
        b = (1363, 730)  # 第二行第一个奖励坐标
        step = 185  # 每个奖励之间的横向偏移量
        nun_in_line = 4  # 每行有几个奖励
        # 遍历所有可能的把握每日奖励的位置，上下两行分别向右侧偏移四个步长，并记录坐标值
        for i in range(0, nun_in_line):
            temp = (a[0] + i * step, a[1])
            re.append(temp)
            temp = (b[0] + i * step, b[1])
            re.append(temp)
        self.GetMatchResultImage(self.img, re, Template)  # 标注遍历出来的所有坐标点
        self.ShowImage()  # 在主窗口内显示标注结果
        return re

    def ShowImage(self, zoom_scale=0.2):
        # 在主窗口内显示图片
        img = self.img  # 获取游戏截图
        x, y = self.GetImageSize(img)  # 获取图片大小
        zoom_image = cv2.resize(img, (int(x * zoom_scale), int(y * zoom_scale)))  # 对图片按照zoom_scale进行缩放处理
        if self.mainUI.ImageLabel is not None:  # 如果主窗口显示控件存在
            image = Image.fromarray(cv2.cvtColor(zoom_image, cv2.COLOR_BGR2RGB))  # 将OpenCV数组图转换为pillow图像
            self.mainUI.Photo = ImageTk.PhotoImage(image)  # 生成pillow图像的Photo格式
            self.mainUI.ImageLabel.__setitem__("imag", self.mainUI.Photo)  # 将Photo显示在主窗口中
        else:
            cv2.imshow('MyOpenCV', zoom_image)
            cv2.waitKey(0)
            cv2.destroyAllWindows()

    def GetMatchResultImage(self, img: numpy.ndarray, PosMat: list, template: numpy.ndarray) -> numpy.ndarray:
        # 绘制多图识别的坐标结果，遍历所有坐标并绘制矩形
        for pt in PosMat:
            self.DrawRect(img, pt, template)
        return img

    def DrawRect(self, img: numpy.ndarray, pos: tuple, template: numpy.ndarray, RGB=(0, 0, 255)):
        # 按模板大小在游戏截图的对应位置上绘制一个矩形，默认使用红色。
        # 注：OpenCV的RGB，R和B是反的不知道为什么。
        w, h = self.GetImageSize(template)
        cv2.rectangle(img, pos, (pos[0] + w, pos[1] + h), RGB, 10)

    @staticmethod
    def GetMatchMat(img: numpy.ndarray, template: numpy.ndarray, threshold=0.9) -> list:
        im_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        # res 返回一个长和宽为图片大小的二维矩阵，矩阵中的元素为：模板图片与原图片的匹配度。
        res = cv2.matchTemplate(im_gray, template, cv2.TM_CCOEFF_NORMED)
        # loc是两个numpy.ndarray组成的二维tuple，loc[0]可以获取所有x坐标，loc[1]可以获取所有y轴坐标
        loc = numpy.where(res >= threshold)  # 返回满足要求的匹配度所对应的矩阵索引值，也就是图像坐标啦。
        LocTable = list([])  # 存储得到的所有匹配坐标
        # zip可以将tuple里的两个数组一一对应绑定在一起成为一个新的单位tuple组成的数组，每个数组中存储了x坐标和y坐标
        # *号使得生成的数组可以被迭代
        for pt in zip(*loc[::-1]):
            LocTable.append(pt)
        return LocTable

    @staticmethod
    def GetWelfareRange(Loc: list) -> tuple:
        """ 函数通过符号->标注了返回值为tuple类型, 通过Loc：标注了传入参数的类型为列表 """
        Top_left = [1014, 2172]  # 随便赋个初值，在屏幕右下角
        Bottom_Right = list([133, 1009])  # 默认初值为第一行第一张图的左上角坐标
        # 第一次循环负责找到左上的点，和y轴的最大值
        for pt in Loc:
            if pt[0] < Top_left[0]:
                Top_left[0] = pt[0]
            if pt[1] < Top_left[1]:
                Top_left[1] = pt[1]
            if pt[1] >= Bottom_Right[1]:
                Bottom_Right[1] = pt[1]
        for pt in Loc:  # 沿着y轴最大值横向扫描，取最右边的点，作为最终的右下点
            if abs(Bottom_Right[1] - pt[1]) <= 20:  # 横向扫描时，上下相差阈值小于20的点都被认为在同一行
                if pt[0] > Bottom_Right[0]:
                    Bottom_Right[0] = pt[0]
        return tuple(Top_left), tuple(Bottom_Right)  # 返回左上点和右下点

    @staticmethod
    def GetWelfareAimPoint(Bottom_Right: tuple) -> list:
        # 根据获取到的右下点，计算将要点击的下一个奖励的位置
        Bottom_Right = list(Bottom_Right)  # 将tuple转为list方便赋值操作
        if Bottom_Right[0] + 240 < 1000:  # 向右偏移240个像素没出屏幕，就说明下一张图片在当前图片右侧
            Bottom_Right[0] = Bottom_Right[0] + 240
        elif Bottom_Right[1] + 328 < 2000:  # 出了屏幕就向下偏移328，同时让横坐标回到133的位置（重启一行）
            Bottom_Right[0] = 133
            Bottom_Right[1] = Bottom_Right[1] + 330
        return Bottom_Right  # 都出屏幕范围了，就随便给个坐标，反正也点不到了

    @staticmethod
    def GetImageSize(img: numpy.ndarray) -> int:
        # 获取图片的宽和高，img存储的宽和高信息是反着的，这个有待研究
        y, x = img.shape[0:2]
        return x, y

    @staticmethod
    def GetPointRGB(img: numpy.ndarray, x, y) -> tuple:
        # 获取图中某个坐标点的像素值，这个方法目前没有用到
        RGB = tuple(img[y, x])
        print(RGB)
        return RGB


def TakeScreenShot(d: u2.Device) -> io.BytesIO:
    # 通过adb和AutoApp进行高精度截图
    process = None
    Size = d.window_size()  # 获取当前手机窗口状态
    if Size[0] > Size[1]:  # x比y大说明为横屏模式，此时使用AutoApp进行截图
        result = ""
        while not result.__contains__("OK"):  # 如果返回了ok说明截图成功，可以退出循环
            temp = "check"
            # 有的时候uiautomator脚本线程会被占用，因此先终端原有线程
            # 如果返回值什么都没有就说明终端成功了，有东西说明线程还在运行
            while not temp.__eq__(""):
                clear = "adb shell am force-stop com.github.uiautomator"
                process = subprocess.Popen(clear, shell=True, stdout=subprocess.PIPE,
                                           stderr=subprocess.STDOUT)
                process.wait()
                check = "adb shell ps | find \"iautomator\""  # 获取当前进程的运行状态
                process = subprocess.Popen(check, shell=True, stdout=subprocess.PIPE,
                                           stderr=subprocess.STDOUT)
                temp = process.stdout.read()  # 检测运行状态返回值
            cmd = "adb shell am instrument -w -r    -e debug false -e class \'com.example.autoapp.UiTest#testDemo\' com.example.autoapp.test/android.support.test.runner.AndroidJUnitRunner"
            print(cmd)
            # 成功结束线程后，创建AutoApp自动化脚本线程，调用com.example.autoapp.UiTest的testDemo函数进行截图(指定函数调用运行速度会加快)
            # 截图会保存在手机的/sdcard/temp.png路径下
            process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT)
            result = str(process.stdout.read())  # 将截图结果保存到result中，如果成功截图才退出
            print(result)

    else:  # 竖屏截图
        process = subprocess.Popen("adb shell screencap -p /sdcard/temp.png", shell=True, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT)
    process.wait()  # 等待命令成功运行完，使用adb截图并将图片保存在/sdcard/temp.png
    process = subprocess.Popen("adb pull /sdcard/temp.png " + TempFilePath + "temp.png", shell=True,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT)
    print("adb pull /sdcard/temp.png " + TempFilePath + "temp.png")
    process.wait()  # 将之前保存的截图下载到电脑上，保存在临时文件夹中以temp.png命名
    with open(TempFilePath + "temp.png", 'rb') as f:
        command_output = f.read()
    buff = io.BytesIO(command_output)
    return buff  # 读取temp.data返回二进制字节


def TakeQuickScreenShot(d: u2.Device):
    # 快速截图虽然图像横屏时会有一定失真但是速度快，在对识别精度要求不高的情况下可以使用这个方法，提高程序运行效率
    image = d.screenshot().resize(d.window_size(), Image.ANTIALIAS)  # 使用线性插值对图像进行展缩
    image.save(TempFilePath + "temp.png")
    return image


def BytesToImage(buff, ImageSize):  # 将二进制字节转换为pillow型图片
    try:
        image = Image.open(buff).convert("RGB")
        return image.resize(ImageSize, Image.ANTIALIAS)  # 将图片调整到适应屏幕大小
    except IOError:
        # 截图失败直接返回一个粉色的图片
        return Image.new("RGB", ImageSize, (220, 120, 100))


# 初始化主窗口控件
app = MainUI()
# 主循环开始
while True:
    try:
        app.mainloop()  # 正常主循环会卡在这里
        app = None  # 正常退出主窗口会运行变量归零操作
        if app is None:
            break  # 正常退出主窗口会跳出死循环
    except KeyboardInterrupt:  # 由于使用ctrl+c终端录屏进程时，主窗口进程也会中断，因此捕捉这个异常，让主循环重新启动
        print("重启UI")  # 捕捉异常时，app=None的代码没有正常运行而被跳过了，因此死循环不退出。

# # 为线程定义一个函数
# def print_time(threadName, delay):
#     count = 0
#     while 1:
#         time.sleep(delay)
#         count += 1
#         print("%s: %s" % (threadName, time.ctime(time.time())))
#
#
# try:
#     _thread.start_new_thread(print_time, ("Thread-1", 2,))
#     _thread.start_new_thread(print_time, ("Thread-2", 4,))
# except:
#     print("Error: 无法启动线程")

# 定时器写法
# # set process 300 sec timeout
# proc_timeout = 300
# proc_timer = Timer(proc_timeout, kill, [proc_obj.pid])
# try:
#     # start timer
#     proc_timer.start()
#     # python 2 not supported proc_exec.wait(timeout=300)
#     rt_code = proc_exec.wait()
# finally:
#     proc_timer.cancel()
