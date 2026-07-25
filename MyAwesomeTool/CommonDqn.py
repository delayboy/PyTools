#!/usr/bin/env python
from __future__ import annotations
from __future__ import print_function
from typing import Type, Dict, List, Tuple, Iterable, TypeVar, Callable
import abc
import torch
import torch.nn as nn
import torch.nn.functional as torch_func
from torch import optim, Tensor, FloatTensor
import cv2
from torch.utils.tensorboard import SummaryWriter
import os
import random
import numpy as np
from collections import deque
from PIL import Image, ImageTk  # pillow型图片支持库
import tkinter as tk  # 窗口控件支持库
import threading
import time
from PyTools.MyAwesomeTool.PyUseCPlus import MyDllLib
from PyTools.MyAwesomeTool.PyUseCPlus import MainUI as MainUIBase
from PyTools.MyAwesomeTool.MyUtil import build_logger, cache_obj, read_obj, InteractiveCmd, this_process
import ctypes
import psutil

"""
MATLAB求解符号函数梯度
syms x;
f = sin(x) + cos(x); % 定义一个符号函数
df = gradient(f, x); % 求函数f相对于x的梯度
disp(df);
"""
logger = build_logger(file_log_debug=True, use_to_debug=True)
device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
GAME = 'bird'  # the name of the game being played for log files
IS_DEBUG = False
# GAMMA = 0.9  # decay rate of past observations
OBSERVE = 40 if IS_DEBUG else 20000  # 1000 timesteps to observe before training
EXPLORE = 3000000.  # frames over which to anneal epsilon
FINAL_EPSILON = 0.0001  # final value of epsilon
INITIAL_EPSILON = 0.01  # starting value of epsilon 使用概率+Q值双头输出时建议设为0.95否则设置为0.1 0.95
# 注意这里任务管理器内存可能上涨的不厉害，是因为没有看提交内存，为了防止溢出最好提交内存低于最大内存限额
REPLAY_MEMORY = 25000  # 50000  number of previous transitions to remember
BATCH = 4 if IS_DEBUG else 16  # size of minibatch
MOCK_LEARNING = False
SINGLE_THREAD = False
TIME_WINDOW = 4
# 定义Windows的优先级常量
THREAD_PRIORITY_BELOW_NORMAL = -1

summary_writer = SummaryWriter(log_dir='./saved_networks/log')

"""
python type define 泛型
T = TypeVar('T', int, float)  # 定义类型变量 T，它必须是 int 或 float  
"""

Tuple_Or_Tensor = TypeVar('Tuple_Or_Tensor', Tuple[torch.Tensor, torch.Tensor], torch.Tensor)


def initialize_weights(m):
    if hasattr(m, 'weight'):
        nn.init.normal_(m.weight, mean=0, std=0.01)
    if hasattr(m, 'weight_hh_l0'):
        nn.init.normal_(m.weight_hh_l0, mean=0, std=0.01)
    if hasattr(m, 'bias_hh_l0'):
        nn.init.constant_(m.bias_hh_l0, 0.01)
    elif hasattr(m, 'bias') and m.bias is not None:
        nn.init.constant_(m.bias, 0.01)


# 定义软更新函数
def soft_update(source_net: nn.Module, target_net: nn.Module, tau: float = 0.01):
    for target_param, source_param in zip(target_net.parameters(), source_net.parameters()):
        target_param.data.copy_(tau * source_param.data + (1.0 - tau) * target_param.data)


def make_histogram(writer: SummaryWriter, tag, step, values, counts):
    min_, max_ = values.min(), values.max()
    limits = np.linspace(min_, max_, len(counts) + 1)

    # Find the first and the last bin defining the support of the histogram:
    cum_counts = np.cumsum(np.greater(counts, 0))
    start, end = np.searchsorted(cum_counts, [0, cum_counts[-1] - 1], side="right")
    start = int(start)
    end = int(end) + 1
    del cum_counts

    # TensorBoard only includes the right bin limits. To still have the leftmost limit
    # included, we include an empty bin left.
    # If start == 0, we need to add an empty one left, otherwise we can just include the bin left to the
    # first nonzero-count bin:
    counts = (
        counts[start - 1: end] if start > 0 else np.concatenate([[0], counts[:end]])
    )
    limits = limits[start: end + 1]

    if counts.size == 0 or limits.size == 0:
        raise ValueError("The histogram is empty, please file a bug report.")

    sum_sq = values.dot(values)
    num, sum_, sum_squres, bucket_limit, bucket = len(values), values.sum(), sum_sq, limits.tolist(), counts.tolist()
    writer.add_histogram_raw(tag, min_, max_, num, sum_, sum_squres, bucket_limit, bucket, step)


def set_thread_priority(priority):
    tid = ctypes.windll.kernel32.GetCurrentThreadId()
    ctypes.windll.kernel32.SetThreadPriority(tid, priority)


def start_thread(target, args: tuple = ()):
    # 子线程启动函数，用于开启一个子线程，target为需要运行目标方法
    threading.Thread(target=target, args=args).start()


def torch_check_backward_grad(my_model: nn.Module) -> Dict[str, np.ndarray]:
    # 先调用 loss.backward()
    # 初始化累积梯度张量
    acc_gradients = {key: torch.zeros_like(param).cpu().numpy() for key, param in my_model.named_parameters()}

    # 累积梯度
    for key, param in my_model.named_parameters():
        if param.grad is not None:
            acc_gradients[key] += param.grad.detach().cpu().numpy()
    return acc_gradients


def get_model_file_list(dir_path) -> dict:
    # 获取目录中所有文件和目录的名称列表
    res = dict({})
    if not os.path.exists(dir_path):
        return res
    items = os.listdir(dir_path)
    # 遍历所有文件和目录
    for item in items:
        # 获取文件或子目录的完整路径
        item_path = os.path.join(dir_path, item)

        # 判断是否为文件
        if os.path.isfile(item_path) and item.__contains__(".pth"):
            print("找到模型文件-[file]:", item)
            sub_items = item.split("_")
            if sub_items[2].__contains__("Temp"):
                # res[0] = item_path
                pass
            else:
                res[int(sub_items[2].split(".")[0])] = item_path

        # 判断是否为目录
        if os.path.isdir(item_path):
            # 处理子目录逻辑
            pass
    return res


class QueueElement:
    def __init__(self, pre_s_t_tensor: torch.Tensor, pre_a_t: np.ndarray, pre_reward: float, s_t_tensor: torch.Tensor,
                 pre_done_value: float, is_human_play=False):
        self.pre_s_t_tensor = pre_s_t_tensor
        self.pre_a_t = torch.FloatTensor(pre_a_t)
        self.pre_reward = torch.FloatTensor([pre_reward])
        self.s_t_tensor = s_t_tensor
        self.pre_done_value = torch.FloatTensor([pre_done_value])
        self.is_human_play = is_human_play
        self.hidden_output = None

    def is_terminal(self):
        return self.pre_done_value < 0.5


