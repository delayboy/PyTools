import openai
import time
import json
import os
from transformers import AutoModel, AutoTokenizer
from PyTools.MyAwesomeTool.MyTcpHelper import TcpServer, TcpHandler, TcpBase, PackageHeader, TcpClient
import threading
import requests


class GptTcpClientHandler(TcpHandler):
    def __init__(self):
        super().__init__()
        self.wait_event = threading.Event()
        self.code = 0
        self.output_text = ""

    def set_signal(self, wait: bool = True):
        self.wait_event.clear()

    def wait_for_signal(self):
        self.wait_event.clear()
        self.wait_event.wait(timeout=0.5)
        return self.code, self.output_text

    def callback(self, tcp_base: TcpClient, pk: PackageHeader) -> str:
        self.code = pk.code
        self.wait_event.set()
        if pk.code >= 0:
            self.output_text = pk.get_str_data()
            # print(str(pk.code) + ">" + output_text.replace("\n", "\\n"), end="\n", flush=True)
        else:
            # print("\r\nEnd", pk.get_str_data())
            pass


class GptTcpClientEngine:
    def __init__(self):
        self.gpt_client = TcpClient(GptTcpClientHandler(), server_port=5454)

    def chat_with_gpt(self, question: str):
        query_dic = {'query': question, 'history': [], 'max_length': 512, 'top_p': 0.98, 'temperature': 0.9}
        self.gpt_client.send_str(json.dumps(query_dic, ensure_ascii=False), wait=False)
        code = 0
        while code >= 0:
            code, output_text = self.gpt_client.handler.wait_for_signal()
            print(code, output_text)


# "C:\\Users\\Administrator\\PycharmProjects\\pythonProject\\ChatGLM-6B-main\\THUDM"
class ChatGLM:
    def __init__(self):
        save_dir = os.path.abspath(
            ".\\models--THUDM--chatglm-6b")
        self.tokenizer = AutoTokenizer.from_pretrained(save_dir, trust_remote_code=True)
        model = AutoModel.from_pretrained(save_dir, trust_remote_code=True).half().cuda()
        self.model = model.eval()

    # 必须通配一个kwargs参数，保证多传了参数不报错
    def chat_with_glm(self, query: str, top_p=1.0, temperature=0.03, max_length=514, history=None, **kwargs) -> str:
        if history is None:
            history = []
        res = ""
        for response, history in self.model.stream_chat(self.tokenizer, query, history, max_length=max_length,
                                                        top_p=top_p,
                                                        temperature=temperature):
            now_c = response[len(res):]
            print(now_c, end='')
            res = response
            yield now_c


# sk-xxxx

class ChatGPT:
    def __init__(self, system_prompt="Serve me as a writing and programming assistant."):
        openai.api_key = "sk-xxxx"  # 将第二步获取的密钥填写到这里
        self.proxies = {
            #          [协议]://  [地址]  :[端口]
            "http": "http://localhost:23457",  # 再例如  "http":  "http://127.0.0.1:7890",
            "https": "http://localhost:23457",  # 再例如  "https": "http://127.0.0.1:7890",
        }
        openai.proxy = self.proxies
        self.system_prompt = system_prompt

    def generate_message_payload(self, inputs: str, history: list):
        if history is None:
            history = []
        conversation_cnt = len(history) // 2

        messages = [{"role": "system", "content": self.system_prompt}]
        if conversation_cnt:
            for index in range(0, 2 * conversation_cnt, 2):
                what_i_have_asked = {"role": "user", "content": history[index]}
                what_gpt_answer = {"role": "assistant", "content": history[index + 1]}
                if what_i_have_asked["content"] != "":
                    if what_gpt_answer["content"] == "": continue
                    messages.append(what_i_have_asked)
                    messages.append(what_gpt_answer)
                else:
                    messages[-1]['content'] = what_gpt_answer['content']
        what_i_ask_now = {"role": "user", "content": inputs}
        messages.append(what_i_ask_now)
        return messages

    def chat_with_gpt(self, query: str, top_p=1.0, temperature=0.03, history=None, **kwargs) -> str:
        # 记录开始时间
        start_time = time.time()
        messages = self.generate_message_payload(query, history)
        # 发起流式请求
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
            top_p=top_p,
            temperature=temperature,
            stream=True  # 流式请求参数值设置为True

        )

        # 记录一下响应时间
        response_time = time.time()
        print(f'latency {response_time - start_time:.2f} s -> response')
        s = ""
        # 迭代读取返回数据
        for i in resp:
            t = time.time()
            dic = i.choices[0].delta.to_dict()
            msg = json.dumps(dic, ensure_ascii=False)
            # print(f'latency {t - start_time:.2f} s -> {msg}', end='\t')
            if 'content' in dic.keys():
                c = dic['content']
                print(c, end='')
                s = s + c
                yield c


# openai.proxy = proxies
# completion = openai.ChatCompletion.create(
#   model="gpt-3.5-turbo",
#   messages=[
#     {"role": "user", "content": "介绍一下广州塔"}
#   ]
# )
# print(completion.choices[0].message["content"])

