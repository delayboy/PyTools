"""

参考代码地址：https://blog.csdn.net/fang_yang_wa/article/details/78791137
"""
from PyTools.MyAwesomeTool.MyTcpHelper import TcpCollector
from PyTools.MyAwesomeTool.MyTcpHelper import TcpServer
from __future__ import annotations
from _ctypes import Array
from _ctypes import FormatError
from _ctypes import POINTER
from _ctypes import Structure as LittleEndianStructure
from _ctypes import Structure
from _ctypes import Union
from _ctypes import Union as LittleEndianUnion
from _ctypes import addressof
from _ctypes import alignment
from _ctypes import byref
from _ctypes import get_errno
from _ctypes import get_last_error
from _ctypes import pointer
from _ctypes import resize
from _ctypes import set_errno
from _ctypes import set_last_error
from _ctypes import sizeof
import ctypes
from ctypes import ARRAY
from ctypes import ArgumentError
from ctypes import CDLL
from ctypes import CFUNCTYPE
from ctypes import DllCanUnloadNow
from ctypes import DllGetClassObject
from ctypes import HRESULT
from ctypes import LibraryLoader
from ctypes import OleDLL
from ctypes import PYFUNCTYPE
from ctypes import PyDLL
from ctypes import SetPointerType
from ctypes import WINFUNCTYPE
from ctypes import WinDLL
from ctypes import WinError
from ctypes._endian import BigEndianStructure
from ctypes._endian import BigEndianUnion
from ctypes import c_bool
from ctypes import c_byte as c_int8
from ctypes import c_byte
from ctypes import c_char
from ctypes import c_char_p
from ctypes import c_double as c_longdouble
from ctypes import c_double
from ctypes import c_float
from ctypes import c_long as c_int
from ctypes import c_long
from ctypes import c_long as c_int32
from ctypes import c_longlong
from ctypes import c_longlong as c_ssize_t
from ctypes import c_longlong as c_int64
from ctypes import c_short
from ctypes import c_short as c_int16
from ctypes import c_ubyte as c_uint8
from ctypes import c_ubyte
from ctypes import c_ulong as c_uint32
from ctypes import c_ulong as c_uint
from ctypes import c_ulong
from ctypes import c_ulonglong as c_uint64
from ctypes import c_ulonglong as c_size_t
from ctypes import c_ulonglong
from ctypes import c_ushort as c_uint16
from ctypes import c_ushort
from ctypes import c_void_p
from ctypes import c_void_p as c_voidp
from ctypes import c_wchar
from ctypes import c_wchar_p
from ctypes import cast
from ctypes import create_string_buffer as c_buffer
from ctypes import create_string_buffer
from ctypes import create_unicode_buffer
from ctypes import py_object
from ctypes import string_at
from ctypes import wstring_at
import numpy as np
import numpy
import soundfile as soundfile
import time as time
import win32com as win32com
__all__ = ['ARRAY', 'ArgumentError', 'Array', 'BigEndianStructure', 'BigEndianUnion', 'CDLL', 'CFUNCTYPE', 'DEFAULT_MODE', 'DllCanUnloadNow', 'DllGetClassObject', 'FRAME_LEN', 'FormatError', 'GetLastError', 'HRESULT', 'LibraryLoader', 'LittleEndianStructure', 'LittleEndianUnion', 'MSP_AUDIO_SAMPLE_CONTINUE', 'MSP_AUDIO_SAMPLE_FIRST', 'MSP_AUDIO_SAMPLE_LAST', 'MSP_REC_STATUS_COMPLETE', 'MSP_SUCCESS', 'Msp', 'OleDLL', 'POINTER', 'PYFUNCTYPE', 'PyDLL', 'RTLD_GLOBAL', 'RTLD_LOCAL', 'SetPointerType', 'Structure', 'TcpCollector', 'TcpServer', 'Union', 'WINFUNCTYPE', 'WinDLL', 'WinError', 'XF_text', 'addressof', 'alignment', 'audio_data', 'byref', 'c_bool', 'c_buffer', 'c_byte', 'c_char', 'c_char_p', 'c_double', 'c_float', 'c_int', 'c_int16', 'c_int32', 'c_int64', 'c_int8', 'c_long', 'c_longdouble', 'c_longlong', 'c_short', 'c_size_t', 'c_ssize_t', 'c_ubyte', 'c_uint', 'c_uint16', 'c_uint32', 'c_uint64', 'c_uint8', 'c_ulong', 'c_ulonglong', 'c_ushort', 'c_void_p', 'c_voidp', 'c_wchar', 'c_wchar_p', 'callback', 'cast', 'cdll', 'create_string_buffer', 'create_unicode_buffer', 'dll', 'filepath', 'get_errno', 'get_last_error', 'ke_da_main', 'login_params', 'memmove', 'memset', 'np', 'oledll', 'pointer', 'py_object', 'pydll', 'pythonapi', 'resize', 'sample_rate', 'set_errno', 'set_last_error', 'sizeof', 'soundfile', 'string_at', 'time', 'waveform', 'win32com', 'windll', 'wstring_at']
class Msp:
    def __init__(self):
        ...
    def isr(self, audiofile, session_begin_params):
        ...
    def isr_arr(self, audio_arr: numpy.ndarray, session_begin_params):
        ...
    def login(self):
        ...
    def logout(self):
        ...
def XF_text(audio_data, audio_rate = 16000):
    ...
def callback(audio_segments: list) -> str:
    ...
def ke_da_main():
    ...
DEFAULT_MODE: int = 0
FRAME_LEN: int = 640
GetLastError: ctypes.CDLL.__init__.<locals>._FuncPtr  # value = <_FuncPtr object>
MSP_AUDIO_SAMPLE_CONTINUE: int = 2
MSP_AUDIO_SAMPLE_FIRST: int = 1
MSP_AUDIO_SAMPLE_LAST: int = 4
MSP_REC_STATUS_COMPLETE: int = 5
MSP_SUCCESS: int = 0
RTLD_GLOBAL: int = 0
RTLD_LOCAL: int = 0
audio_data: numpy.ndarray  # value = array([  0,   0,   0, ...,  68, 113, 126], dtype=int16)
cdll: ctypes.LibraryLoader  # value = <ctypes.LibraryLoader object>
dll: ctypes.CDLL  # value = <CDLL 'Z:\Computer\Program\Program_maker\python3\PyTools\CvScriptHelper\my_pyd_build\KeDa\bin\msc_x64.dll', handle 7ffb87fd0000 at 0x19ddd612310>
filepath: str = 'MyAudioTools/modelscope.wav'
login_params: bytes  # value = b'appid = ad442d7e, work_dir = KeDa.'
memmove: ctypes.CFUNCTYPE.<locals>.CFunctionType  # value = <CFunctionType object>
memset: ctypes.CFUNCTYPE.<locals>.CFunctionType  # value = <CFunctionType object>
oledll: ctypes.LibraryLoader  # value = <ctypes.LibraryLoader object>
pydll: ctypes.LibraryLoader  # value = <ctypes.LibraryLoader object>
pythonapi: ctypes.PyDLL  # value = <PyDLL 'python dll', handle 7ffbc7830000 at 0x19ddd6a0cd0>
sample_rate: int = 16000
waveform: numpy.ndarray  # value = array([ 0.00000000e+00,  0.00000000e+00, -3.05175781e-05, ...,...
windll: ctypes.LibraryLoader  # value = <ctypes.LibraryLoader object>
