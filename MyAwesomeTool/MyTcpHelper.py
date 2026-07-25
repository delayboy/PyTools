import socket
import time
from typing import Dict, List, Callable, TypeVar
import threading
import ctypes
import numpy as np
import pickle
import serial


class ComSocket:
    def __init__(self, *args):
        self.ip = '/dev/ttyUSB0'
        self.port = 9600
        self.ser: serial.Serial = None

    def connect(self, __address) -> None:
        self.ip = __address[0]
        self.port = __address[1]
        self.ser = serial.Serial(self.ip, self.port, rtscts=True)  # , xonxoff=True 会忽略x13

    def close(self) -> None:
        if self.ser is not None:
            self.ser.close()

    def settimeout(self, __value: float | None) -> None:
        # self.ser.timeout = __value
        pass

    def bind(self, __address) -> None:
        self.ip = __address[0]
        self.port = __address[1]
        pass

    def send(self, __data, __flags: int = 0) -> int:
        self.ser.reset_output_buffer()  # 清空输出缓冲
        # self.ser.reset_input_buffer()  # 清空输入缓冲
        # chunk_size = 32
        # total_sent = 0
        # for i in range(0, len(__data), chunk_size):
        #     chunk = __data[i:i + chunk_size]
        #     total_sent += self.ser.write(chunk)
        #     time.sleep(0.05)  # 发送延时，确保接收端有足够时间处理
        # print("Total sent:", total_sent)
        total_sent = self.ser.write(__data)
        # print("Total sent:", total_sent)
        # print("send", __data)
        return total_sent

    def recv(self, __bufsize: int, __flags: int = 0) -> bytes:
        data = bytearray()
        start_time = time.time()
        # print("re", __bufsize)
        while len(data) < __bufsize:
            # 检查是否有新数据可读取
            should_sleep = False
            if self.ser.in_waiting > 0:
                data.extend(self.ser.read_all())
            else:
                should_sleep = True

            # 如果数据足够则返回
            if len(data) >= __bufsize:
                break

            # 超时处理，避免无限等待
            if len(data) > 0 and time.time() - start_time > 0.01:
                break
            if should_sleep:
                time.sleep(0.001)

        # print("recv:", data)
        return bytes(data)

    def listen(self, __backlog: int = 0) -> None:
        self.ser = serial.Serial(self.ip, self.port, rtscts=True)  # , xonxoff=True 会忽略x13

    def accept(self):
        return self, "虚拟串口地址"


def start_thread(target, args: tuple = ()):
    # 子线程启动函数，用于开启一个子线程，target为需要运行目标方法
    threading.Thread(target=target, args=args).start()


class PackageHeader(ctypes.Structure):
    _fields_ = [
        ("valid", ctypes.c_int64),
        ("pkLength", ctypes.c_int64),
        ("code", ctypes.c_int64),
    ]

    def __init__(self, data: np.ndarray, code=0):
        super().__init__(*(), **{})
        self.valid = 0x123456
        self.data: np.ndarray = data
        self.data.dtype = np.uint8
        self.pkLength = self.data.__len__()
        self.code = code

    @classmethod
    def init_str_header(cls, message: str, code=1):
        b_message = message.encode('utf-8')
        return cls.init_binary_header(b_message, code)

    @classmethod
    def init_binary_header(cls, b_message: bytes, code=0):
        data = np.frombuffer(b_message, dtype=np.uint8)
        return cls(data, code)

    def get_str_data(self) -> str:
        try:
            return self.data.tobytes().decode('utf-8')
        except UnicodeDecodeError as e:
            print("UnicodeDecodeError", e)
            return ""

    def get_any_obj(self):
        return pickle.loads(self.data.tobytes())

    def append(self, data: np.ndarray):
        self.data = np.append(self.data, data)

    def to_array(self) -> np.ndarray:
        # np.zeros((ctypes.sizeof(PackageHeader),), dtype=np.uint8)
        info = np.array(np.frombuffer(self, dtype=np.uint8))

        info = np.append(info, self.data)
        return info

    def format_data(self):
        self.data = self.data[0:self.pkLength]