class DeepSeekChat:
    def __init__(self, system_prompt="Serve me as a writing and programming assistant.",
                 api_key="YOUR_DEEPSEEK_API_KEY", base_url="https://api.deepseek.com/v1/chat/completions"):
        self.api_key = api_key
        self.base_url = base_url
        self.system_prompt = system_prompt

        # 可选：代理设置（格式与 OpenAI 示例类似）
        self.proxies = {
            "http": "http://localhost:23457",
            "https": "http://localhost:23457",
        }
        self.use_proxy = False  # 默认不使用，如需要设置为 True

    def generate_message_payload(self, inputs: str, history: list):
        if history is None:
            history = []
        conversation_cnt = len(history) // 2

        messages = [{"role": "system", "content": self.system_prompt}]
        if conversation_cnt:
            for index in range(0, 2 * conversation_cnt, 2):
                what_i_have_asked = {"role": "user", "content": history[index]}
                what_gpt_answer = {"role": "assistant", "content": history[index + 1]}
                if what_i_have_asked["content"] != "":
                    if what_gpt_answer["content"] == "":
                        continue
                    messages.append(what_i_have_asked)
                    messages.append(what_gpt_answer)
                else:
                    messages[-1]['content'] = what_gpt_answer['content']
        what_i_ask_now = {"role": "user", "content": inputs}
        messages.append(what_i_ask_now)
        return messages

    def chat_with_deepseek(self, query: str, top_p=1.0, temperature=0.03, history=None, model="deepseek-chat",
                           **kwargs):
        start_time = time.time()
        messages = self.generate_message_payload(query, history)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "model": model,
            "messages": messages,
            "top_p": top_p,
            "temperature": temperature,
            "stream": True
        }

        # 发送流式请求
        response = requests.post(
            self.base_url,
            headers=headers,
            json=data,
            stream=True,
            proxies=self.proxies if self.use_proxy else None
        )

        response_time = time.time()
        print(f'latency {response_time - start_time:.2f} s -> response')

        s = ""
        reasoning = ""
        in_reasoning = False
        for line in response.iter_lines():
            if line:
                line = line.decode('utf-8')
                if line.startswith("data: "):
                    line = line[6:]  # 去掉 "data: " 前缀
                    if line == "[DONE]":
                        break
                    try:
                        chunk = json.loads(line)
                        delta = chunk["choices"][0]["delta"]
                        if "reasoning_content" in delta:
                            rc = delta["reasoning_content"]
                            if not in_reasoning:
                                print("【思考过程】", end='')
                                in_reasoning = True
                            print(rc, end='')
                            reasoning += rc
                        if "content" in delta:
                            content = delta["content"]
                            if in_reasoning and len(content) > 1:
                                print(f"\n【思考结束】\n", end='')
                                in_reasoning = False
                            print(content, end='')
                            s += content
                            yield content
                    except json.JSONDecodeError:
                        continue


def gpt_tcp_server_example():
    gpt = ChatGPT("请全部使用中文回答，不要使用其他语言。需要你扮演一个叫派蒙的角色，是一个活泼可爱的精灵。")

    class ServerHandler(TcpHandler):
        def callback(self, tcp_base: TcpBase, pk: PackageHeader) -> str:
            request_str = pk.get_str_data()
            dic = dict(json.loads(request_str))
            if dic.__contains__("query"):
                # query = dic["query"]
                for c in gpt.chat_with_gpt(**dic):
                    tcp_base.send_str(c, 0)

            tcp_base.send_str("end chat", -1)

    server = TcpServer(ServerHandler(), port=5454)
    server.start()


def ask_deepseek_example(question: str = "推荐一道简单的菜") -> str:
    deepseek = DeepSeekChat(api_key="sk-xxxx")

    # 流式输出示例
    print("DeepSeek: ", end="")
    chunks = []
    for chunk in deepseek.chat_with_deepseek(question):
        chunks.append(chunk)

    full_response = ''.join(chunks)
    print(f"\n\n累积的完整回答: {full_response}")
    return full_response


def ask_glm_example(question: str = "推荐一道简单的菜") -> str:
    deepseek = DeepSeekChat(api_key="xxx.xxx",
                            base_url="https://api.z.ai/api/coding/paas/v4/chat/completions")

    # 流式输出示例
    print("DeepSeek: ", end="")
    chunks = []
    for chunk in deepseek.chat_with_deepseek(question, model="glm-5-turbo"):
        chunks.append(chunk)

    full_response = ''.join(chunks)
    print(f"\n\n累积的完整回答: {full_response}")
    return full_response


def ask_tencent_example(question: str = "推荐一道简单的菜") -> str:
    deepseek = DeepSeekChat(api_key="sk-tp-xxx",
                            base_url="https://api.lkeap.cloud.tencent.com/plan/v3/chat/completions")

    # 流式输出示例
    print("DeepSeek: ", end="")
    chunks = []
    for chunk in deepseek.chat_with_deepseek(question, model="deepseek-v4-flash-202605"):
        chunks.append(chunk)

    full_response = ''.join(chunks)
    print(f"\n\n累积的完整回答: {full_response}")
    return full_response


if __name__ == '__main__':
    # engine = GptTcpClientEngine()
    # while True:
    #     a = input('提问:')
    #     engine.chat_with_gpt(a)
    ask_tencent_example()
