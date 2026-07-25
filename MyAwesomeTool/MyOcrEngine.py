"""单独调用 MinerU 内置 OCR (PyTorch PP-OCRv5) 对一张图片做识别。

针对游戏角色名截图（小尺寸、艺术字、可能含较多空白）做了如下优化：
1. 构造引擎时直接降低 DB 检测器阈值（det_db_thresh / det_db_box_thresh）
2. 扩大 unclip_ratio 让检测框更完整
3. 多尺度重试：原图 → 1.5× → 2× → 兜底 rec-only
4. is_garbled 启发式过滤明显的乱码候选

模型权重首次运行自动下载到 MinerU 默认缓存目录。
"""
from __future__ import annotations

import argparse
import copy
import os
import re
from typing import List, Optional, Sequence, Tuple

import cv2
import numpy as np
from loguru import logger

from mineru.model.ocr.paddleocr2pytorch.pytorch_paddle import PytorchPaddleOCR
import mineru.model.ocr.paddleocr2pytorch.pytorch_paddle as pp
from mineru.utils.ocr_utils import (
    get_rotate_crop_image,
    merge_det_boxes,
    preprocess_image,
    sorted_boxes,
)

# 关闭 tf，防止 DLL 冲突（与 convert_many_pdf_to_md.py 同理）
os.environ["USE_TORCH"] = "1"
os.environ["USE_TF"] = "0"

# 让"下载根目录"函数直接返回本地路径
pp.auto_download_and_get_model_root_path = lambda rel, repo_mode='pipeline': os.path.abspath("./PaddleOcrModel")

# 类型别名
TextScore = Tuple[np.ndarray, str, float]
LeveledCandidate = Tuple[int, np.ndarray, str, float]


