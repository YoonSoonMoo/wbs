"""JIRA 이슈 통계 리포트 생성 프로그램

지정된 기간 내 이슈유형별, 상태별, 담당자별 카운트를 주차별로 집계하여 마크다운 파일로 생성합니다.
"""
import os
import sys
import logging
import argparse
from pathlib import Path
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Tuple
from collections import Counter, defaultdict
from dotenv import load_dotenv

from config_loader import load_config
from jira_client import JiraClient

load_dotenv()

# 대상 담당자 목록
TARGET_WORKERS = ["윤순무", "박준형", "원준호", "이필원", "조민기", "조경준", "정관희"]

# 집계 대상 이슈유형
TARGET_ISSUE_TYPES = ["개발요청", "기능개선", "버그", "운영요청", "재개발"]

# 상태 그룹 매핑
STATUS_GROUP_MAP = {
    "진행": "진행",
    "Open": "진행",
    "열림": "진행",
    "완료": "완료",
    "Confirmed": "완료",
    "Done": "완료",
    "TC/검수": "완료",
    "배포": "완료",
    "보류": "보류",
    "검토": "보류",
}

STATUS_GROUPS = ["진행", "완료", "보류"]


def validate_date(date_str: str) -> str:
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
        return date_str
    except ValueError:
        raise argparse.ArgumentTypeError(f"날짜 형식이 올바르지 않습니다: {date_str} (yyyy-MM-dd)")


def get_friday_of_week(d: date) -> date:
    """주어진 날짜가 속한 업무주의 금요일 반환 (월~일 → 해당 주 금요일)"""
    weekday = d.weekday()  # 0=Mon, 4=Fri, 6=Sun
    return d + timedelta(days=4 - weekday)


def get_week_label(d: date) -> str:
    """날짜의 주차 레이블 반환 (금요일이 속한 월 기준)

    월초/월말에 주가 나뉠 때 금요일이 속한 월로 판단합니다.
    예) 3/30(월)~4/3(금) → 금요일이 4월 → '4월 1주차'
    예) 4/27(월)~5/1(금) → 금요일이 5월 → '5월 1주차'
    """
    friday = get_friday_of_week(d)
    week = (friday.day - 1) // 7 + 1
    return f"{friday.month}월 {week}주차"


def get_week_labels_in_range(start_date: str, end_date: str) -> List[str]:
    """날짜 범위 내 주차 레이블 목록 반환 (금요일 기준, 순서 보장)"""
    sd = datetime.strptime(start_date, "%Y-%m-%d").date()
    ed = datetime.strptime(end_date, "%Y-%m-%d").date()
    labels = []
    seen = set()
    current = sd
    while current <= ed:
        label = get_week_label(current)
        if label not in seen:
            seen.add(label)
            labels.append(label)
        current += timedelta(days=1)
    return labels


def get_report_monday() -> date:
    """실행일 기준 해당 주 월요일 반환"""
    today = date.today()
    return today - timedelta(days=today.weekday())


