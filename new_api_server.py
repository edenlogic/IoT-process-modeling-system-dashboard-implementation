import os
import sqlite3
from fastapi import FastAPI, HTTPException, Request, Query, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, field
import urllib.parse
import re
import requests
import json
import hashlib
import asyncio
import logging
from dotenv import load_dotenv
import uuid
from ayj_ai_service import generate_alert_message, get_action_recommendation, is_ai_enabled

# 로거 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 환경변수 로드
load_dotenv()

# CoolSMS SDK 임포트 추가
try:
    from sdk.api.message import Message
    from sdk.exceptions import CoolsmsException
    COOLSMS_AVAILABLE = True
except ImportError:
    COOLSMS_AVAILABLE = False
    print("⚠️ CoolSMS SDK가 설치되지 않았습니다. SMS 기능이 제한됩니다.")

# CoolSMS 서비스 초기화
if COOLSMS_AVAILABLE and all([os.getenv("COOLSMS_API_KEY"), os.getenv("COOLSMS_API_SECRET"), os.getenv("COOLSMS_SENDER")]):
    coolsms_api = Message(os.getenv("COOLSMS_API_KEY"), os.getenv("COOLSMS_API_SECRET"))
    coolsms_sender = os.getenv("COOLSMS_SENDER")
    print(f"✅ CoolSMS 초기화 완료 - 발신번호: {coolsms_sender}")
else:
    coolsms_api = None
    coolsms_sender = None
    print("❌ CoolSMS 설정이 완료되지 않았습니다. .env 파일을 확인하세요.")

# 환경변수에서 설정 가져오기
DB_PATH = os.getenv('DB_PATH', 'posco_iot.db')
DDL_PATH = os.getenv('DDL_PATH', 'posco_iot_DDL.sql')
ADMIN_PHONE_NUMBERS = [num.strip() for num in os.getenv("ADMIN_PHONE_NUMBERS", "").split(",") if num.strip()]
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")

app = FastAPI(title="POSCO MOBILITY IoT API", version="1.0.0")

# CORS 설정 (모든 Origin 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 템플릿 설정 (대시보드용)
templates = Jinja2Templates(directory="templates")

# 조치 이력 저장소 (메모리 기반 - 실제로는 DB 테이블 추가 필요)
action_history = []

# SMS 세션 저장소 (전화번호별 최근 알림 정보) - CoolSMS 봇과 통신 대신 사용
sms_sessions = {}

# 알림 상태 저장소 (메모리 기반 - DB에 status 컬럼 없어도 작동)
alert_status_memory = {}  # "equipment_sensor_timestamp" -> status

# 중복 방지를 위한 알림 이력
alert_history = {}  # hash_key -> AlertHistory (중복 체크용)
recent_raw_alerts = []  # 최근 원본 알림 저장
notification_cooldown = {}  # 알림별 쿨다운 시간

# 링크 토큰 저장소 (웹 처리용)
action_tokens = {}  # token -> alert_info

# 설정 가능한 파라미터
COOLDOWN_PERIODS = {
    'error': timedelta(seconds=int(os.getenv("ERROR_COOLDOWN_SECONDS", "30"))),  # 30초
    'warning': timedelta(seconds=int(os.getenv("WARNING_COOLDOWN_SECONDS", "60"))),  # 60초
    'info': timedelta(seconds=int(os.getenv("INFO_COOLDOWN_SECONDS", "120")))  # 120초
}
VALUE_CHANGE_THRESHOLD = float(os.getenv("VALUE_CHANGE_THRESHOLD", "0.1"))
MAX_RAW_ALERTS_HISTORY = int(os.getenv("MAX_RAW_ALERTS_HISTORY", "100"))
MAX_ALERTS_IN_MEMORY = int(os.getenv("MAX_ALERTS_IN_MEMORY", "1000"))
CLEANUP_INTERVAL_HOURS = int(os.getenv("CLEANUP_INTERVAL_HOURS", "24"))

# 데이터 모델 정의
class SensorData(BaseModel):
    equipment: str
    sensor_type: Optional[str] = None
    value: float
    timestamp: Optional[str] = None

class AlertData(BaseModel):
    equipment: str
    sensor_type: Optional[str] = None
    value: Optional[float] = None
    threshold: Optional[float] = None
    severity: str
    timestamp: Optional[str] = None
    message: Optional[str] = None
    action_link: Optional[str] = None  # 이 줄 추가

class EquipmentStatus(BaseModel):
    id: str
    name: str
    status: str
    efficiency: float
    type: str
    last_maintenance: str

class SMSWebhookData(BaseModel):
    """CoolSMS 웹훅 데이터"""
    from_: str = None  # 발신자 번호
    to: str = None     # 수신자 번호
    text: str = None   # 메시지 내용
    message_id: str = None

@dataclass
class AlertHistory:
    """알림 이력 관리 (중복 방지용)"""
    alert_hash: str
    equipment: str
    sensor_type: str
    severity: str
    first_occurrence: datetime
    last_occurrence: datetime
    occurrence_count: int = 1
    values: List[float] = field(default_factory=list)
    is_active: bool = True
    last_notification_time: Optional[datetime] = None

