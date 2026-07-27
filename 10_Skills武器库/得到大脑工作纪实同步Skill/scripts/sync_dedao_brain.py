#!/usr/bin/env python3
"""Sync Dedao Brain notes into the work-record library."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


BASE_URL = "https://openapi.biji.com/open"
MAIN_WORK_RECORD_DIR = Path("02_资产中心") / "01_原始知识库" / "99_我的工作纪实"
STATE_FILE = ".sync-state.json"


def now() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def stamp() -> str:
    return dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")


def workspace_root() -> Path:
    root = os.environ.get("AI_TRAFFIC_FACTORY_ROOT") or os.environ.get("GANHUO_AI_TRAFFIC_FACTORY_ROOT")
    if root:
        return Path(root)
    return Path.cwd()


ROOT = workspace_root()
sys.path.insert(0, str(ROOT / "tools"))

from brand_footer import append_brand_footer

try:
    from dispatch_gate import require_dispatch_record
except ImportError:
    require_dispatch_record = None


def work_record_dir(root: Path) -> Path:
    return root / MAIN_WORK_RECORD_DIR


def read_windows_env(name: str, scope: str) -> str:
    if os.name != "nt":
        return ""
    try:
        import winreg

        root = winreg.HKEY_CURRENT_USER if scope == "User" else winreg.HKEY_LOCAL_MACHINE
        subkey = "Environment" if scope == "User" else r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
        with winreg.OpenKey(root, subkey) as key:
            value, _kind = winreg.QueryValueEx(key, name)
            return str(value)
    except OSError:
        return ""


def require_env(name: str) -> str:
    value = os.environ.get(name) or read_windows_env(name, "User") or read_windows_env(name, "Machine")
    if not value:
        raise SystemExit(f"Missing environment variable: {name}")
    return value


def env_report(client_id: str, api_key: str) -> dict[str, dict[str, int | bool]]:
    return {
        "DEDAO_BRAIN_CLIENT_ID": {"exists": bool(client_id), "length": len(client_id)},
        "DEDAO_BRAIN_API_KEY": {"exists": bool(api_key), "length": len(api_key)},
    }


def request_json(path: str, params: dict[str, str], client_id: str, api_key: str) -> dict:
    query = urllib.parse.urlencode(params)
    url = f"{BASE_URL}{path}"
    if query:
        url = f"{url}?{query}"
    req = urllib.request.Request(
        url,
        headers={
            "X-Client-ID": client_id,
            "Authorization": api_key,
            "User-Agent": "ai-traffic-factory-work-record-sync/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Dedao Brain API HTTP {exc.code}: {body}") from exc


def api_data(payload: dict) -> dict:
    data = payload.get("data")
    if isinstance(data, dict):
        note = data.get("note")
        if isinstance(note, dict):
            return note
        return data
    return payload


def load_state(out_dir: Path) -> dict:
    state_path = out_dir / STATE_FILE
    if not state_path.exists():
        return {"synced_note_ids": []}
    return json.loads(state_path.read_text(encoding="utf-8"))


def save_state(out_dir: Path, state: dict) -> None:
    state["last_synced_at"] = now()
    (out_dir / STATE_FILE).write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def clean_filename(value: str) -> str:
    value = re.sub(r'[<>:"/\\|?*\r\n\t]+', "_", value).strip()
    value = re.sub(r"\s+", " ", value)
    return value[:80] or "未命名工作纪实"


def note_id(note: dict) -> str:
    return str(note.get("note_id") or note.get("id") or "")


def note_created_at(note: dict) -> str:
    return str(note.get("created_at") or note.get("create_time") or "")


def filename_for(note: dict) -> str:
    created = note_created_at(note)
    prefix = created[:16].replace(":", "-").replace(" ", "_") if created else dt.datetime.now().strftime("%Y-%m-%d_%H-%M")
    title = clean_filename(str(note.get("title") or note_id(note)))
    return f"{prefix}_{title}.md"


def unique_output_path(out_dir: Path, note: dict) -> Path:
    base = out_dir / filename_for(note)
    if not base.exists():
        return base
    nid = note_id(note)
    try:
        existing = base.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        existing = ""
    if nid and f"得到大脑 note_id：{nid}" in existing:
        return base
    suffix = nid[-8:] if nid else stamp()
    candidate = base.with_name(f"{base.stem}_{suffix}{base.suffix}")
    counter = 2
    while candidate.exists():
        candidate = base.with_name(f"{base.stem}_{suffix}_{counter}{base.suffix}")
        counter += 1
    return candidate


def note_markdown(note: dict) -> str:
    title = str(note.get("title") or "未命名工作纪实")
    audio = note.get("audio") if isinstance(note.get("audio"), dict) else {}
    content = str(
        note.get("content")
        or note.get("text")
        or note.get("transcript")
        or note.get("markdown")
        or ""
    )
    summary = str(note.get("summary") or "")
    nid = note_id(note)
    note_type = str(note.get("note_type") or note.get("type") or "")
    created = note_created_at(note)
    updated = str(note.get("updated_at") or note.get("update_time") or "")
    tags = note.get("tags") or []
    knowledge = note.get("knowledge") or note.get("knowledge_base") or ""
    synced = now()
    return f"""# {title}