class ExpPoolBase(abc.ABC):
    def __init__(self, t: int, epsilon: float, max_capacity, app: MainUIBase):
        self.queue_pool: List[QueueElement] = []  # deque()
        self.pool_use_lock = threading.Lock()
        self.model_weight_lock = threading.Lock()
        self.eval_model_weight_lock = threading.Lock()
        self.syncMode = False
        self.epsilon = epsilon
        self.max_capacity = max_capacity
        self.t = t
        self.pre_action_log_probs = None
        # self.pre_hidden_output = None
        self.debug_queue_pool: List[QueueElement] = []
        self._reward_trace_debug = False
        self.app = app
        self.dqn: MyDQN = None

    @abc.abstractmethod
    def use_pool_call_back(self, s_t_tensor: torch.tensor, pre_s_t_tensor: torch.tensor, pre_a_t, pre_reward,
                           pre_done_value) -> (int, torch.tensor):
        raise NotImplementedError("use_pool_call_back 未实现")

    def sync_weight(self):
        self.dqn.load_weight()

    def find_pre_hidden(self, now_index: int):
        if (now_index - 1) > 0:
            pre_tuple: QueueElement = self.queue_pool[now_index - 1]
            if not pre_tuple.is_terminal():
                hidden_tuple = pre_tuple.hidden_output
                if hidden_tuple is not None:
                    return hidden_tuple
        return self.dqn.eval_net.lstm_hidden_0

    def load_old_file(self):
        if os.path.exists("expool_cache.bin"):
            if not self.app.show_message_box("是否加载经验池"):
                return
            self.queue_pool = read_obj("expool_cache.bin")
            re_check_pool = self.app.show_message_box("是否检查经验池")
            if re_check_pool:
                self.app.change_pause_mode(True)
                while self.app.Pause:
                    time.sleep(1)

            total_human_play_num = 0
            eche_play_num = 0
            for i, q in enumerate(self.queue_pool):
                q: QueueElement = q
                eche_play_num += 1
                if q.is_terminal() and re_check_pool:
                    total_human_play_num += eche_play_num if q.is_human_play else 0
                    eche_play_num = 0

            if re_check_pool and self.app.show_message_box(
                    f"人类一共玩了{total_human_play_num}次,是否重新保存经验池文件"):
                self.save_model_and_reply_file(reply_cache=True, force=True)

    def find_terminal_index(self, from_index=0, find_human=False, skip_human=True):
        terminal_index = from_index
        if from_index < 0:
            for i in range(len(self.queue_pool) + from_index, 0, -1):
                b: QueueElement = self.queue_pool[i]
                if b.is_terminal():
                    if b.is_human_play:
                        terminal_index = int(i)
                        return terminal_index
                    elif find_human:
                        terminal_index = int(i)
                        continue
                    else:
                        terminal_index = int(i)
                        break
            return terminal_index
        is_human_play_idx = -1
        total_human_play_num = 0
        eche_play_num = 0
        for i in range(from_index, len(self.queue_pool)):  # 找到游戏结束的序列直接扔掉整个序列
            b: QueueElement = self.queue_pool[i]
            eche_play_num += 1
            if b.is_terminal():
                if b.is_human_play:  # 人类玩的把数超过最大值1/3则删除人类玩家数据  and total_human_play_num < self.max_capacity / 3
                    total_human_play_num += eche_play_num
                    is_human_play_idx = int(i)
                    terminal_index = int(i)  # 防止下一个terminal没找到因此设置保底为当前human_index之后

                    if total_human_play_num > self.max_capacity / 3 or eche_play_num > 2000:
                        self.save_model_and_reply_file(reply_cache=True, debug=True)
                        self.app.Pause = True
                        print(
                            f"人类玩家对局数过多total{total_human_play_num} eche{eche_play_num} index{is_human_play_idx}")
                        while self.app.Pause:
                            time.sleep(1)
                    if skip_human:
                        pass
                    else:
                        return is_human_play_idx, terminal_index
                elif find_human:
                    terminal_index = int(i)
                    pass
                else:
                    terminal_index = int(i)
                    break
                eche_play_num = 0

        if terminal_index <= is_human_play_idx:
            self.save_model_and_reply_file(reply_cache=True, debug=True)
            self.app.Pause = True
            print(f"人类索引之后没有找到任何终止索引 human{is_human_play_idx} terminal{terminal_index}")
            while self.app.Pause:
                time.sleep(1)
        return is_human_play_idx, terminal_index

    def save_model_and_reply_file(self, train_model=False, eval_model=False, reply_cache=False,
                                  force=False,
                                  debug=False):
        if train_model:
            save_path = 'saved_networks/DQN_Pause_0.pth'
            save_dir = os.path.dirname(save_path)
            if os.path.exists(save_dir) and not os.path.exists(save_path):
                torch.save(self.dqn.train_net.state_dict(), save_path)
        if reply_cache:
            if self._reward_trace_debug:
                self.save_dbg_queue()
            elif debug:
                cache_obj("expool_cache_debug.bin", self.queue_pool)
                return
            elif force or not os.path.exists("expool_cache.bin"):
                terminal_index = self.find_terminal_index(-1, False, False)
                if terminal_index > 0:
                    cache_obj("expool_cache.bin", self.queue_pool[:terminal_index + 1])
        if eval_model:
            save_path = 'saved_networks/DQN_Eval_Temp.pth'
            save_dir = os.path.dirname(save_path)
            if os.path.exists(save_dir) and not os.path.exists(save_path):
                torch.save(self.dqn.eval_net.state_dict(), save_path)

    def back_reward(self, reward: float):
        back_num = 1
        for i in range(len(self.queue_pool) - 1, 0, -1):
            gamma = pow(0.9, back_num)
            self.queue_pool[i].pre_reward = self.queue_pool[i].pre_reward + reward * gamma
            back_num += 1

            if self._reward_trace_debug:
                pre_tensor = self.debug_queue_pool[i].pre_reward
                back_tensor = torch.FloatTensor([reward * gamma])
                self.debug_queue_pool[i].pre_reward = torch.concat([pre_tensor, back_tensor])
            if back_num > 4:
                break

    def push_queue_reference(self, img: np.ndarray, a_t: np.ndarray, reward: float, done: float, other_tensor=None):
        if self._reward_trace_debug:
            ele = QueueElement(torch.from_numpy(cv2.resize(img, (480, 270))), a_t, reward, other_tensor, done, True)
            self.debug_queue_pool.append(ele)
            if self.debug_queue_pool.__len__() > 3000:
                self.debug_queue_pool.clear()
        # else:
        #     if self.queue_pool.__len__() > 0:
        #         self.queue_pool[-1].s_t_tensor = other_tensor

    def save_dbg_queue(self):
        if self._reward_trace_debug and self.debug_queue_pool.__len__() > 5:
            if not os.path.exists("expool_cache.bin"):
                cache_obj("expool_cache.bin", self.debug_queue_pool)
                time.sleep(2)

    def sample_minibatch(self, batch_size, round_num: int) -> List[tuple]:
        res = []
        self.pool_use_lock.acquire()  # 上锁队列占用
        queue_pool = self.queue_pool
        # sample a minibatch to train on
        many_minibatch = random.sample(queue_pool, batch_size * round_num)
        for i in range(round_num):
            start = i * batch_size
            end = start + batch_size
            minibatch: List[QueueElement] = many_minibatch[start:end]
            s_j_batch = [d.pre_s_t_tensor for d in minibatch]
            # print (s_j_batch.shape)
            a_batch = [d.pre_a_t for d in minibatch]
            # print (a_batch.shape)
            r_batch = [d.pre_reward for d in minibatch]
            # print (r_batch.shape)
            s_j1_batch = [d.s_t_tensor for d in minibatch]
            # print (s_j1_batch.shape)
            terminal = [d.pre_done_value for d in minibatch]
            res.append((s_j_batch, a_batch, r_batch, s_j1_batch, terminal))
        self.pool_use_lock.release()  # 释放队列占用
        return res

    def sample_minibatch_with_idx(self, batch_size, round_num: int) -> list[Train_Tuple_Type]:
        res = []
        self.pool_use_lock.acquire()  # 上锁队列占用
        # 这里索引不能随机满，因为最后一位元素是刚进来的，有可能还没有next_state
        minibatch_indexes = random.sample(range(len(self.queue_pool) - 1), batch_size * round_num)
        if IS_DEBUG:
            # minibatch_indexes = [0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2, 3, 0, 1, 2, 3, ]
            # minibatch_indexes = np.ones(batch_size * round_num).astype(np.int32)
            pass
        for i in range(round_num):
            s_j_batch: List[torch.Tensor] = []
            a_batch = []
            r_batch = []
            s_j1_batch: List[torch.Tensor] = []
            terminal = []
            old_probs = []
            hidden_outputs = []
            queue_elements = []
            for j in range(batch_size):
                idx = i * batch_size + j
                now_batch_index = minibatch_indexes[idx]
                single_unit: QueueElement = self.queue_pool[now_batch_index]
                s_j, s_j1 = self.combine_state_in_pool(None, None, now_batch_index, TIME_WINDOW)
                a, r, t = single_unit.pre_a_t, single_unit.pre_reward, single_unit.pre_done_value
                s_j_batch.append(s_j)
                s_j1_batch.append(s_j1)
                a_batch.append(a)
                r_batch.append(r)
                terminal.append(t)
                old_probs.append(single_unit.s_t_tensor)
                hidden_outputs.append(self.find_pre_hidden(now_batch_index))
                queue_elements.append(single_unit)
            res.append((s_j_batch, a_batch, r_batch, s_j1_batch, terminal, old_probs, queue_elements))
        self.pool_use_lock.release()  # 释放队列占用
        return res

    def reset_illegal_index(self, start_index: int) -> int:
        max_len = len(self.queue_pool)
        if start_index < 0:
            start_index = 0
        if start_index >= max_len:
            start_index = max_len - 1
        return start_index

    def print_queue(self):
        for i, b in enumerate(self.queue_pool):
            print(i, torch.mean(b.pre_done_value), b.s_t_tensor, b.pre_reward, b.is_human_play)

    def combine_state_in_pool(self, input_now_state, now_next_state, now_index: int, combine_num: int) \
            -> (torch.Tensor, torch.Tensor):
        pre_states, pre_next_states = [], []
        if now_next_state is None:
            offset = 0
            now_tuple = self.queue_pool[now_index]
            # 不用怕当前next_state识别错，因为doneValue为1时自动屏蔽next_state可以瞎取（而且sample会帮你擦屁股）
            if (now_index + 1) < len(self.queue_pool):
                now_next_state = self.queue_pool[now_index + 1].pre_s_t_tensor
            else:
                now_next_state = now_tuple.pre_s_t_tensor
            now_state = now_tuple.pre_s_t_tensor
        else:
            offset = 1
            if input_now_state is None:
                now_state, now_next_state = now_next_state, now_next_state
            else:
                now_state, now_next_state = input_now_state, now_next_state

        pre_next_states.append(now_next_state)
        pre_next_states.append(now_state)
        pre_states.append(now_state)

        for i in range(now_index - 1, now_index - combine_num + offset, -1):
            if i < 0:
                break
            pre_tuple: QueueElement = self.queue_pool[i]
            if pre_tuple.is_terminal():  # 到达结尾则退出
                break
            pre_state = pre_tuple.pre_s_t_tensor
            pre_states.append(pre_state)
            pre_next_states.append(pre_state)
        if len(pre_states) >= combine_num:
            return torch.cat(pre_states[:combine_num], dim=0), torch.cat(pre_next_states[:combine_num], dim=0)
        elif len(pre_states) < combine_num:
            temp_state = pre_states[-1]  # now_state最后一个，是最后一个，next_state最后一个是倒数第二个
            while len(pre_states) < combine_num:
                pre_states.append(temp_state)
                pre_next_states.append(temp_state)
            return torch.cat(pre_states[:combine_num], dim=0), torch.cat(pre_next_states[:combine_num], dim=0)


