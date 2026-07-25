import sys
import win32com.client
import os
import pythoncom
from PyTools.MyAwesomeTool.MyUtil import get_file_from_env_path


def write_link(lnk_path, target_path):
    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(lnk_path)
    shortcut.Targetpath = target_path
    shortcut.save()


def smart_guess_file_or_link(lnk_path: str, use_env=True) -> str:
    if not lnk_path.__contains__(":") and use_env:  # 先在环境变量中寻找目标
        env_path = get_file_from_env_path(lnk_path)
        if env_path is None:  # 如果直接在path中找不到
            env_path = get_file_from_env_path(lnk_path + ".lnk")  # 补全成快捷方式再寻找一次

        if env_path is None:  # 如果怎么都找不到，就直接使用当前文件夹下文件
            lnk_path = os.path.abspath(lnk_path)
        else:
            lnk_path = env_path
    if not lnk_path.__contains__(":"):  # 如果仍然是相对路径，则先转换为绝对路径
        lnk_path = os.path.abspath(lnk_path)

    if os.path.isfile(lnk_path):  # 如果文件本来就存在则直接返回原文件,lnk文件的话解析一下再返回
        return read_link(lnk_path) if lnk_path.endswith(".lnk") else lnk_path
    else:  # 否则尝试一下补全成快捷方式，再寻找异常，看能不能找到文件
        lnk_path = lnk_path + ".lnk"

    if not os.path.isfile(lnk_path):  # 如果lnk本身都不存在则直接抛出异常退出
        raise Exception(f'the target file [{lnk_path}] does not exist')
    return read_link(lnk_path)


def read_link(lnk_path: str) -> str:
    pythoncom.CoInitialize()
    shell = win32com.client.Dispatch("WScript.Shell")
    shortcut = shell.CreateShortCut(lnk_path)
    path = shortcut.Targetpath
    print(path)
    # 释放资源
    # pythoncom.CoUninitialize()
    return path


def walk_all_file(rootDir) -> list:
    tab = []
    for root, dirs, files in os.walk(rootDir):
        for file in files:
            tab.append(file)
            tail = os.path.splitext(file)[-1]  # 获取文件后缀名
            if tail.__eq__(".lnk"):
                lnkPath = os.path.join(root, file)
                # print(lnkPath)
                refPath = read_link(lnkPath)
                refPath = refPath.replace("E:\\", "Z:\\")
                write_link(os.path.join(dirAim, file), refPath)
            for subDir in dirs:
                walk_all_file(subDir)
    return tab


if __name__ == '__main__':
    dirRoot = "C:/Users/14094/AppData/Roaming/Microsoft/Windows/Start Menu/Programs/utools快速访问"
    dirAim = "D:\\lnk"
    walk_all_file(dirRoot)
