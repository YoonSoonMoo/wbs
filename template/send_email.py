import os
import time
import hmac
import base64
import hashlib
import requests
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

MAIL_BASE_URL = "https://mail.apigw.ntruss.com"
URL_PATH = "/api/v1/mails"
METHOD = "POST"

def make_signature_v2(secret_key: str, access_key: str, method: str, url_path: str, timestamp_ms: str) -> str:
    """NCP API 호출을 위한 시그니처 생성"""
    message = f"{method} {url_path}\n{timestamp_ms}\n{access_key}".encode("utf-8")
    digest = hmac.new(secret_key.encode("utf-8"), message, hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")

def create_request_headers(access_key: str, secret_key: str, method: str, url_path: str) -> dict:
    """API 요청 헤더 생성"""
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

def upload_file(access_key: str, secret_key: str, file_path: str) -> str:
    """파일 업로드 후 fileId 반환"""
    url_path = "/api/v1/files"
    url = f"{MAIL_BASE_URL}{url_path}"
    
    headers = create_request_headers(access_key, secret_key, "POST", url_path)
    
    # SSL 인증서 검증 실패 시 verify=False 사용
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    try:
        print(f"📤 파일 업로드 중: {file_path}")
        with open(file_path, 'rb') as f:
            # NCP 파일 업로드 API는 multipart/form-data의 fileList 필드 사용
            files = {'fileList': (os.path.basename(file_path), f, 'application/octet-stream')}
            resp = requests.post(url, headers=headers, files=files, verify=False)
            
        if resp.status_code == 201:
            result = resp.json()
            if 'files' in result and len(result['files']) > 0:
                file_id = result['files'][0]['fileId']
                print(f"✅ 파일 업로드 성공 (ID: {file_id})")
                return file_id
        
        print(f"❌ 파일 업로드 실패: {resp.status_code} - {resp.text}")
        return None
        
    except Exception as e:
        print(f"❌ 파일 업로드 중 오류: {e}")
        return None

def send_mail(access_key: str, secret_key: str, payload: dict, file_path: str = None, timeout_sec: int = 10):
    """메일 발송 요청"""
    
    # 파일 첨부가 있는 경우 먼저 업로드
    if file_path and os.path.exists(file_path):
        file_id = upload_file(access_key, secret_key, file_path)
        if file_id:
            payload['attachFileIds'] = [file_id]
        else:
            print("⚠️ 파일 업로드 실패로 인해 첨부파일 없이 메일을 발송합니다.")
    
    url = f"{MAIL_BASE_URL}{URL_PATH}"
    headers = create_request_headers(access_key, secret_key, "POST", URL_PATH)
    headers["Content-Type"] = "application/json; charset=utf-8"
    
    # SSL 인증서 검증 실패 시 verify=False 사용
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    try:
        # JSON으로 전송
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout_sec, verify=False)
        return resp.status_code, resp.text
    except requests.exceptions.RequestException as e:
        return 0, str(e)

def send_mail_html(access_key: str, secret_key: str, payload: dict, html_file_path: str, timeout_sec: int = 10):
    """HTML 파일을 읽어 본문에 넣어 메일 발송"""
    if html_file_path and os.path.exists(html_file_path):
        try:
            print(f"📖 HTML 파일 읽기: {html_file_path}")
            with open(html_file_path, 'r', encoding='utf-8') as f:
                html_content = f.read()
            payload['body'] = html_content
        except Exception as e:
            print(f"❌ HTML 파일 읽기 실패: {e}")
            return 0, str(e)
    else:
        print(f"⚠️ HTML 파일을 찾을 수 없습니다: {html_file_path}")
        return 0, "HTML file not found"
        
    # 기존 send_mail 호출 (첨부파일 없이)
    return send_mail(access_key, secret_key, payload, file_path=None, timeout_sec=timeout_sec)

if __name__ == "__main__":
    # 환경변수에서 키 가져오기
    ACCESS_KEY = os.getenv("NAVER-API-ACCESS-KEY")
    SECRET_KEY = os.getenv("NAVER-API-SECRET-KEY")

    if not ACCESS_KEY or not SECRET_KEY:
        print("❌ Error: .env 파일에 'NAVER-API-ACCESS-KEY' 또는 'NAVER-API-SECRET-KEY'가 설정되지 않았습니다.")
        exit(1)

    # ⚠️ payload는 실제 NCP Mailer 스펙에 맞게 구성해야 합니다.
    payload_example = {
        "senderAddress": "kakasi@daou.co.kr",
        "senderName": "Easy WBS | send-only",
        "title": "Jira 주간 업무 리포트",
        "body": "", # HTML 파일 내용으로 대체됨
        "recipients": [
            {
                "address": "yoonsm@daou.co.kr",
                "name": "팀원",
                "type": "R"
            }
        ],
        "individual": True,
        "advertising": False
    }

    # HTML 리포트 파일 경로
    # (테스트용으로 가장 최근 생성된 리포트 파일 사용 권장)
    target_html = r"d:\Dev\AI_workspace\project\jiraReport\reports\2025-12-10\조민기_AIReport.html"

    print("📧 HTML 메일 발송 시도 중...")
    status, text = send_mail_html(ACCESS_KEY, SECRET_KEY, payload_example, html_file_path=target_html)
    
    if status == 201:
        print(f"✅ 메일 발송 성공 (Status: {status})")
    else:
        print(f"❌ 메일 발송 실패 (Status: {status})")
        print(f"응답 내용: {text}")