class MyPytorchPaddleOCR:
    """针对游戏角色名等小尺寸艺术字截图优化的 OCR 封装。

    通过降低 DB 检测器阈值 + 多尺度重试，缓解默认配置下：
      - det=True 因阈值过严而返回 None
      - det=False 因整图被压扁而输出乱码

    Parameters
    ----------
    lang : str
        PaddleOCR 语言，默认 "ch_lite"（CPU 友好）。
    scales : Sequence[float]
        多尺度重试的缩放因子序列，按顺序尝试。
    det_db_thresh : float
        DB score map 二值化阈值，PaddleOCR 默认 0.3，本类默认降至 0.15。
    det_db_box_thresh : float
        单 box 得分过滤阈值，PaddleOCR 默认 0.6，本类默认降至 0.3。
    det_db_unclip_ratio : float
        DB 框扩张系数，PaddleOCR 默认 1.5，本类默认升至 2.0。
    drop_score : float
        rec 结果置信度过滤阈值，PaddleOCR 默认 0.5，本类默认降至 0.3。
    garbled_min_valid_ratio : float
        is_garbled 的判定阈值：可识别字符占比低于此值视为乱码。
    """

    _GARBLED_VALID_RE = re.compile(r'[\u4e00-\u9fa5A-Za-z0-9·\-\.\s]')

    def __init__(
            self,
            lang: str = "ch_lite",
            scales: Sequence[float] = (1.0, 1.5, 2.0),
            det_db_thresh: float = 0.15,
            det_db_box_thresh: float = 0.3,
            det_db_unclip_ratio: float = 2.0,
            drop_score: float = 0.3,
            garbled_min_valid_ratio: float = 0.6,
    ) -> None:
        self.scales: Tuple[float, ...] = tuple(scales)
        self.garbled_min_valid_ratio: float = garbled_min_valid_ratio
        self.engine: PytorchPaddleOCR = PytorchPaddleOCR(
            lang=lang,
            det_db_thresh=det_db_thresh,
            det_db_box_thresh=det_db_box_thresh,
            det_db_unclip_ratio=det_db_unclip_ratio,
            drop_score=drop_score,
        )

    def det_then_rec(self, img: np.ndarray) -> List[TextScore]:
        """单尺度 det → 裁剪 → rec，返回已按 drop_score 过滤的 (text, score) 列表。

        镜像 pytorch_paddle.py:158-199 的 __call__ 流程。
        """
        img = preprocess_image(img)
        ori_im = img.copy()

        dt_boxes, _ = self.engine.text_detector(img)
        if dt_boxes is None or len(dt_boxes) == 0:
            return []

        dt_boxes = sorted_boxes(dt_boxes)
        if getattr(self.engine, "enable_merge_det_boxes", True):
            dt_boxes = merge_det_boxes(dt_boxes)
        if len(dt_boxes) == 0:
            return []

        crops: List[np.ndarray] = [
            get_rotate_crop_image(ori_im, copy.deepcopy(box)) for box in dt_boxes
        ]
        if not crops:
            return []

        rec_res, _ = self.engine.text_recognizer(crops)
        return [
            (dt_boxes[i], text, float(score))
            for i, (text, score) in enumerate(rec_res)
            if score >= self.engine.drop_score
        ]

    def is_garbled(self, text: str) -> bool:
        """可识别字符占比 < garbled_min_valid_ratio 视为乱码。"""
        if not text:
            return True
        valid = self._GARBLED_VALID_RE.findall(text)
        return len(valid) / len(text) < self.garbled_min_valid_ratio

    @staticmethod
    def _resize(img: np.ndarray, scale: float) -> np.ndarray:
        """按 scale 等比上采样；scale == 1.0 时原样返回（避免无谓拷贝）。"""
        if scale == 1.0:
            return img
        h, w = img.shape[:2]
        return cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_CUBIC)

    def ocr_with_retry(self, img: np.ndarray) -> Tuple[int, List[LeveledCandidate]]:
        """多尺度重试 det_then_rec，必要时启用 rec-only 兜底。

        Returns
        -------
        hit_level : int
            最终选中的候选所在的 level；-1 表示完全无候选。
            0..len(scales)-1 对应多尺度 det_then_rec；
            len(scales) 对应 rec-only 兜底。
        candidates : List[LeveledCandidate]
            所有 (level, text, score) 候选，未去重。
        """
        candidates: List[LeveledCandidate] = []

        for level, scale in enumerate(self.scales):
            scaled = self._resize(img, scale)
            try:
                results = self.det_then_rec(scaled)
            except Exception as e:
                logger.warning(f"det_then_rec 在 L{level}(scale={scale}) 失败: {e}")
                results = []
            for box, text, score in results:
                candidates.append((level, box, text, score))

            # 任意尺度拿到非乱码结果就停，避免无谓的更大尺度推理
            if any(not self.is_garbled(t) for _, _, t, _ in candidates):
                return level, candidates

        # 兜底：原图 det=False, rec=True
        try:
            rec_only = self.engine.ocr(img, det=False, rec=True)
            if rec_only and rec_only[0]:
                fallback_level = len(self.scales)
                for box, text, score in rec_only[0]:
                    candidates.append((fallback_level, box, text, float(score)))
        except Exception as e:
            logger.warning(f"rec-only 兜底失败: {e}")

        hit_level = max((c[0] for c in candidates), default=-1)
        return hit_level, candidates

    def ocr_image(
            self,
            img: np.ndarray,
    ) -> Tuple[int, Optional[LeveledCandidate], List[LeveledCandidate]]:
        """读取图片并跑 OCR。

        Returns
        -------
        hit_level : int
            见 ocr_with_retry。
        best : Optional[LeveledCandidate]
            最终采纳的 (level, text, score)；无候选时为 None。
        candidates : List[LeveledCandidate]
            全部候选，供调试观察。
        """

        hit_level, candidates = self.ocr_with_retry(img)

        non_garbled = [c for c in candidates if not self.is_garbled(c[2])]
        pool = non_garbled if non_garbled else candidates
        best = max(pool, key=lambda x: x[2]) if pool else None
        return hit_level, best, candidates

    def ocr(self, img: np.ndarray, *args, **kwargs) -> List[LeveledCandidate]:
        hit_level, best, candidates = self.ocr_image(img)
        lvl, box, text, score = best
        return candidates


def main() -> None:
    parser = argparse.ArgumentParser(description="MinerU OCR 单图识别（针对游戏角色名优化）")
    parser.add_argument("image", nargs="?", default="test.png", help="图片路径，默认 test.png")
    parser.add_argument("--lang", default="ch_lite", help="语言，默认 ch_lite")
    args = parser.parse_args()

    ocr = MyPytorchPaddleOCR(lang=args.lang)

    hit_level, best, candidates = ocr.ocr_image(cv2.imread(args.image))

    print(f"== 候选列表（共 {len(candidates)} 条）==")
    for lvl, box, text, score in candidates:
        garbled_tag = " [乱码]" if ocr.is_garbled(text) else ""
        print(f"  L{lvl} {box} [{score:.3f}] {text}{garbled_tag}")
    print(f"== 命中等级: L{hit_level} ==")
    if best:
        lvl, box, text, score = best
        print(f"== 最终结果:{box} [{score:.3f}] {text} ==")
    else:
        print("== 未识别到任何文本 ==")


if __name__ == "__main__":
    main()