Train_Tuple_Type = tuple[
    list[Tensor], list[FloatTensor], list[FloatTensor], list[Tensor], list[FloatTensor], list[Tensor], list[
        QueueElement]]


class GameEnvBase(abc.ABC):
    def __init__(self, app: MainUIBase):
        self.s_t = None
        self.action_dim = 0
        self.s_t_tensor = None
        self.app = app
        self.information = ""
        self.information2 = ""
        self.information3 = ""
        self.watch_me_index = -1
        self.watch_me_all_the_time = True if MOCK_LEARNING else False
        self.watch_me_all_the_time = False if IS_DEBUG else self.watch_me_all_the_time
        self.stop_eval = False
        self.epsilon = INITIAL_EPSILON
        self.first_run = True
        self.use_opencv_script = False
        self.record_opencv_script = False

        self.exp_pool: ExpPoolBase = None

    def set_exp_pool(self, exp_pool: ExpPool):
        self.exp_pool = exp_pool

    def information_thread(self):
        while True:
            time.sleep(1)
            self.app.show_text(self.get_player_status_str())

    def get_player_status_str(self):
        base = f"base:Pause{self.app.Pause}Render{self.app.Render}Watch{self.watch_me_all_the_time}Stop{self.stop_eval}"
        return "base:{}\ninfo:{}\n info2:{}\n info3:{}\n".format(base, self.information, self.information2,
                                                                 self.information3)

    @abc.abstractmethod
    def game_step(self, action_index: int) -> (torch.tensor, float, bool, np.ndarray):
        raise NotImplementedError("game_step未实现")

    @abc.abstractmethod
    def game_reset(self) -> torch.tensor:
        raise NotImplementedError("game_reset未实现")

    @abc.abstractmethod
    def calculate_game_state(self, x_t: torch.tensor, is_reset: bool) -> torch.tensor:
        raise NotImplementedError("game_reset未实现")

    def reset(self) -> (torch.tensor, torch.tensor, np.core.multiarray, float, float):
        return self.__reset()

    def step(self, action_index: int) -> (torch.tensor, torch.tensor, np.core.multiarray, float, float):
        return self.__step(action_index)

    def _default_calculate_game_state(self, x_t: torch.tensor, is_reset: bool) -> torch.tensor:
        x_t1 = cv2.cvtColor(cv2.resize(x_t, (80, 80)), cv2.COLOR_BGR2GRAY)
        ret, x_t1 = cv2.threshold(x_t1, 1, 255, cv2.THRESH_BINARY)
        if is_reset:
            s_t1 = np.stack((x_t1, x_t1, x_t1, x_t1), axis=2)
            self.s_t = s_t1
        else:
            x_t1_temp = np.reshape(x_t1, (80, 80, 1))
            s_t1 = np.append(x_t1_temp, self.s_t[:, :, :3], axis=2)  # concat front 3 frame and now frame
            self.s_t = s_t1  # change state to next

        s_t1_tensor = torch.from_numpy(x_t1).unsqueeze(0) * 1.0  # torch.from_numpy(s_t1).permute(2, 0, 1) * 1.0
        return s_t1_tensor

    def __reset(self) -> (torch.tensor, torch.tensor, np.core.multiarray, float, float):
        x_t = self.game_reset()
        self.s_t_tensor = self.calculate_game_state(x_t, True)
        pre_state = None
        a_t = None
        reward = None
        done_value = 1
        return self.s_t_tensor, pre_state, a_t, reward, done_value

    def __step(self, action_index: int) -> (torch.tensor, torch.tensor, np.core.multiarray, float, float):
        x_t, reward, terminal, a_t = self.game_step(action_index)
        done_value = 0 if terminal else 1

        pre_state = self.s_t_tensor
        self.s_t_tensor = self.calculate_game_state(x_t, False)

        return self.s_t_tensor, pre_state, a_t, reward, done_value

    def old_reset(self) -> (torch.tensor, bool):
        s_t_tensor, pre_state, a_t, reward, done_value = self.__reset()
        return s_t_tensor, done_value == 0

    def old_step(self, action_index: int) -> ():
        s_t1_tensor, pre_state, a_t, reward, done_value = self.__step(action_index)
        return a_t, s_t1_tensor, reward, done_value