- 得到大脑 note_id：{nid}
- note_type：{note_type}
- created_at：{created}
- updated_at：{updated}
- synced_at：{synced}
- 来源：得到大脑
- 标签：{tags}
- 知识库：{knowledge}
- audio_original：{audio.get("original", "")}
- audio_play_url：{audio.get("play_url", "")}
- audio_duration：{audio.get("duration", "")}

## 原始转写

{content}

## 得到大脑摘要

{summary}
"""


def extract_notes(payload: dict) -> tuple[list[dict], str | None, bool]:
    data = payload.get("data") or {}
    notes = data.get("notes") or data.get("list") or data.get("items") or []
    cursor = data.get("next_cursor") or data.get("cursor")
    has_more = bool(data.get("has_more"))
    return notes, str(cursor) if cursor else None, has_more


def fetch_note_pages(path: str, client_id: str, api_key: str, limit: int | None) -> list[dict]:
    notes: list[dict] = []
    cursor = ""
    while limit is None or len(notes) < limit:
        params: dict[str, str] = {}
        if cursor:
            params["cursor"] = cursor
        payload = request_json(path, params, client_id, api_key)
        page_notes, next_cursor, has_more = extract_notes(payload)
        notes.extend(page_notes)
        if not has_more or not next_cursor or next_cursor == cursor:
            break
        cursor = next_cursor
    return notes if limit is None else notes[:limit]


def try_fetch_note_pages(path: str, client_id: str, api_key: str, limit: int | None) -> list[dict]:
    try:
        return fetch_note_pages(path, client_id, api_key, limit)
    except SystemExit as exc:
        print(json.dumps({
            "source": path,
            "status": "skipped",
            "reason": str(exc),
        }, ensure_ascii=False), file=sys.stderr)
        return []


def fetch_note_detail(note: dict, client_id: str, api_key: str) -> dict:
    nid = note_id(note)
    if not nid:
        return note
    for path in ["/api/v1/resource/note/detail", "/api/v1/resource/record-card/detail"]:
        try:
            payload = request_json(path, {"id": nid}, client_id, api_key)
        except SystemExit:
            continue
        data = api_data(payload)
        if data:
            merged = dict(note)
            merged.update(data)
            return merged
    return note


def dedupe_notes(notes: list[dict]) -> list[dict]:
    seen: set[str] = set()
    unique: list[dict] = []
    for note in notes:
        nid = note_id(note)
        if not nid or nid in seen:
            continue
        seen.add(nid)
        unique.append(note)
    return unique


def write_audit(root: Path, outputs: list[Path], issues: list[str], env_status: dict, fetched: int, new_count: int) -> Path:
    audit_dir = root / "01_Agent系统" / "02_小审-质量审核Agent" / "99_审核记录"
    audit_dir.mkdir(parents=True, exist_ok=True)
    path = audit_dir / f"{stamp()}_得到大脑全部笔记同步入库审核.md"
    lines = [
        "# 小审审核记录",
        "",
        f"- 审核时间：{now()}",
        "- 审核对象：得到大脑全部笔记同步到工作纪实原始库",
        "- 审核标准：原始资料入库字段完整、鉴权不落盘、旧文件不覆盖",
        f"- 审核结论：{'通过' if not issues else '退回'}",
        "",
        "## 同步概况",
        "",
        f"- 接口拉取去重后数量：{fetched}",
        f"- 新增入库数量：{new_count}",
        f"- Client ID 状态：exists={env_status['DEDAO_BRAIN_CLIENT_ID']['exists']} length={env_status['DEDAO_BRAIN_CLIENT_ID']['length']}",
        f"- API Key 状态：exists={env_status['DEDAO_BRAIN_API_KEY']['exists']} length={env_status['DEDAO_BRAIN_API_KEY']['length']}",
        "",
        "## 新增文件",
        "",
    ]
    lines += [f"- `{path}`" for path in outputs] or ["- 本次无新增文件，已同步 note_id 未重复写入。"]
    lines += ["", "## 发现", ""]
    lines += ["- 未发现阻断问题，允许作为工作纪实原始资料留存。" if not issues else "- " + "\n- ".join(issues)]
    path.write_text(append_brand_footer("\n".join(lines)), encoding="utf-8")
    return path


def write_exec_record(root: Path, outputs: list[Path], audit: Path, status: str) -> Path:
    exec_dir = root / "01_Agent系统" / "03_小息-信息采集Agent" / "99_执行记录"
    exec_dir.mkdir(parents=True, exist_ok=True)
    path = exec_dir / f"{stamp()}_得到大脑全部笔记同步_工作纪实原始库.md"
    lines = [
        "# 小息执行记录",
        "",
        "- 任务：得到大脑全部笔记同步到工作纪实原始库",
        "- 执行模式：全量分页同步，只入原始资料库，不拆解",
        f"- 执行状态：{status}",
        f"- 执行时间：{now()}",
        "",
        "## 新增文件",
        "",
    ]
    lines += [f"- `{path}`" for path in outputs] or ["- 本次无新增文件。"]
    lines += ["", f"- 小审审核记录：`{audit}`", ""]
    path.write_text(append_brand_footer("\n".join(lines)), encoding="utf-8")
    return path


def refresh_dashboard(root: Path) -> None:
    script = root / "tools" / "build_xiaojiang_dashboard.py"
    if script.exists():
        import subprocess

        subprocess.run([sys.executable, str(script)], check=False)


def validate_outputs(paths: list[Path]) -> list[str]:
    issues: list[str] = []
    required = ["得到大脑 note_id", "created_at", "updated_at", "synced_at", "来源：得到大脑", "## 原始转写"]
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for item in required:
            if item not in text:
                issues.append(f"{path.name} 缺少 {item}")
        if "DEDAO_BRAIN_API_KEY" in text or "DEDAO_BRAIN_CLIENT_ID" in text:
            issues.append(f"{path.name} 疑似写入鉴权变量名")
    return issues


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="Write synced notes to the work-record directory for the current runtime mode.")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--all", action="store_true", help="Fetch all pages until the Dedao Brain API reports no more notes.")
    parser.add_argument("--include-record-cards", action="store_true", help="Also try record-card list endpoint if the account supports it.")
    args = parser.parse_args()

    root = workspace_root()
    if args.write and require_dispatch_record is not None:
        require_dispatch_record(
            root,
            task_type="得到大脑",
            target_agent="小息",
            input_keyword="99_我的工作纪实",
        )

    client_id = require_env("DEDAO_BRAIN_CLIENT_ID")
    api_key = require_env("DEDAO_BRAIN_API_KEY")
    safe_env = env_report(client_id, api_key)
    out_dir = work_record_dir(root)
    state = load_state(out_dir) if out_dir.exists() else {"synced_note_ids": []}
    synced_ids = set(map(str, state.get("synced_note_ids", [])))
    limit = None if args.all else args.limit

    sources = ["/api/v1/resource/note/list"]
    if args.include_record_cards:
        sources.append("/api/v1/resource/record-card/list")

    fetched: list[dict] = []
    for path in sources:
        fetched.extend(try_fetch_note_pages(path, client_id, api_key, limit))
    fetched = dedupe_notes(fetched)

    fresh = [note for note in fetched if note_id(note) and note_id(note) not in synced_ids]
    fresh_details = [fetch_note_detail(note, client_id, api_key) for note in fresh]

    print(json.dumps({
        "fetched": len(fetched),
        "new": len(fresh_details),
        "write": args.write,
        "all": args.all,
        "output_dir": str(out_dir),
        "env": safe_env,
    }, ensure_ascii=False, indent=2))

    if not args.write:
        return 0

    out_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    for note in fresh_details:
        output = unique_output_path(out_dir, note)
        output.write_text(note_markdown(note), encoding="utf-8")
        outputs.append(output)
        synced_ids.add(note_id(note))

    state["synced_note_ids"] = sorted(synced_ids)
    save_state(out_dir, state)
    issues = validate_outputs(outputs)
    audit = write_audit(root, outputs, issues, safe_env, len(fetched), len(outputs))
    write_exec_record(root, outputs, audit, "通过" if not issues else "退回")
    refresh_dashboard(root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