class TcpHandler:
    TcpBase = TypeVar('TcpBase', bound='TcpBase')

    def __init__(self, timeout=-1):
        self.recv_signal = threading.Event()
        self.response_pk: PackageHeader = None
        self.timeout = timeout

    def raw_response_callback(self, response: bytes):
        self.set_signal(False)

    def set_signal(self, wait: bool = True):
        if wait:
            self.recv_signal.clear()
        else:
            self.recv_signal.set()

    def wait_for_signal(self):
        if self.timeout > 0:
            self.recv_signal.wait(timeout=self.timeout)
        else:
            self.recv_signal.wait()

    def callback(self, tcp_base: TcpBase, pk: PackageHeader) -> str:
        self.response_pk = pk
        self.set_signal(False)

    def on_add_data(self, tcp_base: TcpBase, pk: PackageHeader, new_data: np.ndarray):
        pass


class TcpBase:

    def __init__(self, handler: TcpHandler):
        self.running = True
        self.pkSize = ctypes.sizeof(PackageHeader)
        self.handler: TcpHandler = handler
        self.handler.set_signal(True)
        self.client_socket = None
        self.queue: np.ndarray = np.array([], dtype=np.uint8)
        self.send_queue: List[bytes] = []
        self.__inner_tcp_loop_over_event = threading.Event()
        self.__inner_send_loop_over_event = threading.Event()

    def is_connect(self):
        return self.client_socket is not None

    def find_package_header_index(self, byte_array: np.ndarray) -> int:
        for i in range(0, byte_array.__len__() - self.pkSize + 1):
            pk_header = PackageHeader.from_buffer_copy(byte_array, i)
            if pk_header.valid == 0x123456:
                return i
        return -1

    def stop(self):
        self.running = False
        if self.client_socket is not None:
            self.client_socket.close()
        self.__inner_tcp_loop_over_event.wait()
        self.__inner_send_loop_over_event.wait()

    def start(self):
        start_thread(self.__inner_tcp_loop, ())
        start_thread(self.send_loop, ())

    def __inner_tcp_loop(self):
        self.__inner_tcp_loop_over_event.clear()
        self.tcp_loop()
        self.__inner_tcp_loop_over_event.set()

    def tcp_loop(self):
        raise NotImplementedError("子类必须实现tcp_loop()方法")

    def send_loop(self):
        self.__inner_send_loop_over_event.clear()
        while self.running:
            if self.send_queue.__len__() > 0:
                raw = self.send_queue[0]
                self.send_raw(raw, wait=False)
                self.send_queue = self.send_queue[1:]
            else:
                time.sleep(0.1)
        self.__inner_send_loop_over_event.set()

    def send_raw(self, raw_bytes: bytes, wait: bool = True) -> PackageHeader | None:
        try:
            if self.client_socket is None:
                return None
            # 接收服务器的响应数据
            self.handler.set_signal(True)
            self.client_socket.send(raw_bytes)
            if wait:
                self.handler.wait_for_signal()
                return self.handler.response_pk
            return None
        except Exception as e:
            print("发生错误：", e)
            # 关闭客户端套接字
            self.client_socket.close()
            self.client_socket = None
            return None

    def send_pk(self, header: PackageHeader, wait: bool = True) -> PackageHeader | None:
        return self.send_raw(header.to_array().tobytes(), wait)

    def async_queue_send_raw(self, raw_bytes: bytes):
        if self.send_queue.__len__() < 10:  # 最多压队10组
            self.send_queue.append(raw_bytes)

    def async_queue_send_pk(self, header: PackageHeader):
        self.async_queue_send_raw(header.to_array().tobytes())

    def send_str(self, response: str, code=1, wait: bool = True) -> PackageHeader | None:
        header = PackageHeader.init_str_header(response, code)
        return self.send_pk(header, wait)

    def send_any_obj(self, any_obj, code=0, wait: bool = True) -> PackageHeader | None:
        return self.send_binary(pickle.dumps(any_obj), code, wait)

    def send_binary(self, raw_bytes: bytes, code=0, wait: bool = True) -> PackageHeader | None:
        header = PackageHeader.init_binary_header(raw_bytes, code)
        return self.send_raw(header.to_array().tobytes(), wait)

    def send_array(self, data: np.ndarray, code=0, wait: bool = True) -> PackageHeader | None:
        # 发送数据到服务器
        header = PackageHeader(data, code)
        return self.send_pk(header, wait)

    def default_callback(self, pk_header: PackageHeader):
        if self.handler is not None:
            self.handler.callback(self, pk_header)
        self.client_socket.send(b'0')

    def socket_recv_loop(self, client_socket):
        pk_header = None
        self.handler: TcpHandler = self.handler
        while self.running:
            try:
                # 接收客户端消息
                request = client_socket.recv(1024)
                self.handler.raw_response_callback(request)
                if request == b'0':
                    continue
                request = np.frombuffer(request, dtype=np.uint8)
                self.queue = np.append(self.queue, request)

                if len(request) <= 0:
                    print("reset due to request is None")
                    break

                buffer_end = len(self.queue)

                if pk_header is None:
                    if buffer_end < self.pkSize:
                        continue
                    header_start = self.find_package_header_index(self.queue)
                    if header_start < 0:
                        self.queue = np.array([], dtype=np.uint8)
                        continue
                    pk_header = PackageHeader.from_buffer_copy(self.queue, header_start)
                    pk_header.data = np.array([], dtype=np.uint8)
                    self.queue = self.queue[header_start + ctypes.sizeof(PackageHeader):]
                    buffer_end = len(self.queue)

                if pk_header is None:
                    continue

                if pk_header.data.__len__() < pk_header.pkLength:
                    rest_length = pk_header.pkLength - pk_header.data.__len__()
                    end = buffer_end if buffer_end < rest_length else rest_length
                    if self.handler is not None:
                        self.handler.on_add_data(self, pk_header, self.queue[0:end])
                    pk_header.append(self.queue[0:end])
                    self.queue = self.queue[end:]

                if pk_header.data.__len__() >= pk_header.pkLength:
                    pk_header.format_data()
                    offset = pk_header.pkLength - pk_header.data.__len__()
                    if offset < 0:
                        raise Exception("包长和预期不匹配")

                    start_thread(self.default_callback, (pk_header,))
                    pk_header = None  # 下一次重新获取包头
                else:
                    pass  # 下一次从0开始取

            except TimeoutError:
                # print("ConnectionAbortedError")
                client_socket.close()
                break

            except ConnectionAbortedError:
                # 关闭客户端连接
                # print("ConnectionAbortedError")
                client_socket.close()
                break
            except ConnectionResetError:
                # 关闭客户端连接
                # print("ConnectionResetError")
                client_socket.close()
                break
        self.client_socket = None
        self.handler.set_signal(False)