# 타임스탬프 정규화 함수
def normalize_timestamp(timestamp: str) -> str:
    """타임스탬프를 초 단위까지만 잘라서 정규화"""
    # ISO 형식에서 초 단위까지만 추출
    match = re.match(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', timestamp)
    if match:
        return match.group(1)
    return timestamp

# 전화번호 정규화 함수
def normalize_phone(phone: str) -> str:
    """전화번호 정규화"""
    if phone.startswith('+82'):
        phone = '0' + phone[3:]
    elif phone.startswith('82'):
        phone = '0' + phone[2:]
    return phone.replace('-', '').replace(' ', '')

# 처리 링크 생성 함수
def generate_action_link(alert_data: dict) -> str:
    """알림 처리용 고유 링크 생성"""
    token = str(uuid.uuid4())
    
    # 토큰과 알림 정보 저장
    action_tokens[token] = {
        "alert_data": alert_data,
        "created_at": datetime.now(),
        "processed": False,
        "expires_at": datetime.now() + timedelta(hours=24)
    }
    
    return f"{PUBLIC_BASE_URL}/action/{token}"

# 중복 체크 함수
def check_duplicate_alert(alert_data: Dict) -> Tuple[bool, str]:
    """알림 중복 체크 - True면 중복(스킵), False면 신규(발송)"""
    
    # 알림 고유 해시 생성
    unique_string = f"{alert_data['equipment']}:{alert_data['sensor_type']}:{alert_data['severity']}"
    hash_key = hashlib.md5(unique_string.encode()).hexdigest()
    
    # 처음 보는 알림인지 확인
    if hash_key not in alert_history:
        # 새로운 알림 타입
        alert_history[hash_key] = AlertHistory(
            alert_hash=hash_key,
            equipment=alert_data['equipment'],
            sensor_type=alert_data['sensor_type'],
            severity=alert_data['severity'],
            first_occurrence=datetime.now(),
            last_occurrence=datetime.now(),
            occurrence_count=1,
            values=[alert_data['value']],
            is_active=True,
            last_notification_time=datetime.now()
        )
        return False, "새로운 알림 타입"
    
    history = alert_history[hash_key]
    now = datetime.now()
    
    # 직전 값과 동일한지 체크 (완화된 조건)
    if history.values and len(history.values) > 0:
        last_value = history.values[-1]
        if abs(alert_data['value'] - last_value) < 0.01:  # 거의 같은 값
            time_since_last = now - history.last_occurrence
            if time_since_last < timedelta(seconds=5):  # 5초 이내 동일값만 스킵
                history.last_occurrence = now
                return True, f"동일한 값 반복 (값: {alert_data['value']})"
    
    # 쿨다운 체크
    if history.last_notification_time:
        cooldown = COOLDOWN_PERIODS.get(alert_data['severity'], timedelta(seconds=30))
        if now - history.last_notification_time < cooldown:
            remaining = int((history.last_notification_time + cooldown - now).total_seconds())
            return True, f"쿨다운 중 (남은시간: {remaining}초)"
    
    # 값 변화율 체크는 더 관대하게
    if history.values and len(history.values) > 1:
        last_value = history.values[-1]
        if last_value != 0:
            change_rate = abs(alert_data['value'] - last_value) / abs(last_value)
            if change_rate < 0.05:  # 5% 미만 변화는 스킵
                return True, f"변화율 미달 ({change_rate*100:.1f}% < 5%)"
    
    # 값 이력 업데이트
    history.last_occurrence = now
    history.occurrence_count += 1
    history.values.append(alert_data['value'])
    history.last_notification_time = now
    history.is_active = True
    
    # 값 이력은 최대 20개까지만 유지
    if len(history.values) > 20:
        history.values = history.values[-20:]
        
    return False, f"새로운 알림 (값: {alert_data['value']})"

def cleanup_old_data():
    """오래된 데이터 정리"""
    now = datetime.now()
    cutoff_time = now - timedelta(hours=CLEANUP_INTERVAL_HOURS)
    
    # 1. 오래된 알림 상태 정리
    keys_to_delete = []
    for key in alert_status_memory:
        try:
            # key: "equipment_sensor_timestamp"
            parts = key.split('_')
            if len(parts) >= 3:
                timestamp_str = parts[-1]
                timestamp = datetime.fromisoformat(timestamp_str)
                if timestamp < cutoff_time:
                    keys_to_delete.append(key)
        except:
            pass
    
    for key in keys_to_delete:
        del alert_status_memory[key]
    
    logger.info(f"알림 상태 정리: {len(keys_to_delete)}개 삭제")
    
    # 2. 만료된 SMS 세션 정리
    expired_phones = []
    for phone, session in sms_sessions.items():
        if datetime.fromisoformat(session['expires_at']) < now:
            expired_phones.append(phone)
    
    for phone in expired_phones:
        del sms_sessions[phone]
    
    logger.info(f"SMS 세션 정리: {len(expired_phones)}개 삭제")
    
    # 3. 오래된 알림 이력 정리 (비활성 상태인 것만)
    history_to_delete = []
    for hash_key, history in alert_history.items():
        if not history.is_active and history.last_occurrence < cutoff_time:
            history_to_delete.append(hash_key)
    
    for hash_key in history_to_delete:
        del alert_history[hash_key]
    
    logger.info(f"알림 이력 정리: {len(history_to_delete)}개 삭제")
    
    # 4. 원본 알림 이력 크기 제한
    if len(recent_raw_alerts) > MAX_RAW_ALERTS_HISTORY:
        recent_raw_alerts[:] = recent_raw_alerts[-MAX_RAW_ALERTS_HISTORY:]
    
    # 5. 메모리 크기 제한 (가장 오래된 것부터 삭제)
    if len(alert_status_memory) > MAX_ALERTS_IN_MEMORY:
        sorted_keys = sorted(alert_status_memory.keys())
        for key in sorted_keys[:len(alert_status_memory) - MAX_ALERTS_IN_MEMORY]:
            del alert_status_memory[key]
    
    # 6. 만료된 액션 토큰 정리
    expired_tokens = []
    for token, data in action_tokens.items():
        if datetime.now() > data["expires_at"]:
            expired_tokens.append(token)
    
    for token in expired_tokens:
        del action_tokens[token]
    
    logger.info(f"액션 토큰 정리: {len(expired_tokens)}개 삭제")
    
    logger.info(f"메모리 정리 완료 - 현재 상태: 알림 {len(alert_status_memory)}개, 세션 {len(sms_sessions)}개")

# 주기적 정리 태스크
async def periodic_cleanup():
    """주기적으로 메모리 정리 실행"""
    while True:
        await asyncio.sleep(3600)  # 1시간마다
        try:
            cleanup_old_data()
        except Exception as e:
            logger.error(f"메모리 정리 중 오류: {e}")

# 원본 알림 중복 체크
def check_duplicate_raw_alert(raw_alert: Dict) -> bool:
    """완전히 동일한 원본 알림인지 확인"""
    alert_signature = {
        'equipment': raw_alert.get('equipment'),
        'sensor_type': raw_alert.get('sensor_type'),
        'value': raw_alert.get('value'),
        'severity': raw_alert.get('severity'),
        'timestamp': raw_alert.get('timestamp')
    }
    
    # 최근 20개 알림과 비교
    for recent in recent_raw_alerts[-20:]:
        if all(recent.get(k) == v for k, v in alert_signature.items()):
            return True  # 완전히 동일한 알림
            
    # 원본 알림 저장
    recent_raw_alerts.append(raw_alert)
    if len(recent_raw_alerts) > MAX_RAW_ALERTS_HISTORY:
        recent_raw_alerts[:] = recent_raw_alerts[-MAX_RAW_ALERTS_HISTORY:]
        
    return False

# DB 초기화 함수 (DDL 적용 및 장비 초기 데이터 삽입)
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # DDL 파일 실행
    with open(DDL_PATH, encoding='utf-8') as f:
        ddl = f.read()
    c.executescript(ddl)
    # 장비 초기 데이터 (16개 설비로 확장)
    initial_equipment = [
        # 프레스기 4대
        ("press_001", "프레스기 #1", "정상", 98.2, "프레스", "2024-01-15"),
        ("press_002", "프레스기 #2", "정상", 95.5, "프레스", "2024-01-10"),
        ("press_003", "프레스기 #3", "정상", 97.1, "프레스", "2024-01-12"),
        ("press_004", "프레스기 #4", "정상", 94.8, "프레스", "2024-01-08"),
        # 용접기 4대
        ("weld_001", "용접기 #1", "정상", 89.3, "용접", "2024-01-12"),
        ("weld_002", "용접기 #2", "정상", 91.7, "용접", "2024-01-08"),
        ("weld_003", "용접기 #3", "정상", 88.5, "용접", "2024-01-10"),
        ("weld_004", "용접기 #4", "정상", 90.2, "용접", "2024-01-14"),
        # 조립기 3대
        ("assemble_001", "조립기 #1", "정상", 96.1, "조립", "2024-01-14"),
        ("assemble_002", "조립기 #2", "정상", 93.8, "조립", "2024-01-11"),
        ("assemble_003", "조립기 #3", "정상", 95.2, "조립", "2024-01-13"),
        # 검사기 3대
        ("inspect_001", "검사기 #1", "정상", 99.2, "검사", "2024-01-05"),
        ("inspect_002", "검사기 #2", "정상", 98.5, "검사", "2024-01-07"),
        ("inspect_003", "검사기 #3", "정상", 99.8, "검사", "2024-01-09"),
        # 포장기 2대
        ("pack_001", "포장기 #1", "정상", 92.3, "포장", "2024-01-06"),
        ("pack_002", "포장기 #2", "정상", 94.1, "포장", "2024-01-10")
    ]
    c.executemany('''INSERT OR IGNORE INTO equipment_status \
        (id, name, status, efficiency, type, last_maintenance) VALUES (?, ?, ?, ?, ?, ?)''', initial_equipment)
    conn.commit()
    conn.close()

@app.on_event("startup")
async def startup():
    init_db()
    print("="*50)
    print("✅ POSCO IoT FastAPI 서버 시작")
    print(f"📂 DB 경로: {DB_PATH}")
    print(f"📱 CoolSMS 상태: {'활성화' if coolsms_api else '비활성화'}")
    print("🔗 웹 링크 처리 모드 활성화")
    if coolsms_api:
        print(f"📞 발신번호: {coolsms_sender}")
        print(f"👥 관리자: {len(ADMIN_PHONE_NUMBERS)}명")
    print(f"🌐 공개 URL: {PUBLIC_BASE_URL}")
    print("="*50)
    
    # 주기적 정리 태스크 시작
    asyncio.create_task(periodic_cleanup())
    print("🧹 메모리 자동 정리 활성화 (1시간 간격)")
    print(f"⏰ 쿨다운 설정: error {COOLDOWN_PERIODS['error'].seconds}초, warning {COOLDOWN_PERIODS['warning'].seconds}초")

# CoolSMS 봇으로 알림 전달 (웹 링크 포함)
async def notify_coolsms_bot(alert_data: dict):
    """CoolSMS 큐 기반 알림 전달 (웹 링크 포함)"""
    try:
        # 처리 링크 생성
        action_link = generate_action_link(alert_data)
        
        # CoolSMS 봇에 링크 포함하여 전달
        alert_data['action_link'] = action_link
        
        logger.info(f"CoolSMS 큐 시스템으로 알림 전달: {alert_data['equipment']}")
        logger.info(f"알림 내용: {alert_data['sensor_type']} {alert_data['value']:.1f} > {alert_data['threshold']}")
        logger.info(f"처리 링크: {action_link}")
        
    except Exception as e:
        logger.error(f"CoolSMS 알림 처리 오류: {e}")

# 간단한 처리 페이지 (GET)
@app.get("/action/{token}", response_class=HTMLResponse)
async def show_action_page(token: str):
    """처리 페이지 표시"""
    
    # 토큰 확인
    token_data = action_tokens.get(token)
    if not token_data:
        return """
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>처리 오류</title>
        </head>
        <body style="font-family: Arial; padding: 20px; text-align: center;">
            <h2>❌ 유효하지 않은 링크입니다</h2>
            <p>링크가 만료되었거나 잘못된 접근입니다.</p>
        </body>
        </html>
        """
    
    # 만료 확인
    if datetime.now() > token_data["expires_at"]:
        del action_tokens[token]
        return """
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>링크 만료</title>
        </head>
        <body style="font-family: Arial; padding: 20px; text-align: center;">
            <h2>⏰ 링크가 만료되었습니다</h2>
            <p>24시간이 경과하여 처리할 수 없습니다.</p>
        </body>
        </html>
        """
    
    # 이미 처리됨
    if token_data["processed"]:
        return """
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>처리 완료</title>
        </head>
        <body style="font-family: Arial; padding: 20px; text-align: center;">
            <h2>✅ 이미 처리되었습니다</h2>
            <p>이 알림은 이미 처리 완료되었습니다.</p>
        </body>
        </html>
        """
    
    # 알림 정보 추출
    alert = token_data["alert_data"]
    
    # 센서 타입 한글 변환
    sensor_map = {
        'temperature': '온도',
        'pressure': '압력',
        'vibration': '진동',
        'power': '전력'
    }
    sensor_ko = sensor_map.get(alert['sensor_type'], alert['sensor_type'])
    
    # 처리 페이지 HTML
    html_content = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>알림 처리</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                padding: 20px;
                max-width: 400px;
                margin: 0 auto;
                background-color: #f5f5f5;
            }}
            .container {{
                background: white;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            }}
            h2 {{
                color: #333;
                margin-bottom: 20px;
            }}
            .alert-info {{
                background: #f0f0f0;
                padding: 15px;
                border-radius: 5px;
                margin-bottom: 20px;
            }}
            .info-row {{
                margin: 5px 0;
            }}
            .label {{
                font-weight: bold;
                color: #666;
            }}
            .value {{
                color: #333;
            }}
            .severity-error {{
                color: #d32f2f;
                font-weight: bold;
            }}
            .severity-warning {{
                color: #f57c00;
                font-weight: bold;
            }}
            .actions {{
                margin-top: 30px;
            }}
            .btn {{
                display: block;
                width: 100%;
                padding: 15px;
                margin: 10px 0;
                font-size: 18px;
                font-weight: bold;
                text-align: center;
                text-decoration: none;
                border-radius: 5px;
                cursor: pointer;
                border: none;
            }}
            .btn-interlock {{
                background: #d32f2f;
                color: white;
            }}
            .btn-bypass {{
                background: #10b981;
                color: white;
            }}
            .btn:hover {{
                opacity: 0.9;
            }}
            .time {{
                text-align: center;
                color: #666;
                font-size: 14px;
                margin-top: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h2>🚨 설비 알림 처리</h2>
            
            <div class="alert-info">
                <div class="info-row">
                    <span class="label">설비:</span>
                    <span class="value">{alert['equipment']}</span>
                </div>
                <div class="info-row">
                    <span class="label">센서:</span>
                    <span class="value">{sensor_ko}</span>
                </div>
                <div class="info-row">
                    <span class="label">측정값:</span>
                    <span class="value">{alert['value']:.1f}</span>
                </div>
                <div class="info-row">
                    <span class="label">임계값:</span>
                    <span class="value">{alert['threshold']:.1f}</span>
                </div>
                <div class="info-row">
                    <span class="label">심각도:</span>
                    <span class="value severity-{alert['severity']}">{alert['severity'].upper()}</span>
                </div>
                <div class="info-row">
                    <span class="label">발생시간:</span>
                    <span class="value">{alert['timestamp']}</span>
                </div>
            </div>
            
            <div class="actions">
                <h3>처리 방법을 선택하세요:</h3>
                <a href="/action/{token}/process?action=interlock" class="btn btn-interlock">
                    1. 인터락 (설비 정지)
                </a>
                <a href="/action/{token}/process?action=bypass" class="btn btn-bypass">
                    2. 바이패스 (계속 운전)
                </a>
            </div>
            
            <div class="time">
                현재시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            </div>
        </div>
    </body>
    </html>
    """
    
    return html_content

# 처리 실행 (GET)
@app.get("/action/{token}/process")
async def process_action(token: str, action: str):
    """실제 처리 실행"""
    
    # 토큰 확인
    token_data = action_tokens.get(token)
    if not token_data or token_data["processed"]:
        return HTMLResponse("""
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>처리 오류</title>
        </head>
        <body style="font-family: Arial; padding: 20px; text-align: center;">
            <h2>❌ 처리할 수 없습니다</h2>
            <p>유효하지 않거나 이미 처리된 요청입니다.</p>
        </body>
        </html>
        """)
    
    # 알림 정보
    alert = token_data["alert_data"]
    
    # 액션 처리
    if action == "interlock":
        # 설비 정지
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('UPDATE equipment_status SET status = ?, efficiency = ? WHERE id = ?', 
                 ("정지", 0.0, alert['equipment']))
        conn.commit()
        conn.close()
        
        action_type = "interlock"
        action_text = "인터락"
        result_emoji = "🔴"
        result_text = "설비가 정지되었습니다"
        
    elif action == "bypass":
        action_type = "bypass"
        action_text = "바이패스"
        result_emoji = "🟢"
        result_text = "설비가 계속 운전됩니다"
    else:
        return HTMLResponse("잘못된 액션입니다")
    
    # 알림 상태 업데이트
    alert_key = f"{alert['equipment']}_{alert['sensor_type']}_{alert['timestamp']}"
    alert_status_memory[alert_key] = action_text
    
    # 조치 이력 저장
    action_record = {
        "action_id": f"action_{len(action_history) + 1}",
        "alert_id": alert_key,
        "equipment": alert['equipment'],
        "sensor_type": alert['sensor_type'],
        "action_type": action_type,
        "action_time": datetime.now().isoformat(),
        "assigned_to": "web_link",
        "value": alert['value'],
        "threshold": alert['threshold'],
        "severity": alert['severity'],
        "status": "completed",
        "message": f"웹 링크로 {action_text} 처리됨"
    }
    action_history.append(action_record)
    
    # 토큰 처리 완료 표시
    token_data["processed"] = True
    token_data["processed_at"] = datetime.now()
    token_data["action"] = action_type
    
    logger.info(f"✅ 웹 링크 처리 완료: {alert['equipment']} → {action_text}")
    
    # 처리 완료 페이지
    html_content = f"""
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>처리 완료</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                padding: 20px;
                max-width: 400px;
                margin: 0 auto;
                background-color: #f5f5f5;
            }}
            .container {{
                background: white;
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                text-align: center;
            }}
            .result-emoji {{
                font-size: 60px;
                margin-bottom: 20px;
            }}
            h2 {{
                color: #333;
                margin-bottom: 10px;
            }}
            .result-text {{
                color: #666;
                font-size: 18px;
                margin-bottom: 30px;
            }}
            .details {{
                background: #f0f0f0;
                padding: 15px;
                border-radius: 5px;
                text-align: left;
                margin-bottom: 20px;
            }}
            .detail-row {{
                margin: 5px 0;
            }}
            .label {{
                font-weight: bold;
                color: #666;
            }}
            .time {{
                color: #999;
                font-size: 14px;
                margin-top: 20px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="result-emoji">{result_emoji}</div>
            <h2>처리 완료</h2>
            <p class="result-text">{result_text}</p>
            
            <div class="details">
                <div class="detail-row">
                    <span class="label">설비:</span> {alert['equipment']}
                </div>
                <div class="detail-row">
                    <span class="label">처리:</span> {action_text}
                </div>
                <div class="detail-row">
                    <span class="label">처리자:</span> 웹 링크
                </div>
                <div class="detail-row">
                    <span class="label">처리시간:</span> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                </div>
            </div>
            
            <p style="color: #666;">이 창은 닫으셔도 됩니다.</p>
            
            <div class="time">
                처리 ID: {action_record['action_id']}
            </div>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(html_content)

# 웹 링크 통계 조회
@app.get("/link_stats")
def get_link_stats():
    """웹 링크 처리 통계"""
    active_links = sum(1 for t in action_tokens.values() if not t["processed"])
    processed_links = sum(1 for t in action_tokens.values() if t["processed"])
    
    # 액션별 통계
    action_stats = {"interlock": 0, "bypass": 0}
    for token_data in action_tokens.values():
        if token_data.get("processed") and token_data.get("action"):
            action_stats[token_data["action"]] = action_stats.get(token_data["action"], 0) + 1
    
    return {
        "total_links": len(action_tokens),
        "active_links": active_links,
        "processed_links": processed_links,
        "action_stats": action_stats,
        "timestamp": datetime.now().isoformat()
    }

# 헬스체크
@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "sms_sessions": len(sms_sessions),
        "action_history": len(action_history),
        "alert_status_memory": len(alert_status_memory),
        "alert_history": len(alert_history),
        "action_tokens": len(action_tokens),
        "web_link_mode": True
    }

# 대시보드 메인 페이지 (HTML)
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

# 센서 데이터 조회 (시뮬레이터/대시보드)
@app.get("/sensors", response_model=List[SensorData])
def get_sensors(equipment: Optional[str] = None, sensor_type: Optional[str] = None, limit: int = 100):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    query = "SELECT equipment, sensor_type, value, timestamp FROM sensor_data"
    params = []
    conditions = []
    if equipment:
        conditions.append("equipment = ?")
        params.append(equipment)
    if sensor_type:
        conditions.append("sensor_type = ?")
        params.append(sensor_type)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return [SensorData(equipment=row[0], sensor_type=row[1], value=row[2], timestamp=row[3]) for row in rows]

# 센서 데이터 저장 (시뮬레이터)
@app.post("/sensors")
def post_sensor(data: SensorData):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    timestamp = data.timestamp or datetime.now().isoformat()
    # 타임스탬프 정규화 (초 단위까지만 저장)
    normalized_timestamp = normalize_timestamp(timestamp)
    c.execute('''INSERT INTO sensor_data (equipment, sensor_type, value, timestamp) \
        VALUES (?, ?, ?, ?)''', (data.equipment, data.sensor_type, data.value, normalized_timestamp))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "센서 데이터가 저장되었습니다."}

