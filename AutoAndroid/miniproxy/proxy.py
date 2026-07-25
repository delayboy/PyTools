##
#
#   Copyright (C) 2002-2022 MlgmXyysd All Rights Reserved.
#
##

##
#
#   Animation Company script for mitmproxy
#
#   https://github.com/MlgmXyysd/
#
#   *Original fiddler script from https://github.lunatic.moe/fiddlerscript
#
#   Environment requirement:
#     - mitmdump from mitmproxy
#
#   @author MlgmXyysd
#   @version 1.1
#
##

import collections
import random
from mitmproxy import http, connection, ctx, tls
from abc import ABC, abstractmethod
from enum import Enum
from mitmproxy.utils import human
from mitmproxy.connection import Server
from mitmproxy.net.server_spec import ServerSpec
from proxy_config import USE_SSL
from proxy_config import REMOTE_HOST
from proxy_config import REMOTE_PORT
from urllib.parse import urlparse
import winreg as reg
import os
import threading
import time
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning

# 禁用不验证证书的警告
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
UPSTREAM_PROXY_HEADER = 'X-Upstream-Proxy'

def start_thread(target, args: tuple = ()):
    # 子线程启动函数，用于开启一个子线程，target为需要运行目标方法
    thread_handle = threading.Thread(target=target, args=args)
    thread_handle.start()
    return thread_handle

def set_windows_proxy(proxy,switch=1):
    # 设置代理服务器地址和端口，例如 "http=127.0.0.1:8080;https=127.0.0.1:8080"
    proxy_server = proxy# f"http={proxy};https={proxy}"
    
    # 打开 Windows 注册表项
    internet_settings = reg.OpenKey(reg.HKEY_CURRENT_USER, 
                                    r"Software\Microsoft\Windows\CurrentVersion\Internet Settings",
                                    0, reg.KEY_SET_VALUE)

    # 启用代理
    reg.SetValueEx(internet_settings, "ProxyEnable", 0, reg.REG_DWORD, switch)

    # 设置代理服务器地址
    reg.SetValueEx(internet_settings, "ProxyServer", 0, reg.REG_SZ, proxy_server)

    # 强制代理立即生效
    reg.SetValueEx(internet_settings, "ProxyOverride", 0, reg.REG_SZ, "<local>")

    # 关闭注册表
    reg.CloseKey(internet_settings)
    
    print(f"Proxy set to: {proxy}")



def get_upstream_proxy(flow: http.HTTPFlow) -> tuple[str, tuple[str, int]] | None:
    upstream_proxy = flow.request.headers.get(UPSTREAM_PROXY_HEADER)
    if upstream_proxy is not None:
        parsed_upstream_proxy = urlparse(upstream_proxy)

        if parsed_upstream_proxy.scheme not in ('http', 'https'):
            return None

        del flow.request.headers[UPSTREAM_PROXY_HEADER]
        return parsed_upstream_proxy.scheme, (parsed_upstream_proxy.hostname, parsed_upstream_proxy.port)

    return None

