from PyTools.MyAwesomeTool.PyUseCPlus import *


class KeyCodeHookEventListener:
    def __init__(self, app: MainUI, my_dll: MyDll):
        self.myDll = my_dll
        self.app = app  # myPopupWin
        self.scripThread = None
        self.rect = Rect(0, 0, 1, 1)

        self.TempFilePath = os.path.dirname(os.path.abspath("./templates")) + "/templates/"  # 获取临时文件夹在电脑上的绝对路径
        self.mainManager = WinManager(self.myDll)
        self.vmManager = WinManager(self.myDll, "V1-1")
        self.taskId = -1
        self.taskTotalReward = 0  # 当前任务进度条100%时退出任务
        self.taskErrorReward = 0  # 当前任务可容忍的错误次数
        self.taskSuccess: Dict[int] = {}
        self.myDll.register_event_hook(1, True)
        self.keyCodeSignal = threading.Event()
        self.keyCodeSignal.clear()
        self.keyCode = 0

        def hook_call_back(pk: dllMain.HookPackage):
            if pk.wParam == dllMain.WM_KEYDOWN:
                self.keyCodeSignal.set()
                self.keyCode = pk.code

        self.myDll.set_py_hook_proc(hook_call_back)

    def set_task_success(self):
        if not self.taskSuccess.__contains__(self.taskId):
            self.taskSuccess[self.taskId] = 1

    def _match_sub_pos_and_do(self, temp_path, src_mat: np.ndarray, percent_rect: Rect, threshold: float,
                              sleep_time: int,
                              reward: int,
                              call_back: Callable) -> bool:

        temp = MyOpenCv.cv_imread(self.TempFilePath + temp_path, cv2.IMREAD_UNCHANGED)
        src_sub_mat, rect = MyOpenCv.cut_picture_with_percent(src_mat, percent_rect)
        score, loc = MyOpenCv.match_single_score_and_pos(src_sub_mat, temp)
        loc = (loc[0] + rect.left, loc[1] + rect.top)
        img = MyOpenCv.draw_rect(src_mat, rect)
        img = MyOpenCv.show_single_match_pic(img, temp, score, loc)
        now = datetime.datetime.now()
        large_than = '>' if score > threshold else '<'
        log_text = "[%s]--%d,%d--[%.2f %s %.2f]--%s" % (
            now, self.taskTotalReward, self.taskErrorReward, score, large_than, threshold, temp_path)
        print(log_text)
        self.app.show_image(img, log_text)
        if score > threshold:
            # self.vmManager.clickPointWithTemplates(temp, loc, 0.5, 0.5)
            call_back(temp, loc)
            time.sleep(sleep_time)
            if reward < 0:
                self.taskErrorReward += reward
            else:
                self.taskTotalReward += reward
            return True
        return False

    def _match_pos_and_do(self, temp_path, src_mat: np.ndarray, threshold: float, sleep_time: int, reward: int,
                          call_back: Callable) -> bool:

        return self._match_sub_pos_and_do(temp_path, src_mat, Rect(0, 0, 1, 1), threshold, sleep_time, reward,
                                          call_back)

    def force_to_vertical_screen(self):
        # 强制先回到竖屏模式
        if self.vmManager.is_horizon_screen():
            img = self.vmManager.capture_window_with_other_manager(self.mainManager)
            self._match_pos_and_do("虚拟手机更多功能按钮.png", img, 0.8, 2, 0,
                                   lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc))

            img = self.vmManager.capture_window_with_other_manager(self.mainManager)
            self._match_pos_and_do("虚拟手机旋转屏幕按钮.png", img, 0.8, 2, 0,
                                   lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc))

        else:
            w, h = self.vmManager.get_rect().get_size()
            offset_left = 733
            offset_top = 101
            width = 464
            height = 840
            if width - 1 <= w <= width + 1 and height - 1 <= h <= height + 1:
                pass
            else:
                # 拉动一下窗口防止缩放bug
                self.vmManager.move_window(Rect(offset_left, offset_top, offset_left + width, offset_top + height))
                time.sleep(3)
                self.myDll.set_cursor_pos(offset_left + int(width / 2), offset_top + 2)
                time.sleep(1)
                self.vmManager.drag_mouse(0, 3)
                time.sleep(3)
                # 解决缩放bug之后再移动一次窗口
                self.vmManager.move_window(Rect(offset_left, offset_top, offset_left + width, offset_top + height))
                time.sleep(1)

    @staticmethod
    def get_key_code(key_str: str):
        return key_str.encode("gbk")[0]

    def start(self):
        start_thread(self.key_code_call_back_loop, ())
        self.scripThread = start_thread(self.do_script_loop, ())

    def vm_phone_exit_to_home_script(self) -> bool:

        img = self.vmManager.capture_window_with_other_manager(self.mainManager)
        finish = False
        success = self._match_pos_and_do("虚拟手机边栏退出.png", img, 0.8, 3, 0,
                                         lambda temp, loc: [self.vmManager.click_point_with_templates(temp, loc),
                                                            time.sleep(3),
                                                            self.vmManager.click_point_with_templates(temp, loc, 0.5,
                                                                                                      0.8)])
        if success:
            self.vmManager.click_point_with_wnd_percent(0.5, 0.5, click=False)
            self.vmManager.drag_mouse(0, 100)
            time.sleep(2)
            self.vmManager.click_point_with_wnd_percent(0.5, 0.5, click=False)
            self.vmManager.drag_mouse(0, 100)
            time.sleep(2)
            img = self.vmManager.capture_window_with_other_manager(self.mainManager)
        success = self._match_pos_and_do("虚拟手机进程全部清除.png", img, 0.8, 3, 0,
                                         lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc))
        if not success:
            # 找不到清除键的时候，随便点一下，退出进程预览器
            self.vmManager.click_point_with_wnd_percent(0.8, 0.7)
            time.sleep(2)
        else:
            img = self.vmManager.capture_window_with_other_manager(self.mainManager)
            finish = True

        success = self._match_pos_and_do("米友社.png", img, 0.8, 0, 0,
                                         lambda temp, loc: None)
        if success:
            finish = True
        return finish

    def jump_to_next_task(self, normal_exit: bool = False):
        if self.taskSuccess.__contains__(self.taskId):
            if self.taskSuccess[self.taskId] <= 1:
                MyFileEditor().log(f'任务{self.taskId}成功完成')
                self.taskSuccess[self.taskId] = 100
        else:
            MyFileEditor().log(f'任务{self.taskId}执行失败')

        if normal_exit:
            # 成功则状态转移到下一个任务
            self.taskId += 1
            self.taskTotalReward = 0
            self.taskErrorReward = 0

            print("jump to next task without exit home:%d" % self.taskId)
            return True
        elif self.vm_phone_exit_to_home_script():
            # 成功则状态转移到下一个任务
            self.taskId += 1
            self.taskTotalReward = 0
            self.taskErrorReward = 0

            print("jump to next task:%d" % self.taskId)
            return True
        else:
            # 失败则保持不动
            self.taskErrorReward -= 1  # 失败则重启红手指
            print("fail to jump next task now taskId is:%d" % self.taskId)
            self.kill_red_finger()

            return False

    def do_mi_yo_she_task(self) -> bool:
        start_task_id = 0
        if self.taskId is not start_task_id:
            return False

        if self.taskTotalReward > 20 or self.taskErrorReward < -100:
            self.jump_to_next_task()
            return True

        img = self.vmManager.capture_window_with_other_manager(self.mainManager)
        if self._match_sub_pos_and_do("米友社.png", img, Rect(0, 0.2, 1, 0.8), 0.8, 2, 1,
                                      lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True
        if self._match_pos_and_do("米友社我知道了按钮.png", img, 0.8, 2, -1,
                                  lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True
        if self._match_pos_and_do("米友社每日签到入口.png", img, 0.8, 2, -1,
                                  lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True
        if self._match_pos_and_do("米友社单个福利项.png", img, 0.92, 2, 10,
                                  lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            self.set_task_success()
            return True
        if self._match_pos_and_do("立即重连.png", img, 0.8, 2, -1,
                                  lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True
        self.taskErrorReward -= 1
        return True

    def tie_dao_sub_task0(self, img: np.ndarray, task_start_id: int):
        this_task_id = 0
        if (self.taskId - task_start_id) is not this_task_id:
            return False

        if self._match_sub_pos_and_do("铁道手机图标.png", img, Rect(0.8, 0.05, 0.9, 0.1), 0.8, 2, 1,
                                      lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True

        if self._match_sub_pos_and_do("铁道委托任务图标.png", img, Rect(0.48, 0.84, 0.58, 0.94), 0.8, 2, 1,
                                      lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True
        if self._match_sub_pos_and_do("铁道黄键领取.png", img, Rect(0.02, 0.7, 0.12, 0.98), 0.8, 2, 1,
                                      lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True

        if self._match_sub_pos_and_do("铁道再次派遣.png", img, Rect(0.1, 0.54, 0.2, 0.84), 0.8, 2, 1,
                                      lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True
        if self._match_sub_pos_and_do("铁道派遣中.png", img, Rect(0.02, 0.7, 0.12, 0.98), 0.8, 2, 1,
                                      lambda temp, loc: self.vmManager.click_point_with_wnd_percent(0.86, 0.96)):
            self.set_task_success()
            return True
        return False

    def do_te_dao_task(self) -> bool:
        start_task_id = 1
        if self.taskId is not start_task_id:
            return False

        if self.taskTotalReward > 20 or self.taskErrorReward < -100:
            self.jump_to_next_task()
            return True

        img = self.vmManager.capture_window_with_other_manager(self.mainManager)

        if self._match_pos_and_do("铁道.png", img, 0.8, 2, 1,
                                  lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True

        if self.tie_dao_sub_task0(img, start_task_id):
            return True

        if self._match_pos_and_do("立即重连.png", img, 0.8, 2, -1,
                                  lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True
        if self._match_pos_and_do("虚拟手机边栏退出.png", img, 0.8, 3, -1,
                                  lambda temp, loc: self.vmManager.click_point_with_wnd_percent(0.5, 0.5)):
            return True
        self.taskErrorReward -= 1
        return True

    # 获取尘歌壶每日货币
    def 获取尘歌壶每日货币原神任务0(self, img: np.ndarray, task_start_id: int):
        this_task_id = 0
        if (self.taskId - task_start_id) is not this_task_id:
            return False

        can_get_coin = False
        if self._match_sub_pos_and_do("尘歌壶钱币.png", img, Rect(0.12, 0.4, 0.3, 0.7), 0.8, 0, 100,
                                      lambda temp, loc: None):

            can_get_coin = True
        elif self._match_sub_pos_and_do("尘歌壶第二种钱币.png", img, Rect(0.12, 0.4, 0.3, 0.7), 0.8, 0, 100,
                                        lambda temp, loc: None):
            can_get_coin = True

        if can_get_coin:
            self.vmManager.click_point_with_wnd_percent(0.12, 0.48)
            time.sleep(2)
            self.vmManager.click_point_with_wnd_percent(0.22, 0.94)
            time.sleep(2)
            return True

        if self._match_sub_pos_and_do("对话信任等阶.png", img, Rect(0, 0.62, 1, 0.72), 0.8, 2, 1,
                                      lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            self.set_task_success()
            return True

        if self._match_pos_and_do("阿园.png", img, 0.93, 2, 1,
                                  lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True

        # 电机移动按钮向右侧走两步，获取对话框
        if self._match_sub_pos_and_do("尘歌壶手指.png", img, Rect(0.8, 0.54, 0.9, 0.64), 0.8, 2, 1,
                                      lambda temp, loc: self.vmManager.click_point_with_wnd_percent(0.2, 0.22)):
            return True

        # 点击小地图
        if self._match_sub_pos_and_do("派蒙.png", img, Rect(0.8, 0.05, 0.9, 0.1), 0.8, 2, 1,
                                      lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc, -1, 3)):
            return True

        if self._match_sub_pos_and_do("原神地图星形罗盘图标.png", img, Rect(0.01, 0.92, 0.12, 1), 0.97, 2, 1,
                                      lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True

        if self._match_sub_pos_and_do("原神地图尘哥壶图标.png", img, Rect(0, 0.7, 1, 0.8), 0.8, 2, 2,
                                      lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True

        if self._match_sub_pos_and_do("原神地图两个字.png", img, Rect(0.82, 0.68, 0.92, 0.78), 0.8, 0, 1,
                                      lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc, -5, 2,
                                                                                                  click=False)):
            self.vmManager.drag_mouse(30, 0)
            time.sleep(2)
            return True

        if self._match_sub_pos_and_do("宅邸地图图标.png", img, Rect(0, 0.4, 1, 0.7), 0.8, 2, 2,
                                      lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True

        if self._match_pos_and_do("宅邸弹出图标.png", img, 0.8, 2, 2,
                                  lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True

        if self._match_sub_pos_and_do("黄黑键传送.png", img, Rect(0.02, 0.7, 0.12, 1), 0.8, 2, 2,
                                      lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True
        return False

    # 进行探索派遣
    def 进行探索派遣原神任务1(self, img: np.ndarray, task_start_id: int):
        this_task_id = 1
        if (self.taskId - task_start_id) is not this_task_id:
            return False

        if self._match_pos_and_do("对话凯瑟琳.png", img, 0.93, 2, 1,
                                  lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True

        if self._match_pos_and_do("对话探索派遣.png", img, 0.8, 2, 0,
                                  lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True

        if self._match_sub_pos_and_do("原神绿按领取.png", img, Rect(0.02, 0.76, 0.12, 1), 0.9, 2, 0,
                                      lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True

        if self._match_sub_pos_and_do("选择角色.png", img, Rect(0.02, 0.76, 0.12, 1), 0.8, 2, 10,
                                      lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            self.vmManager.click_point_with_wnd_percent(0.72, 0.28)
            time.sleep(1)
            self.vmManager.click_point_with_wnd_percent(0.64, 0.28)
            time.sleep(1)
            return True

        def pai_qian_switch_temp_function(temp: np.ndarray, loc: tuple):
            i = -self.taskErrorReward % 4
            print(self.taskErrorReward, i)
            self.vmManager.click_point_with_templates(temp, loc, percent_x=-1.1 * i)

        if self._match_sub_pos_and_do("切换探索派遣.png", img, Rect(0.80, 0.04, 0.92, 0.24), 0.8, 2, -1,
                                      lambda temp, loc: pai_qian_switch_temp_function(temp, loc)):
            self.set_task_success()
            return True

        # 点击小地图
        if self._match_sub_pos_and_do("尘歌壶手指.png", img, Rect(0.8, 0.54, 0.9, 0.64), 0.8, 2, 0,
                                      lambda temp, loc: self.vmManager.click_point_with_wnd_percent(0.78, 0.16)):
            return True

        if self._match_sub_pos_and_do("黄黑键传送.png", img, Rect(0.02, 0.7, 0.12, 1), 0.8, 2, 2,
                                      lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True

        if self._match_sub_pos_and_do("尘歌壶地图Logo.png", img, Rect(0.01, 0.92, 0.12, 1), 0.9, 2, 0,
                                      lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True

        if self._match_pos_and_do("传送锚点展开图标.png", img, 0.9, 2, 0,
                                  lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True

        if self._match_sub_pos_and_do("蒙德地图展开图标.png", img, Rect(0, 0.7, 1, 0.8), 0.8, 2, 2,
                                      lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            self.vmManager.click_point_with_wnd_percent(0.46, 0.52)
            time.sleep(2)
            return True

        if self._match_sub_pos_and_do("原神地图两个字.png", img, Rect(0.82, 0.68, 0.92, 0.78), 0.8, 0, 1,
                                      lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc, -5, 2,
                                                                                                  click=False)):
            self.vmManager.drag_mouse(-30, 0)
            time.sleep(2)
            return True

        if self._match_sub_pos_and_do("对话再见.png", img, Rect(0.24, 0.64, 0.34, 0.74), 0.8, 2, 0,
                                      lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True

        if self._match_sub_pos_and_do("原神叉号按钮.png", img, Rect(0.8, 0.92, 0.9, 1), 0.8, 2, 0,
                                      lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True

        if self._match_sub_pos_and_do("原神小地图铁匠图标.png", img, Rect(0.68, 0.12, 0.78, 0.22), 0.8, 2, 1,
                                      lambda temp, loc: None):
            self.vmManager.click_point_with_wnd_percent(0.30, 0.198, click=False)
            self.myDll.send_mouse_down(True)
            time.sleep(0.5)
            self.myDll.send_mouse_down(False)
            time.sleep(1)
            return True

        if self._match_sub_pos_and_do("原神小地图图标传送锚点.png", img, Rect(0.74, 0.135, 0.86, 0.16), 0.8, 2, 1,
                                      lambda temp, loc: None):
            self.vmManager.click_point_with_wnd_percent(0.30, 0.18, click=False)
            self.myDll.send_mouse_down(True)
            time.sleep(0.5)
            self.myDll.send_mouse_down(False)
            time.sleep(1)
            return True

        # 默认播放走路脚本
        if self._match_sub_pos_and_do("派蒙.png", img, Rect(0.8, 0.05, 0.9, 0.1), 0.8, 2, 1,
                                      lambda temp, loc: None):
            self.vmManager.click_point_with_wnd_percent(0.30, 0.20, click=False)
            self.myDll.send_mouse_down(True)
            time.sleep(1)
            self.myDll.send_mouse_down(False)
            time.sleep(1)

            return True

        return False

    # 领取纪行任务
    def 领取纪行任务原神任务2(self, img: np.ndarray, task_start_id: int) -> bool:
        this_task_id = 2
        if (self.taskId - task_start_id) is not this_task_id:
            return False

        if self._match_sub_pos_and_do("纪行一件领取.png", img, Rect(0.02, 0.76, 0.12, 1), 0.8, 2, 10,
                                      lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True

        if self._match_sub_pos_and_do("纪行左上角ui图标.png", img, Rect(0.8, 0.02, 1, 0.14), 0.8, 2, 1,
                                      lambda temp, loc: None):
            self.vmManager.click_point_with_wnd_percent(0.64, 0.1)
            self.set_task_success()
            return True

        if self._match_sub_pos_and_do("派蒙.png", img, Rect(0.8, 0.05, 0.9, 0.1), 0.8, 2, 1,
                                      lambda temp, loc: None):
            self.vmManager.click_point_with_wnd_percent(0.86, 0.73)

            return True

        if self._match_sub_pos_and_do("原神叉号按钮.png", img, Rect(0.8, 0.92, 0.9, 1), 0.8, 2, 0,
                                      lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True

        if self._match_sub_pos_and_do("对话再见.png", img, Rect(0.24, 0.64, 0.34, 0.74), 0.8, 2, 0,
                                      lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True
        return False

    def do_yuan_shen_task(self) -> bool:
        start_task_id = 2
        end_task_id = 4
        if not (start_task_id <= self.taskId <= end_task_id):
            return False
        if self.taskTotalReward > 100 or self.taskErrorReward < -100:
            self.jump_to_next_task(start_task_id <= self.taskId + 1 <= end_task_id)
            return True

        img = self.vmManager.capture_window_with_other_manager(self.mainManager)
        if self._match_pos_and_do("原神.png", img, 0.8, 2, 1,
                                  lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True

        if self.获取尘歌壶每日货币原神任务0(img, start_task_id):
            return True

        if self.进行探索派遣原神任务1(img, start_task_id):
            return True

        if self.领取纪行任务原神任务2(img, start_task_id):
            return True

        if self._match_pos_and_do("立即重连.png", img, 0.8, 2, -1,
                                  lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True
        if self._match_pos_and_do("虚拟手机边栏退出.png", img, 0.8, 3, -1,
                                  lambda temp, loc: self.vmManager.click_point_with_wnd_percent(0.42, 0.42)):
            return True
        self.taskErrorReward -= 1
        return True

    def do_idle_task(self):

        if self.taskErrorReward < -20:
            self.kill_red_finger()
            return True

        img = self.vmManager.capture_window_with_other_manager(self.mainManager)
        if self._match_pos_and_do("米友社.png", img, 0.8, 5, 0,
                                  lambda temp, loc: self.vmManager.click_point_with_wnd_percent(0.8, 0.7)):

            if self.taskTotalReward < 65530:
                self.taskTotalReward += 1
            now = datetime.datetime.now()  # now += datetime.timedelta(seconds=1)

            # 在每天的7:00-18:00之间，每隔2小时重新做一遍任务。
            if 7 <= now.hour <= 18 and (self.taskTotalReward > 60 * 24 or self.taskErrorReward < -20):
                self.taskTotalReward = 0
                self.taskErrorReward = 0
                self.taskId = 0
            return True

        if self.vm_phone_exit_to_home_script():
            return True

        elif self._match_pos_and_do("立即重连.png", img, 0.8, 5, -1,
                                    lambda temp, loc: self.vmManager.click_point_with_templates(temp, loc)):
            return True

        if self.taskErrorReward > -65530:
            self.taskErrorReward -= 1
        return True

    def kill_red_finger(self):
        print("kill RedFingerPlayer")
        aim_pid = procHelper.search_process_by_name("RedFingerPlayer.exe")
        if aim_pid > 0:
            procHelper.kill_process_by_pid(aim_pid)
            self.vmManager.hwnd = 0  # 必须要将当前手机窗口设置为无效状态，才能重启手机

    def vm_phone_script(self):
        if self.do_mi_yo_she_task():
            return
        elif self.do_te_dao_task():
            return
        elif self.do_yuan_shen_task():
            return
        else:
            self.do_idle_task()

    def do_script_loop(self):
        while True:
            now = datetime.datetime.now()
            if 2 <= now.hour <= 5:  # 凌晨2:00到5:00之间关闭红手指
                self.kill_red_finger()
                self.taskSuccess = {}
                time.sleep(20)
                continue

            if self.vmManager.hwnd == 0:  # 如果没找到手机窗口，则重启红手指
                self.kill_red_finger()
                aim_process_name = smart_guess_file_or_link("redFinger")
                cmd_command = "\"{}\"".format(aim_process_name)
                start_thread(procHelper.run_cmd, (cmd_command,))
                time.sleep(5)
                print(f"run cmd:{aim_process_name}")
                parent_win = WinManager(self.myDll, "RedFingerPlayer.exe", True)
                if parent_win.hwnd != 0:

                    img = self.mainManager.capture_window(None)
                    self._match_pos_and_do("关闭更新.png", img, 0.9, 5, 0,
                                           lambda temp, loc: self.mainManager.click_point_with_templates(temp, loc))
                    img = self.mainManager.capture_window(None)
                    self._match_pos_and_do("广告关闭.png", img, 0.8, 2, 0,
                                           lambda temp, loc: self.mainManager.click_point_with_templates(temp, loc))
                    img = self.mainManager.capture_window(None)
                    self._match_pos_and_do("红手指启动虚拟手机按钮.png", img, 0.9, 2, 0,
                                           lambda temp, loc: self.mainManager.click_point_with_templates(temp, loc, 0.5,
                                                                                                         0.5, True, 1))
                    img = self.mainManager.capture_window(None)
                    self._match_pos_and_do("红手指重启按钮.png", img, 0.8, 2, 0,
                                           lambda temp, loc: self.mainManager.click_point_with_templates(temp, loc))

                    img = self.mainManager.capture_window(None)
                    self._match_pos_and_do("红手指确定按钮.png", img, 0.9, 2, 0,
                                           lambda temp, loc: self.mainManager.click_point_with_templates(temp, loc))

                    img = self.mainManager.capture_window(None)
                    self._match_pos_and_do("红手指确定按钮.png", img, 0.9, 2, 0,
                                           lambda temp, loc: self.mainManager.click_point_with_templates(temp, loc))

                    img = self.mainManager.capture_window(None)
                    self._match_pos_and_do("红手指启动虚拟手机按钮.png", img, 0.9, 2, 0,
                                           lambda temp, loc: self.mainManager.click_point_with_templates(temp, loc))
                    self.vmManager = WinManager(self.myDll, "V1-1")
                    self.taskErrorReward = 0  # 必须要重置当前奖励值
                    self.taskTotalReward = 0
                    if self.vmManager.hwnd != 0:
                        MyFileEditor().log("重启红手指")
                        time.sleep(5)
                    else:
                        MyFileEditor().log("重启红手指失败")
                        time.sleep(60 * 30)

                continue

            self.force_to_vertical_screen()
            if self.app.Pause:
                img = self.vmManager.capture_window_with_other_manager(self.mainManager)
                rect = MyOpenCv.get_real_rect_by_percent_rect(img, self.rect)
                img = MyOpenCv.draw_rect(img, rect)
                self.app.show_image(img, self.rect.__str__() + "\n" + rect.__str__())
                time.sleep(0.1)
                continue
            else:
                self.vm_phone_script()

    def key_code_call_back_loop(self):
        while True:
            self.keyCodeSignal.wait()
            self.keyCodeSignal.clear()
            key_code = self.keyCode
            print(self.get_key_code('A'), key_code)

            if key_code == 192:
                self.app.change_pause_mode()
                print("pause:", self.app.Pause)
            elif key_code == dllMain.VK_F1:
                img = self.vmManager.capture_window_with_other_manager(self.mainManager)
                MyOpenCv.cv_im_write('整机截图.png', img)
            elif self.get_key_code('0') <= key_code <= self.get_key_code('9'):
                self.taskId = key_code - self.get_key_code('0') - 1
                print("jump to taskID:", self.taskId)
            elif key_code == 38:  # 上
                self.rect.move_offset(offset_y=-0.02)
                print(self.rect.__str__())
            elif key_code == 37:  # 左
                self.rect.move_offset(offset_x=-0.02)
            elif key_code == 39:  # 右
                self.rect.move_offset(offset_x=0.02)
            elif key_code == 40:  # 下
                self.rect.move_offset(offset_y=0.02)
