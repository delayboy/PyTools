import socket
import threading
import time
import json
from datetime import datetime

import socket
import threading
import time
import json
import uuid
import sys


class NATUdpServer:
    def __init__(self, host='0.0.0.0', port=8888):
        self.host = host
        self.port = port
        self.clients = {}  # {client_id: (public_addr, last_seen)}
        self.client_info = {}  # {client_id: {'name': name, 'local_addr': local_addr}}
        self.lock = threading.Lock()

    def start(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind((self.host, self.port))
        print(f"NAT穿透服务器启动在 {self.host}:{self.port}")

        # 启动清理线程
        cleaner = threading.Thread(target=self.cleanup_clients, daemon=True)
        cleaner.start()

        while True:
            try:
                data, addr = self.sock.recvfrom(1024)
                threading.Thread(target=self.handle_client, args=(data, addr)).start()
            except Exception as e:
                print(f"接收数据错误: {e}")

    def handle_client(self, data, addr):
        try:
            message = json.loads(data.decode('utf-8'))
            client_id = message.get('client_id')
            action = message.get('action')

            if action == 'register':
                self.register_client(client_id, addr, message)
            elif action == 'get_peers':
                self.send_peer_info(client_id, addr)
            elif action == 'connect_request':
                self.handle_connect_request(client_id, message.get('target_id'))
            elif action == 'heartbeat':
                self.update_heartbeat(client_id, addr)

        except json.JSONDecodeError:
            print(f"无效的JSON数据来自 {addr}")
        except Exception as e:
            print(f"处理客户端消息错误: {e}")

    def register_client(self, client_id, addr, message):
        with self.lock:
            self.clients[client_id] = (addr, time.time())
            self.client_info[client_id] = {
                'name': message.get('name', 'Unknown'),
                'local_addr': message.get('local_addr', 'Unknown')
            }
        print(f"客户端注册: {client_id} ({addr}) - {self.client_info[client_id]['name']}")
        self.send_response(client_id, addr, {'status': 'registered'})

    def send_peer_info(self, client_id, addr):
        with self.lock:
            peers = []
            for cid, info in self.client_info.items():
                if cid != client_id:
                    peers.append({
                        'client_id': cid,
                        'name': info['name'],
                        'public_addr': self.clients[cid][0]
                    })

        response = {
            'action': 'peer_list',
            'peers': peers
        }
        self.send_response(client_id, addr, response)

    def handle_connect_request(self, client_id, target_id):
        with self.lock:
            if target_id not in self.clients:
                self.send_response(client_id, self.clients[client_id][0],
                                   {'status': 'error', 'message': '目标客户端不存在'})
                return

            # 告诉目标客户端有人要连接
            target_addr = self.clients[target_id][0]
            connect_msg = {
                'action': 'incoming_connection',
                'from_client': client_id,
                'from_name': self.client_info[client_id]['name'],
                'from_public_addr': self.clients[client_id][0]
            }

            # 告诉发起方目标客户端的公网地址
            initiator_msg = {
                'action': 'target_info',
                'target_id': target_id,
                'target_name': self.client_info[target_id]['name'],
                'target_public_addr': target_addr
            }

            self.send_response(target_id, target_addr, connect_msg)
            self.send_response(client_id, self.clients[client_id][0], initiator_msg)

            print(f"连接请求: {client_id} -> {target_id}")

    def update_heartbeat(self, client_id, addr):
        with self.lock:
            if client_id in self.clients:
                self.clients[client_id] = (addr, time.time())

    def send_response(self, client_id, addr, data):
        try:
            message = json.dumps(data).encode('utf-8')
            self.sock.sendto(message, addr)
        except Exception as e:
            print(f"发送响应错误给 {client_id}: {e}")

    def cleanup_clients(self):
        """清理超时客户端"""
        while True:
            time.sleep(30)  # 每30秒清理一次
            current_time = time.time()
            with self.lock:
                expired_clients = []
                for client_id, (addr, last_seen) in self.clients.items():
                    if current_time - last_seen > 60:  # 60秒超时
                        expired_clients.append(client_id)

                for client_id in expired_clients:
                    del self.clients[client_id]
                    if client_id in self.client_info:
                        del self.client_info[client_id]
                    print(f"清理超时客户端: {client_id}")

    def stop(self):
        if hasattr(self, 'sock'):
            self.sock.close()


class NATUdpClient:
    def __init__(self, server_host='favor.delayboy.cn', server_port=8888, client_name=None):
        self.peer_sock = None
        self.server_sock = None
        self.server_host = server_host
        self.server_port = server_port
        self.client_id = str(uuid.uuid4())[:8]
        self.client_name = client_name or f"Client-{self.client_id}"
        self.local_port = 0  # 将由系统分配
        self.peer_socket = None
        self.connected_peer = None
        self.is_running = True

    def start(self):
        # 连接到服务器的socket
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # 用于P2P通信的socket
        self.peer_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.peer_sock.bind(('0.0.0.0', 0))
        self.local_port = self.peer_sock.getsockname()[1]

        print(f"客户端启动: {self.client_name} (ID: {self.client_id})")
        print(f"本地通信端口: {self.local_port}")

        # 注册到服务器
        self.register_with_server()

        # 启动心跳线程
        heartbeat_thread = threading.Thread(target=self.send_heartbeat, daemon=True)
        heartbeat_thread.start()

        # 启动接收服务器消息线程
        server_thread = threading.Thread(target=self.listen_server, daemon=True)
        server_thread.start()

        # 启动接收对等端消息线程
        peer_thread = threading.Thread(target=self.listen_peer, daemon=True)
        peer_thread.start()

        # 启动命令行界面
        self.command_interface()

    def register_with_server(self):
        message = {
            'action': 'register',
            'client_id': self.client_id,
            'name': self.client_name,
            'local_addr': f"127.0.0.1:{self.local_port}"
        }
        self.send_to_server(message)

    def send_heartbeat(self):
        while self.is_running:
            time.sleep(20)  # 每20秒发送一次心跳
            message = {
                'action': 'heartbeat',
                'client_id': self.client_id
            }
            self.send_to_server(message)

    def listen_server(self):
        buffer = {}
        while self.is_running:
            try:
                data, addr = self.server_sock.recvfrom(1024)
                message = json.loads(data.decode('utf-8'))
                self.handle_server_message(message)
            except Exception as e:
                if self.is_running:
                    print(f"接收服务器消息错误: {e}")

    def listen_peer(self):
        while self.is_running:
            try:
                data, addr = self.peer_sock.recvfrom(1024)
                try:
                    # 尝试解析为JSON消息
                    message = json.loads(data.decode('utf-8'))
                    if message.get('type') == 'p2p_message':
                        print(f"\n[来自 {addr}]: {message.get('content')}")
                    else:
                        print(f"\n[来自 {addr}]: {data.decode('utf-8')}")
                except:
                    print(f"\n[来自 {addr}]: {data.decode('utf-8')}")
            except Exception as e:
                if self.is_running:
                    print(f"接收对等端消息错误: {e}")

    def handle_server_message(self, message):
        action = message.get('action')

        if action == 'peer_list':
            peers = message.get('peers', [])
            print("\n=== 在线客户端 ===")
            for peer in peers:
                print(f"ID: {peer['client_id']}, 名称: {peer['name']}, 公网地址: {peer['public_addr']}")
            print("==================")

        elif action == 'incoming_connection':
            from_client = message.get('from_client')
            from_name = message.get('from_name')
            from_addr = tuple(message.get('from_public_addr'))

            print(f"\n*** 连接请求来自: {from_name} ({from_client})")
            response = input("是否接受连接? (y/n): ").lower().strip()

            if response == 'y':
                self.connected_peer = from_addr
                print(f"已连接到 {from_name}")
                # 发送打洞消息
                self.send_punch_message(from_addr)
            else:
                print("已拒绝连接")

        elif action == 'target_info':
            target_addr = tuple(message.get('target_public_addr'))
            target_name = message.get('target_name')

            print(f"\n*** 目标信息: {target_name} 在 {target_addr}")
            self.connected_peer = target_addr
            # 发送打洞消息
            self.send_punch_message(target_addr)

    def send_punch_message(self, target_addr):
        """发送打洞消息建立连接"""
        punch_msg = {
            'type': 'punch',
            'from_client': self.client_id,
            'from_name': self.client_name
        }
        try:
            self.peer_sock.sendto(json.dumps(punch_msg).encode('utf-8'), target_addr)
            print(f"已发送打洞消息到 {target_addr}")
        except Exception as e:
            print(f"发送打洞消息错误: {e}")

    def send_to_server(self, message):
        try:
            data = json.dumps(message).encode('utf-8')
            self.server_sock.sendto(data, (self.server_host, self.server_port))
        except Exception as e:
            print(f"发送消息到服务器错误: {e}")

    def list_peers(self):
        message = {
            'action': 'get_peers',
            'client_id': self.client_id
        }
        self.send_to_server(message)

    def connect_to_peer(self, peer_id):
        message = {
            'action': 'connect_request',
            'client_id': self.client_id,
            'target_id': peer_id
        }
        self.send_to_server(message)
        print(f"连接请求已发送到客户端 {peer_id}")

    def send_message(self, message_text):
        if not self.connected_peer:
            print("错误: 没有连接的对等端")
            return

        message = {
            'type': 'p2p_message',
            'from_client': self.client_id,
            'from_name': self.client_name,
            'content': message_text
        }

        try:
            self.peer_sock.sendto(json.dumps(message).encode('utf-8'), self.connected_peer)
            print(f"[发送到 {self.connected_peer}]: {message_text}")
        except Exception as e:
            print(f"发送消息错误: {e}")

    def command_interface(self):
        print("\n=== NAT穿透客户端命令 ===")
        print("list - 列出在线客户端")
        print("connect <client_id> - 连接到指定客户端")
        print("send <message> - 发送消息")
        print("quit - 退出")
        print("=========================")

        while self.is_running:
            try:
                cmd = input("\n请输入命令: ").strip().split()
                if not cmd:
                    continue

                if cmd[0] == 'list':
                    self.list_peers()
                elif cmd[0] == 'connect' and len(cmd) > 1:
                    self.connect_to_peer(cmd[1])
                elif cmd[0] == 'send' and len(cmd) > 1:
                    message = ' '.join(cmd[1:])
                    self.send_message(message)
                elif cmd[0] == 'quit':
                    self.stop()
                    break
                else:
                    print("未知命令")
            except KeyboardInterrupt:
                self.stop()
                break
            except Exception as e:
                print(f"命令处理错误: {e}")

    def stop(self):
        self.is_running = False
        if hasattr(self, 'server_sock'):
            self.server_sock.close()
        if hasattr(self, 'peer_sock'):
            self.peer_sock.close()
        print("客户端已关闭")