class TcpServer(TcpBase):

    def __init__(self, handler: TcpHandler, host='0.0.0.0', port=5353):
        super().__init__(handler)
        self.host = host
        self.port = port

    def is_com_type(self):
        return self.host.__contains__("COM")

    def tcp_loop(self):
        # 定义服务器地址和端口

        # 创建一个TCP socket对象
        server_socket = ComSocket() if self.host.__contains__("COM") else \
            socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # 绑定服务器地址和端口
        server_socket.bind((self.host, self.port))
        # 监听连接
        server_socket.listen(1)
        while self.running:
            # 接受客户端连接
            print('服务器已启动，等待客户端连接...')
            self.client_socket = None
            client_socket, client_address = server_socket.accept()
            client_socket.settimeout(5000)
            print('客户端已连接：', client_address)
            self.client_socket = client_socket
            self.socket_recv_loop(self.client_socket)

        # 关闭服务器socket
        server_socket.close()
        self.running = False


class TcpClient(TcpBase):
    def __init__(self, handler: TcpHandler, server_ip='127.0.0.1', server_port=5353, keep_alive=False):
        # 服务器地址和端口
        super().__init__(handler)
        self.server_ip = server_ip
        self.server_port = server_port
        self.keep_alive = keep_alive
        self.connect()
        self.start()

    def is_com_type(self):
        return self.server_ip.__contains__("COM")

    def tcp_loop(self):

        if self.keep_alive:  # keep alive状态下反复连接服务器，永不停止
            while self.running:
                if self.client_socket is not None:
                    self.socket_recv_loop(self.client_socket)
                self.client_socket = None
                self.connect()

        else:
            if self.client_socket is not None:
                self.socket_recv_loop(self.client_socket)
            self.running = False

    def connect(self):
        if self.client_socket is not None:
            return

        # 创建一个TCP套接字
        client_socket = ComSocket() if self.server_ip.__contains__("COM") else \
            socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            # 连接到服务器
            client_socket.connect((self.server_ip, self.server_port))
            self.client_socket = client_socket  # 连接成功再赋值
        except OSError as e:
            client_socket.close()
            self.client_socket = None
            print(time.asctime(), e)