# 알림 데이터 조회 (대시보드/시뮬레이터)
@app.get("/alerts", response_model=List[AlertData])
def get_alerts(equipment: Optional[str] = None, severity: Optional[str] = None, status: Optional[str] = None, limit: int = 50):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # DB에는 status 컬럼이 없으므로 제외
    query = "SELECT equipment, sensor_type, value, threshold, severity, timestamp, message FROM alerts"
    params = []
    conditions = []
    if equipment:
        conditions.append("equipment = ?")
        params.append(equipment)
    if severity:
        conditions.append("severity = ?")
        params.append(severity)
    # status 필터는 메모리에서 처리
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit * 2)  # status 필터링을 위해 더 많이 조회
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        # 메모리에서 status 가져오기
        alert_key = f"{row[0]}_{row[1]}_{row[5]}"  # equipment_sensor_timestamp
        alert_status = alert_status_memory.get(alert_key, "미처리")
        
        # status 필터 적용
        if status and alert_status != status:
            continue
            
        # AlertData는 status 필드가 없으므로 제외
        # AlertData 생성
        alert_dict = {
            "equipment": row[0], 
            "sensor_type": row[1], 
            "value": row[2], 
            "threshold": row[3],
            "severity": row[4], 
            "timestamp": row[5], 
            "message": row[6]
        }
        
        # 웹 링크 생성 (미처리 상태인 경우만)
        if alert_status == "미처리":
            alert_dict["action_link"] = generate_action_link(alert_dict)
            
        results.append(AlertData(**alert_dict))
        
        if len(results) >= limit:
            break
            
    return results

