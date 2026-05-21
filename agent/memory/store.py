"""
memory/store.py — 记忆文件 CRUD，Memory.md 索引，keywords.md 反向索引维护。
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

# ── 路径常量（以 store.py 位置推导项目根目录）────────────────────────────────
_PROJECT_ROOT   = Path(__file__).parent.parent.parent
MEMORY_DIR      = _PROJECT_ROOT / "memory"
EVENTS_DIR      = MEMORY_DIR / "events"
RECOGNITIONS_DIR = MEMORY_DIR / "recognitions"
MEMORY_INDEX    = MEMORY_DIR / "Memory.md"
KEYWORDS_FILE   = MEMORY_DIR / "keywords.md"
PURPOSE_FILE    = MEMORY_DIR / "purpose.md"


# ── 内部工具 ──────────────────────────────────────────────────────────────────

def _next_id(directory: Path, prefix: str) -> str:
    """返回下一个可用的编号，如 event_003。"""
    nums = []
    for f in directory.glob(f"{prefix}_*.md"):
        try:
            nums.append(int(f.stem.split("_")[-1]))
        except ValueError:
            pass
    return f"{prefix}_{(max(nums) + 1 if nums else 1):03d}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_keywords_file() -> dict[str, tuple[int, list[str]]]:
    """解析 keywords.md，返回 {keyword: (count, [files])}。"""
    result: dict[str, tuple[int, list[str]]] = {}
    if not KEYWORDS_FILE.exists():
        return result
    for line in KEYWORDS_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^(.+?):\s*(\d+),\s*\[(.*)\]\s*$", line)
        if m:
            kw    = m.group(1).strip()
            count = int(m.group(2))
            files = [f.strip() for f in m.group(3).split(",") if f.strip()]
            result[kw] = (count, files)
    return result


def _write_keywords_file(data: dict[str, tuple[int, list[str]]]) -> None:
    lines = [
        "# Keywords Index\n",
        "# 格式：keyword: count, [file1.md, file2.md, ...]\n",
    ]
    for kw, (count, files) in data.items():
        lines.append(f"{kw}: {count}, [{', '.join(files)}]\n")
    KEYWORDS_FILE.write_text("".join(lines), encoding="utf-8")


# ── 公开 API ──────────────────────────────────────────────────────────────────

def create_event(
    summary: str,
    what: str,
    how: str,
    why: str,
    importance: int,
    keywords: list[str],
) -> Path:
    """生成 events/event_NNN.md，同步更新 Memory.md 和 keywords.md。"""
    file_id  = _next_id(EVENTS_DIR, "event")
    filepath = EVENTS_DIR / f"{file_id}.md"
    now      = _now_iso()
    kw_str   = ", ".join(keywords)

    filepath.write_text(
        f"---\n"
        f"Description: {summary}\n"
        f"Time: {now}\n"
        f"Keywords: [{kw_str}]\n"
        f"Type: event\n"
        f"Importance: {importance}\n"
        f"---\n\n"
        f"## What\n{what}\n\n"
        f"## How\n{how}\n\n"
        f"## Why\n{why}\n",
        encoding="utf-8",
    )
    update_memory_index(filepath, summary, now, importance)
    update_keywords(keywords, filepath)
    return filepath


def create_recognition(
    summary: str,
    content: str,
    importance: int,
    keywords: list[str],
) -> Path:
    """生成 recognitions/recog_NNN.md，同步更新 Memory.md 和 keywords.md。"""
    file_id  = _next_id(RECOGNITIONS_DIR, "recog")
    filepath = RECOGNITIONS_DIR / f"{file_id}.md"
    now      = _now_iso()
    kw_str   = ", ".join(keywords)

    filepath.write_text(
        f"---\n"
        f"Description: {summary}\n"
        f"Time: {now}\n"
        f"Keywords: [{kw_str}]\n"
        f"Type: recognition\n"
        f"Importance: {importance}\n"
        f"---\n\n"
        f"{content}\n",
        encoding="utf-8",
    )
    update_memory_index(filepath, summary, now, importance)
    update_keywords(keywords, filepath)
    return filepath


def update_memory_index(
    filepath: Path,
    description: str,
    time: str,
    importance: int,
) -> None:
    """向 Memory.md 追加一行索引记录。"""
    rel  = filepath.relative_to(MEMORY_DIR)
    name = filepath.stem
    with MEMORY_INDEX.open("a", encoding="utf-8") as f:
        f.write(f"- [{name}]({rel}) — {description} | {time} | imp={importance}\n")


def update_keywords(keywords: list[str], filepath: Path) -> None:
    """更新 keywords.md：计数 +1，将文件加入反向索引（去重）。"""
    rel  = str(filepath.relative_to(MEMORY_DIR))
    data = _parse_keywords_file()

    for kw in keywords:
        if kw in data:
            count, files = data[kw]
            if rel not in files:
                files.append(rel)
            data[kw] = (count + 1, files)
        else:
            data[kw] = (1, [rel])

    _write_keywords_file(data)


def get_keywords_index() -> dict[str, list[str]]:
    """返回关键词反向索引 {keyword: [filepath, ...]}，供 retrieve.py 使用。"""
    data = _parse_keywords_file()
    return {kw: files for kw, (count, files) in data.items()}


def read_purpose() -> str:
    """返回 purpose.md 全文。"""
    return PURPOSE_FILE.read_text(encoding="utf-8").strip()


def load_memory_index() -> str:
    """返回 Memory.md 全文（用于注入 system prompt）。"""
    if not MEMORY_INDEX.exists():
        return ""
    return MEMORY_INDEX.read_text(encoding="utf-8")


def load_files(filepaths: list[Path | str]) -> list[str]:
    """读取指定记忆文件列表，返回各文件全文。路径可为绝对或相对于 memory/。"""
    results = []
    for fp in filepaths:
        fp = Path(fp) if not isinstance(fp, Path) else fp
        if not fp.is_absolute():
            fp = MEMORY_DIR / fp
        if fp.exists():
            results.append(fp.read_text(encoding="utf-8"))
    return results


# ── 清除函数 ──────────────────────────────────────────────────────────────────

def clear_events() -> int:
    """删除所有 event 记忆文件，返回删除数量。"""
    count = 0
    for f in EVENTS_DIR.glob("*.md"):
        f.unlink()
        count += 1
    return count


def clear_recognitions() -> int:
    """删除所有 recognition 记忆文件，返回删除数量。"""
    count = 0
    for f in RECOGNITIONS_DIR.glob("*.md"):
        f.unlink()
        count += 1
    return count


def clear_auxiliary() -> None:
    """重置 Memory.md 索引和 keywords.md 反向索引。"""
    MEMORY_INDEX.write_text("# Memory Index\n", encoding="utf-8")
    KEYWORDS_FILE.write_text(
        "# Keywords Index\n# 格式：keyword: count, [file1.md, file2.md, ...]\n",
        encoding="utf-8",
    )


def reset_purpose(content: str) -> None:
    """覆盖 purpose.md 内容。"""
    PURPOSE_FILE.write_text(content, encoding="utf-8")
