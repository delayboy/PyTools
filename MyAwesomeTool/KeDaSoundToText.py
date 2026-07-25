# -*- coding：utf-8 -*-
# -*- author：zzZ_CMing  CSDN address:https://blog.csdn.net/zzZ_CMing
# -*- 2018/08/11; 10:19
# -*- python3.5
"""
参考代码地址：https://blog.csdn.net/fang_yang_wa/article/details/78791137
"""
from ctypes import *
import time
import win32com.client
import numpy as np
from PyTools.MyAwesomeTool.MyTcpHelper import TcpCollector, TcpServer
import soundfile

FRAME_LEN = 640  # Byte
MSP_SUCCESS = 0
# 返回结果状态
MSP_AUDIO_SAMPLE_FIRST = 1
MSP_AUDIO_SAMPLE_CONTINUE = 2
MSP_AUDIO_SAMPLE_LAST = 4
MSP_REC_STATUS_COMPLETE = 5

# 调用动态链接库
dll = cdll.LoadLibrary("./KeDa/bin/msc_x64.dll")
# 登录参数，apppid一定要和你的下载SDK对应
login_params = b"appid = ad442d7e, work_dir = KeDa."


class Msp:
    def __init__(self):
        pass

    def login(self):
        ret = dll.MSPLogin(None, None, login_params)
        # print('MSPLogin =>', ret)

    def logout(self):
        ret = dll.MSPLogout()
        # print('MSPLogout =>', ret)

    def isr_arr(self, audio_arr: np.ndarray, session_begin_params):
        ret = c_int()
        dll.QISRSessionBegin.restype = c_char_p
        sessionID = dll.QISRSessionBegin(None, session_begin_params, byref(ret))
        # print('QISRSessionBegin => sessionID:', sessionID, '\nret:', ret.value)

        # 每秒【1000ms】  16000 次 * 16 bit 【20B】 ，每毫秒：1.6 * 16bit 【1.6*2B】 = 32Byte
        # 1帧音频20ms【640B】 每次写入 10帧=200ms 【6400B】

        # piceLne = FRAME_LEN * 20
        # 将 numpy 数组转换为 bytes 类型
        audio_bytes = audio_arr.tobytes()
        piceLne = 1638 * 2
        epStatus = c_int(0)
        recogStatus = c_int(0)

        total_length = len(audio_bytes)
        pointer = 0
        first_flag = True
        # 分段读取并处理数据
        time.sleep(0.1)
        while pointer < total_length:
            # 获取当前块的数据
            wavData = audio_bytes[pointer:pointer + piceLne]
            if first_flag:
                ret = dll.QISRAudioWrite(sessionID, audio_bytes, len(audio_bytes), MSP_AUDIO_SAMPLE_FIRST,
                                         byref(epStatus),
                                         byref(recogStatus))
                first_flag = False
                break
            else:
                ret = dll.QISRAudioWrite(sessionID, wavData, len(wavData), MSP_AUDIO_SAMPLE_CONTINUE, byref(epStatus),
                                         byref(recogStatus))
            time.sleep(0.1)
            # 更新指针
            pointer += piceLne
            print(pointer, "/", total_length)

        # print('len(wavData):', len(wavData), '\nQISRAudioWrite ret:', ret,'\nepStatus:', epStatus.value, '\nrecogStatus:', recogStatus.value)

        ret = dll.QISRAudioWrite(sessionID, None, 0, MSP_AUDIO_SAMPLE_LAST, byref(epStatus), byref(recogStatus))
        # print('len(wavData):', len(wavData), 'QISRAudioWrite ret:', ret, 'epStatus:', epStatus.value, 'recogStatus:', recogStatus.value)

        print("\n所有待识别音频已全部发送完毕\n获取的识别结果:")

        # -- 获取音频
        laststr = ''
        counter = 0
        while recogStatus.value != MSP_REC_STATUS_COMPLETE:
            ret = c_int()
            dll.QISRGetResult.restype = c_char_p
            retstr = dll.QISRGetResult(sessionID, byref(recogStatus), 0, byref(ret))
            if retstr is not None:
                laststr += retstr.decode()
                # print('333',laststr)
            # print('ret:', ret.value, 'recogStatus:', recogStatus.value)
            counter += 1
            time.sleep(0.2)
            counter += 1
            """
            if counter == 50:
                laststr += '讯飞语音识别失败'
                break
            """
        # print(laststr)

        # 不知道为什么注解了？
        # ret = dll.QISRSessionEnd(sessionID, '\0')

        # print('end ret: ', ret)
        return laststr

    def isr(self, audiofile, session_begin_params):
        ret = c_int()
        dll.QISRSessionBegin.restype = c_char_p
        sessionID = dll.QISRSessionBegin(None, session_begin_params, byref(ret))
        # print('QISRSessionBegin => sessionID:', sessionID, '\nret:', ret.value)

        # 每秒【1000ms】  16000 次 * 16 bit 【20B】 ，每毫秒：1.6 * 16bit 【1.6*2B】 = 32Byte
        # 1帧音频20ms【640B】 每次写入 10帧=200ms 【6400B】

        # piceLne = FRAME_LEN * 20
        piceLne = 1638 * 2
        epStatus = c_int(0)
        recogStatus = c_int(0)

        wavFile = open(audiofile, 'rb')
        wavData = wavFile.read(piceLne)

        ret = dll.QISRAudioWrite(sessionID, wavData, len(wavData), MSP_AUDIO_SAMPLE_FIRST, byref(epStatus),
                                 byref(recogStatus))
        # print('len(wavData):', len(wavData), '\nQISRAudioWrite ret:', ret,'\nepStatus:', epStatus.value, '\nrecogStatus:', recogStatus.value)

        time.sleep(0.1)
        while wavData:
            wavData = wavFile.read(piceLne)
            if len(wavData) == 0:
                break
            ret = dll.QISRAudioWrite(sessionID, wavData, len(wavData), MSP_AUDIO_SAMPLE_CONTINUE, byref(epStatus),
                                     byref(recogStatus))
            # print('len(wavData):', len(wavData), 'QISRAudioWrite ret:', ret, 'epStatus:', epStatus.value, 'recogStatus:', recogStatus.value)
            time.sleep(0.1)
        wavFile.close()
        ret = dll.QISRAudioWrite(sessionID, None, 0, MSP_AUDIO_SAMPLE_LAST, byref(epStatus), byref(recogStatus))
        # print('len(wavData):', len(wavData), 'QISRAudioWrite ret:', ret, 'epStatus:', epStatus.value, 'recogStatus:', recogStatus.value)

        # print("\n所有待识别音频已全部发送完毕\n获取的识别结果:")

        # -- 获取音频
        laststr = ''
        counter = 0
        while recogStatus.value != MSP_REC_STATUS_COMPLETE:
            ret = c_int()
            dll.QISRGetResult.restype = c_char_p
            retstr = dll.QISRGetResult(sessionID, byref(recogStatus), 0, byref(ret))
            if retstr is not None:
                laststr += retstr.decode()
                # print('333',laststr)
            # print('ret:', ret.value, 'recogStatus:', recogStatus.value)
            counter += 1
            time.sleep(0.2)
            counter += 1
            """
            if counter == 50:
                laststr += '讯飞语音识别失败'
                break
            """
        # print(laststr)

        # 不知道为什么注解了？
        # ret = dll.QISRSessionEnd(sessionID, '\0')

        # print('end ret: ', ret)
        return laststr