def fetch_issues(jira_client: JiraClient, config: Dict, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """기간 내 FULFILMENT 프로젝트 이슈 조회"""
    worker_field_id = config['jira'].get('worker_field_id', 'customfield_12291')

    jql = (
        f'project = FULFILMENT AND '
        f'createdDate >= "{start_date}" AND createdDate <= "{end_date}" '
        f'ORDER BY created DESC'
    )

    logging.info(f"JQL: {jql}")

    result = jira_client.search_issues(
        jql,
        fields=["summary", "status", "issuetype", "assignee", "created", worker_field_id],
        max_total=config['jira'].get('max_total', 1000)
    )

    return result.get('issues', [])


def extract_worker_name(fields: Dict, worker_field_id: str) -> str:
    """이슈 필드에서 작업 담당자명 추출"""
    worker = fields.get(worker_field_id)
    if worker:
        if isinstance(worker, dict):
            return worker.get('displayName') or worker.get('name', '미지정')
        return str(worker)
    return "미지정"


def classify_issue(fields: Dict, worker_field_id: str) -> Dict[str, str]:
    """이슈에서 유형, 상태그룹, 담당자 추출"""
    issue_type = fields.get('issuetype', {}).get('name', '기타')
    status_name = fields.get('status', {}).get('name', '기타')
    status_group = STATUS_GROUP_MAP.get(status_name, status_name)
    worker_name = extract_worker_name(fields, worker_field_id)
    return {
        'issue_type': issue_type,
        'status_group': status_group,
        'worker': worker_name,
    }


def build_weekly_statistics(issues: List[Dict[str, Any]], worker_field_id: str,
                            start_date: str, end_date: str) -> Dict[str, Any]:
    """이슈를 주차별로 분류하여 통계 집계 (금요일 기준 월/주차 판단)"""
    # 금요일 기준으로 주차 레이블 목록 생성
    week_labels = get_week_labels_in_range(start_date, end_date)

    # 주차별 집계 초기화
    weekly_issue_type = defaultdict(Counter)    # week_label -> Counter(issue_type)
    weekly_status = defaultdict(Counter)        # week_label -> Counter(status_group)
    weekly_worker = defaultdict(Counter)        # week_label -> Counter(worker_name)
    weekly_total = Counter()                    # week_label -> total count

    for issue in issues:
        fields = issue.get('fields', {})
        created_str = fields.get('created', '')
        if not created_str:
            continue

        try:
            created_date = datetime.strptime(created_str[:10], "%Y-%m-%d").date()
        except ValueError:
            continue

        week_label = get_week_label(created_date)

        if week_label not in week_labels:
            continue

        info = classify_issue(fields, worker_field_id)

        weekly_total[week_label] += 1
        weekly_issue_type[week_label][info['issue_type']] += 1
        weekly_status[week_label][info['status_group']] += 1
        weekly_worker[week_label][info['worker']] += 1

    return {
        'week_labels': week_labels,
        'weekly_total': weekly_total,
        'weekly_issue_type': weekly_issue_type,
        'weekly_status': weekly_status,
        'weekly_worker': weekly_worker,
        'grand_total': len(issues),
    }


def fmt_pct(count: int, total: int) -> str:
    """비율 포맷 (소수점 2자리)"""
    if total == 0:
        return "0.00%"
    return f"{count / total * 100:.2f}%"


def generate_markdown(stats: Dict[str, Any], start_date: str, end_date: str) -> str:
    """주차별 3개 테이블 마크다운 리포트 생성"""
    week_labels = stats['week_labels']
    grand_total = stats['grand_total']
    lines = []

    lines.append("# JIRA 이슈 통계 리포트")
    lines.append("")
    lines.append(f"- **프로젝트**: FULFILMENT")
    lines.append(f"- **조회 기간**: {start_date} ~ {end_date}")
    lines.append(f"- **총 이슈 수**: {grand_total}건")
    lines.append(f"- **생성일시**: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")

    # ── 1. 이슈유형별 테이블 ──
    lines.append("---")
    lines.append("")
    lines.append("## 1. 이슈유형별 카운트")
    lines.append("")

    # 헤더
    type_cols = ["총 이슈"] + TARGET_ISSUE_TYPES
    header = "| 주차 | " + " | ".join(type_cols) + " |"
    sep = "|" + "|".join(["------"] * (len(type_cols) + 1)) + "|"
    lines.append(header)
    lines.append(sep)

    # 각 주차 행
    type_totals = Counter()
    for wl in week_labels:
        wt = stats['weekly_total'].get(wl, 0)
        row = [str(wt)]
        for itype in TARGET_ISSUE_TYPES:
            c = stats['weekly_issue_type'].get(wl, {}).get(itype, 0)
            type_totals[itype] += c
            row.append(str(c))
        lines.append(f"| {wl} | " + " | ".join(row) + " |")

    # 합계 행
    type_grand = sum(type_totals.values())
    total_row = [str(grand_total)]
    for itype in TARGET_ISSUE_TYPES:
        total_row.append(str(type_totals[itype]))
    lines.append(f"| **합계** | " + " | ".join(f"**{v}**" for v in total_row) + " |")

    # 비율 행
    pct_row = [fmt_pct(grand_total, grand_total)]
    for itype in TARGET_ISSUE_TYPES:
        pct_row.append(fmt_pct(type_totals[itype], grand_total))
    lines.append(f"| **비율** | " + " | ".join(pct_row) + " |")
    lines.append("")

    # ── 2. 상태별 테이블 ──
    lines.append("---")
    lines.append("")
    lines.append("## 2. 상태별 카운트")
    lines.append("")

    header = "| 주차 | " + " | ".join(STATUS_GROUPS) + " |"
    sep = "|" + "|".join(["------"] * (len(STATUS_GROUPS) + 1)) + "|"
    lines.append(header)
    lines.append(sep)

    status_totals = Counter()
    for wl in week_labels:
        row = []
        for sg in STATUS_GROUPS:
            c = stats['weekly_status'].get(wl, {}).get(sg, 0)
            status_totals[sg] += c
            row.append(str(c))
        lines.append(f"| {wl} | " + " | ".join(row) + " |")

    total_row = [str(status_totals[sg]) for sg in STATUS_GROUPS]
    lines.append(f"| **합계** | " + " | ".join(f"**{v}**" for v in total_row) + " |")

    pct_row = [fmt_pct(status_totals[sg], grand_total) for sg in STATUS_GROUPS]
    lines.append(f"| **비율** | " + " | ".join(pct_row) + " |")
    lines.append("")

    # ── 3. 담당자별 테이블 ──
    lines.append("---")
    lines.append("")
    lines.append("## 3. 담당자별 카운트")
    lines.append("")

    header = "| 주차 | " + " | ".join(TARGET_WORKERS) + " |"
    sep = "|" + "|".join(["------"] * (len(TARGET_WORKERS) + 1)) + "|"
    lines.append(header)
    lines.append(sep)

    worker_totals = Counter()
    for wl in week_labels:
        row = []
        for worker in TARGET_WORKERS:
            c = stats['weekly_worker'].get(wl, {}).get(worker, 0)
            worker_totals[worker] += c
            row.append(str(c))
        lines.append(f"| {wl} | " + " | ".join(row) + " |")

    total_row = [str(worker_totals[w]) for w in TARGET_WORKERS]
    lines.append(f"| **합계** | " + " | ".join(f"**{v}**" for v in total_row) + " |")

    pct_row = [fmt_pct(worker_totals[w], grand_total) for w in TARGET_WORKERS]
    lines.append(f"| **비율** | " + " | ".join(pct_row) + " |")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description='JIRA 이슈 통계 리포트 생성')
    parser.add_argument('start_date', type=validate_date, help='대상 시작일 (yyyy-MM-dd)')
    parser.add_argument('end_date', type=validate_date, help='대상 종료일 (yyyy-MM-dd)')
    args = parser.parse_args()

    # 로깅 설정
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s',
        handlers=[
            logging.FileHandler(log_dir / 'issue_statistics.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

    logging.info(f"이슈 통계 리포트 생성 시작: {args.start_date} ~ {args.end_date}")

    config = load_config()

    jira_base = os.getenv('JIRA_BASE_URL')
    jira_email = os.getenv('JIRA_EMAIL')
    jira_token = os.getenv('JIRA_API_TOKEN')

    if not all([jira_base, jira_email, jira_token]):
        logging.error("JIRA 환경변수가 설정되지 않았습니다 (JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN)")
        sys.exit(1)

    jira_client = JiraClient(jira_base, jira_email, jira_token)

    # 이슈 조회
    issues = fetch_issues(jira_client, config, args.start_date, args.end_date)
    logging.info(f"조회된 이슈 수: {len(issues)}건")

    if not issues:
        logging.warning("조회된 이슈가 없습니다.")
        print("조회된 이슈가 없습니다.")
        sys.exit(0)

    # 주차별 통계 집계
    worker_field_id = config['jira'].get('worker_field_id', 'customfield_12291')
    stats = build_weekly_statistics(issues, worker_field_id, args.start_date, args.end_date)

    # 마크다운 생성
    md_content = generate_markdown(stats, args.start_date, args.end_date)

    # 파일 저장 (실행일 기준 해당주 월요일 폴더)
    monday = get_report_monday()
    output_dir = Path('reports') / monday.strftime('%Y-%m-%d')
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"jira_weekly_report_{args.end_date}.md"
    output_file.write_text(md_content, encoding='utf-8')

    logging.info(f"리포트 생성 완료: {output_file}")
    print(f"\n리포트 생성 완료: {output_file}")


if __name__ == '__main__':
    main()