class TcpCollector(TcpHandler):
    def __init__(self, collect_callback: Callable[[list], str]):
        super().__init__()
        self.__list = []
        self.collect_callback = collect_callback

    def callback(self, tcp_base: TcpBase, header: PackageHeader) -> str:
        if header.code == 0:
            header.data.dtype = np.int16
            print(header.data)
            self.__list.append(header.data)
            return "default"
        else:
            res = self.collect_callback(self.__list)
            self.__list = []
            tcp_base.send_str(res)
            return res


class DefaultTcpServerHandler(TcpHandler):

    def callback(self, tcp_base: TcpServer, pk: PackageHeader) -> str:
        print(pk.get_str_data())
        tcp_base.send_str("hello from server")
        # num = 0
        # while True:
        #     da = np.array([1, 2, 3, 4], dtype=np.int16)
        #     client.send_str("{}".format(num), wait=True)
        #     num += 1


class DefaultTcpClientHandler(TcpHandler):

    def raw_response_callback(self, response: bytes):
        pass

    def callback(self, tcp_base: TcpClient, pk: PackageHeader) -> str:
        super().callback(tcp_base, pk)


class TestObj:
    def __init__(self):
        self.c = 1
        self.b = 2


test_ce_lua_script = """
local jsonString = '%s'

-- 将json字符串解析为Lua表
local myTable = json.decode(jsonString)

-- 访问表属性
--print(myTable.firstname)

local born_time = readFloat(gameobj+0x18);
if born_time < 0.1 then
  writeFloat(gameobj+0x18,game_time);
  born_time = game_time;
end
local rest_life_time = 4 - (game_time-born_time);
if rest_life_time > 4 then
   rest_life_time = 4;
end
if rest_life_time < -4 then
   rest_life_time = -4;
end

return jsonString
"""
test_ce_lua_script2 = """

local game_time_base = readQword(getAddress("data_addr7FF9A28E189E"))
local game_time = readFloat(game_time_base+0x5C)
local ingame = readInteger(getAddress("data_addr7FF9A28E189E")+0x8)
local blood_base = readQword(getAddress("float_blood_addr"));
local score_base = readQword(getAddress("float_score_addr"));

local player_base =readQword(getAddress("data_addr7FF9AC4BA50F"));

local player_x = readFloat(player_base+0x28);
local player_z = readFloat(player_base+0x24);
local player_y = readFloat(player_base+0x20);

local score = readFloat(score_base+0x16C);
local energy = readFloat(score_base+0xB8);
local using_energy = readInteger(score_base+0x1B8);
local blood = readInteger(blood_base);

local game_obj_list = {elements={},game_time=game_time,ingame=ingame,count=0,score=score,using_energy=using_energy,energy=energy,blood=blood,x=player_x,y=player_y,z=player_z};


local timeout=getTickCount()+5000;
monopipe=connectToPipe('cemonodc_pid'..getOpenedProcessID() ,mono_timeout);
monopipe.writeByte(CMD_INITMONO);
local q = monopipe.readQword();
if q ~= 0 then
    monopipe.lock()
    monopipe.writeByte(MONOCMD_ENUMDOMAINS)
    local count=monopipe.readDword()
    if count~=nil then
      result={}
      local i
      for i=1, count do
        result[i]=monopipe.readQword()
        local gameobj = result[i];
        local z_pos =readFloat(gameobj+0x6C);
        local y_pos=readFloat(gameobj+0x68);
        local index_in_g_table = readInteger(gameobj+0x1A0);
        local is_hide = readInteger(gameobj+0xE8);
        local life_time = readFloat(gameobj+0xE0);
        local tagId=readInteger(gameobj+0x294);
        tagId = (tagId - 0x3DBC8B8D) % 1000 + 1;

        local obj = {index=index_in_g_table,life_time=life_time,is_hide=is_hide,addr=string.format("0x%x",gameobj),z_pos=z_pos,y_pos=y_pos,x_pos=readFloat(gameobj+0x70),tag=tagId}
        table.insert(game_obj_list.elements,obj)
      end
    end
    monopipe.unlock()
    game_obj_list.count = count;
end
monopipe.destroy();
return json.encode(game_obj_list);
"""
test_ce_lua_script3 = """
local game_time_base = readQword(getAddress("data_addr7FF9A28E189E"))
local game_time = readFloat(game_time_base+0x5C)
local ingame = readInteger(getAddress("data_addr7FF9A28E189E")+0x8)
local blood_base = readQword(getAddress("float_blood_addr"));
local score_base = readQword(getAddress("float_score_addr"));
local unit_gameobj_base =readQword(getAddress("data_addr7FFA83200DF2"))
local player_base =readQword(getAddress("data_addr7FF9AC4BA50F"));

local player_x = readFloat(player_base+0x28);
local player_z = readFloat(player_base+0x24);
local player_y = readFloat(player_base+0x20);

local score = readFloat(score_base+0x16C);
local energy = readFloat(score_base+0xB8);
local using_energy = readInteger(score_base+0x1B8);
local blood = readInteger(blood_base);

local game_obj_list = {elements={},game_time=game_time,ingame=ingame,count=0,score=score,using_energy=using_energy,energy=energy,blood=blood,x=player_x,y=player_y,z=player_z};

local count=0;
for i=3028,5040 do
    local offset = i*8;
    local gameobj = readQword(unit_gameobj_base+ offset);
    local z_pos =readFloat(gameobj+0x6C);
    local y_pos=readFloat(gameobj+0x68);
    local tagId=readInteger(gameobj+0x294);
    if y_pos~=nil and z_pos~=nil and tagId~=nil  then
        tagId = (tagId - 0x3DBC8B8D) % 1000 + 1;
        --0xC 怪物唯一标识符 0x48怪物是否已经倒下
        if (z_pos>-14.76 and z_pos < -12.2 and y_pos> 375.8975 ) and readInteger(gameobj+0xC)==251658297 and readInteger(gameobj+0x48)==0 then--or (z_pos>-12.76 and z_pos < -12.3 and tagId==1073741824) then --筛选出子弹
          
           local is_hide = readInteger(gameobj+0xE8);
           local life_time = readFloat(gameobj+0xE0);
           
           local is_dead_base = readQword(gameobj+0x110);
           local is_dead =readInteger(is_dead_base+0x90); -- 4193997783 is alive  2883351975 is dead
    
           if is_hide== 0 and (is_dead==nil or is_dead > 2983351975)  then --去掉玩家的gameobject，筛选出滚筒
           local index_in_g_table = readInteger(gameobj+0x1A0);
           local obj = {index=index_in_g_table,life_time=life_time,is_hide=is_hide,addr=string.format("0x%x",gameobj),z_pos=z_pos,y_pos=y_pos,x_pos=readFloat(gameobj+0x70),tag=tagId}
           table.insert(game_obj_list.elements,obj)
           count = count+1;
           end
        end
    end
end
game_obj_list.count = count;
return json.encode(game_obj_list);

"""