# 如果代码作为外置包被其他程序调用，请注释掉下两行；单独使用时保留
filepath = "MyAudioTools/modelscope.wav"
waveform, sample_rate = soundfile.read(filepath)
audio_data = (waveform * 32767).astype(np.int16)


def XF_text(audio_data, audio_rate=16000):
    # print("科大讯飞登录成功")
    msp = Msp()
    # print("登录科大讯飞")
    msp.login()
    session_begin_params = b"sub = iat, ptt = 0, result_encoding = utf8, result_type = plain, domain = iat"
    if 16000 == audio_rate:
        session_begin_params = b"sub = iat, domain = iat, language = zh_cn, accent = mandarin, sample_rate = 16000, result_type = plain, result_encoding = utf8"

    # audio_data = (audio_data / 32767)
    # text = msp.isr(filepath, session_begin_params)
    text = msp.isr_arr(audio_data, session_begin_params)
    msp.logout()
    print(text)
    # 文本转语音
    # speaker = win32com.client.Dispatch("SAPI.SpVoice")
    # speaker.Speak(text)
    return text


XF_text(audio_data, 16000)


def callback(audio_segments: list) -> str:
    waveform = np.concatenate(audio_segments)  # / 32767

    result = XF_text(waveform)
    return result


def ke_da_main():
    collector = TcpCollector(callback)
    server = TcpServer(collector, port=5454)
    server.start()
    while True:
        time.sleep(1)


if __name__ == '__main__':
    ke_da_main()
