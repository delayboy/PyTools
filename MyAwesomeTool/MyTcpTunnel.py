import socket
import threading
import logging
import time
from typing import Tuple
import sys

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Bridge(threading.Thread):
    """TCP流量转发桥接器"""

    def __init__(self, sock1: socket.socket, sock2: socket.socket, name: str):
        super().__init__(daemon=True)
        self.sock1 = sock1
        self.sock2 = sock2
        self.name = name
        self.buffer_size = 4096

    def run(self):
        """启动双向转发"""
        try:
            self._bridge_loop()
        except Exception as e:
            logger.error(f"Bridge {self.name} error: {e}")
        finally:
            self._cleanup()

    def _bridge_loop(self):
        """桥接循环"""
        while True:
            # 检查socket是否仍然有效
            if not self._sockets_valid():
                break

            try:
                # 从sock1读取并转发到sock2
                data = self.sock1.recv(self.buffer_size)
                if not data:
                    logger.info(f"Bridge {self.name}: sock1 closed")
                    break

                self.sock2.sendall(data)
            except socket.timeout:
                continue
            except (socket.error, OSError) as e:
                logger.debug(f"Bridge {self.name} sock1->sock2 error: {e}")
                break

            # 短暂休息避免CPU占用过高
            time.sleep(0.001)

    def _sockets_valid(self) -> bool:
        """检查socket是否仍然有效"""
        try:
            # 使用getsockopt检查socket状态
            self.sock1.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            self.sock2.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
            return True
        except (socket.error, OSError):
            return False

    def _cleanup(self):
        """清理资源"""
        for sock in [self.sock1, self.sock2]:
            try:
                sock.close()
            except:
                pass


class TunnelServer:
    """TCP隧道服务器"""

    def __init__(self, host: str = '0.0.0.0', port: int = 8888,
                 auth_timeout: int = 5, buffer_size: int = 4096):
        self.host = host
        self.port = port
        self.auth_timeout = auth_timeout
        self.buffer_size = buffer_size
        self.running = False
        self.server_socket = None

    def start(self):
        """启动服务器"""
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(10)  # 增加 backlog
            self.server_socket.settimeout(1)  # 设置超时以便可以检查运行状态

            logger.info(f"Tunnel server started on {self.host}:{self.port}")
            self.running = True
            self._accept_loop()

        except Exception as e:
            logger.error(f"Failed to start server: {e}")
            raise
        finally:
            self.stop()

    def stop(self):
        """停止服务器"""
        self.running = False
        if self.server_socket:
            try:
                self.server_socket.close()
            except:
                pass
        logger.info("Tunnel server stopped")

    def _accept_loop(self):
        """接受连接循环"""
        while self.running:
            try:
                # 等待客户端连接（隧道客户端）
                client_sock, client_addr = self.server_socket.accept()
                logger.info(f"New connection from {client_addr}")

                # 在新线程中处理客户端
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_sock, client_addr),
                    daemon=True
                )
                client_thread.start()

            except socket.timeout:
                continue
            except OSError as e:
                if self.running:
                    logger.error(f"Accept error: {e}")
                break

    def _handle_client(self, client_sock: socket.socket, client_addr: Tuple[str, int]):
        """处理隧道客户端连接"""
        try:
            # 认证客户端
            if not self._authenticate_client(client_sock):
                logger.warning(f"Client authentication failed: {client_addr}")
                return

            # 等待用户连接
            user_sock, user_addr = self._wait_for_user_connection()
            if not user_sock:
                logger.warning(f"No user connection received for client: {client_addr}")
                return

            logger.info(f"Starting bridge: {client_addr} <-> {user_addr}")

            # 通知客户端准备就绪
            client_sock.sendall(b'ok')

            # 创建双向桥接
            bridge1 = Bridge(client_sock, user_sock, f"{client_addr}->{user_addr}")
            bridge2 = Bridge(user_sock, client_sock, f"{user_addr}->{client_addr}")

            bridge1.start()
            bridge2.start()

            # 等待桥接完成
            bridge1.join()
            bridge2.join()

        except Exception as e:
            logger.error(f"Error handling client {client_addr}: {e}")
        finally:
            try:
                client_sock.close()
            except:
                pass

    def _authenticate_client(self, sock: socket.socket) -> bool:
        """认证隧道客户端"""
        try:
            sock.settimeout(self.auth_timeout)
            sock.sendall(b'server?')

            data = sock.recv(2)
            if data != b'ok':
                return False

            sock.settimeout(None)
            return True

        except (socket.timeout, socket.error) as e:
            logger.debug(f"Authentication failed: {e}")
            return False

    def _wait_for_user_connection(self, timeout: int = 30) -> Tuple[socket.socket, Tuple[str, int]]:
        """等待用户连接"""
        try:
            self.server_socket.settimeout(timeout)
            user_sock, user_addr = self.server_socket.accept()
            self.server_socket.settimeout(1)
            logger.info(f"User connected from {user_addr}")
            return user_sock, user_addr
        except socket.timeout:
            logger.warning("Timeout waiting for user connection")
            return None, None


