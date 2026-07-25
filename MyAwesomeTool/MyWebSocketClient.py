import time
import threading
import websocket
import re
import json


class WebsocketClient(object):
    """docstring for WebsocketClient"""

    def __init__(self, address, message_callback):
        super(WebsocketClient, self).__init__()
        self.address = address
        self.message_callback = message_callback
        self.strBuffer = ""
        self.wait_event = threading.Event()
        self.code = 1

    def isJsonObject(self, message: str):
        b = re.findall(r"^\s*\{([\w\W]*)\}$", message, re.A)
        return len(b) == 1

    def send(self, messageDic: dict) -> str:
        if self.code > 0:
            self.code = -1
        else:
            return "[error] multi connection is forbidden"
        self.strBuffer = ""

        self.ws.send(json.dumps(messageDic, ensure_ascii=False))
        self.wait_event.clear()
        self.wait_event.wait()
        print("<WAIT OVER>")
        return self.strBuffer

    def on_message(self, ws, message):

        if self.isJsonObject(message):
            dic = dict(json.loads(message))
            if dic.__contains__("msg"):
                self.code = int(dic["code"])
                msg = dic["msg"]
                if self.code == 0:
                    print(msg, end='')
                    self.strBuffer += msg
                    self.message_callback(msg)
                elif self.code > 0:
                    print("<END CHAT>")
                    self.wait_event.set()
        else:
            print("接收到非json消息", message)

    def on_error(self, ws, error):
        print("client error:", error)

    def on_close(self, ws):
        print("### client closed ###")
        self.ws.close()
        self.is_running = False

    def on_open(self, ws):
        self.is_running = True
        print("on open")

    def close_connect(self):
        self.ws.close()

    def send_message(self, message):
        try:
            self.ws.send(message)
        except BaseException as err:
            pass

    def run(self):
        # websocket.enableTrace(True) 用于调试的时候使用
        self.ws = websocket.WebSocketApp(self.address,
                                         on_message=lambda ws, message: self.on_message(ws, message),
                                         on_error=lambda ws, error: self.on_error(ws, error),
                                         on_close=lambda ws: self.on_close(ws))
        self.ws.on_open = lambda ws: self.on_open(ws)
        self.is_running = False
        while True:
            print("isRunning:", self.is_running)
            if not self.is_running:
                self.ws.run_forever()


class WSClient(object):
    def __init__(self, call_back, address: str = "ws://gpt.delayboy.cn:8888/websocket"):
        super(WSClient, self).__init__()
        self.client = WebsocketClient(address, call_back)
        self.client_thread = None
        self.run()

    def run(self):
        self.client_thread = threading.Thread(target=self.run_client)
        self.client_thread.start()
        print("waiting for connection ...")
        time.sleep(5)  # 一定要延时，否则无法建立连接

    def run_client(self):
        self.client.run()

    def send(self, messageDic: dict) -> str:
        return self.client.send(messageDic)

    def send_message(self, message):
        self.client.send_message(message)


if __name__ == '__main__':
    wsClient = WSClient(lambda msg: print(msg), "ws://127.0.0.1/ws")
    question = '你好'
    chatHistory = [['What can I do?', 'Serve me as a writing and programming assistant.']]
    queryDic = {'query': question, 'history': chatHistory, 'max_length': 512, 'top_p': 0.98, 'temperature': 0.9}
    response = wsClient.send(queryDic)
    # print("回答说:", response)
