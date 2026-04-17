import base64
import hashlib
import hmac
import os
import time
from datetime import date, datetime

import requests
import urllib3

MAIL_BASE_URL = "https://mail.apigw.ntruss.com"
URL_PATH = "/api/v1/mails"
METHOD = "POST"


# ===== NCP API 공통 유틸 (send_email.py 기준) =====

def make_signature_v2(secret_key: str, access_key: str, method: str, url_path: str, timestamp_ms: str) -> str:
    """NCP API 호출을 위한 시그니처 생성"""
    message = f"{method} {url_path}\n{timestamp_ms}\n{access_key}".encode("utf-8")
    digest = hmac.new(secret_key.encode("utf-8"), message, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


def create_request_headers(access_key: str, secret_key: str, method: str, url_path: str) -> dict:
    """NCP API 인증 헤더 생성 (Content-Type 미포함 — 호출 측에서 별도 지정)"""
    timestamp = str(int(time.time() * 1000))
    signature = make_signature_v2(
        secret_key=secret_key,
        access_key=access_key,
        method=method,
        url_path=url_path,
        timestamp_ms=timestamp,
    )
    return {
        "x-ncp-apigw-timestamp": timestamp,
        "x-ncp-iam-access-key": access_key,
        "x-ncp-apigw-signature-v2": signature,
    }


def upload_file(access_key: str, secret_key: str, file_path: str) -> str | None:
    """파일을 NCP 메일 서버에 업로드하고 fileId를 반환한다."""
    url_path = "/api/v1/files"
    url = f"{MAIL_BASE_URL}{url_path}"
    headers = create_request_headers(access_key, secret_key, "POST", url_path)

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    try:
        with open(file_path, "rb") as f:
            files = {"fileList": (os.path.basename(file_path), f, "application/octet-stream")}
            resp = requests.post(url, headers=headers, files=files, verify=False)

        if resp.status_code == 201:
            result = resp.json()
            if result.get("files"):
                return result["files"][0]["fileId"]

        return None
    except Exception:
        return None


def send_mail(
    access_key: str,
    secret_key: str,
    payload: dict,
    file_path: str = None,
    timeout_sec: int = 10,
) -> tuple[int, str]:
    """메일 발송 요청. 파일 경로가 있으면 먼저 업로드 후 첨부한다."""
    if file_path and os.path.exists(file_path):
        file_id = upload_file(access_key, secret_key, file_path)
        if file_id:
            payload["attachFileIds"] = [file_id]

    url = f"{MAIL_BASE_URL}{URL_PATH}"
    headers = create_request_headers(access_key, secret_key, METHOD, URL_PATH)
    headers["Content-Type"] = "application/json; charset=utf-8"

    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout_sec, verify=False)
        return resp.status_code, resp.text
    except requests.exceptions.RequestException as e:
        return 0, str(e)


# ===== WBS 전용 래퍼 =====

def _get_keys() -> tuple[str | None, str | None]:
    """환경변수에서 NCP 키를 읽는다."""
    return os.environ.get("NAVER-API-ACCESS-KEY"), os.environ.get("NAVER-API-SECRET-KEY")


def send_html_mail(
    to_address: str,
    to_name: str,
    subject: str,
    html_body: str,
    file_path: str = None,
) -> tuple[bool, str]:
    """HTML 문자열로 메일을 발송한다. (success, message) 반환"""
    access_key, secret_key = _get_keys()
    if not access_key or not secret_key:
        return False, "API 키가 설정되지 않았습니다."

    payload = {
        "senderAddress": "send-only@daou.co.kr",
        "senderName": "WBS 관리 시스템",
        "title": subject,
        "body": html_body,
        "recipients": [{"address": to_address, "name": to_name, "type": "R"}],
        "individual": True,
        "advertising": False,
    }

    status, text = send_mail(access_key, secret_key, payload, file_path=file_path)
    if status == 201:
        return True, "발송 성공"
    return False, f"발송 실패 ({status}): {text}"


