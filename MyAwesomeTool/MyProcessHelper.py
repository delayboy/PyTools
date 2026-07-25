import psutil
import subprocess
import ctypes


def run_cmd_new_window(command="ping www.baidu.com"):
    # 使用ShellExecuteW启动一个新的cmd窗口并运行命令
    sub_cmd = '/c {}'.format(command + "||pause")
    print(sub_cmd)
    ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", sub_cmd, None, 1)


def run_cmd_new_window2():
    # 使用ShellExecuteW启动一个新的cmd窗口并运行命令
    result = subprocess.run(
        ['Z:\\Program Files (Portable)\\IDA PRO 7.5 (x86, x64, ARM, ARM64)\\plugins\\fakepdb\\win32\\fakepdb.exe',
         'pe_guidage',
         'C:\\Users\\14094\\Desktop\\Latest-Benson-FakeSign\\Signtool-TimeStamping-Fake自建时间戳版\\签名工具逆向\\DSignTool.exe'],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        universal_newlines=True)
    # p = subprocess.Popen([self.__executable_path] + args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # stdout, _ = p.communicate()
    # return stdout
    return result.stdout + result.stderr  # , result.stderr


def run_cmd(cmd_command: str):
    # 使用subprocess执行命令，设置参数为非阻塞模式
    process = subprocess.Popen(cmd_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    # 获取命令的标准输出和标准错误输出
    stdout, stderr = process.communicate()
    # 打印输出结果
    print("标准输出：")
    print(stdout.decode('utf-8'))

    print("标准错误输出：")
    print(stderr.decode('utf-8'))


def search_process_by_name(process_name) -> int:
    for proc in psutil.process_iter(['pid', 'name']):
        print(f"Process Name: {proc.info['name']}, PID: {proc.info['pid']}")
        if proc.info['name'].__contains__(process_name):
            return proc.info['pid']
    return -1


def kill_process_by_pid(pid):
    try:
        process = psutil.Process(pid)
        process.terminate()
        print(f"Process with PID {pid} terminated.")
    except psutil.NoSuchProcess:
        print(f"Process with PID {pid} not found.")
    except psutil.AccessDenied:
        print(f"Access denied for terminating process with PID {pid}.")


if __name__ == '__main__':
    print('    * command return: %s' % run_cmd_new_window2())
    # aim_pid = search_process_by_name("WeChat.exe")
    # kill_process_by_pid(aim_pid)
