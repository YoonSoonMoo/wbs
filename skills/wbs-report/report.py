#!/usr/bin/env python3
"""WBS 조회/리포팅 헬퍼 — 읽기 전용.

같은 디렉토리의 env.json(url/project_id/token)을 읽어 본인 담당 태스크를
조회하고, 지연업무 / 이번주 주요업무를 정렬·요약해 stdout 으로 출력한다.
갱신(PATCH)은 하지 않는다 — 갱신은 SKILL.md 의 반영 플로우(curl)에서 수행.

크로스플랫폼: 표준 라이브러리(urllib)만 사용. Windows 한글 깨짐 방지를 위해
stdout 을 UTF-8 로 재설정한다.

사용:
  python3 report.py delayed                 # 지연업무 (plan_end 경과 + progress<100)
  python3 report.py week                     # 이번주(월~일) 주요업무
  python3 report.py all                      # 진행중/이번주/지연 통합
  python3 report.py week --today 2026-06-23  # 기준일 명시(미지정 시 시스템 날짜)
  python3 report.py week --assignee 홍길동    # 담당자 직접 지정(미지정 시 /api/users/me)
  python3 report.py week --json              # 사람용 표 대신 JSON 출력(모델 후처리용)
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Windows 콘솔 한글 mojibake 방지
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def _die(msg: str) -> "NoReturn":  # type: ignore[name-defined]
    print(msg, file=sys.stderr)
    sys.exit(1)


def load_env() -> dict:
    env_path = Path(__file__).with_name("env.json")
    if not env_path.exists():
        _die(f"env.json 이 없습니다: {env_path}\n→ url/project_id/token 을 채워주세요.")
    try:
        env = json.loads(env_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        _die(f"env.json 파싱 실패: {e}")
    token = (env.get("token") or "").strip()
    if not token or "여기에" in token or token.startswith("관리자"):
        _die("env.json 의 token 이 비어있거나 샘플 값입니다. 관리자 발급 토큰으로 교체하세요.")
    # url 끝 슬래시 제거 (이중 슬래시로 404/리다이렉트 방지)
    env["url"] = (env.get("url") or "").rstrip("/")
    if not env["url"]:
        _die("env.json 의 url 이 비어있습니다.")
    if env.get("project_id") in (None, ""):
        _die("env.json 의 project_id 가 비어있습니다.")
    return env


def api_get(env: dict, path: str):
    req = urllib.request.Request(
        f"{env['url']}{path}",
        headers={"Authorization": f"Bearer {env['token']}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        if e.code == 401:
            _die("401 인증 실패 — 토큰이 잘못/만료되었습니다. 관리자 재발급 후 env.json 갱신 필요.")
        _die(f"HTTP {e.code} ({path}): {body}")
    except urllib.error.URLError as e:
        _die(f"WBS 서버 연결 실패 ({env['url']}): {e.reason}")


def week_bounds(today: dt.date) -> tuple[dt.date, dt.date]:
    """today 가 속한 주의 월요일~일요일."""
    monday = today - dt.timedelta(days=today.weekday())
    return monday, monday + dt.timedelta(days=6)


def parse_date(s):
    if not s:
        return None
    try:
        return dt.date.fromisoformat(str(s)[:10])
    except ValueError:
        return None


def is_delayed(it, today) -> bool:
    pe = parse_date(it.get("plan_end"))
    return bool(pe and pe < today and (it.get("progress") or 0) < 100)


def in_week(it, wk_start, wk_end) -> bool:
    ps = parse_date(it.get("plan_start"))
    pe = parse_date(it.get("plan_end"))
    if ps is None and pe is None:
        return False
    ps = ps or pe
    pe = pe or ps
    return ps <= wk_end and pe >= wk_start  # 기간 겹침


def fmt(it, today) -> str:
    prog = it.get("progress") or 0
    ps, pe = it.get("plan_start") or "?", it.get("plan_end") or "?"
    peo = parse_date(it.get("plan_end"))
    delay = ""
    if peo and peo < today and prog < 100:
        delay = f"  🔴{(today - peo).days}일지연"
    name = " > ".join(x for x in (it.get("task_name"), it.get("subtask")) if x)
    detail = it.get("detail") or ""
    status = (it.get("status") or "").replace("\n", " / ").strip()
    line = (f"[id {it['id']}] {it.get('wbs_code','')}  {name}\n"
            f"    {detail}\n"
            f"    계획 {ps}~{pe} | 진척 {prog}% | 우선순위 {it.get('priority','-')}{delay}")
    if status:
        line += f"\n    상태: {status}"
    return line


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["delayed", "week", "all"])
    ap.add_argument("--today", help="기준일 YYYY-MM-DD (미지정 시 시스템 날짜)")
    ap.add_argument("--assignee", help="담당자명 (미지정 시 /api/users/me)")
    ap.add_argument("--json", action="store_true", help="JSON 출력")
    args = ap.parse_args()

    today = parse_date(args.today) or dt.date.today()
    env = load_env()

    me = args.assignee
    if not me:
        me = (api_get(env, "/api/users/me") or {}).get("name")
        if not me:
            _die("담당자명을 확인하지 못했습니다. --assignee 로 직접 지정하세요.")

    items = api_get(env, f"/api/wbs/{env['project_id']}/items")
    if isinstance(items, dict):
        _die(f"items 응답이 객체입니다(에러일 수 있음): {items}")
    if not items:
        _die(f"project_id={env['project_id']} 의 아이템이 0건입니다. "
             "project_id 가 올바른지(그리드 URL /project/<id>/wbs) 확인하세요.")

    mine = [i for i in items if i.get("assignee") == me]
    wk_start, wk_end = week_bounds(today)

    delayed = sorted((i for i in mine if is_delayed(i, today)),
                     key=lambda i: i.get("plan_end") or "")
    weekly = sorted((i for i in mine if in_week(i, wk_start, wk_end)),
                    key=lambda i: (i.get("plan_start") or "", i.get("wbs_code") or ""))

    if args.json:
        sel = {"delayed": delayed, "week": weekly,
               "all": {"delayed": delayed, "week": weekly}}[args.mode]
        print(json.dumps(sel, ensure_ascii=False, indent=2))
        return 0

    print(f"담당자: {me} | 기준일: {today} | 이번주: {wk_start}~{wk_end} | 내 담당 총 {len(mine)}건")
    if args.mode in ("delayed", "all"):
        print(f"\n■ 지연업무 {len(delayed)}건 (plan_end 경과 + 진척<100%)")
        print("=" * 64)
        for i in delayed:
            print(fmt(i, today) + "\n")
        if not delayed:
            print("  (없음)\n")
    if args.mode in ("week", "all"):
        print(f"\n■ 이번주 주요업무 {len(weekly)}건 ({wk_start}~{wk_end} 기간 겹침)")
        print("=" * 64)
        for i in weekly:
            print(fmt(i, today) + "\n")
        if not weekly:
            print("  (없음)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