class BaseQNetwork(abc.ABC, nn.Module):
    def __init__(self, app: MainUIBase, action_dim: int, d_model=512, net_input_dim=512, net_hidden_dim=128,
                 is_img_input=True):
        super(BaseQNetwork, self).__init__()
        self.app = app
        self.action_dim = action_dim
        self.USE_TUPLE_OUTPUT = True
        self.lstm_hidden_0 = None  # torch.zeros(2, 1, self.d_model)  # seq,batch
        self.use_lstm = False
        self.is_img_input = is_img_input
        self.time_window = TIME_WINDOW  # 时间窗口包含多少帧图像
        self.img_size = 256
        self.d_model = d_model
        self.__probs_value_net_hidden_dim = net_hidden_dim
        self.__probs_value_net_input_dim = net_input_dim
        self.probs_net: nn.Sequential = self.__initialize_probs_net()
        self.value_net: nn.Sequential = self.__initialize_value_net()

    def probs_is_nan(self):
        return torch.isnan(self.probs_net[0].weight).any() or torch.isnan(self.probs_net[1].weight).any()

    def __throw_error(self, method_name) -> NotImplementedError:
        return NotImplementedError(f"{self.__name__}.{method_name} 函数未实现")

    def __initialize_probs_net(self) -> nn.Sequential:
        return nn.Sequential(
            # nn.BatchNorm1d(self.__probs_value_net_input_dim), # 防止梯度消失
            nn.Linear(self.__probs_value_net_input_dim, self.__probs_value_net_hidden_dim),
            # nn.BatchNorm1d(self.__probs_value_net_hidden_dim), # 防止梯度消失
            nn.Linear(self.__probs_value_net_hidden_dim, self.action_dim),
            nn.Softmax(dim=-1)
        ).apply(initialize_weights)

    def __initialize_value_net(self) -> nn.Sequential:
        return nn.Sequential(
            nn.Linear(self.__probs_value_net_input_dim, self.__probs_value_net_hidden_dim),
            nn.Linear(self.__probs_value_net_hidden_dim, self.action_dim),
        ).apply(initialize_weights)

    def prepare_soft_update(self, ref_model: BaseQNetwork):
        ref_model.probs_net.load_state_dict(self.probs_net.state_dict())

    def soft_update(self, ref_model: BaseQNetwork, tau: float = 0.01):
        soft_update(self.probs_net, ref_model.probs_net, tau)
        self.probs_net.load_state_dict(ref_model.probs_net.state_dict())

    def reset_weight(self, reset: bool, ref_model: BaseQNetwork):
        if reset:
            self.probs_net.apply(initialize_weights)
            self.prepare_soft_update(ref_model)
        else:  # 撤回的时候顺便中和一下权重，让参数更平均一些，有效提高低概率输出，避免梯度死亡
            self.probs_net.apply(initialize_weights)
            self.soft_update(ref_model)
            # self.probs_net.load_state_dict(ref_model.probs_net.state_dict())

    def norm_grad(self):
        torch.nn.utils.clip_grad_norm_(self.probs_net.parameters(), max_norm=1.0)  # 裁剪梯度

    def probs_forward(self, attention_x: torch.Tensor) -> torch.Tensor:
        probs_x = self.probs_net(attention_x)
        return probs_x

    @abc.abstractmethod
    def forward(self, x: torch.Tensor, lstm_hidden=None) -> (Tuple_Or_Tensor, torch.Tensor):
        raise self.__throw_error(self.forward.__name__)

    def load_state_dict(self, state_dict: dict, strict: bool = True):
        now_dict = self.state_dict()
        error_map = {
            "value_linear": "value_net.1",
            "value_pre_linear": "value_net.0",
            "probs_linear": "probs_net.1",
            "probs_pre_linear": "probs_net.0",
            "pre_linear": "pre_net",
        }
        for key in now_dict.keys():
            if not state_dict.__contains__(key):
                print("now_dict", key)
        state_dict_key_list: List[str] = []
        for key in state_dict.keys():
            if not now_dict.__contains__(key):
                print("state_dict", key)
                state_dict_key_list.append(key)
        for key in state_dict_key_list:
            value = state_dict.pop(key)
            index = key.rfind(".")
            pure_key = key[0:index]  # 注意: 默认取到index不会包括index字符本身
            tail = key[index:]
            handle_error = False
            for error_key in error_map.keys():
                if pure_key.__eq__(error_key):
                    pure_key = error_map[error_key]
                    handle_error = True
                    break
            if not handle_error:
                raise RuntimeError(f"系统不知道如何修复异常key，请手动查看: state_dict {key} pure{pure_key} tail {tail}")
            key = pure_key + tail
            state_dict[key] = value
        super().load_state_dict(state_dict)


class MainUI(MainUIBase):
    """继承tk.Frame的主窗口，master为窗口的父控件"""

    def user_key_code(self, key_code) -> bool:
        if key_code == MyDllLib.VK_OEM_3:
            self.change_pause_mode()
        elif key_code == MyDllLib.VK_F1:
            self.change_draw_mode()

        if self.exp_pool is None or len(self.exp_pool.queue_pool) < 1:
            return False
        draw_image = False
        if key_code == 38:  # 上
            if self.on_ctrl:
                self.start_index = self.exp_pool.reset_illegal_index(self.start_index - 1)
                index = self.start_index - len(self.exp_pool.queue_pool)
                self.start_index = self.exp_pool.find_terminal_index(index, True, False)
            else:
                self.start_index -= 50

            draw_image = True
        elif key_code == 37:  # 左
            if self.on_ctrl:
                self.start_index = self.exp_pool.reset_illegal_index(self.start_index - 1)
                index = self.start_index - len(self.exp_pool.queue_pool)
                self.start_index = self.exp_pool.find_terminal_index(index, False, False)
            else:
                self.start_index -= 1

            draw_image = True
        elif key_code == 39:  # 右
            if self.on_ctrl:
                self.start_index = self.exp_pool.reset_illegal_index(self.start_index + 1)
                _, self.start_index = self.exp_pool.find_terminal_index(self.start_index, False, False)
            else:
                self.start_index += 1

            draw_image = True
        elif key_code == 40:  # 下
            if self.on_ctrl:
                self.start_index = self.exp_pool.reset_illegal_index(self.start_index + 1)
                self.start_index, _ = self.exp_pool.find_terminal_index(self.start_index, True, False)
            else:
                self.start_index += 50
            draw_image = True
        elif key_code == ord("H"):
            q: QueueElement = self.exp_pool.queue_pool[self.start_index]
            q.is_human_play = not q.is_human_play
            draw_image = True
        elif key_code == MyDllLib.VK_F1 + 7:
            del self.exp_pool.queue_pool[self.start_index]
            draw_image = True
        elif key_code == MyDllLib.VK_F1 + 8:
            human, terminal_index = self.exp_pool.find_terminal_index(self.start_index, False, False)
            if self.start_index == terminal_index:
                terminal_index = len(self.exp_pool.queue_pool) - 1
            del self.exp_pool.queue_pool[self.start_index:terminal_index + 1]
            draw_image = True

        self.start_index = self.exp_pool.reset_illegal_index(self.start_index)
        if draw_image:
            human, terminal_index = self.exp_pool.find_terminal_index(self.start_index, False, False)
            q: QueueElement = self.exp_pool.queue_pool[self.start_index]
            img = q.pre_s_t_tensor.numpy()
            super().show_image(img, f"{self.start_index}/{terminal_index}\n - {q.pre_a_t} - {q.is_terminal()} "
                                    f"\n {q.is_human_play} - {q.pre_reward}")
            self.show_text(f"{q.hidden_output}" + "\n" + f"{q.s_t_tensor}")

            time.sleep(0.005)

        return draw_image

    def check_need_sync(self):
        if self.SyncModel:
            self.SyncModel = False
            return True
        else:
            return False

    def set_sync(self):
        self.SyncModel = True

    def show_image(self, img_array: np.ndarray, show_text: str = "", row=0, use_cache=True, add_to_summery=False):
        # 在主窗口内显示图片
        # 将OpenCV数组图转换为pillow图像
        # image = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        photos = []
        self.__img_frame.config(text="Image Panel:{}".format(show_text))
        for i in range(img_array.shape[0]):
            img = img_array[i].squeeze()
            if img.dtype == np.float32 and np.mean(img) < 2:  # 是float数
                img = (img * 255).astype(np.uint8)
            if add_to_summery:
                summary_writer.add_image("input{}".format(i), img, dataformats='HW')
            image = Image.fromarray(img)
            photo = ImageTk.PhotoImage(image)  # 生成pillow图像的Photo格式 先赋值临时变量，防止self.Photo内存释放造成闪屏
            if i < self.__ImageLabels.__len__():
                image_label = self.__ImageLabels[i]
            else:
                image_label = tk.Label(self.__img_frame)  # 负责显示结果图
                col_index = i % 2  # 每行两张图
                row_index = int(i / 2)  # 一共多少行
                image_label.grid(row=row + row_index, column=1 + col_index)
                self.__ImageLabels.append(image_label)
            image_label.__setitem__("imag", photo)  # 将Photo显示在主窗口中
            photos.append(photo)
        self.__Photos.clear()
        self.Photos = photos

    def __init__(self, game_env: Type[GameEnvBase], q_network: Type[BaseQNetwork]):
        super().__init__(self.start_multi_thread)
        self.env: GameEnvBase = game_env(self)
        self.train_model = q_network(self, self.env.action_dim).to(device)
        if SINGLE_THREAD:
            self.model = self.train_model
        else:
            self.model = q_network(self, self.env.action_dim).to(device).eval()

        self.SyncModel = False
        self.change_pause_mode(False)
        # self.change_draw_mode()
        # 设置窗口标题
        self.set_user_key_code_callback(self.user_key_code)

        self.start_index = 0
        self.exp_pool: ExpPool = None

    def start_multi_thread(self, app):
        # open up a game state to communicate with emulator
        # env = GameEnv()
        # store the previous observations in replay memory
        self.my_dll.register_event_hook(1, True)
        app = self
        dqn = MyDQN(self.model, self.train_model, BATCH, app, self.env.action_dim)  # MyDQN不会初始化模型，只是作为训练器
        exp_pool = ExpPool(0, dqn, self.env, INITIAL_EPSILON, REPLAY_MEMORY)
        self.exp_pool = exp_pool
        start_thread(train_network, (app, self.env, exp_pool))
        start_thread(eval_network, (app, self.env, exp_pool))

    def __myloop_un_use(self):
        # StartThread(evalNetwork, (app,))
        self.start_multi_thread(self)
        # 主循环开始
        while True:
            try:
                self.mainloop()  # 正常主循环会卡在这里
                break  # 正常退出主窗口会跳出死循环
            except KeyboardInterrupt:  # 由于使用ctrl+c终端录屏进程时，主窗口进程也会中断，因此捕捉这个异常，让主循环重新启动
                print("重启UI")  # 捕捉异常时，app=None的代码没有正常运行而被跳过了，因此死循环不退出。


