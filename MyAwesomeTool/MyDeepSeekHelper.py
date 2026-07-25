import urllib.parse
import urllib.request

from threading import Thread
from typing import Optional, List, Generator
import json
import time
import re

SLOW_BACKEND = False  # 使用慢模式，方便调试输出和显示


# self.chat_history.append({"role": "assistant", "content": ai_message})
# self.chat_history.append({"role": "user", "content": message})
class DeepSeekHelper:
    def __init__(self):
        self.api_url: str = "http://127.0.0.1:11434"
        self.chat_history: List[dict] = []

    # 处理文本中的think标签
    def process_message(self, message):
        # 将自定义标签（如<think>）替换为Markdown的格式，或HTML的自定义标签
        # 例如，将 <think> 标签替换成 Markdown 格式的标记 # r'**\1**'
        message = re.sub(r"<think>(.*?)</think>", "", message, flags=re.DOTALL)
        return message

    def fetch_models(self) -> List[str]:
        with urllib.request.urlopen(
                urllib.parse.urljoin(self.api_url, "/api/tags")
        ) as response:
            data = json.load(response)
            models = [model["name"] for model in data["models"]]
            return models

    def fetch_chat_stream_result(self) -> Generator:
        request = urllib.request.Request(
            urllib.parse.urljoin(self.api_url, "/api/chat"),
            data=json.dumps(
                {
                    "model": self.fetch_models()[0],
                    "messages": self.chat_history,
                    "stream": True,
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        with urllib.request.urlopen(request) as resp:
            for line in resp:
                # if "disabled" in self.stop_button.state():  # stop
                #     break
                data = json.loads(line.decode("utf-8"))
                if "message" in data:
                    if SLOW_BACKEND:
                        time.sleep(0.01)
                    yield data["message"]["content"]

    def ask_one_question(self, question: str) -> str:
        ai_message = ""
        self.chat_history.clear()
        self.chat_history.append({"role": "user", "content": question})

        for c in self.fetch_chat_stream_result():
            ai_message += c
            if SLOW_BACKEND:
                print(c, end='', flush=True)  # 加入flush参数后，程序运行较慢，可以注释掉本句，有效提速
            else:
                print(c, end='')
        return self.process_message(ai_message)


if __name__ == '__main__':
    print("\r\nDeepSeek的回答:", DeepSeekHelper().ask_one_question("你好,帮我写首诗"))