class TunnelClient:
    """TCP隧道客户端"""

    def __init__(self, server_host: str, server_port: int,
                 local_host: str = '127.0.0.1', local_port: int = 22,
                 reconnect_delay: int = 5):
        self.server_host = server_host
        self.server_port = server_port
        self.local_host = local_host
        self.local_port = local_port
        self.reconnect_delay = reconnect_delay
        self.running = False

    def start(self):
        """启动客户端"""
        self.running = True
        logger.info(f"Tunnel client started, connecting to {self.server_host}:{self.server_port}")

        while self.running:
            try:
                self._connect_and_serve()
            except Exception as e:
                logger.error(f"Connection error: {e}")

            if self.running:
                logger.info(f"Reconnecting in {self.reconnect_delay} seconds...")
                time.sleep(self.reconnect_delay)

    def stop(self):
        """停止客户端"""
        self.running = False
        logger.info("Tunnel client stopped")

    def _connect_and_serve(self):
        """连接服务器并开始服务"""
        server_sock = None
        local_sock = None

        try:
            # 连接隧道服务器
            server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_sock.settimeout(35)
            server_sock.connect((self.server_host, self.server_port))
            logger.info("Connected to tunnel server")

            # 认证流程
            if not self._authenticate_with_server(server_sock):
                logger.error("Authentication with server failed")
                return

            # 连接本地服务
            local_sock = self._connect_to_local_service()
            if not local_sock:
                logger.error("Failed to connect to local service")
                return

            logger.info("Starting tunnel bridge")

            # 创建双向桥接
            bridge1 = Bridge(server_sock, local_sock, "server->local")
            bridge2 = Bridge(local_sock, server_sock, "local->server")

            bridge1.start()
            bridge2.start()

            # 等待桥接完成
            bridge1.join()
            bridge2.join()

        except socket.timeout:
            logger.error("Connection timeout")
        except ConnectionRefusedError:
            logger.error("Connection refused")
        except Exception as e:
            logger.error(f"Service error: {e}")
        finally:
            # 清理连接
            for sock in [server_sock, local_sock]:
                if sock:
                    try:
                        sock.close()
                    except:
                        pass

    def _authenticate_with_server(self, sock: socket.socket) -> bool:
        """与服务器进行认证"""
        try:
            # 接收服务器询问
            data = sock.recv(7)
            if data != b'server?':
                logger.error(f"Unexpected server message: {data}")
                return False

            # 回复确认
            sock.send(b'ok')
            sock.settimeout(None)

            # 等待服务器准备信号
            data = sock.recv(2)
            if data != b'ok':
                logger.error(f"Server not ready: {data}")
                return False

            return True

        except socket.timeout:
            logger.error("Authentication timeout")
            return False
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False

    def _connect_to_local_service(self) -> socket.socket:
        """连接本地服务"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(10)
            sock.connect((self.local_host, self.local_port))
            sock.settimeout(None)
            logger.info(f"Connected to local service at {self.local_host}:{self.local_port}")
            return sock
        except Exception as e:
            logger.error(f"Failed to connect to local service: {e}")
            return None


def client_main():

    """主函数"""
    if len(sys.argv) > 1:
        server_host = sys.argv[1]
    else:
        server_host = 'best.delayboy.cn'

    client = TunnelClient(
        server_host=server_host,
        server_port=8888,
        local_host='127.0.0.1',
        local_port=9600
    )

    try:
        client.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Client crashed: {e}")
    finally:
        client.stop()


def main():
    """主函数"""
    server = TunnelServer(port=8888)
    try:
        server.start()
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Server crashed: {e}")
    finally:
        server.stop()


if __name__ == "__main__":
    from PyTools.MyAwesomeTool.MyTcpHelper import TcpServer, DefaultTcpServerHandler
    server = TcpServer(DefaultTcpServerHandler(), port=9600)
    server.start()
    client_main()
