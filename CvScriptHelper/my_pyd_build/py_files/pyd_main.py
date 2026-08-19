from __future__ import annotations  # 使用高级注解器，
# from PartnerHelper import main

from PyTools.MyAwesomeTool.MyUtil import auto_patch_python, get_file_list
from PyTools.MyAwesomeTool.MyBoxLayout import ask_choice
from PyTools.MyAwesomeTool.PyUseCPlus import Rect, PyRect, MainUI, MyOpenCv, start_thread, build_logger


# from patch import main
# from patch import *


def hidden_imports():
    import comtypes.stream
    import uiautomation as auto
    from PIL import Image, ImageTk  # pillow型图片支持库
    import tkinter as tk  # 窗口控件支持库
    import base64
    from typing import List, TypeVar, Callable, Generic, Dict, Tuple, Sequence
    import ctypes
    import numpy as np
    import threading
    import time
    import os
    import cv2
    import datetime
    import ctypes
    import time
    from tkinter import ttk
    from uiautomator2 import core
    import pdb

    import numpy.ctypeslib as npct
    import numpy as np
    from typing import Callable, Any
    import win32gui
    import subprocess
    import threading
    from abc import abstractmethod
    import logging
    import os
    import datetime
    from logging.handlers import TimedRotatingFileHandler, RotatingFileHandler
    import hashlib

    # 银行自动化
    import socket
    import time
    from typing import Dict, List, Callable, TypeVar
    import threading
    import ctypes
    import numpy as np
    import PyTools.MyAwesomeTool.MyDll as MyDllLib
    import PyTools.MyAwesomeTool.MyUtil
    import PyTools.MyAwesomeTool.MyTcpHelper
    import PyTools.MyAwesomeTool.PyUseCPlus
    import PyTools.MyAwesomeTool.MyProcessHelper
    import PyTools.MyAwesomeTool.MyLinkHelper
    import os
    import threading
    import time
    from typing import List, TypeVar, Callable, Generic, Tuple, Any, Dict, Type
    import uiautomator2 as u2
    import cv2
    import ctypes
    import numpy as np
    from lxml.etree import _Element as MyXmlElement
    from PyTools.MyAwesomeTool.PyUseCPlus import Rect, PyRect, MainUI, MyOpenCv, start_thread, build_logger
    from PyTools.MyAwesomeTool.MyUtil import group_str_pipline, WxStringClassifier, TimeStringClassifier
    import re
    from datetime import datetime, timedelta

    # 剪贴板辅助
    import os.path
    import threading
    import time
    import pyaudio
    import soundfile
    import cv2
    import numpy as np
    import win32clipboard
    from PyTools.MyAwesomeTool.MyDll import HookPackage
    import PyTools.MyAwesomeTool.MyDll as MyDll
    from PyTools.MyAwesomeTool.PyUseCPlus import WinManager, start_thread, image_to_binary_arr, binary_arr_to_image, \
        Rect, \
        MyOpenCv, AndroidApp
    from PyTools.MyAwesomeTool.MyTcpHelper import TcpServer, TcpClient, TcpHandler, PackageHeader, TcpBase
    from PyTools.MyAwesomeTool.MyUtil import auto_patch_python
    from PyTools.MyAwesomeTool.KeDaSoundToText import ke_da_main
    from PIL import Image
    import matplotlib.pyplot as plt
    import locale
    import serial
    import opencc
    import torchvision
    import pypinyin
    from selenium import webdriver
    import customtkinter
    import ultralytics
    import PyTools.MyAwesomeTool.pack_icons
    import PyTools.MyAwesomeTool.MyWebDriver
    import PyTools.MyAwesomeTool.MyBoxLayout
    import mineru
    from mineru.model.ocr.paddleocr2pytorch.pytorch_paddle import PytorchPaddleOCR
    import mineru.model.ocr.paddleocr2pytorch.pytorch_paddle as pp

    # 强制设置系统默认编码为UTF-8
    import easyocr


if __name__ == '__main__':
    chosen = ask_choice("黑客工具箱", "请选择patch方式：", get_file_list("./patch"))
    if chosen:
        print(f"用户选择了: {chosen}")
        while True:
            md5_py = auto_patch_python(globals(), patch_path=chosen)
            main(md5_py, chosen)
            print("over")