def tcp_client_run_lua_json_in_ce():
    # server = TcpServer(DefaultTcpServerHandler())
    # server.start()
    import psutil
    import os

    def loop():
        if False:
            json_input = json.dumps({"firstname": "John", "lastname": "Doe", "age": 23})
            pk = ce_client.send_str("return nil", wait=True)
            if pk is not None:
                print(pk.get_str_data())
                js_dic = json.loads(pk.get_str_data())
                ele_s = js_dic["elements"]
                ele_s.sort(key=lambda item: item["life_time"], reverse=False)
                print(pk.code, js_dic["count"], js_dic["elements"], "\n", end='')
            a = input()
        else:
            pk = ce_client.send_str(test_ce_lua_script2, wait=True)
            if pk is not None:
                json_str = pk.get_str_data()
                print(json_str)
        time.sleep(0.5)
        print("set pause")

    ce_client = TcpClient(DefaultTcpClientHandler(), server_port=5151)  #
    import json
    while True:
        loop()


if __name__ == '__main__':
    # tcp_client_run_lua_json_in_ce()
    # server = TcpServer(DefaultTcpServerHandler(), port=9600)
    # server.start()
    # a = input()
    client = TcpClient(DefaultTcpClientHandler(), server_ip="best.delayboy.cn", server_port=6000, keep_alive=True)  #
    # client.start()
    num = 0
    while True:
        # ob = TestObj()
        # client.send_any_obj(ob)
        # da = np.array([1, 2, 3, 4], dtype=np.int16)
        pk2 = client.send_str("{}---hello_server---测试与调试---hello_server---hello_server".format(num), wait=True)
        if pk2 is not None:
            print(pk2.code, pk2.get_str_data() + "\n", end='')
        # a = input()
        num += 1
        time.sleep(0.2)
