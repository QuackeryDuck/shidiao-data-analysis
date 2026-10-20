"""通用工具函数：文本清洗、Markdown 表格、数值格式化。"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Iterable, Sequence


def read_text(path: str | Path) -> str:
    """以 UTF-8 读取文本，兼容带 BOM 的文件。"""
    return Path(path).read_text(encoding="utf-8-sig")


def write_text(path: str | Path, content: str) -> None:
    """以 UTF-8 写入文本，自动创建父目录。"""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8", newline="\n")


def norm_key(text: str) -> str:
    """把标题/键名归一化，便于匹配中英文别名。"""
    text = (text or "").strip().lower()
    text = re.sub(r"[\s\-_/（）()【】\[\]：:]+", "", text)
    return text


def clean_inline(text: str) -> str:
    """清理单行文本中的多余空白。"""
    return re.sub(r"[ \t　]+", " ", (text or "").strip())


def strip_bullet(text: str) -> str:
    """去掉列表符号、序号和复选框标记。"""
    text = clean_inline(text)
    text = re.sub(r"^(?:[-*+•·]|\d+[.、)）]|[（(]\d+[）)]|\[[ xX]\])\s*", "", text)
    return text.strip()


def split_inline_list(value: str) -> list[str]:
    """解析行内列表：[a, b, c] 或 a、b、c。"""
    value = (value or "").strip()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    if not value:
        return []
    parts = re.split(r"[,，、;；|]", value)
    return [p.strip().strip("\"'") for p in parts if p.strip()]


def as_float(value, default: float | None = None) -> float | None:
    if value is None or value == "":
        return default
    try:
        return float(str(value).strip().replace("%", "").replace("％", ""))
    except (TypeError, ValueError):
        return default


def as_int(value, default: int | None = None) -> int | None:
    f = as_float(value)
    if f is None:
        return default
    return int(round(f))


def normalize_rate(value, default: float = 0.95) -> float:
    """把 95、0.95、95% 统一为 0—1 之间的小数。"""
    f = as_float(value, default)
    if f is None:
        return default
    if f > 1:
        f = f / 100.0
    return min(max(f, 0.01), 0.999)


def normalize_error(value, default: float = 0.05) -> float:
    f = as_float(value, default)
    if f is None:
        return default
    if f > 1:
        f = f / 100.0
    return min(max(f, 0.001), 0.5)


def normalize_confidence(value, default: float = 0.95) -> float:
    f = as_float(value, default)
    if f is None:
        return default
    if f > 1:
        f = f / 100.0
    return f


def fmt_num(x: float | int | None, digits: int = 2) -> str:
    if x is None:
        return "—"
    if isinstance(x, int):
        return f"{x:,}"
    if abs(x - round(x)) < 1e-9:
        return f"{int(round(x)):,}"
    return f"{x:,.{digits}f}"


def fmt_pct(x: float | None, digits: int = 1) -> str:
    if x is None:
        return "—"
    return f"{x * 100:.{digits}f}%"


def fmt_prob(x: float | None, digits: int = 2) -> str:
    if x is None:
        return "—"
    return f"{x:.{digits}f}"


def md_escape(text: object) -> str:
    """转义 Markdown 表格中的竖线与换行。"""
    s = str(text if text is not None else "")
    s = s.replace("\r", " ").replace("\n", "<br>")
    s = s.replace("|", "\\|")
    return s.strip()


def md_table(headers: Sequence[str], rows: Iterable[Sequence[object]], align: str | None = None) -> str:
    """生成标准 Markdown 表格。"""
    headers = [md_escape(h) for h in headers]
    lines = ["| " + " | ".join(headers) + " |"]
    if align:
        marks = {"l": ":---", "c": ":---:", "r": "---:"}
        lines.append("| " + " | ".join(marks.get(a, "---") for a in align) + " |")
    else:
        lines.append("| " + " | ".join(["---"] * len(headers)) + " |")
    for row in rows:
        cells = []
        for cell in row:
            if isinstance(cell, (list, tuple)):
                cell = "；".join(str(c) for c in cell)
            cells.append(md_escape(cell))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def bullets(items: Iterable[str], symbol: str = "-") -> str:
    out = []
    for item in items:
        item = clean_inline(item)
        if item:
            out.append(f"{symbol} {item}")
    return "\n".join(out)


def numbered(items: Iterable[str]) -> str:
    out = []
    for i, item in enumerate(items, 1):
        item = clean_inline(item)
        if item:
            out.append(f"{i}. {item}")
    return "\n".join(out)


def unique_keep_order(items: Iterable[str]) -> list[str]:
    seen = set()
    out = []
    for item in items:
        key = norm_key(item)
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def largest_remainder(total: int, weights: Sequence[float]) -> list[int]:
    """按权重分配整数，使用最大余数法保证总和等于 total。"""
    if not weights or total <= 0:
        return [0 for _ in weights]
    s = sum(weights)
    if s <= 0:
        weights = [1.0 for _ in weights]
        s = float(len(weights))
    raw = [total * w / s for w in weights]
    base = [int(math.floor(x)) for x in raw]
    remain = total - sum(base)
    order = sorted(range(len(raw)), key=lambda i: raw[i] - base[i], reverse=True)
    for i in order[:remain]:
        base[i] += 1
    return base


def safe_filename(name: str, fallback: str = "data_requirement") -> str:
    name = re.sub(r'[\\/:*?"<>|\r\n]+', "-", name or "").strip(" .-")
    return name or fallback