# 这里我重新实现了Double DQN
class MyDQN:
    def __init__(self, eval_net: BaseQNetwork, train_net: BaseQNetwork, batch_size: int, app: MainUI, action_dim,
                 lr=1e-3,
                 gamma=0.9):  # 1e-6
        self.eval_net = eval_net
        self.train_net = train_net
        # 添加 L2 正则化,以防止模型参数过大或过小，出现过拟合。
        # 经过实测这里不能加L2正则化，会导致卷积神经网络权重归0，从而永久性获取不到图片关键信息，间接导致梯度死亡！！！
        if MOCK_LEARNING:
            self.optimizer = optim.Adam(self.train_net.parameters(), lr=1e-5, weight_decay=1e-4)
        else:
            self.optimizer = optim.Adam(self.train_net.parameters(), lr=lr)
        self.loss = nn.MSELoss()
        self.cross_loss = nn.CrossEntropyLoss()
        self.gamma = gamma
        self.batch_size = batch_size
        self.crash_on_probs_error_branch_count = 0
        self.learn_count = 0
        self.eps_clip = 0.2
        self.static_loss = 0
        self.soft_update = False
        if hasattr(self.train_net, "soft_update"):
            self.soft_update = True

    def learn_with_round(self, exp_pool: ExpPoolBase, round_num: int) -> Iterable[float]:
        batch_list = exp_pool.sample_minibatch_with_idx(BATCH, round_num)
        self.learn_count += 1
        for i in range(round_num):
            mini_batch = batch_list[i]
            loss = self.learn(exp_pool, mini_batch)
            self.static_loss += loss
            yield i, loss

    def learn(self, exp_pool: ExpPoolBase, minibatch: Train_Tuple_Type) -> float:
        s_j_batch, a_batch, r_batch, s_j1_batch, terminal, old_probs, queue_elements = minibatch
        batch_state = torch.stack(s_j_batch).to(device)
        batch_action = torch.stack(a_batch).to(device)
        batch_reward = torch.stack(r_batch).to(device)
        batch_dones = torch.stack(terminal).to(device)
        batch_next_state = torch.stack(s_j1_batch).to(device)

        exp_pool.model_weight_lock.acquire()  # 一定要加互斥锁，防止并发更新权重
        action_probs = None

        action_value, hidden_output = self.train_net.forward(batch_state, None)

        if self.train_net.USE_TUPLE_OUTPUT:
            action_value, action_probs = action_value
            with torch.no_grad():
                q_next = self.eval_net.forward(batch_next_state, None)[0][0].detach().to(device)
        else:
            with torch.no_grad():
                q_next = self.eval_net.forward(batch_next_state, None)[0].detach().to(device)

        q_target = batch_reward + batch_dones * self.gamma * q_next.max(1)[0].view(self.batch_size, 1)
        # 参考等比数列求和公式可知$$ S_n=a_1\frac{1-q^n}{1-q} $$ 在每次只加减1分的情况下分数上限为(-10,10)区间
        # q_target = torch.clamp(q_target, - 10, 10)
        # q_eval = action_value.gather(1, torch.max(batch_action, dim=1, keepdim=True)[1])
        q_eval = action_value * batch_action  # 对应位置为0
        q_eval = torch.sum(q_eval, dim=1).view(self.batch_size, 1)
        offset = q_target - q_eval
        ppo_loss, mean_loss = 0.0, 0.0
        mini_prob = 1
        if False:
            # 产生的梯度 $$ \sum{\left( R-\log p-1 \right) \times p\nabla \log p} $$
            # 极值点gamma系数取值 $$ \frac{R}{\log p+1}=\gamma  $$ 可计算出0.33时最大概率封顶为0.9，0.9之后信息熵梯度占主导权
            # 信息熵衰减系数，概率上下限差距越大，越重视信息熵，衰减系数从0.03到0.06
            # gamma = 0.03 + 0.03 * torch.max((action_probs.max(dim=1)[0]), (1 - action_probs.min(dim=1)[0]))

            dist = torch.distributions.Categorical(action_probs)
            dist_entropy = dist.entropy()
            # dist_entropy = gamma * dist_entropy

            # old_logprobs = torch.stack(old_probs).to(device).detach()
            action_log_probs = dist.log_prob(torch.max(batch_action, 1)[1])
            ratios = torch.exp(action_log_probs)  # - old_logprobs
            # 我认为在DQN和PPO的结合过程中相对优势就是他的目标q值与当前状态最大Q值(或均值)的差异， 而不是 batch_reward 或 offset
            advantages = q_target - action_value.mean(dim=1, keepdim=True)  # 这里当前最大Q值要脱离梯度计算
            surr1 = ratios * advantages
            # surr2 = torch.clamp(ratios, 1 - self.eps_clip, 1 + self.eps_clip) * advantages
            # ppo_loss = - torch.min(surr1, surr2) - 0.01 * dist_entropy  # 通过信息熵损失控制概率分布尽量平均，别出现极端概率
            ppo_loss = - surr1 - 0.01 * dist_entropy
            ppo_loss = -ppo_loss.mean()
            exp_pool.env.information = str([advantages[:2], action_value[:2], action_probs[:2]])
        try:
            if action_probs is not None:
                dist = torch.distributions.Categorical(action_probs)
                # 在原有动作Q值基础上倍率乘2，以拉开最低分和最高分的分数差异
                d_action_value = action_value.detach()  # 将得分脱离attention梯度，不要影响Q值的梯度计算
                if True:
                    _, max_q_value_index = d_action_value.max(dim=1, keepdim=True)  # 除了最小值，默认其他概率的信息熵重要性都为1
                    batch_size, action_dim = d_action_value.shape
                    # * 0.1 / (action_dim - 1)  # 均值分布 3 / 4 + 1 / action_dim / 4 上限0.9
                    # aim_action_value_probs = torch.ones_like(d_action_value)
                    # aim_action_value_probs = aim_action_value_probs.to(device) * 0.1 / (action_dim - 1)  # 保底概率0.01

                    min_value, max_value = torch.min(action_value, 1, keepdim=True)[0], \
                        torch.max(action_value, 1, keepdim=True)[0]  # 获取分数取值范围
                    action_value_minus = (action_value - max_value) / (max_value - min_value)  # 归一化到-1 ~ 0区间
                    # 对于低分给予更低的概率映射(由于指数函数特性，加个0.1保底，保证最低概率不会造成梯度死亡
                    action_value_plus = torch.exp(action_value_minus) + 0.1
                    max_ac = action_value_plus.gather(1, max_q_value_index)
                    # 将这些值设置为 0
                    action_value_plus.scatter_(1, max_q_value_index,
                                               torch.ones_like(max_ac) * 9 * 0.5 * (action_dim - 1))
                    aim_action_value_probs = action_value_plus / torch.sum(action_value_plus, dim=1)[0]  # 按当前数值计算概率分布
                    # 先对分数差进行指数函数映射,通过指数归一化到-0.5到0.5区间（概率分布第一名和第二名之间概率差异非常大）
                    # 归一化到指数的好处在于，可以有效控制均值所产生的概率响应，否则Q值上下限差异过大产生剧烈梯度响应，会造成概率崩坏
                    # mean_loss = self.loss(aim_action_value_probs.detach(), action_probs)
                    # 防止 log(0) 导致数值问题，添加一个很小的 epsilon
                    epsilon = 1e-10
                    cross_entropy = -torch.sum(aim_action_value_probs.detach() * torch.log(action_probs + epsilon))
                    mean_loss = cross_entropy
                if IS_DEBUG:  # 归一化到+0.5到-0.5之间用于做概率压力测试
                    pass
                    max_action_value = d_action_value.max(dim=1, keepdim=True)[0]
                    exp_action_value = (torch.exp(d_action_value - max_action_value))
                    d_action_value = exp_action_value - 0.5
                    # aim_action_value_probs = aim_action_value_probs * exp_action_value / exp_action_value.sum(dim=1,
                    #                                                                                           keepdim=True)
                    # aim_action_value_probs = aim_action_value_probs / aim_action_value_probs.sum(dim=1, keepdim=True)
                    # exp_action_value = torch.Tensor(
                    #     [[0.5, -0.3, -0.2, -0.1, 0.2, 0.4, -0.5], [0.5, -0.3, -0.2, -0.1, 0.2, 0.4, -0.5],
                    #      [0.5, -0.3, -0.2, -0.1, 0.2, 0.4, -0.5], [0.5, -0.3, -0.2, -0.1, 0.2, 0.4, -0.5]]).to(device)
                    # exp_action_value = torch.Tensor(
                    #     [[0.0001, 0.1, 0.1, 0.1, 0.1, 0.9, 0.1], [0.0001, 0.1, 0.1, 0.1, 0.1, 0.9, 0.1],
                    #      [0.0001, 0.1, 0.1, 0.1, 0.1, 0.9, 0.1], [0.0001, 0.1, 0.1, 0.1, 0.1, 0.9, 0.1]]).to(device)

                if False:
                    # 通过上下限归一化到+0.5和-0.5区间（传统方法）（概率分布第一名和第二名之间概率差异更小）
                    max_action_value = d_action_value.max(dim=1, keepdim=True)[0]
                    min_action_value = d_action_value.min(dim=1, keepdim=True)[0]
                    d_action_value = (d_action_value - min_action_value) / (max_action_value - min_action_value) - 0.5

                    # max_action_value = d_action_value.max()
                    # min_action_value = d_action_value.min()
                    # norm_action_value = ((d_action_value - min_action_value) / (max_action_value - min_action_value) - 0.5)

                    # (0,0.5)取值 0.35 到 0.2 (0.5,1) 取值0.2 到 0.25 下限非常容易发生梯度死亡，所以额外限定一个低于0.01以下概率的保底信息熵

                    # 替换掉torch.log防止溢出否则会出现inf 导致梯度nan
                    log_probs = dist.logits - torch.logsumexp(dist.logits, dim=-1, keepdim=True)
                    mini_dist_entropy = -action_probs * log_probs
                    mean_loss = d_action_value * action_probs  # 直接利用最大化Q Value的均值来优化所有概率输出

                    mini_prob = action_probs.min()
                    alpha = torch_func.relu(0.01 - action_probs.min(dim=1, keepdim=True)[0])
                    alpha2 = torch_func.relu(action_probs.max(dim=1, keepdim=True)[0] - 0.95)
                    # gamma控制每个元素的概率细节
                    gamma = 0.6 * torch_func.relu(0.5 - action_probs) ** 2 + 0.6 * torch_func.relu(
                        action_probs - 0.5) ** 2 + 0.08 + 50 * alpha2 + 50 * alpha  # 实测0.1收敛到0.92最大概率0.08收敛到0.94最大概率
                    gamma = gamma.detach()  # gamma是常数不要参与梯度计算
                    mini_dist_entropy = gamma * mini_dist_entropy

                    mean_loss = - mean_loss.mean() - mini_dist_entropy.mean()

                    # if IS_DEBUG:
                    exp_pool.env.information = str([action_value[:2], d_action_value[:2], action_probs[:2]])
        except ValueError as e:
            if self.train_net.probs_is_nan():
                print("概率网络出现Nan，因此执行权重重置")
                self.train_net.reset_weight(True, self.eval_net)
            else:
                print("未知的数据错误:")
                raise e
        # MSE的q_value损失，加上ppo的概率均值损失
        if MOCK_LEARNING:
            loss = self.cross_loss(action_probs, batch_action)
            exp_pool.env.information = str([batch_action[:2], action_probs[:2]])
        elif mini_prob < 1e-19:  # 梯度已经死亡则重置
            self.crash_on_probs_error_branch_count += 1000

            if self.crash_on_probs_error_branch_count > 1000:
                logger.debug("梯度无效过于频繁,执行权重大重置 p=%e count=%d" % (
                    mini_prob, self.crash_on_probs_error_branch_count))
                exp_pool.eval_model_weight_lock.acquire()
                self.train_net.reset_weight(True, self.eval_net)
                exp_pool.eval_model_weight_lock.release()
                self.crash_on_probs_error_branch_count = 0
            else:
                logger.debug("存在已经死亡的梯度,执行权重大撤回 p=%e count=%d" % (
                    mini_prob, self.crash_on_probs_error_branch_count))
                self.train_net.reset_weight(False, self.eval_net)
                mini_prob = self.train_net.probs_forward(hidden_output).min()
                if mini_prob < 1e-5:
                    logger.debug("撤回梯度无效,执行权重大重置  p=%e count=%d" % (
                        mini_prob, self.crash_on_probs_error_branch_count))
                    exp_pool.eval_model_weight_lock.acquire()
                    self.train_net.reset_weight(True, self.eval_net)
                    exp_pool.eval_model_weight_lock.release()

            loss = torch.mean(torch.square(offset))
        elif IS_DEBUG:
            loss = mean_loss
            if self.crash_on_probs_error_branch_count > 0:
                self.crash_on_probs_error_branch_count -= 1
        else:
            loss = torch.mean(torch.square(offset)) + mean_loss
            if self.crash_on_probs_error_branch_count > 0:
                self.crash_on_probs_error_branch_count -= 1

        self.optimizer.zero_grad()
        loss.backward()
        # if torch.isnan(self.train_net.pre_linear.weight.grad).any():
        #     print("权重出现nan执行权重大重置")
        #     self.train_net.reset_weight(True, self.eval_net)
        #     raise RuntimeError("梯度为nan 输入张量{}{}{}", action_probs, action_value, exp_action_value)
        self.optimizer.step()
        self.train_net.zero_grad()

        if action_probs is None:  # 没有概率层直接返回
            exp_pool.model_weight_lock.release()  # 一定要加互斥锁，防止并发更新权重
            return loss.detach().cpu()

        mini_prob = self.train_net.probs_forward(hidden_output).min()
        threshold = 1e-3 if MOCK_LEARNING else 6e-4
        if mini_prob > threshold:
            exp_pool.eval_model_weight_lock.acquire()
            self.train_net.soft_update(self.eval_net)
            exp_pool.eval_model_weight_lock.release()
        else:
            print("输出概率过小,撤回更新 p=%e" % mini_prob)
            exp_pool.eval_model_weight_lock.acquire()
            self.train_net.reset_weight(False, self.eval_net)
            exp_pool.eval_model_weight_lock.release()
            # exp_pool.env.app.change_pause_mode(MOCK_LEARNING)

        exp_pool.model_weight_lock.release()  # 一定要加互斥锁，防止并发更新权重
        return loss.detach().cpu()

    def load_weight(self):
        self.eval_net.load_state_dict(self.train_net.state_dict())


