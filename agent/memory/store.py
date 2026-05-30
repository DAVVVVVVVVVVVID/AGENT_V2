"""
memory/store.py — 记忆文件 CRUD，Memory.md 索引，keywords.md 反向索引维护。
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

# ── 路径变量（由 init() 设置）────────────────────────────────────────────────
_MEMORY_DIR:          Path | None = None
_EVENTS_DIR:          Path | None = None
_RECOGNITIONS_DIR:    Path | None = None
_CONSOLIDATED_DIR:    Path | None = None
_MEMORY_INDEX:        Path | None = None
_KEYWORDS_FILE:       Path | None = None
_PURPOSE_FILE:        Path | None = None
_DREAM_STATE_FILE:    Path | None = None


def init(profile_dir: str | Path) -> None:
    """根据 profile 文件夹路径初始化所有记忆路径，并确保目录存在。"""
    global _MEMORY_DIR, _EVENTS_DIR, _RECOGNITIONS_DIR, _CONSOLIDATED_DIR
    global _MEMORY_INDEX, _KEYWORDS_FILE, _PURPOSE_FILE, _DREAM_STATE_FILE

    base = Path(profile_dir) / "memory"
    _MEMORY_DIR        = base
    _EVENTS_DIR        = base / "events"
    _RECOGNITIONS_DIR  = base / "recognitions"
    _CONSOLIDATED_DIR  = base / "consolidated"
    _MEMORY_INDEX      = base / "Memory.md"
    _KEYWORDS_FILE     = base / "keywords.md"
    _PURPOSE_FILE      = base / "purpose.md"
    _DREAM_STATE_FILE  = base / "dream_state.md"

    _EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    _RECOGNITIONS_DIR.mkdir(parents=True, exist_ok=True)
    _CONSOLIDATED_DIR.mkdir(parents=True, exist_ok=True)

    if not _MEMORY_INDEX.exists():
        _MEMORY_INDEX.write_text("# Memory Index\n", encoding="utf-8")
    if not _KEYWORDS_FILE.exists():
        _KEYWORDS_FILE.write_text(
            "# Keywords Index\n# 格式：keyword: count, [file1.md, file2.md, ...]\n",
            encoding="utf-8",
        )
    if not _PURPOSE_FILE.exists():
        _PURPOSE_FILE.write_text("", encoding="utf-8")


def _require_init() -> None:
    if _MEMORY_DIR is None:
        raise RuntimeError("store 未初始化，请先调用 store.init(profile_dir)")


def get_memory_dir() -> Path:
    _require_init()
    return _MEMORY_DIR  # type: ignore[return-value]


def get_events_dir() -> Path:
    _require_init()
    return _EVENTS_DIR  # type: ignore[return-value]


def get_recognitions_dir() -> Path:
    _require_init()
    return _RECOGNITIONS_DIR  # type: ignore[return-value]


def get_keywords_file() -> Path:
    _require_init()
    return _KEYWORDS_FILE  # type: ignore[return-value]


def get_memory_index() -> Path:
    _require_init()
    return _MEMORY_INDEX  # type: ignore[return-value]


def get_consolidated_dir() -> Path:
    _require_init()
    return _CONSOLIDATED_DIR  # type: ignore[return-value]


# ── 内部工具 ──────────────────────────────────────────────────────────────────

def _next_id(directory: Path, prefix: str) -> str:
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
    result: dict[str, tuple[int, list[str]]] = {}
    if not _KEYWORDS_FILE.exists():  # type: ignore[union-attr]
        return result
    for line in _KEYWORDS_FILE.read_text(encoding="utf-8").splitlines():  # type: ignore[union-attr]
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
    _KEYWORDS_FILE.write_text("".join(lines), encoding="utf-8")  # type: ignore[union-attr]


# ── 公开 API ──────────────────────────────────────────────────────────────────

def create_event(
    summary: str,
    what: str,
    how: str,
    why: str,
    importance: int,
    keywords: list[str],
) -> Path:
    _require_init()
    file_id  = _next_id(_EVENTS_DIR, "event")  # type: ignore[arg-type]
    filepath = _EVENTS_DIR / f"{file_id}.md"  # type: ignore[operator]
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
    trigger: str = "",
    sources: list[str] | None = None,
) -> Path:
    _require_init()
    file_id  = _next_id(_RECOGNITIONS_DIR, "recog")  # type: ignore[arg-type]
    filepath = _RECOGNITIONS_DIR / f"{file_id}.md"  # type: ignore[operator]
    now      = _now_iso()
    kw_str   = ", ".join(keywords)
    trigger_line = f"Trigger: {trigger}\n" if trigger else ""
    sources_line = f"Sources: [{', '.join(sources)}]\n" if sources else ""

    filepath.write_text(
        f"---\n"
        f"Description: {summary}\n"
        f"Time: {now}\n"
        f"Keywords: [{kw_str}]\n"
        f"Type: recognition\n"
        f"Importance: {importance}\n"
        f"{trigger_line}"
        f"{sources_line}"
        f"---\n\n"
        f"{content}\n",
        encoding="utf-8",
    )
    update_memory_index(filepath, summary, now, importance)
    update_keywords(keywords, filepath)
    return filepath


def delete_memory_file(path: str) -> bool:
    """
    删除 events 或 recognitions 下的记忆文件，同时移除 Memory.md 索引行和 keywords.md 引用。
    path 为相对于 memory/ 的路径，例如 events/event_001.md。
    返回 True 表示删除成功，False 表示文件不存在。
    """
    _require_init()
    fp = (_MEMORY_DIR / path).resolve()  # type: ignore[operator]
    events_dir       = _EVENTS_DIR.resolve()       # type: ignore[union-attr]
    recognitions_dir = _RECOGNITIONS_DIR.resolve()  # type: ignore[union-attr]
    # 只允许删除 events/ 或 recognitions/ 下的 .md 文件
    if not (str(fp).startswith(str(events_dir)) or str(fp).startswith(str(recognitions_dir))):
        raise ValueError(f"不允许删除该路径：{path}")
    if not fp.exists():
        return False
    fp.unlink()
    _remove_index_entry(path)
    _remove_keywords_entry(path)
    return True


def _remove_index_entry(rel_path: str) -> None:
    """从 Memory.md 中移除包含指定相对路径的行。"""
    _require_init()
    if not _MEMORY_INDEX.exists():  # type: ignore[union-attr]
        return
    needle = rel_path.replace("\\", "/")
    lines = _MEMORY_INDEX.read_text(encoding="utf-8").splitlines(keepends=True)  # type: ignore[union-attr]
    new_lines = [l for l in lines if f"({needle})" not in l]
    _MEMORY_INDEX.write_text("".join(new_lines), encoding="utf-8")  # type: ignore[union-attr]


def _remove_keywords_entry(rel_path: str) -> None:
    """从 keywords.md 中移除所有对 rel_path 的引用；若某关键词文件列表为空则删除该条目。"""
    _require_init()
    data = _parse_keywords_file()
    needle = rel_path.replace("\\", "/")
    updated: dict[str, tuple[int, list[str]]] = {}
    for kw, (count, files) in data.items():
        new_files = [f for f in files if f.replace("\\", "/") != needle]
        if new_files:
            updated[kw] = (count, new_files)
        # 文件列表为空则直接丢弃该关键词条目
    _write_keywords_file(updated)


def update_memory_index(filepath: Path, description: str, time: str, importance: int) -> None:
    _require_init()
    rel  = filepath.relative_to(_MEMORY_DIR)  # type: ignore[arg-type]
    name = filepath.stem
    with _MEMORY_INDEX.open("a", encoding="utf-8") as f:  # type: ignore[union-attr]
        f.write(f"- [{name}]({rel}) — {description} | {time} | imp={importance}\n")


def update_keywords(keywords: list[str], filepath: Path) -> None:
    _require_init()
    rel  = str(filepath.relative_to(_MEMORY_DIR))  # type: ignore[arg-type]
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
    _require_init()
    data = _parse_keywords_file()
    return {kw: files for kw, (count, files) in data.items()}


def read_purpose() -> str:
    _require_init()
    return _PURPOSE_FILE.read_text(encoding="utf-8").strip()  # type: ignore[union-attr]


def load_memory_index() -> str:
    _require_init()
    if not _MEMORY_INDEX.exists():  # type: ignore[union-attr]
        return ""
    return _MEMORY_INDEX.read_text(encoding="utf-8")  # type: ignore[union-attr]


def load_files(filepaths: list[Path | str]) -> list[str]:
    _require_init()
    results = []
    for fp in filepaths:
        fp = Path(fp) if not isinstance(fp, Path) else fp
        if not fp.is_absolute():
            fp = _MEMORY_DIR / fp  # type: ignore[operator]
        if fp.exists():
            results.append(fp.read_text(encoding="utf-8"))
    return results


# ── Dream 相关函数 ────────────────────────────────────────────────────────────

def create_consolidated_memory(
    description: str,
    content: str,
    importance: int,
    keywords: list[str],
    sources: list[str],
) -> Path:
    """新建一条整合记忆文件，sources 为相对于 memory/ 目录的路径列表。"""
    _require_init()
    file_id  = _next_id(_CONSOLIDATED_DIR, "consolidated")  # type: ignore[arg-type]
    filepath = _CONSOLIDATED_DIR / f"{file_id}.md"  # type: ignore[operator]
    now      = _now_iso()
    kw_str   = ", ".join(keywords)
    src_str  = ", ".join(sources)

    filepath.write_text(
        f"---\n"
        f"Description: {description}\n"
        f"Time: {now}\n"
        f"Importance: {importance}\n"
        f"Keywords: [{kw_str}]\n"
        f"Type: consolidated\n"
        f"Sources: [{src_str}]\n"
        f"---\n\n"
        f"## 内容\n\n{content}\n",
        encoding="utf-8",
    )
    update_memory_index(filepath, description, now, importance)
    update_keywords(keywords, filepath)
    return filepath


def update_consolidated_memory(
    filepath: Path | str,
    new_sources: list[str],
    new_content: str,
    added_importance: int,
    extra_keywords: list[str] | None = None,
) -> None:
    """追加来源并重写整合记忆内容，Importance 增加 added_importance。"""
    _require_init()
    fp = Path(filepath) if not isinstance(filepath, Path) else filepath
    if not fp.is_absolute():
        fp = _MEMORY_DIR / fp  # type: ignore[operator]

    text = fp.read_text(encoding="utf-8")

    # 解析现有 frontmatter
    fm_match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not fm_match:
        raise ValueError(f"无法解析 frontmatter：{fp}")
    fm_text = fm_match.group(1)

    # 更新 Importance
    imp_match = re.search(r"^Importance:\s*(\d+)", fm_text, re.MULTILINE)
    old_imp = int(imp_match.group(1)) if imp_match else 0
    new_imp = old_imp + added_importance
    fm_text = re.sub(r"^Importance:\s*\d+", f"Importance: {new_imp}", fm_text, flags=re.MULTILINE)

    # 追加 Sources
    src_match = re.search(r"^Sources:\s*\[(.*?)\]", fm_text, re.MULTILINE)
    if src_match:
        existing = [s.strip() for s in src_match.group(1).split(",") if s.strip()]
        merged   = existing + [s for s in new_sources if s not in existing]
        fm_text  = re.sub(
            r"^Sources:\s*\[.*?\]",
            f"Sources: [{', '.join(merged)}]",
            fm_text,
            flags=re.MULTILINE,
        )
    else:
        fm_text += f"\nSources: [{', '.join(new_sources)}]"

    # 重写文件
    fp.write_text(
        f"---\n{fm_text}\n---\n\n## 内容\n\n{new_content}\n",
        encoding="utf-8",
    )

    # 更新 Memory.md 中的 imp 值
    rel = str(fp.relative_to(_MEMORY_DIR))  # type: ignore[arg-type]
    if _MEMORY_INDEX.exists():  # type: ignore[union-attr]
        lines = _MEMORY_INDEX.read_text(encoding="utf-8").splitlines(keepends=True)  # type: ignore[union-attr]
        new_lines = []
        for line in lines:
            if f"({rel.replace(chr(92), '/')})" in line:
                line = re.sub(r"imp=\d+", f"imp={new_imp}", line)
            new_lines.append(line)
        _MEMORY_INDEX.write_text("".join(new_lines), encoding="utf-8")  # type: ignore[union-attr]

    if extra_keywords:
        update_keywords(extra_keywords, fp)


def hide_from_index(rel_paths: list[str]) -> None:
    """将指定相对路径的记忆从 Memory.md 和 keywords.md 中移除（文件本身保留在磁盘）。"""
    _require_init()
    for rel_path in rel_paths:
        _remove_index_entry(rel_path)
        _remove_keywords_entry(rel_path)


def write_last_dream_time(dt: datetime | None = None) -> None:
    """写入上次 dream 时间（默认当前时间）到 dream_state.md。"""
    _require_init()
    ts = (dt or datetime.now(timezone.utc)).isoformat(timespec="seconds")
    _DREAM_STATE_FILE.write_text(f"last_dream_time: {ts}\n", encoding="utf-8")  # type: ignore[union-attr]


def read_last_dream_time() -> datetime | None:
    """读取上次 dream 时间，文件不存在或解析失败则返回 None。"""
    _require_init()
    if not _DREAM_STATE_FILE.exists():  # type: ignore[union-attr]
        return None
    for line in _DREAM_STATE_FILE.read_text(encoding="utf-8").splitlines():  # type: ignore[union-attr]
        m = re.match(r"^last_dream_time:\s*(.+)$", line.strip())
        if m:
            try:
                return datetime.fromisoformat(m.group(1))
            except ValueError:
                return None
    return None


def get_new_memory_count(since: datetime) -> int:
    """统计 since 时间之后新增的记忆数（events + recognitions，不含 consolidated）。"""
    _require_init()
    count = 0
    for directory in (_EVENTS_DIR, _RECOGNITIONS_DIR):
        for fp in directory.glob("*.md"):  # type: ignore[union-attr]
            text = fp.read_text(encoding="utf-8")
            m = re.search(r"^Time:\s*(.+)$", text, re.MULTILINE)
            if m:
                try:
                    t = datetime.fromisoformat(m.group(1).strip())
                    if t > since:
                        count += 1
                except ValueError:
                    pass
    return count


def get_memories_since(since: datetime) -> list[Path]:
    """返回 since 时间之后新增的记忆文件路径列表（events + recognitions）。"""
    _require_init()
    result = []
    for directory in (_EVENTS_DIR, _RECOGNITIONS_DIR):
        for fp in sorted(directory.glob("*.md")):  # type: ignore[union-attr]
            text = fp.read_text(encoding="utf-8")
            m = re.search(r"^Time:\s*(.+)$", text, re.MULTILINE)
            if m:
                try:
                    t = datetime.fromisoformat(m.group(1).strip())
                    if t > since:
                        result.append(fp)
                except ValueError:
                    pass
    return result


# ── 清除函数 ──────────────────────────────────────────────────────────────────

def clear_events() -> int:
    _require_init()
    count = 0
    for f in _EVENTS_DIR.glob("*.md"):  # type: ignore[union-attr]
        f.unlink()
        count += 1
    return count


def clear_recognitions() -> int:
    _require_init()
    count = 0
    for f in _RECOGNITIONS_DIR.glob("*.md"):  # type: ignore[union-attr]
        f.unlink()
        count += 1
    return count


def clear_auxiliary() -> None:
    _require_init()
    _MEMORY_INDEX.write_text("# Memory Index\n", encoding="utf-8")  # type: ignore[union-attr]
    _KEYWORDS_FILE.write_text(  # type: ignore[union-attr]
        "# Keywords Index\n# 格式：keyword: count, [file1.md, file2.md, ...]\n",
        encoding="utf-8",
    )


def reset_purpose(content: str) -> None:
    _require_init()
    _PURPOSE_FILE.write_text(content, encoding="utf-8")  # type: ignore[union-attr]


def save_plan_batch(plans: list[str]) -> None:
    """将当前 Plan Batch 写入 current_plans.md，使用状态标记格式。"""
    _require_init()
    now = _now_iso()
    lines = ["# Current Plan Batch\n", f"生成时间: {now}\n\n"]
    for plan in plans:
        lines.append(f"- [ ] {plan}\n")
    (_MEMORY_DIR / "current_plans.md").write_text("".join(lines), encoding="utf-8")  # type: ignore[operator]


def read_plan_batch() -> str:
    """返回 current_plans.md 全文，文件不存在时返回空字符串。"""
    _require_init()
    fp = _MEMORY_DIR / "current_plans.md"  # type: ignore[operator]
    return fp.read_text(encoding="utf-8") if fp.exists() else ""  # type: ignore[union-attr]


def read_plan_states() -> list[dict]:
    """解析 current_plans.md，返回 [{"status": "todo"|"running"|"done"|"interrupted", "text": str}, ...]"""
    _require_init()
    fp = _MEMORY_DIR / "current_plans.md"  # type: ignore[operator]
    if not fp.exists():  # type: ignore[union-attr]
        return []
    result = []
    for line in fp.read_text(encoding="utf-8").splitlines():  # type: ignore[union-attr]
        m = re.match(r"^-\s+\[([^\]]*)\]\s+(.+)$", line.strip())
        if m:
            marker = m.group(1)
            text   = m.group(2)
            if marker in ("x", "done"):
                status = "done"
            elif marker == "running":
                status = "running"
            elif marker == "interrupted":
                status = "interrupted"
            else:
                status = "todo"
            result.append({"status": status, "text": text})
    return result


def set_plan_status(index: int, status: str) -> None:
    """将第 index 个（0-based）Plan 的状态更新为 status。"""
    _require_init()
    fp = _MEMORY_DIR / "current_plans.md"  # type: ignore[operator]
    if not fp.exists():  # type: ignore[union-attr]
        return
    marker_map = {"todo": " ", "running": "running", "done": "x", "interrupted": "interrupted"}
    marker = marker_map.get(status, " ")
    lines = fp.read_text(encoding="utf-8").splitlines()  # type: ignore[union-attr]
    plan_count = 0
    new_lines  = []
    for line in lines:
        m = re.match(r"^(- \[)[^\]]*(\] .+)$", line)
        if m:
            if plan_count == index:
                new_lines.append(f"{m.group(1)}{marker}{m.group(2)}")
            else:
                new_lines.append(line)
            plan_count += 1
        else:
            new_lines.append(line)
    fp.write_text("\n".join(new_lines) + "\n", encoding="utf-8")  # type: ignore[union-attr]