class MlgmXyysd_Animation_Company_Proxy:

    LIST_DOMAINS = [
        "api-os-takumi.mihoyo.com",
        "hk4e-api-os-static.mihoyo.com",
        "hk4e-sdk-os.mihoyo.com",
        "dispatchosglobal.yuanshen.com",
        "osusadispatch.yuanshen.com",
        "account.mihoyo.com",
        "log-upload-os.mihoyo.com",
        "dispatchcntest.yuanshen.com",
        "devlog-upload.mihoyo.com",
        "webstatic.mihoyo.com",
        "log-upload.mihoyo.com",
        "hk4e-sdk.mihoyo.com",
        "api-beta-sdk.mihoyo.com",
        "api-beta-sdk-os.mihoyo.com",
        "cnbeta01dispatch.yuanshen.com",
        "dispatchcnglobal.yuanshen.com",
        "cnbeta02dispatch.yuanshen.com",
        "sdk-os-static.mihoyo.com",
        "webstatic-sea.mihoyo.com",
        "webstatic-sea.hoyoverse.com",
        "hk4e-sdk-os-static.hoyoverse.com",
        "sdk-os-static.hoyoverse.com",
        "api-account-os.hoyoverse.com",
        "hk4e-sdk-os.hoyoverse.com",
        "overseauspider.yuanshen.com",
        "gameapi-account.mihoyo.com",
        "minor-api.mihoyo.com",
        "public-data-api.mihoyo.com",
        "uspider.yuanshen.com",
        "sdk-static.mihoyo.com",
        "abtest-api-data-sg.hoyoverse.com",
        "log-upload-os.hoyoverse.com",
        "www.baidu.com"
    ]
    def __init__(self) -> None:
        
        # 获取当前的监听端口号
        port = ctx.options.listen_port
        print(f"当前监听端口号为: {port}")
        # 示例使用
        set_windows_proxy(f"127.0.0.1:{port}",1)
        def curl_loop():
            # 创建一个会话对象
            session = requests.Session()
            os.environ["HTTP_PROXY"]=f"http://127.0.0.1:{port}"
            while True:
                # print("curl loop is running to keep proxy alive")
                # os.system("curl http://hkrpg-log-upload.mihoyo.com:443 > nul")
                time.sleep(2)
                proxies = {'http': f"http://127.0.0.1:{port}", 'https': f"http://127.0.0.1:{port}"}
                res = session.get('https://hkrpg-log-upload.mihoyo.com',verify=False, proxies=proxies) 
                print(time.asctime(),res.content) 
            # 请求完成后关闭会话
            session.close()
        start_thread(curl_loop,());


    def request(self,flow: http.HTTPFlow) -> None:
     
        if flow.request.host.endswith(".starrails.com") or flow.request.host.endswith(".hoyoverse.com") or flow.request.host.endswith(".mihoyo.com") or flow.request.host.endswith(".bhsr.com"):
             print(f"Host set to: {flow.request.host} {flow.request.port}")
             flow.server_conn.via = None
             flow.request.scheme = "http"
             flow.request.host = REMOTE_HOST  # This can also be replaced with another IP address.
             return
        # if flow.request.host in self.LIST_DOMAINS:
        #     if USE_SSL:
        #         flow.request.scheme = "https"
        #     else:
        #         flow.request.scheme = "http"
        #     flow.request.host = REMOTE_HOST
        #     # flow.request.port = 443
        #     return
        flow.server_conn.via = ('http', ('127.0.0.1', 10809))
        address = (REMOTE_HOST,REMOTE_PORT)
        ctx.log("now upstream server:"+str(flow.server_conn.via))
        if flow.server_conn.via is None:
            is_proxy_change = address != flow.server_conn.via[1]
            server_connection_already_open = flow.server_conn.timestamp_start is not None
            if is_proxy_change and server_connection_already_open:
                # server_conn already refers to an existing connection (which cannot be modified),
                # so we need to replace it with a new server connection object.
                flow.server_conn = Server(address=flow.server_conn.address)
            if is_proxy_change:
                newConnection = ServerSpec(("http", address))
                ctx.log("redirect upstream to addr:"+str(address))
                flow.server_conn.via = newConnection
     
        # if flow.request.pretty_host.__contains__("www.google"):
        #     flow.request.host = "favor.delayboy.cn"

    def done(self):
        set_windows_proxy("127.0.0.1:8080",0)

    # def request(self, flow: http.HTTPFlow) -> None:
            # if USE_SSL:
            #     flow.request.scheme = "https"
            # else:
            #     flow.request.scheme = "http"
            # flow.request.host = REMOTE_HOST
            # flow.request.port = REMOTE_PORT

class InterceptionResult(Enum):
    SUCCESS = 1
    FAILURE = 2
    SKIPPED = 3


class TlsStrategy(ABC):
    def __init__(self):
        self.history = collections.defaultdict(lambda: collections.deque(maxlen=200))

    @abstractmethod
    def should_intercept(self, server_address: connection.Address) -> bool:
        raise NotImplementedError()

    def record_success(self, server_address):
        self.history[server_address].append(InterceptionResult.SUCCESS)

    def record_failure(self, server_address):
        self.history[server_address].append(InterceptionResult.FAILURE)

    def record_skipped(self, server_address):
        self.history[server_address].append(InterceptionResult.SKIPPED)


class ConservativeStrategy(TlsStrategy):
    def should_intercept(self, server_address: connection.Address) -> bool:
        return InterceptionResult.FAILURE not in self.history[server_address]


class ProbabilisticStrategy(TlsStrategy):
    def __init__(self, p: float):
        self.p = p
        super().__init__()

    def should_intercept(self, server_address: connection.Address) -> bool:
        return random.uniform(0, 1) < self.p


class MaybeTls:
    strategy: TlsStrategy

    def load(self, l):
        l.add_option(
            "tls_strategy", int, 0,
            "TLS passthrough strategy. If set to 0, connections will be passed through after the first unsuccessful "
            "handshake. If set to 0 < p <= 100, connections with be passed through with probability p.",
        )

    def configure(self, updated):
        if "tls_strategy" not in updated:
            return
        if ctx.options.tls_strategy > 0:
            self.strategy = ProbabilisticStrategy(ctx.options.tls_strategy / 100)
        else:
            self.strategy = ConservativeStrategy()

    def tls_clienthello(self, data: tls.ClientHelloData):
        server_address = data.context.server.peername
        if not self.strategy.should_intercept(server_address):
            ctx.log(f"TLS passthrough: {human.format_address(server_address)}.")
            data.ignore_connection = True
            self.strategy.record_skipped(server_address)

    def tls_established_client(self, data: tls.TlsData):
        server_address = data.context.server.peername
        ctx.log(f"TLS handshake successful: {human.format_address(server_address)}")
        self.strategy.record_success(server_address)

    def tls_failed_client(self, data: tls.TlsData):
        server_address = data.context.server.peername
        ctx.log(f"TLS handshake failed: {human.format_address(server_address)}")
        self.strategy.record_failure(server_address)
        
addons = [
	MlgmXyysd_Animation_Company_Proxy(),MaybeTls()
]