# 알림 데이터 저장 (시뮬레이터/AI)
@app.post("/alerts")
async def post_alert(data: AlertData, background_tasks: BackgroundTasks):
    # ===== 여기에 디버그 로그 추가 =====
    logger.info(f"[알람 수신] equipment={data.equipment}, sensor={data.sensor_type}, "
                f"severity={data.severity}, value={data.value}, threshold={data.threshold}")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    timestamp = data.timestamp or datetime.now().isoformat()
    # 타임스탬프 정규화 (초 단위까지만 저장)
    normalized_timestamp = normalize_timestamp(timestamp)
    
    # 원본 알림 중복 체크
    alert_dict = data.dict()
    alert_dict['timestamp'] = normalized_timestamp
    
    if check_duplicate_raw_alert(alert_dict):
        conn.close()
        # ===== 여기에도 디버그 로그 추가 =====
        logger.info(f"[알람 스킵] 원본 중복: {data.equipment}/{data.sensor_type}")
        return {"status": "skipped", "message": "중복 알림 스킵됨", "timestamp": normalized_timestamp}
    
    # 알림 중복 체크 (값 변화, 쿨다운 등)
    is_duplicate, reason = check_duplicate_alert(alert_dict)
    if is_duplicate:
        logger.info(f"알림 스킵: {data.equipment}/{data.sensor_type} - {reason}")
        conn.close()
        return {"status": "filtered", "message": f"알림 필터링됨: {reason}", "timestamp": normalized_timestamp}
    
    # ===== DB 저장 직전 로그 추가 =====
    logger.info(f"[알람 저장] DB에 저장: {data.equipment}/{data.sensor_type} severity={data.severity}")

    # AI 메시지 생성 추가 (이 부분만 추가)
    if not data.message and is_ai_enabled():
        try:
            data.message = await generate_alert_message(data.dict())
        except Exception as e:
            logger.error(f"AI 메시지 생성 실패: {e}")
    
    # DB에 저장
    c.execute('''INSERT INTO alerts (equipment, sensor_type, value, threshold, severity, timestamp, message) \
        VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (data.equipment, data.sensor_type, data.value, data.threshold, data.severity, normalized_timestamp, data.message))
    conn.commit()
    conn.close()
    
    # 메모리에 status 저장
    alert_key = f"{data.equipment}_{data.sensor_type}_{normalized_timestamp}"
    alert_status_memory[alert_key] = "미처리"
    
    # CoolSMS 큐 시스템에 알림 (백그라운드)
    background_tasks.add_task(notify_coolsms_bot, alert_dict)
    
    return {"status": "ok", "message": "알림이 저장되었습니다.", "timestamp": normalized_timestamp}

# 알림 상태 업데이트 (인터락/바이패스 처리 포함)
@app.put("/alerts/{alert_id}/status")
def update_alert_status(
    alert_id: str,
    status: str = Query(...),
    assigned_to: Optional[str] = Query(None),
    action_type: Optional[str] = Query(None)
):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 디버깅 로그
    logger.info(f"[DEBUG] 받은 alert_id: {alert_id}")
    logger.info(f"[DEBUG] status: {status}, assigned_to: {assigned_to}, action_type: {action_type}")
    
    # alert_id 파싱 - equipment_id가 press_001 형태일 수 있음을 고려
    parts = alert_id.split('_')
    equipment = sensor_type = timestamp = None
    alert_info = None
    
    # 설비_번호_센서_타임스탬프 형태 처리
    if len(parts) >= 4:
        # 첫 두 부분이 설비 ID (예: press_001, weld_002, pack_001)
        equipment = f"{parts[0]}_{parts[1]}"
        sensor_type = parts[2]
        timestamp = '_'.join(parts[3:])
        
        # URL 디코딩
        timestamp = urllib.parse.unquote(timestamp)
        logger.info(f"[DEBUG] 파싱된 값 - equipment: {equipment}, sensor_type: {sensor_type}, timestamp: {timestamp}")
        
        # 타임스탬프 정규화 (초 단위까지만)
        normalized_timestamp = normalize_timestamp(timestamp)
        logger.info(f"[DEBUG] 정규화된 timestamp: {normalized_timestamp}")
        
        # 정규화된 타임스탬프로 검색
        c.execute('''SELECT id, value, threshold, severity FROM alerts 
                    WHERE equipment = ? AND sensor_type = ? AND timestamp = ?''',
                 (equipment, sensor_type, normalized_timestamp))
        row = c.fetchone()
        
        if row:
            alert_id_db, value, threshold, severity = row
            alert_info = (value, threshold, severity)
            logger.info(f"[DEBUG] 찾은 알림 ID: {alert_id_db}")
            
            # 상태 업데이트 (메모리에만)
            alert_key = f"{equipment}_{sensor_type}_{normalized_timestamp}"
            alert_status_memory[alert_key] = status
            
            # 조치 이력 저장
            if action_type and equipment:
                action_record = {
                    "action_id": f"action_{len(action_history) + 1}",
                    "alert_id": alert_id,
                    "equipment": equipment,
                    "sensor_type": sensor_type,
                    "action_type": action_type,
                    "action_time": datetime.now().isoformat(),
                    "assigned_to": assigned_to,
                    "value": value,
                    "threshold": threshold,
                    "severity": severity,
                    "status": status
                }
                action_history.append(action_record)
                
                # 인터락인 경우 설비 상태도 업데이트
                if action_type == "interlock":
                    c.execute('UPDATE equipment_status SET status = ?, efficiency = ? WHERE id = ?', 
                             ("정지", 0.0, equipment))
                    logger.info(f"[인터락] {equipment} 설비가 정지되었습니다.")
            
            conn.commit()
            conn.close()
            
            return {
                "status": "ok", 
                "message": f"알림 상태가 '{status}'로 업데이트되었습니다.",
                "action_type": action_type,
                "assigned_to": assigned_to,
                "equipment": equipment
            }
        else:
            # 찾지 못한 경우 디버깅을 위해 유사한 알림 검색
            c.execute('''SELECT id, timestamp FROM alerts 
                        WHERE equipment = ? AND sensor_type = ? 
                        ORDER BY timestamp DESC LIMIT 5''',
                     (equipment, sensor_type))
            similar_rows = c.fetchall()
            logger.info(f"[DEBUG] 유사한 알림들: {similar_rows}")
            
            conn.close()
            raise HTTPException(
                status_code=404, 
                detail=f"알림을 찾을 수 없습니다. equipment={equipment}, sensor_type={sensor_type}, timestamp={normalized_timestamp}"
            )
    elif len(parts) >= 3:
        # 다른 equipment 형태 처리
        # 모든 설비는 "타입_번호" 형태이므로 일관되게 처리
        if len(parts) >= 4:  # 정상적인 형태: 타입_번호_센서_타임스탬프
            equipment = f"{parts[0]}_{parts[1]}"
            sensor_type = parts[2]
            timestamp = '_'.join(parts[3:])
        else:
            # 예외 처리 (기존 호환성)
            equipment = parts[0]
            sensor_type = parts[1]
            timestamp = '_'.join(parts[2:])
        
        # URL 디코딩
        timestamp = urllib.parse.unquote(timestamp)
        logger.info(f"[DEBUG] 파싱된 값 - equipment: {equipment}, sensor_type: {sensor_type}, timestamp: {timestamp}")
        
        # 타임스탬프 정규화
        normalized_timestamp = normalize_timestamp(timestamp)
        
        # 검색 시도
        c.execute('''SELECT id, value, threshold, severity FROM alerts 
                    WHERE equipment = ? AND sensor_type = ? AND timestamp = ?''',
                 (equipment, sensor_type, normalized_timestamp))
        row = c.fetchone()
        
        if row:
            alert_id_db, value, threshold, severity = row
            alert_info = (value, threshold, severity)
            
            # 메모리에만 상태 저장
            alert_key = f"{equipment}_{sensor_type}_{normalized_timestamp}"
            alert_status_memory[alert_key] = status
            
            if action_type and equipment:
                action_record = {
                    "action_id": f"action_{len(action_history) + 1}",
                    "alert_id": alert_id,
                    "equipment": equipment,
                    "sensor_type": sensor_type,
                    "action_type": action_type,
                    "action_time": datetime.now().isoformat(),
                    "assigned_to": assigned_to,
                    "value": value,
                    "threshold": threshold,
                    "severity": severity,
                    "status": status
                }
                action_history.append(action_record)
                
                if action_type == "interlock":
                    c.execute('UPDATE equipment_status SET status = ?, efficiency = ? WHERE id = ?', 
                             ("정지", 0.0, equipment))
            
            conn.commit()
            conn.close()
            
            return {
                "status": "ok", 
                "message": f"알림 상태가 '{status}'로 업데이트되었습니다.",
                "action_type": action_type,
                "assigned_to": assigned_to,
                "equipment": equipment
            }
    else:
        # 기존 방식 (숫자 ID)
        try:
            numeric_id = int(alert_id)
            c.execute('''SELECT equipment, sensor_type, value, threshold, severity, timestamp 
                        FROM alerts WHERE id = ?''', (numeric_id,))
            row = c.fetchone()
            if row:
                equipment, sensor_type, value, threshold, severity, timestamp = row
                alert_info = (value, threshold, severity)
                
                # 메모리에만 상태 저장
                alert_key = f"{equipment}_{sensor_type}_{timestamp}"
                alert_status_memory[alert_key] = status
                
            if row:
                conn.commit()
                conn.close()
                return {
                    "status": "ok", 
                    "message": f"알림 상태가 '{status}'로 업데이트되었습니다.",
                    "equipment": equipment
                }
        except ValueError:
            conn.close()
            raise HTTPException(status_code=400, detail="잘못된 alert_id 형식입니다.")
    
    conn.close()
    raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다.")

# 설비 상태 조회 (대시보드)
@app.get("/equipment", response_model=List[EquipmentStatus])
def get_equipment():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, name, status, efficiency, type, last_maintenance FROM equipment_status')
    rows = c.fetchall()
    conn.close()
    return [EquipmentStatus(
        id=row[0], name=row[1], status=row[2], efficiency=row[3], type=row[4], last_maintenance=row[5]
    ) for row in rows]

# 설비 상태 업데이트 (시뮬레이터)
@app.put("/equipment/{equipment_id}/status")
def update_equipment_status(equipment_id: str, status: str, efficiency: float):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE equipment_status SET status = ?, efficiency = ? WHERE id = ?', (status, efficiency, equipment_id))
    if c.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="설비를 찾을 수 없습니다.")
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "설비 상태가 업데이트되었습니다."}

# 조치 이력 조회
@app.get("/action_history")
def get_action_history(limit: int = 20):
    """인터락/바이패스 조치 이력 조회"""
    logger.info(f"[조치 이력 조회] 현재 {len(action_history)}개의 기록")
    
    # 최신순으로 정렬하여 반환
    sorted_history = sorted(action_history, key=lambda x: x['action_time'], reverse=True)
    result = sorted_history[:limit]
    
    # 디버깅 정보 추가
    if len(result) == 0:
        logger.warning("[조치 이력 조회] ⚠️ 조치 이력이 비어있습니다!")
        logger.info("SMS 응답(1 또는 2) 또는 웹 링크 처리 시 이력이 생성됩니다.")
    else:
        logger.info(f"[조치 이력 조회] 최근 {len(result)}개 반환")
        
    return result

# 조치 통계 조회
@app.get("/action_stats")
def get_action_stats():
    """조치 통계 (인터락/바이패스 횟수 등)"""
    interlock_count = sum(1 for a in action_history if a['action_type'] == 'interlock')
    bypass_count = sum(1 for a in action_history if a['action_type'] == 'bypass')
    
    # 설비별 통계
    equipment_stats = {}
    for action in action_history:
        eq = action['equipment']
        if eq not in equipment_stats:
            equipment_stats[eq] = {'interlock': 0, 'bypass': 0}
        equipment_stats[eq][action['action_type']] += 1
    
    # 처리 방법별 통계
    method_stats = {'sms': 0, 'web_link': 0}
    for action in action_history:
        if action.get('assigned_to', '').startswith('sms_'):
            method_stats['sms'] += 1
        elif action.get('assigned_to') == 'web_link':
            method_stats['web_link'] += 1
    
    return {
        "total_actions": len(action_history),
        "interlock_count": interlock_count,
        "bypass_count": bypass_count,
        "equipment_stats": equipment_stats,
        "method_stats": method_stats,
        "last_action": action_history[-1] if action_history else None
    }

# 조치 이력 POST 엔드포인트 (SMS용)
@app.post("/action_history")
async def create_action_history(data: dict):
    """조치 이력 생성 (CoolSMS에서 호출)"""
    # 디버깅을 위한 로그 추가
    logger.info(f"[조치 이력 생성] 받은 데이터: {data}")
    
    action_record = {
        "action_id": f"action_{len(action_history) + 1}",
        "alert_id": data.get("alert_id"),
        "equipment": data.get("equipment"),
        "sensor_type": data.get("sensor_type"),
        "action_type": data.get("action_type"),
        "action_time": datetime.now().isoformat(),
        "assigned_to": f"sms_{data.get('phone')}",
        "value": data.get("value"),
        "threshold": data.get("threshold"),
        "severity": data.get("severity"),
        "status": "completed",
        "message": data.get("message", ""),
        "alert_number": data.get("alert_number")
    }
    
    action_history.append(action_record)
    
    # 통계 캐시 무효화
    if hasattr(app.state, 'action_stats_cache'):
        app.state.action_stats_cache = None
    
    logger.info(f"[조치 이력] ✅ 생성 완료: {action_record['action_id']} - {action_record['equipment']} {action_record['action_type']}")
    logger.info(f"[조치 이력] 현재 총 {len(action_history)}개의 기록")
    
    return {
        "status": "ok",
        "action_id": action_record["action_id"],
        "message": "조치 이력이 기록되었습니다.",
        "total_records": len(action_history)
    }

# 디버깅용 엔드포인트 추가
@app.get("/debug/action_history")
def debug_action_history():
    """조치 이력 디버깅 정보"""
    return {
        "total_count": len(action_history),
        "memory_address": id(action_history),
        "first_3_records": action_history[:3] if action_history else [],
        "last_3_records": action_history[-3:] if action_history else [],
        "is_empty": len(action_history) == 0,
        "timestamp": datetime.now().isoformat()
    }

# === 대시보드용 조치 이력 API ===
@app.get("/api/action_history")
def get_action_history_dashboard(equipment: Optional[str] = None, limit: int = 50):
    """대시보드용 조치 이력 조회"""
    filtered_history = action_history
    
    if equipment:
        filtered_history = [a for a in action_history if a['equipment'] == equipment]
    
    # 최신순 정렬
    sorted_history = sorted(filtered_history, key=lambda x: x['action_time'], reverse=True)
    
    # 대시보드 표시용 포맷
    formatted_history = []
    for action in sorted_history[:limit]:
        # 센서 타입 한글 변환
        sensor_ko = {
            'temperature': '온도',
            'pressure': '압력',
            'vibration': '진동',
            'power': '전력'
        }.get(action['sensor_type'], action['sensor_type'])
        
        # 처리자 표시
        if action['assigned_to'] == 'web_link':
            operator = "웹 링크"
        elif action['assigned_to'].startswith('sms_'):
            operator = action['assigned_to'].replace('sms_', '')
        else:
            operator = action['assigned_to']
        
        formatted_history.append({
            "time": action['action_time'],
            "equipment": action['equipment'],
            "sensor": sensor_ko,
            "action": "인터락" if action['action_type'] == 'interlock' else "바이패스",
            "value": f"{action['value']:.1f}" if action['value'] else "-",
            "threshold": f"{action['threshold']:.1f}" if action['threshold'] else "-",
            "operator": operator,
            "status": "완료",
            "alert_number": action.get('alert_number', '-')
        })
    
    return formatted_history

# === 기존 대시보드 API 유지 ===

# 대시보드용 센서 데이터 (시간별 집계)
@app.get("/api/sensor_data")
def get_sensor_data(equipment: Optional[str] = None, hours: int = 6):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    since = datetime.now() - timedelta(hours=hours)
    if equipment:
        c.execute('''SELECT sensor_type, value, timestamp FROM sensor_data \
            WHERE equipment = ? AND timestamp >= ? ORDER BY timestamp''', (equipment, since.isoformat()))
    else:
        c.execute('''SELECT sensor_type, value, timestamp FROM sensor_data \
            WHERE timestamp >= ? ORDER BY timestamp''', (since.isoformat(),))
    rows = c.fetchall()
    conn.close()
    temperature = []
    pressure = []
    for row in rows:
        if row[0] == 'temperature':
            temperature.append({'timestamp': row[2], 'value': row[1]})
        elif row[0] == 'pressure':
            pressure.append({'timestamp': row[2], 'value': row[1]})
    return {
        'temperature': temperature,
        'pressure': pressure
    }

# 대시보드용 설비 상태
@app.get("/api/equipment_status")
def get_equipment_status_api():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, name, status, efficiency, type, last_maintenance FROM equipment_status')
    rows = c.fetchall()
    conn.close()
    return [{
        'id': row[0],
        'name': row[1],
        'status': row[2],
        'efficiency': row[3],
        'type': row[4],
        'last_maintenance': row[5]
    } for row in rows]

# 대시보드용 알림 데이터
@app.get("/api/alerts")
def get_alerts_api():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # DB에는 status 컬럼이 없으므로 제외
    c.execute('SELECT equipment, sensor_type, value, threshold, severity, timestamp, message FROM alerts ORDER BY timestamp DESC LIMIT 20')
    rows = c.fetchall()
    conn.close()
    result = []
    for row in rows:
        # 메모리에서 status 가져오기
        alert_key = f"{row[0]}_{row[1]}_{row[5]}"  # equipment_sensor_timestamp
        alert_status = alert_status_memory.get(alert_key, "미처리")
        
        result.append({
            'time': row[5],
            'issue': row[6] or f"{row[0]} {row[1] or ''} 알림",
            'equipment': row[0],
            'severity': row[4],
            'status': alert_status  # 메모리에서 가져온 status
        })
    return result

# 대시보드용 품질 추세 (더미 데이터)
@app.get("/api/quality_trend")
def get_quality_trend():
    days = ['월', '화', '수', '목', '금', '토', '일']
    quality_rates = [98.1, 97.8, 95.5, 99.1, 98.2, 92.3, 94.7]
    production_volume = [1200, 1350, 1180, 1420, 1247, 980, 650]
    defect_rates = [2.1, 1.8, 2.5, 1.9, 2.8, 3.1, 2.2]
    return {
        'days': days,
        'quality_rates': quality_rates,
        'production_volume': production_volume,
        'defect_rates': defect_rates
    }

# 시뮬레이터용 품질 추세 POST 엔드포인트
@app.post("/api/quality_trend")
def post_quality_trend(data: dict):
    return {"status": "ok", "message": "품질 추세 데이터가 업데이트되었습니다."}

# 대시보드용 생산성 KPI (더미 데이터)
@app.get("/api/production_kpi")
def get_production_kpi():
    return {
        'daily_target': 1300,
        'daily_actual': 1247,
        'weekly_target': 9100,
        'weekly_actual': 8727,
        'monthly_target': 39000,
        'monthly_actual': 35420,
        'oee': 87.3,
        'availability': 94.2,
        'performance': 92.8,
        'quality': 97.6
    }

# 시뮬레이터용 생산성 KPI POST 엔드포인트
@app.post("/api/production_kpi")
def post_production_kpi(data: dict):
    return {"status": "ok", "message": "생산성 KPI 데이터가 업데이트되었습니다."}

# 테스트용: 수동 알림 트리거
@app.post("/trigger_alert")
def trigger_test_alert():
    """테스트용 알림 생성"""
    import random
    
    equipment_list = ["press_001", "press_002", "weld_001", "weld_002", "assemble_001"]
    equipment = random.choice(equipment_list)
    sensor_type = random.choice(["temperature", "pressure", "vibration"])
    thresholds = {"temperature": 65.0, "pressure": 1.1, "vibration": 3.0}
    value = thresholds[sensor_type] * random.uniform(1.1, 1.5)
    
    alert = AlertData(
        equipment=equipment,
        sensor_type=sensor_type,
        value=round(value, 2),
        threshold=thresholds[sensor_type],
        severity="error" if value > thresholds[sensor_type] * 1.2 else "warning",
        timestamp=datetime.now().isoformat(),
        message=f"{equipment} {sensor_type} 임계치 초과: {value:.2f}"
    )
    
    # 직접 저장
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    timestamp = alert.timestamp or datetime.now().isoformat()
    normalized_timestamp = normalize_timestamp(timestamp)
    c.execute('''INSERT INTO alerts (equipment, sensor_type, value, threshold, severity, timestamp, message) \
        VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (alert.equipment, alert.sensor_type, alert.value, alert.threshold, alert.severity, normalized_timestamp, alert.message))
    conn.commit()
    conn.close()
    
    # 메모리에 status 저장
    alert_key = f"{alert.equipment}_{alert.sensor_type}_{normalized_timestamp}"
    alert_status_memory[alert_key] = "미처리"
    
    return {"status": "ok", "message": "테스트 알림이 생성되었습니다.", "timestamp": normalized_timestamp}