# ===== 지연 태스크 메일 HTML 빌더 =====

def build_delay_mail_html(
    assignee_name: str,
    delayed_tasks: list,
    project_name: str,
    project_url: str,
) -> str:
    """지연 태스크 알림 HTML 이메일 본문을 생성한다."""
    today_str = date.today().strftime("%Y-%m-%d")

    rows_html = ""
    for t in delayed_tasks:
        plan_end = t.get("plan_end") or "-"
        task_name = t.get("task_name") or "-"
        subtask = t.get("subtask") or ""
        detail = t.get("detail") or ""
        progress = int(t.get("progress") or 0)
        status = t.get("status") or ""

        try:
            pe = datetime.strptime(plan_end, "%Y-%m-%d").date()
            delay_days = (date.today() - pe).days
            delay_badge = f"+{delay_days}일"
        except Exception:
            delay_badge = "-"

        prog_color = (
            "#16a34a" if progress >= 100
            else "#2563eb" if progress >= 50
            else "#d97706" if progress > 0
            else "#d1d5db"
        )

        # 짝수/홀수 행 배경 교대
        row_bg = "#fdf8f8" if len(rows_html) % 2 == 0 else "#ffffff"
        rows_html += (
            f'<tr style="border-bottom:1px solid #e8eaef;background:{row_bg};">'
            f'<td style="padding:10px 12px;vertical-align:middle;font-weight:600;color:#1a1d24;border-right:1px solid #e8eaef;">{task_name}</td>'
            f'<td style="padding:10px 12px;vertical-align:middle;color:#4a5068;border-right:1px solid #e8eaef;">{subtask}</td>'
            f'<td style="padding:10px 12px;vertical-align:middle;color:#6b7280;font-size:11px;border-right:1px solid #e8eaef;">{detail}</td>'
            f'<td style="padding:10px 12px;vertical-align:middle;font-family:Courier New,monospace;color:#dc2626;font-weight:600;white-space:nowrap;border-right:1px solid #e8eaef;">{plan_end}</td>'
            f'<td style="padding:10px 12px;vertical-align:middle;text-align:center;white-space:nowrap;border-right:1px solid #e8eaef;">'
            f'<span style="background:#dc2626;color:#fff;padding:3px 9px;border-radius:20px;font-size:10px;font-weight:700;font-family:Courier New,monospace;display:inline-block;">{delay_badge}</span>'
            f'</td>'
            f'<td style="padding:10px 12px;vertical-align:middle;white-space:nowrap;">'
            f'<table cellpadding="0" cellspacing="0" border="0" style="display:inline-table;vertical-align:middle;margin-right:5px;">'
            f'<tr><td style="width:60px;height:7px;background:#e8eaef;border-radius:4px;overflow:hidden;padding:0;">'
            f'<div style="width:{progress}%;height:7px;background:{prog_color};"></div>'
            f'</td></tr></table>'
            f'<span style="font-size:11px;color:#4a5068;font-family:Courier New,monospace;">{progress}%</span>'
            f'</td>'
            f'</tr>'
        )

    count = len(delayed_tasks)
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>지연 태스크 알림</title>
</head>
<body style="margin:0;padding:0;background:#f4f6f9;font-family:'Apple SD Gothic Neo','Malgun Gothic',Arial,sans-serif;font-size:13px;color:#1a1d24;">

