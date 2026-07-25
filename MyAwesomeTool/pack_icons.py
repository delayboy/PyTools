import zipfile
import numpy as np
import cv2
from PIL import Image
from io import BytesIO
import os
import threading
import sqlite3
import os

ICON_DIR = "icons/"
ZIP_FILE = "icons.zip"
DB_FILE = "icons.db"

"""将 icons/ 目录打包到 SQLite 数据库"""


def pack_db():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
    conn = sqlite3.connect(DB_FILE)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS icons (
            name  TEXT PRIMARY KEY,
            data  BLOB NOT NULL,
            size  INTEGER
        )
    """)
    for fname in sorted(os.listdir(ICON_DIR)):
        if not fname.lower().endswith('.png'):
            continue
        fpath = os.path.join(ICON_DIR, fname)
        with open(fpath, 'rb') as f:
            data = f.read()
        conn.execute("INSERT INTO icons (name, data, size) VALUES (?, ?, ?)",
                     (fname, data, len(data)))
    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM icons").fetchone()[0]
    conn.close()
    print(f"✅ 已打包 {total} 个图标到 {DB_FILE}")


"""
将 icons/ 目录下所有 PNG 打包为 icons.zip
运行一次即可：python pack_icons.py
"""


def pack():
    with zipfile.ZipFile(ZIP_FILE, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fname in sorted(os.listdir(ICON_DIR)):
            if fname.lower().endswith('.png'):
                fpath = os.path.join(ICON_DIR, fname)
                zf.write(fpath, arcname=fname)  # 扁平化，不带目录前缀
                print(f"  已打包: {fname}")
    print(f"\n✅ 共打包完成，输出: {ZIP_FILE}")


"""
统一的图标资源管理器 —— 从 ZIP 文件一次性加载到内存
支持两种输出格式：OpenCV (numpy) 和 PIL Image
"""


class IconStore:
    """从 ZIP 文件加载所有图标到内存，线程安全读取"""

    def __init__(self, zip_path: str):
        self.zip_path = zip_path
        self._raw_bytes: dict[str, bytes] = {}  # filename -> raw PNG bytes
        self._cv_cache: dict[str, np.ndarray] = {}  # filename -> cv2 Mat (懒加载)
        self._pil_cache: dict[str, Image.Image] = {}  # filename -> PIL Image (懒加载)
        self._lock = threading.Lock()
        self._load_all()

    def _load_all(self):
        """启动时一次性从 ZIP 读取所有文件到内存"""
        if not os.path.exists(self.zip_path):
            raise FileNotFoundError(f"图标ZIP文件不存在: {self.zip_path}")

        with zipfile.ZipFile(self.zip_path, 'r') as zf:
            for name in zf.namelist():
                if name.lower().endswith('.png'):
                    # key 只取文件名，去掉可能的目录前缀
                    key = os.path.basename(name)
                    self._raw_bytes[key] = zf.read(name)

        print(f"[IconStore] 已从 {self.zip_path} 加载 {len(self._raw_bytes)} 个图标到内存")

    # ──────── OpenCV 格式输出（用于模板匹配）────────
    def get_cv(self, filename: str, flags: int = -1) -> np.ndarray | None:
        """
        获取 OpenCV 格式的图片 (BGR/BGRA numpy array)
        等价于原来的 MyOpenCv.cv_imread(path, -1)
        flags: -1=保持原样(含alpha), 1=彩色, 0=灰度
        """
        # 懒加载 + 缓存
        if filename not in self._raw_bytes:
            # 尝试补 .png 后缀
            alt = filename if filename.endswith('.png') else f"{filename}.png"
            if alt in self._raw_bytes:
                filename = alt
            else:
                return None

        if flags == -1:
            return cv2.imdecode(
                np.frombuffer(self._raw_bytes[filename], np.uint8), cv2.IMREAD_UNCHANGED
            )
        elif flags == 0:
            return cv2.imdecode(
                np.frombuffer(self._raw_bytes[filename], np.uint8), cv2.IMREAD_GRAYSCALE
            )
        else:
            return cv2.imdecode(
                np.frombuffer(self._raw_bytes[filename], np.uint8), cv2.IMREAD_COLOR
            )

    # ──────── PIL Image 格式输出（用于 GUI 显示）────────
    def get_pil(self, filename: str) -> Image.Image | None:
        """
        获取 PIL Image 对象
        等价于原来的 Image.open(path)
        """
        if filename not in self._raw_bytes:
            alt = filename if filename.endswith('.png') else f"{filename}.png"
            if alt in self._raw_bytes:
                filename = alt
            else:
                return None
        return Image.open(BytesIO(self._raw_bytes[filename]))

    # ──────── 工具方法 ────────
    def exists(self, filename: str) -> bool:
        """检查图标是否存在"""
        if filename in self._raw_bytes:
            return True
        alt = filename if filename.endswith('.png') else f"{filename}.png"
        return alt in self._raw_bytes

    def list_all(self) -> list[str]:
        """列出所有图标文件名"""
        return list(self._raw_bytes.keys())

    @property
    def count(self) -> int:
        return len(self._raw_bytes)


"""SQLite 懒加载版图标管理器"""


class IconStoreSQLite:
    def __init__(self, db_path: str):
        self.db_path = db_path

        self.conn = self._get_conn()

    def _get_conn(self):
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        return self.conn

    def get_cv(self, filename: str, flags: int = -1) -> np.ndarray | None:
        if not filename.endswith('.png'):
            filename += '.png'

        row = self.conn.execute("SELECT data FROM icons WHERE name = ?", (filename,)).fetchone()
        if row is None:
            return None
        buf = np.frombuffer(row[0], np.uint8)
        if flags == -1:
            return cv2.imdecode(buf, cv2.IMREAD_UNCHANGED)
        elif flags == 0:
            return cv2.imdecode(buf, cv2.IMREAD_GRAYSCALE)
        else:
            return cv2.imdecode(buf, cv2.IMREAD_COLOR)

    def get_pil(self, filename: str) -> Image.Image | None:
        if not filename.endswith('.png'):
            filename += '.png'
        conn = self._get_conn()
        row = conn.execute("SELECT data FROM icons WHERE name = ?", (filename,)).fetchone()
        if row is None:
            return None
        return Image.open(BytesIO(row[0]))

    def exists(self, filename: str) -> bool:
        if not filename.endswith('.png'):
            filename += '.png'
        conn = self._get_conn()
        row = conn.execute("SELECT 1 FROM icons WHERE name = ?", (filename,)).fetchone()
        return row is not None


if __name__ == "__main__":
    pack_db()