# 데이터베이스 초기화 (기존 데이터 삭제)
@app.post("/clear_data")
def clear_data():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        # 기존 데이터 삭제
        c.execute('DELETE FROM sensor_data')
        c.execute('DELETE FROM alerts')
        c.execute('DELETE FROM equipment_status')
        
        # 장비 초기 데이터 다시 삽입 (16개 설비)
        initial_equipment = [
            # 프레스기 4대
            ("press_001", "프레스기 #1", "정상", 98.2, "프레스", "2024-01-15"),
            ("press_002", "프레스기 #2", "정상", 95.5, "프레스", "2024-01-10"),
            ("press_003", "프레스기 #3", "정상", 97.1, "프레스", "2024-01-12"),
            ("press_004", "프레스기 #4", "정상", 94.8, "프레스", "2024-01-08"),
            # 용접기 4대
            ("weld_001", "용접기 #1", "정상", 89.3, "용접", "2024-01-12"),
            ("weld_002", "용접기 #2", "정상", 91.7, "용접", "2024-01-08"),
            ("weld_003", "용접기 #3", "정상", 88.5, "용접", "2024-01-10"),
            ("weld_004", "용접기 #4", "정상", 90.2, "용접", "2024-01-14"),
            # 조립기 3대
            ("assemble_001", "조립기 #1", "정상", 96.1, "조립", "2024-01-14"),
            ("assemble_002", "조립기 #2", "정상", 93.8, "조립", "2024-01-11"),
            ("assemble_003", "조립기 #3", "정상", 95.2, "조립", "2024-01-13"),
            # 검사기 3대
            ("inspect_001", "검사기 #1", "정상", 99.2, "검사", "2024-01-05"),
            ("inspect_002", "검사기 #2", "정상", 98.5, "검사", "2024-01-07"),
            ("inspect_003", "검사기 #3", "정상", 99.8, "검사", "2024-01-09"),
            # 포장기 2대
            ("pack_001", "포장기 #1", "정상", 92.3, "포장", "2024-01-06"),
            ("pack_002", "포장기 #2", "정상", 94.1, "포장", "2024-01-10")
        ]
        c.executemany('''INSERT OR IGNORE INTO equipment_status \
            (id, name, status, efficiency, type, last_maintenance) VALUES (?, ?, ?, ?, ?, ?)''', initial_equipment)
        
        conn.commit()
        
        # 메모리 기반 조치 이력도 초기화
        global action_history, sms_sessions, alert_status_memory, alert_history, recent_raw_alerts, action_tokens
        action_history = []
        sms_sessions = {}
        alert_status_memory = {}
        alert_history = {}
        recent_raw_alerts = []
        action_tokens = {}
        
        return {"status": "ok", "message": "데이터베이스가 초기화되었습니다."}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"데이터베이스 초기화 실패: {str(e)}")
    finally:
        conn.close()