<table width="100%" cellpadding="0" cellspacing="0" border="0" style="background:#f4f6f9;">
<tr><td align="center" style="padding:32px 16px;">

  <!-- 메일 본문 wrapper -->
  <table width="900" cellpadding="0" cellspacing="0" border="0" style="max-width:900px;width:100%;background:#ffffff;border-radius:12px;overflow:hidden;border:1px solid #dde0e7;">

    <!-- 헤더 -->
    <tr>
      <td style="background:#1e293b;padding:28px 32px;">
        <p style="margin:0 0 6px;color:#ffffff;font-size:20px;font-weight:700;letter-spacing:-0.3px;">&#9888; 지연 태스크 알림</p>
        <p style="margin:0;color:#94a3b8;font-size:12px;">{project_name} &middot; {today_str} 기준</p>
      </td>
    </tr>

    <!-- 요약 바 -->
    <tr>
      <td style="background:#fef2f2;border-bottom:3px solid #fca5a5;padding:14px 32px;">
        <p style="margin:0;font-size:12px;color:#dc2626;">
          <strong style="font-size:28px;font-weight:700;display:block;line-height:1;margin-bottom:2px;">{count}</strong>
          건 지연 중
        </p>
      </td>
    </tr>

    <!-- 본문 -->
    <tr>
      <td style="padding:28px 32px;">

        <!-- 인사말 -->
        <p style="margin:0 0 24px;font-size:13px;color:#1a1d24;line-height:1.8;padding:16px 20px;background:#f8f9fb;border-left:4px solid #2563eb;">
          안녕하세요, <strong style="color:#2563eb;">{assignee_name}</strong>님.<br>
          오늘({today_str}) 기준으로 계획 완료일이 지난 미완료 태스크가
          <strong style="color:#dc2626;">{count}건</strong> 있습니다.<br>
          아래 목록을 확인하시고 진행 현황을 업데이트해 주시기 바랍니다.
        </p>

        <!-- 지연 태스크 테이블 -->
        <table width="100%" cellpadding="0" cellspacing="0" border="0" style="width:100%;border-collapse:collapse;margin-bottom:24px;font-size:12px;border:1px solid #dde0e7;">
          <thead>
            <tr style="background:#1e293b;">
              <th style="padding:10px 12px;text-align:left;color:#e2e8f0;font-weight:600;font-size:11px;letter-spacing:0.5px;border-right:1px solid #374151;white-space:nowrap;">Task</th>
              <th style="padding:10px 12px;text-align:left;color:#e2e8f0;font-weight:600;font-size:11px;letter-spacing:0.5px;border-right:1px solid #374151;white-space:nowrap;">서브태스크</th>
              <th style="padding:10px 12px;text-align:left;color:#e2e8f0;font-weight:600;font-size:11px;letter-spacing:0.5px;border-right:1px solid #374151;white-space:nowrap;">세부항목</th>
              <th style="padding:10px 12px;text-align:left;color:#e2e8f0;font-weight:600;font-size:11px;letter-spacing:0.5px;border-right:1px solid #374151;white-space:nowrap;">계획완료일</th>
              <th style="padding:10px 12px;text-align:center;color:#e2e8f0;font-weight:600;font-size:11px;letter-spacing:0.5px;border-right:1px solid #374151;white-space:nowrap;">지연</th>
              <th style="padding:10px 12px;text-align:left;color:#e2e8f0;font-weight:600;font-size:11px;letter-spacing:0.5px;white-space:nowrap;">진행률</th>
            </tr>
          </thead>
          <tbody>
            {rows_html}
          </tbody>
        </table>

        <!-- CTA 버튼 -->
        <table width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr>
            <td align="center" style="padding:8px 0 16px;">
              <a href="{project_url}" style="display:inline-block;padding:13px 36px;background:#2563eb;color:#ffffff;text-decoration:none;border-radius:8px;font-size:14px;font-weight:700;letter-spacing:-0.2px;">WBS 바로가기 &#8594;</a>
            </td>
          </tr>
        </table>

      </td>
    </tr>

    <!-- 푸터 -->
    <tr>
      <td style="background:#f8f9fb;border-top:1px solid #e8eaef;padding:16px 32px;font-size:11px;color:#8b90a0;text-align:center;">
        본 메일은 WBS 관리 시스템에서 자동 발송된 알림입니다. &middot; {project_url}
      </td>
    </tr>

  </table>
</td></tr>
</table>

</body>
</html>"""
