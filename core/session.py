"""
core/session.py — 中间状态读写，支持断点续提

wip 文件保存在与输入文件相同目录，命名为 {stem}_wip.json
格式：
{
  "source_file": "xxx.docx",
  "total_images": 1000,
  "stage1_done": true,
  "candidates": [3, 7, 12, ...],
  "processed": {
    "3": {"match": true, "url": "...", ...},
    "12": {"match": false}
  }
}
"""
import json
import threading
from pathlib import Path


class Session:
    def __init__(self, source_file: str):
        src = Path(source_file)
        self._wip_path = src.parent / f"{src.stem}_wip.json"
        self._lock = threading.Lock()
        self._data: dict = {}

    @property
    def wip_path(self) -> Path:
        return self._wip_path

    def exists(self) -> bool:
        return self._wip_path.exists()

    def load(self) -> dict:
        """加载已有 wip 文件，返回 data dict。"""
        with self._lock:
            self._data = json.loads(self._wip_path.read_text(encoding="utf-8"))
            return dict(self._data)

    def init(self, source_file: str, total_images: int):
        """初始化新的 wip（首次运行）。"""
        with self._lock:
            self._data = {
                "source_file": source_file,
                "total_images": total_images,
                "stage1_done": False,
                "candidates": [],
                "processed": {},
            }
            self._save()

    def set_candidates(self, candidates: list[int]):
        with self._lock:
            self._data["candidates"] = candidates
            self._data["stage1_done"] = True
            self._save()

    def save_result(self, img_index: int, result: dict):
        """Stage2 每处理一张图立即调用，实时写盘。"""
        with self._lock:
            if "processed" not in self._data:
                self._data["processed"] = {}
            self._data["processed"][str(img_index)] = result
            self._save()

    def get_processed(self) -> dict[str, dict]:
        return dict(self._data.get("processed", {}))

    def get_candidates(self) -> list[int]:
        return list(self._data.get("candidates", []))

    def is_stage1_done(self) -> bool:
        return bool(self._data.get("stage1_done", False))

    def total_images(self) -> int:
        return int(self._data.get("total_images", 0))

    def count_processed(self) -> int:
        return len(self._data.get("processed", {}))

    def delete(self):
        """提取完成后删除 wip 文件。"""
        if self._wip_path.exists():
            self._wip_path.unlink()

    def _save(self):
        self._wip_path.write_text(
            json.dumps(self._data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