def print_state(now_state):
    if type(now_state) == list:
        b = len(now_state)
    else:
        b = now_state.shape[0]
    res = []
    for i in range(b):
        feature = torch.mean(now_state[i])
        res.append(feature)
    print(res)
    return res


class ExpPool(ExpPoolBase):

    def __init__(self, t: int, dqn: MyDQN, env: GameEnvBase, epsilon: float, max_capacity):
        super().__init__(t, epsilon, max_capacity, env.app)
        self.dqn = dqn
        self.env = env
        self.action_dim = env.action_dim
        self.env.set_exp_pool(self)

    def use_pool_call_back(self, s_t_tensor: torch.tensor, pre_s_t_tensor: torch.tensor, pre_a_t, pre_reward,
                           pre_done_value) -> (int, torch.tensor):
        action_index = self.env.watch_me_index if self.env.record_opencv_script else None
        score = None
        action_log_probs = None
        hidden_output = None
        if pre_done_value < 0.5:
            action_index = None
        if pre_done_value > 0 and not self.env.record_opencv_script:  # 游戏还在继续
            self.epsilon = self.env.epsilon
            if self.epsilon > FINAL_EPSILON:  # 低于最终概率则不调整
                # scale down epsilon
                self.epsilon = INITIAL_EPSILON - self.t * (INITIAL_EPSILON - FINAL_EPSILON) / EXPLORE
            if self.env.watch_me_all_the_time:
                if self.env.watch_me_index > -1:
                    action_index = self.env.watch_me_index
                else:
                    action_index = 0
                score = -123456
            else:
                with torch.no_grad():
                    _, temp_s_t = self.combine_state_in_pool(pre_s_t_tensor, s_t_tensor, self.queue_pool.__len__(),
                                                             TIME_WINDOW)
                    if self.env.first_run:  # 模型可视化
                        if self.dqn.eval_net.is_img_input:
                            self.env.app.show_image(temp_s_t.numpy(), add_to_summery=True)
                        trace_input = [temp_s_t.to(device), temp_s_t.to(device)]
                        summary_writer.add_graph(self.dqn.eval_net, input_to_model=trace_input)

                    # 计算所有action的Q值
                    self.eval_model_weight_lock.acquire()
                    action_value, hidden_output = self.dqn.eval_net.forward(temp_s_t.to(device), hidden_output)
                    self.eval_model_weight_lock.release()

                    if self.dqn.eval_net.USE_TUPLE_OUTPUT:  # 如果用户使用了概率网络模型，则用概率来采样目标动作
                        action_value_probs = action_value[1].detach().cpu()  # 脱离显卡
                        dist = torch.distributions.Categorical(action_value_probs)  # 按给定概率分布进行采样
                        score = torch.cat(action_value, dim=0).detach().cpu().numpy()  # 直接返回q值输出和概率输出作为score记录
                        if action_index is None:  # 没有被用户hook则直接采样动作，否则就遵从用户的选择
                            if random.random() <= self.epsilon:  # 如果小于epsilon则使用概率采样法探索
                                action_index = dist.sample().data.numpy()[0]  # 采样获取到对应动作，并将Tensor转成可用的int64整数
                            else:  # 否则使用最大得分法进行探索
                                temp_action_value = action_value[0].detach().cpu()  # 脱离显卡
                                action_index = torch.max(temp_action_value, 1)[1].data.numpy()[0]  # 取最高分
                        action_log_probs = dist.log_prob(torch.LongTensor([action_index]))  # 记录选取该动作时的概率p的log对数

                        if self.t % 1000 == 0 or self.env.first_run:
                            values = np.linspace(0, self.action_dim, self.action_dim)
                            counts = (action_value_probs[0].numpy() * 1000).astype(np.int32)
                            make_histogram(summary_writer, "action_probs", self.t, values, counts)
                            summary_writer.flush()

                    elif action_index is None:  # 使用Q值网络模型就走这里，且注意有没有被用户hook，优先遵从用户的选择
                        action_value = action_value.detach().cpu()  # 脱离显卡
                        action_index = torch.max(action_value, 1)[1].data.numpy()[0]  # 取最高分
                        score = action_value  # 直接返回action的所有Q值作为返回值
                        # score = torch.max(action_value, 1)[0].data.numpy()[0]

                        if random.random() <= self.epsilon:  # 小于epsilon时将Q值换算成概率分布进行探索
                            # 走到这里肯定不取max_value因此我们以max_value作为水平线，计算其他动作的得分差，得分差异小的给予更高的概率去选中它
                            # action_index = random.randrange(self.action_dim)
                            min_value, max_value = torch.min(action_value, 1)[0], torch.max(action_value, 1)[
                                0]  # 获取分数取值范围
                            action_value_minus = (action_value - max_value) / (max_value - min_value)  # 归一化到-1 ~ 0区间
                            action_value_plus = torch.exp(action_value_minus)  # 对于低分给予更低的概率映射(由于指数函数特性，最低概率也不为0)
                            action_value_plus[0][action_index] = 0  # 这里我们肯定不会取最优解，所以直接将概率置零
                            action_value_probs = action_value_plus / torch.sum(action_value_plus)  # 按当前数值计算概率分布
                            dist = torch.distributions.Categorical(action_value_probs)  # 按给定概率分布进行采样
                            action_index = dist.sample().data.numpy()[0]  # 采样获取到对应动作
                            score = action_value_probs

        # self.env.information3 = "use_pool_call_back使用经验池"
        self.pool_use_lock.acquire()  # 上锁经验队列
        # store the transition in D
        if pre_s_t_tensor is not None:  # 是否是reset后直接调用了use_pool
            s_t_tensor = None
            if self.dqn.eval_net.USE_TUPLE_OUTPUT:
                s_t_tensor = self.pre_action_log_probs
            q_ele = QueueElement(pre_s_t_tensor, pre_a_t, pre_reward, s_t_tensor, pre_done_value)
            if self.env.watch_me_all_the_time:
                q_ele.is_human_play = True

            self.queue_pool.append(q_ele)

            larger_than_memory_replay = len(self.queue_pool) > (self.max_capacity - 200)
            while larger_than_memory_replay and q_ele.is_terminal():  # 结束时再更新经验池，否则人类玩家数据会拼接在当前经验区后面
                # sample is enough so slow down and always wait for next training finish

                is_human_play_idx, terminal_index = self.find_terminal_index()

                if is_human_play_idx > 0:
                    human_list = self.queue_pool[0:is_human_play_idx + 1]
                    self.queue_pool = self.queue_pool[terminal_index + 1:]
                    self.queue_pool.extend(human_list)
                else:
                    self.queue_pool = self.queue_pool[terminal_index + 1:]
                larger_than_memory_replay = len(self.queue_pool) > (self.max_capacity - 200)

        self.pool_use_lock.release()  # 释放经验队列
        self.pre_action_log_probs = action_log_probs
        return action_index, score