# 메모리 상태 조회 API 추가
# 메모리 상태 조회 API 추가
@app.get("/memory_status")
def get_memory_status():
    """현재 메모리 사용 상태 조회"""
    import sys
    
    # 알림 이력 통계
    active_alerts = sum(1 for h in alert_history.values() if h.is_active)
    total_occurrences = sum(h.occurrence_count for h in alert_history.values())
    
    # 액션 토큰 통계
    active_tokens = sum(1 for t in action_tokens.values() if not t["processed"])
    processed_tokens = sum(1 for t in action_tokens.values() if t["processed"])
    
    return {
        "alert_status_count": len(alert_status_memory),
        "sms_session_count": len(sms_sessions),
        "action_history_count": len(action_history),
        "alert_history_count": len(alert_history),
        "active_alerts": active_alerts,
        "total_occurrences": total_occurrences,
        "raw_alerts_count": len(recent_raw_alerts),
        "action_tokens": {
            "total": len(action_tokens),
            "active": active_tokens,
            "processed": processed_tokens
        },
        "estimated_memory_mb": {
            "alert_status": sys.getsizeof(alert_status_memory) / 1024 / 1024,
            "alert_history": sys.getsizeof(alert_history) / 1024 / 1024,
            "action_tokens": sys.getsizeof(action_tokens) / 1024 / 1024,
            "total": (sys.getsizeof(alert_status_memory) + 
                     sys.getsizeof(alert_history) + 
                     sys.getsizeof(sms_sessions) +
                     sys.getsizeof(action_tokens)) / 1024 / 1024
        },
        "cooldown_settings": {
            "error": f"{COOLDOWN_PERIODS['error'].seconds // 60}분",
            "warning": f"{COOLDOWN_PERIODS['warning'].seconds // 60}분",
            "info": f"{COOLDOWN_PERIODS['info'].seconds // 60}분"
        },
        "cleanup_interval": f"{CLEANUP_INTERVAL_HOURS}시간"
    }

