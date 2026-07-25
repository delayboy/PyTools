# -*- coding: utf-8 -*-
"""
基于 faster-whisper 的多语言语音识别服务
替代科大讯飞 SDK，支持中/英/日/韩等多语言识别
在 5454 端口启动 TCP 服务，对接其他进程的实时录音数据
"""
import os
import time
import numpy as np
from faster_whisper import WhisperModel
from PyTools.MyAwesomeTool.MyTcpHelper import TcpCollector, TcpServer
from deep_translator import GoogleTranslator

# 使用本地下载的 CTranslate2 格式模型
MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "faster-whisper-large-v3-turbo")

# 全局加载模型，避免每次识别重复加载
_model = None
translator = GoogleTranslator(source='auto', target='zh-CN')


def translate_example():
    # 单个翻译
    print(translator.translate("Hello world"))
    print(translator.translate("こんにちは世界"))
    print(translator.translate("안녕하세요 세계"))

    # 批量翻译
    texts = ["I love Python", "Pythonが好き", "Python을 좋아해요"]
    result = translator.translate_batch(texts)
    print(result)


def get_model() -> WhisperModel:
    global _model
    if _model is None:
        print(f"正在加载 Whisper 模型: {MODEL_PATH}")
        # device="auto" 会自动选择 CUDA > CPU
        # compute_type="auto" 会根据设备选择最佳精度
        _model = WhisperModel(MODEL_PATH, device="auto", compute_type="auto")
        print("Whisper 模型加载完成")
    return _model


def whisper_transcribe(audio_data: np.ndarray, sample_rate: int = 16000,
                       language: str = None) -> str:
    """
    使用 faster-whisper 对音频数据进行语音识别

    Args:
        audio_data: int16 numpy 数组
        sample_rate: 采样率，默认 16000
        language: 指定语言代码（如 "zh", "en", "ja", "ko"），
                  None 表示自动检测语言

    Returns:
        识别出的文本
    """
    model = get_model()

    # faster-whisper 期望 float32 格式，归一化到 [-1, 1]
    audio_float = audio_data.astype(np.float32) / 32768.0

    segments, info = model.transcribe(
        audio_float,
        beam_size=5,
        language=language,
        vad_filter=True,
        vad_parameters=dict(
            min_silence_duration_ms=500,
        ),
    )

    text = "".join(segment.text for segment in segments).strip()
    print(f"[Whisper] 检测语言: {info.language} (概率: {info.language_probability:.2f})")
    print(f"[Whisper] 识别结果: {text}")
    return text


def whisper_text(audio_data: np.ndarray, audio_rate: int = 16000,
                 language: str = None) -> str:
    """
    对外接口，与原 XF_text 签名保持一致，方便替换
    """
    return whisper_transcribe(audio_data, audio_rate, language)


# def callback(audio_segments: list) -> str:
#     waveform = np.concatenate(audio_segments)
#     result = whisper_text(waveform)
#     return result


def whisper_main(port: int = 5454, language: str = None):
    """
    启动 Whisper TCP 语音识别服务

    Args:
        port: TCP 服务端口
        language: 指定识别语言，None 为自动检测
    """
    # 预加载模型
    get_model()

    def _callback(segments: list) -> str:
        waveform = np.concatenate(segments)
        result = whisper_transcribe(waveform, language=language)
        return translator.translate(result)

    collector = TcpCollector(_callback)
    server = TcpServer(collector, port=port)
    server.start()
    print(f"Whisper 语音识别 TCP 服务已启动，端口: {port}")
    while True:
        time.sleep(1)


if __name__ == '__main__':
    import soundfile

    # 测试：用本地 wav 文件验证模型能正常工作
    filepath = "MyAudioTools/modelscope.wav"
    if os.path.exists(filepath):
        waveform, sample_rate = soundfile.read(filepath)
        audio_data = (waveform * 32767).astype(np.int16)
        text = whisper_text(audio_data, sample_rate)
        print(f"测试识别结果: {text}")
    else:
        print(f"测试文件不存在: {filepath}，跳过测试")

    # 启动 TCP 服务
    whisper_main()
