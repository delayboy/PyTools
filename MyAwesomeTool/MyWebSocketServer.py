import json
from typing import Optional, Awaitable, Type
import tornado.websocket
import tornado.web
import re


class WebSocketHandler(tornado.websocket.WebSocketHandler):
    def __init__(self, application: tornado.web.Application, request, **kwargs):
        self.extra_param = kwargs.pop("extra_param")
        super().__init__(application, request, **kwargs)

    # def initialize(self, extra_param):
    #     self.glm = extra_param

    @staticmethod
    def is_json_object(message: str):
        b = re.findall(r"^\s*\{([\w\W]*)\}$", message, re.A)
        return len(b) == 1

    def data_received(self, chunk: bytes) -> Optional[Awaitable[None]]:
        pass

    def open(self):
        print("WebSocket opened")

    def on_message(self, message):
        print(f"Received message: {message}")
        if self.is_json_object(message):
            dic = dict(json.loads(message))
            if dic.__contains__("query"):
                # query = dic["query"]
                resDic = {"code": -1, "msg": "begin chat"}
                self.write_message(f"{json.dumps(resDic, ensure_ascii=False)}")
                for c in glm.chat_with_glm(**dic):
                    resDic = {"code": 0, "msg": c}
                    self.write_message(f"{json.dumps(resDic, ensure_ascii=False)}")
            resDic = {"code": 1, "msg": "end chat"}  # end chat
            self.write_message(f"{json.dumps(resDic, ensure_ascii=False)}")
        else:
            self.write_message(f"you said: {message}")

    def on_close(self):
        print("WebSocket closed")

    def check_origin(self, origin):
        # Allow all origins by returning True
        # Be cautious as this makes your server vulnerable to CSRF attacks
        return True


def start_websocket_server_loop(web_socket_class_name: Type[tornado.websocket.WebSocketHandler], extra_param):
    app = tornado.web.Application([
        (r"/ws", web_socket_class_name, {'extra_param': extra_param})
    ])
    app.listen(80, address="0.0.0.0")
    tornado.ioloop.IOLoop.current().start()


if __name__ == "__main__":
    from PyTools.MyAwesomeTool.MyGptHelper import ChatGLM

    # glm = ChatGLM()
    start_websocket_server_loop(WebSocketHandler, "")