# ===== 여기에 AI 엔드포인트 추가 =====
@app.get("/api/ai/recommend-action")
async def get_ai_recommendation(
    equipment: str = Query(...),
    sensor_type: str = Query(...),
    value: float = Query(...),
    threshold: float = Query(...),
    severity: str = Query(...)
):
    """AI 조치 추천 API"""
    if not is_ai_enabled():
        raise HTTPException(status_code=503, detail="AI 기능이 비활성화되어 있습니다")
    
    alert_data = {
        "equipment": equipment,
        "sensor_type": sensor_type,
        "value": value,
        "threshold": threshold,
        "severity": severity
    }
    
    recommendation = await get_action_recommendation(alert_data)
    return recommendation

# 수동 메모리 정리 API
@app.post("/cleanup_memory")
def manual_cleanup():
    """수동으로 메모리 정리 실행"""
    before_status = {
        "alert_status": len(alert_status_memory),
        "sessions": len(sms_sessions),
        "history": len(alert_history),
        "raw_alerts": len(recent_raw_alerts),
        "tokens": len(action_tokens)
    }
    
    cleanup_old_data()
    
    after_status = {
        "alert_status": len(alert_status_memory),
        "sessions": len(sms_sessions),
        "history": len(alert_history),
        "raw_alerts": len(recent_raw_alerts),
        "tokens": len(action_tokens)
    }
    
    return {
        "before": before_status,
        "after": after_status,
        "cleaned": {
            "alert_status": before_status["alert_status"] - after_status["alert_status"],
            "sessions": before_status["sessions"] - after_status["sessions"],
            "history": before_status["history"] - after_status["history"],
            "raw_alerts": before_status["raw_alerts"] - after_status["raw_alerts"],
            "tokens": before_status["tokens"] - after_status["tokens"]
        },
        "timestamp": datetime.now().isoformat()
    }

# 알림 이력 통계 API
@app.get("/alert_statistics")
def get_alert_statistics():
    """알림 통계 정보"""
    stats = {
        'total_alerts': len(alert_status_memory),
        'active_alerts': sum(1 for h in alert_history.values() if h.is_active),
        'unique_alert_types': len(alert_history),
        'equipment_stats': {},
        'severity_stats': {'error': 0, 'warning': 0, 'info': 0}
    }
    
    for history in alert_history.values():
        # 설비별 통계
        if history.equipment not in stats['equipment_stats']:
            stats['equipment_stats'][history.equipment] = {
                'total': 0,
                'active': 0,
                'sensors': set()
            }
        
        stats['equipment_stats'][history.equipment]['total'] += history.occurrence_count
        if history.is_active:
            stats['equipment_stats'][history.equipment]['active'] += 1
        stats['equipment_stats'][history.equipment]['sensors'].add(history.sensor_type)
        
        # 심각도별 통계
        stats['severity_stats'][history.severity] += history.occurrence_count
        
    # set을 리스트로 변환
    for eq in stats['equipment_stats']:
        stats['equipment_stats'][eq]['sensors'] = list(stats['equipment_stats'][eq]['sensors'])
        
    return stats

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)