def main_thread_train_network(epoch: int, dqn: MyDQN, app: MainUI, env: GameEnvBase, exp_pool: ExpPool,
                              round_num: int) -> Iterable[int]:
    observe = exp_pool.queue_pool.__len__()  # only train if done observing
    if observe > OBSERVE and not env.watch_me_all_the_time:  # 用户没有接管键盘时训练，否则用户玩的会比较卡
        for i, loss in dqn.learn_with_round(exp_pool, round_num):

            while app.Pause:
                exp_pool.save_model_and_reply_file(train_model=True)
                env.information = time.asctime() + "###Train Thread Pause!###"
                # print(env.information)
                time.sleep(2)

            exp_pool.t += 1

            if exp_pool.t % 500 == 0:
                env.information = "observe:{},TrainStep:{},loss:{}".format(observe, exp_pool.t,
                                                                           dqn.static_loss)
                # if dqn.static_loss > 1000:
                #     dqn.static_loss = 1000
                # elif dqn.static_loss < -1000:
                #     dqn.static_loss = -1000
                # 获取当前内存使用情况
                summary_writer.add_scalar(tag='loss/step', scalar_value=dqn.static_loss, global_step=exp_pool.t)
                if False:
                    now_observe = observe
                    eval_time = exp_pool.t
                    memory_usage = psutil.virtual_memory()
                    pc_use_mb = getattr(memory_usage, 'used', 0) / 1024 / 1024
                    use_mb = this_process.memory_full_info().uss / 1024 / 1024
                    print(f"pc_memory:{pc_use_mb} memory:{use_mb} observe:{now_observe}")
                    summary_writer.add_scalar(tag='pc_memory_use/step', scalar_value=pc_use_mb, global_step=eval_time)
                    summary_writer.add_scalar(tag='memory_use/step', scalar_value=use_mb, global_step=eval_time)
                    summary_writer.add_scalar(tag='observe/step', scalar_value=now_observe, global_step=eval_time)
                logger.debug(env.information)
                dqn.static_loss = 0
            # save progress every 10000 iterations
            if exp_pool.t % 10000 == 0:
                epoch = int(exp_pool.t / 10000)
                torch.save(dqn.train_net.state_dict(), 'saved_networks/DQN_Temp_{}.pth'.format(epoch))
            yield epoch, i
    else:
        time.sleep(1)
        yield epoch, -1

    yield epoch, -1


