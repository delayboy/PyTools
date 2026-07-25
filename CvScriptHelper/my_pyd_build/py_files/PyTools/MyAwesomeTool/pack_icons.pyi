from PIL import Image
from __future__ import annotations
from _io import BytesIO
import cv2 as cv2
import numpy as np
import os as os
import sqlite3 as sqlite3
import threading as threading
import zipfile as zipfile
__all__ = ['BytesIO', 'DB_FILE', 'ICON_DIR', 'IconStore', 'IconStoreSQLite', 'Image', 'ZIP_FILE', 'cv2', 'np', 'os', 'pack', 'pack_db', 'sqlite3', 'threading', 'zipfile']
class IconStore:
    """
    从 ZIP 文件加载所有图标到内存，线程安全读取
    """
    def __init__(self, zip_path: str):
        ...
    def _load_all(self):
        """
        启动时一次性从 ZIP 读取所有文件到内存
        """
    def exists(self, filename: str) -> bool:
        """
        检查图标是否存在
        """
    def get_cv(self, filename: str, flags: int = -1) -> numpy.ndarray | None:
        """
        
                获取 OpenCV 格式的图片 (BGR/BGRA numpy array)
                等价于原来的 MyOpenCv.cv_imread(path, -1)
                flags: -1=保持原样(含alpha), 1=彩色, 0=灰度
                
        """
    def get_pil(self, filename: str) -> PIL.Image.Image | None:
        """
        
                获取 PIL Image 对象
                等价于原来的 Image.open(path)
                
        """
    def list_all(self) -> list[str]:
        """
        列出所有图标文件名
        """
    @property
    def count(self) -> int:
        ...
class IconStoreSQLite:
    def __init__(self, db_path: str):
        ...
    def _get_conn(self):
        ...
    def exists(self, filename: str) -> bool:
        ...
    def get_cv(self, filename: str, flags: int = -1) -> numpy.ndarray | None:
        ...
    def get_pil(self, filename: str) -> PIL.Image.Image | None:
        ...
def pack():
    ...
def pack_db():
    ...
DB_FILE: str = 'icons.db'
ICON_DIR: str = 'icons/'
ZIP_FILE: str = 'icons.zip'