def prepare_train_network(app: MainUI, exp_pool: ExpPool):
    # saving and loading networks
    dqn = exp_pool.dqn
    epoch = -1
    res = get_model_file_list('saved_networks')
    for k in res.keys():
        if k > epoch:
            epoch = k
    if epoch >= 0:
        print("Load old Model DQN_Temp {}".format(res[epoch]))
        try:
            dqn.train_net.load_state_dict(torch.load(res[epoch]))
            if dqn.soft_update:
                dqn.train_net.prepare_soft_update(dqn.eval_net)
            # if app.show_message_box("是否重置死亡梯度"):
            #     pass
            #     # dqn.train_net.probs_pre_linear = nn.Linear(512, 512)
            #     # dqn.train_net.reset_weight()
            #     dqn.train_net.probs_linear.bias = None
            #     save_model_and_reply_file(exp_pool, train_model=True)
        except RuntimeError as e:
            print(e)
        app.set_sync()
        exp_pool.t = epoch * 10000
        epoch += 1
    else:
        epoch = 0

    exp_pool.load_old_file()
    return epoch, dqn


# 多线程训练，适用于复杂度低的模型
def train_network(app: MainUI, env: GameEnvBase, exp_pool: ExpPool):
    if SINGLE_THREAD:
        return
    exp_pool.model_weight_lock.acquire()  # 上锁权重，准备更新
    epoch, dqn = prepare_train_network(app, exp_pool)
    exp_pool.sync_weight()
    exp_pool.model_weight_lock.release()  # 权重更新完毕，释放锁

    # set_thread_priority(THREAD_PRIORITY_BELOW_NORMAL)  # 降低训练线程优先级，防止卡到推理线程玩游戏
    # 设置一个低优先级的CUDA流
    # low_priority_stream = torch.cuda.Stream(priority=-1)
    # with torch.cuda.stream(low_priority_stream):

    time.sleep(2)  # 先进入推理线程，后进入训练线程
    while True:
        old_epoch = epoch
        round_num = 5
        for ep, i in main_thread_train_network(old_epoch, dqn, app, env, exp_pool, round_num):
            epoch = ep
            # if epoch >= 500:  # 500万次迭代后直接关机
            #     InteractiveCmd("shutdown -s -t 30")
            #     break


def eval_network(app: MainUI, env: GameEnvBase, exp_pool: ExpPool):
    # if IS_DEBUG:
    #     return
    # define the cost function
    eval_time = 0
    batch_group = 2 if IS_DEBUG else 30
    run_reward = 0
    single_eval_t = 1
    pre_sync_step = 0
    history_reward = np.array([])
    pre_rewards = deque()

    # start training
    if SINGLE_THREAD:
        epoch, dqn = prepare_train_network(app, exp_pool)
    else:
        time.sleep(1)  # 等待train_network线程启动
        exp_pool.model_weight_lock.acquire()  # 上锁权重，准备更新
        exp_pool.model_weight_lock.release()  # 权重更新完毕，释放锁
        print("eval权重同步完毕")
    start_thread(env.information_thread, ())
    now_state, pre_state, a_t, reward, done_value = env.reset()

    while "flappy bird" != "angry bird":

        if app.Render:
            # img = now_state.data.numpy()
            # app.show_image(img)
            pass
        while app.Pause:
            exp_pool.save_model_and_reply_file(reply_cache=True, eval_model=True)
            env.information3 = time.asctime() + "###Eval Thread Pause!###"
            # print(env.information3)
            time.sleep(2)

        # if app.checkNeedSync():
        #     print("need to sync training model")
        #     dqn.loadWeight(trainingDqn)
        #     dqn.eval_net = dqn.eval_net.eval()
        # env.information3 = "准备调用exp_pool.use_pool_call_back"
        action_index, score = exp_pool.use_pool_call_back(now_state, pre_state, a_t, reward, done_value)
        # env.information3 = "exp_pool.use_pool_call_back调用完成"
        now_observe = len(exp_pool.queue_pool)

        if action_index is not None:
            now_state, pre_state, a_t, reward, done_value = env.step(action_index)
            # exp_pool.debug_queue_pool[-1].hidden_output = score
            run_reward += reward
            if len(pre_rewards) > 10:
                pre_rewards.popleft()
            else:
                pre_rewards.append(reward)
            eval_time += 1
            log_str = f"TRAIN_STEP{exp_pool.t} / EVAL_STEP{single_eval_t}%{eval_time}  / EPSILON{exp_pool.epsilon}\n" \
                      + f"/ ACTION{action_index}  / REWARD{run_reward}+{pre_rewards} /OBSERVE{now_observe}" \
                      + f"/ Q_VALUE\n {score}"
            env.information3 = log_str
            single_eval_t += 1
            if eval_time % 500 == 0:
                logger.debug(log_str)
                print(log_str)
                # run_reward = 0
        else:
            # 获取当前内存使用情况
            memory_usage = psutil.virtual_memory()
            pc_use_mb = getattr(memory_usage, 'used', 0) / 1024 / 1024
            use_mb = this_process.memory_full_info().uss / 1024 / 1024
            # print(f"pc_memory:{pc_use_mb} memory:{use_mb} observe:{now_observe}")
            summary_writer.add_scalar(tag='pc_memory_use/step', scalar_value=pc_use_mb, global_step=exp_pool.t)
            summary_writer.add_scalar(tag='memory_use/step', scalar_value=use_mb, global_step=exp_pool.t)
            summary_writer.add_scalar(tag='observe/step', scalar_value=now_observe, global_step=exp_pool.t)
            """
            注意，注意！修了一晚上bug，这里绝对绝对不能使用exp_pool信号量，否则会造成推理线程卡死，虽然不知道具体原因，但是实测最好是在train线程set
            再eval线程wait即可
            """
            # if env.record_opencv_script:
            #     env.stop_eval = True
            while env.stop_eval:
                exp_pool.save_model_and_reply_file(reply_cache=True, eval_model=True)
                env.information3 = time.asctime() + "###Eval Thread Stop!###"
                print(env.information3)
                time.sleep(2)

            if SINGLE_THREAD:
                now_observe = len(exp_pool.queue_pool)
                percent = 0.2 - 0.1 * (REPLAY_MEMORY + 10 - now_observe) / REPLAY_MEMORY  # 训练比例从0.1线性增长到0.2
                percent = 1 if percent > 1 else percent
                round_num = 10 if IS_DEBUG else int(now_observe * percent / batch_group / BATCH)
                round_num = 1 if round_num < 1 else round_num
                old_epoch = epoch
                for r in range(round_num):
                    for ep, i in main_thread_train_network(old_epoch, dqn, app, env, exp_pool, batch_group):
                        log_str = f"EPOCH: {ep}/ TRAIN_STEP{exp_pool.t} / EVAL_STEP{single_eval_t}%{eval_time} " \
                                  f"/ EPSILON{exp_pool.epsilon} / ROUND{i}%{r}%{round_num} / REWARD{run_reward}"
                        env.information3 = log_str
                        epoch = ep
            else:

                if exp_pool.t - pre_sync_step > 100 or IS_DEBUG:  # 1000步进行一次同步
                    exp_pool.model_weight_lock.acquire()  # 上锁权重，准备更新
                    exp_pool.sync_weight()
                    exp_pool.model_weight_lock.release()  # 权重更新完毕，释放锁
                    pre_sync_step = exp_pool.t
            now_state, pre_state, a_t, reward, done_value = env.reset()

            history_reward = np.append(history_reward, run_reward)  # run_reward / single_eval_t
            if len(history_reward) >= 5:
                summary_writer.add_scalar(tag='reward/step', scalar_value=history_reward.mean(), global_step=exp_pool.t)
                summary_writer.flush()
                history_reward = np.array([])
            single_eval_t = 1
            run_reward = 0

            if now_observe > OBSERVE:
                exp_pool.save_model_and_reply_file(reply_cache=True)

        if now_observe < OBSERVE or env.watch_me_all_the_time:  # 观察数量未到时高频显示观察增长趋势
            env.information = f"observe:{now_observe} run_reward:{run_reward / single_eval_t} " + \
                              f"EVAL_STEP{single_eval_t}%{eval_time}"
        if env.first_run:
            env.first_run = False

        # if t > 300:
        #     done_value = 0
