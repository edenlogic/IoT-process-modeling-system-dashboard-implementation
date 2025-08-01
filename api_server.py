import os
import sqlite3
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import uvicorn
import hashlib
import uuid
from dataclasses import dataclass, field
import logging
import re

# dotenv 추가
from dotenv import load_dotenv
load_dotenv()

# 로거 설정 추가
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = 'posco_iot.db'
DDL_PATH = 'posco_iot_DDL.sql'

# 환경변수 설정 추가
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
COOLDOWN_PERIODS = {
    'error': timedelta(seconds=int(os.getenv("ERROR_COOLDOWN_SECONDS", "30"))),
    'warning': timedelta(seconds=int(os.getenv("WARNING_COOLDOWN_SECONDS", "60"))),
    'info': timedelta(seconds=int(os.getenv("INFO_COOLDOWN_SECONDS", "120")))
}

app = FastAPI(title="POSCO MOBILITY IoT API", version="1.0.0")

# 전역 변수 추가
action_history = []
alert_history = {}
recent_raw_alerts = []
action_tokens = {}
alert_status_memory = {}

# CORS 설정 (모든 Origin 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    action_link: Optional[str] = None  # 추가

class EquipmentStatus(BaseModel):
    id: str
    name: str
    status: str
    efficiency: float
    type: str
    last_maintenance: str

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

# 유틸리티 함수들
def normalize_timestamp(timestamp: str) -> str:
    """타임스탬프를 초 단위까지만 잘라서 정규화"""
    match = re.match(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', timestamp)
    if match:
        return match.group(1)
    return timestamp

def generate_action_link(alert_data: dict) -> str:
    """알림 처리용 고유 링크 생성"""
    token = str(uuid.uuid4())
    
    action_tokens[token] = {
        "alert_data": alert_data,
        "created_at": datetime.now(),
        "processed": False,
        "expires_at": datetime.now() + timedelta(hours=24)
    }
    
    return f"{PUBLIC_BASE_URL}/action/{token}"

def check_duplicate_alert(alert_data: Dict) -> Tuple[bool, str]:
    """알림 중복 체크 - True면 중복(스킵), False면 신규(발송)"""
    unique_string = f"{alert_data['equipment']}:{alert_data['sensor_type']}:{alert_data['severity']}"
    hash_key = hashlib.md5(unique_string.encode()).hexdigest()
    
    if hash_key not in alert_history:
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
    
    # 직전 값과 동일한지 체크
    if history.values and len(history.values) > 0:
        last_value = history.values[-1]
        if abs(alert_data['value'] - last_value) < 0.01:
            time_since_last = now - history.last_occurrence
            if time_since_last < timedelta(seconds=5):
                history.last_occurrence = now
                return True, f"동일한 값 반복 (값: {alert_data['value']})"
    
    # 쿨다운 체크
    if history.last_notification_time:
        cooldown = COOLDOWN_PERIODS.get(alert_data['severity'], timedelta(seconds=30))
        if now - history.last_notification_time < cooldown:
            remaining = int((history.last_notification_time + cooldown - now).total_seconds())
            return True, f"쿨다운 중 (남은시간: {remaining}초)"
    
    # 값 변화율 체크
    if history.values and len(history.values) > 1:
        last_value = history.values[-1]
        if last_value != 0:
            change_rate = abs(alert_data['value'] - last_value) / abs(last_value)
            if change_rate < 0.05:
                return True, f"변화율 미달 ({change_rate*100:.1f}% < 5%)"
    
    history.last_occurrence = now
    history.occurrence_count += 1
    history.values.append(alert_data['value'])
    history.last_notification_time = now
    history.is_active = True
    
    if len(history.values) > 20:
        history.values = history.values[-20:]
        
    return False, f"새로운 알림 (값: {alert_data['value']})"

# DB 초기화 함수 (DDL 적용 및 장비 초기 데이터 삽입)
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # DDL 파일 실행
    with open(DDL_PATH, encoding='utf-8') as f:
        ddl = f.read()
    c.executescript(ddl)
    # 장비 초기 데이터 (시뮬레이터와 완전히 일치)
    initial_equipment = [
        # 프레스기 4개
        ("press_001", "프레스기 #1", "정상", 98.2, "프레스", "2024-01-15"),
        ("press_002", "프레스기 #2", "정상", 95.5, "프레스", "2024-01-10"),
        ("press_003", "프레스기 #3", "정상", 96.8, "프레스", "2024-01-16"),
        ("press_004", "프레스기 #4", "정상", 94.1, "프레스", "2024-01-17"),
        # 용접기 4개
        ("weld_001", "용접기 #1", "정상", 89.3, "용접", "2024-01-12"),
        ("weld_002", "용접기 #2", "정상", 92.7, "용접", "2024-01-13"),
        ("weld_003", "용접기 #3", "정상", 88.9, "용접", "2024-01-11"),
        ("weld_004", "용접기 #4", "정상", 91.4, "용접", "2024-01-14"),
        # 조립기 3개
        ("assemble_001", "조립기 #1", "정상", 96.1, "조립", "2024-01-14"),
        ("assemble_002", "조립기 #2", "정상", 94.3, "조립", "2024-01-17"),
        ("assemble_003", "조립기 #3", "정상", 97.2, "조립", "2024-01-18"),
        # 검사기 3개
        ("inspect_001", "검사기 #1", "정상", 91.5, "검사", "2024-01-05"),
        ("inspect_002", "검사기 #2", "정상", 93.8, "검사", "2024-01-06"),
        ("inspect_003", "검사기 #3", "정상", 90.2, "검사", "2024-01-07"),
        # 포장기 2개
        ("pack_001", "포장기 #1", "정상", 93.5, "포장", "2024-01-19"),
        ("pack_002", "포장기 #2", "정상", 95.8, "포장", "2024-01-20")
    ]
    c.executemany('''INSERT OR IGNORE INTO equipment_status \
        (id, name, status, efficiency, type, last_maintenance) VALUES (?, ?, ?, ?, ?, ?)''', initial_equipment)
    conn.commit()
    conn.close()

@app.on_event("startup")
def startup():
    init_db()
    # 환경변수 확인 로그 추가
    logger.info("="*50)
    logger.info("환경변수 설정 확인:")
    logger.info(f"PUBLIC_BASE_URL: {PUBLIC_BASE_URL}")
    logger.info(f"ERROR_COOLDOWN: {COOLDOWN_PERIODS['error'].seconds}초")
    logger.info(f"WARNING_COOLDOWN: {COOLDOWN_PERIODS['warning'].seconds}초")
    logger.info(f"INFO_COOLDOWN: {COOLDOWN_PERIODS['info'].seconds}초")
    logger.info("="*50)

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
    c.execute('''INSERT INTO sensor_data (equipment, sensor_type, value, timestamp) \
        VALUES (?, ?, ?, ?)''', (data.equipment, data.sensor_type, data.value, timestamp))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "센서 데이터가 저장되었습니다."}

# 알림 데이터 조회 (대시보드/시뮬레이터) - 수정됨
@app.get("/alerts", response_model=List[AlertData])
def get_alerts(equipment: Optional[str] = None, severity: Optional[str] = None, status: Optional[str] = None, limit: int = 50):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    query = "SELECT equipment, sensor_type, value, threshold, severity, timestamp, message FROM alerts"
    params = []
    conditions = []
    if equipment:
        conditions.append("equipment = ?")
        params.append(equipment)
    if severity:
        conditions.append("severity = ?")
        params.append(severity)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    
    results = []
    for row in rows:
        alert_dict = {
            "equipment": row[0], 
            "sensor_type": row[1], 
            "value": row[2], 
            "threshold": row[3],
            "severity": row[4], 
            "timestamp": row[5], 
            "message": row[6]
        }
        
        # 웹 링크 생성 (error severity만)
        if row[4] == 'error':
            alert_dict["action_link"] = generate_action_link(alert_dict)
            
        results.append(AlertData(**alert_dict))
            
    return results

# 알림 데이터 저장 (시뮬레이터/AI) - 수정됨
@app.post("/alerts")
def post_alert(data: AlertData):
    logger.info(f"[알람 수신] equipment={data.equipment}, sensor={data.sensor_type}, "
                f"severity={data.severity}, value={data.value}, threshold={data.threshold}")
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    timestamp = data.timestamp or datetime.now().isoformat()
    normalized_timestamp = normalize_timestamp(timestamp)
    
    # 중복 체크
    alert_dict = data.dict()
    alert_dict['timestamp'] = normalized_timestamp
    
    is_duplicate, reason = check_duplicate_alert(alert_dict)
    if is_duplicate:
        logger.info(f"알림 스킵: {data.equipment}/{data.sensor_type} - {reason}")
        conn.close()
        return {"status": "filtered", "message": f"알림 필터링됨: {reason}", "timestamp": normalized_timestamp}
    
    logger.info(f"[알람 저장] DB에 저장: {data.equipment}/{data.sensor_type} severity={data.severity}")
    
    c.execute('''INSERT INTO alerts (equipment, sensor_type, value, threshold, severity, timestamp, message) \
        VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (data.equipment, data.sensor_type, data.value, data.threshold, data.severity, normalized_timestamp, data.message))
    conn.commit()
    conn.close()
    
    # 메모리에 status 저장
    alert_key = f"{data.equipment}_{data.sensor_type}_{normalized_timestamp}"
    alert_status_memory[alert_key] = "미처리"
    
    return {"status": "ok", "message": "알림이 저장되었습니다.", "timestamp": normalized_timestamp}

# 알림 상태 업데이트 (처리/미처리 등)
@app.put("/alerts/{alert_id}/status")
def update_alert_status(alert_id: int, status: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE alerts SET status = ? WHERE id = ?', (status, alert_id))
    if c.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다.")
    conn.commit()
    conn.close()
    return {"status": "ok", "message": f"알림 상태가 '{status}'로 업데이트되었습니다."}

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
def update_equipment_status(equipment_id: str, status: str = Query(...), efficiency: float = Query(...)):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 먼저 설비가 존재하는지 확인
    c.execute('SELECT id FROM equipment_status WHERE id = ?', (equipment_id,))
    if not c.fetchone():
        conn.close()
        raise HTTPException(status_code=404, detail=f"설비를 찾을 수 없습니다: {equipment_id}")
    
    c.execute('UPDATE equipment_status SET status = ?, efficiency = ? WHERE id = ?', (status, efficiency, equipment_id))
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "설비 상태가 업데이트되었습니다."}

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
    vibration = []
    for row in rows:
        if row[0] == 'temperature':
            temperature.append({'timestamp': row[2], 'value': row[1]})
        elif row[0] == 'pressure':
            pressure.append({'timestamp': row[2], 'value': row[1]})
        elif row[0] == 'vibration':
            vibration.append({'timestamp': row[2], 'value': row[1]})
    return {
        'temperature': temperature,
        'pressure': pressure,
        'vibration': vibration
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
    c.execute('SELECT equipment, sensor_type, value, threshold, severity, timestamp, message FROM alerts ORDER BY timestamp DESC LIMIT 20')
    rows = c.fetchall()
    conn.close()
    result = []
    for row in rows:
        result.append({
            'time': row[5],
            'issue': row[6] or f"{row[0]} {row[1] or ''} 알림",
            'equipment': row[0],
            'severity': row[4]
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
    # DB에 품질 트렌드 데이터 저장
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        # 기존 품질 트렌드 데이터 삭제
        c.execute('DELETE FROM quality_trend')
        
        # 새로운 데이터 삽입 (JSON 형태로 저장)
        import json
        c.execute('''INSERT INTO quality_trend (days, quality_rates, defect_rates, production_volume, timestamp) 
                    VALUES (?, ?, ?, ?, ?)''', 
                 (json.dumps(data.get('days', [])),
                  json.dumps(data.get('quality_rates', [])),
                  json.dumps(data.get('defect_rates', [])),
                  json.dumps(data.get('production_volume', [])),
                  datetime.now().isoformat()))
        
        conn.commit()
        return {"status": "ok", "message": "품질 추세 데이터가 업데이트되었습니다."}
    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": f"품질 추세 데이터 저장 실패: {str(e)}"}
    finally:
        conn.close()

# 대시보드용 생산성 KPI (DB에서 읽기)
@app.get("/api/production_kpi")
def get_production_kpi():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        # DB에서 KPI 데이터 읽기 (없으면 기본값 반환)
        c.execute('SELECT * FROM production_kpi ORDER BY timestamp DESC LIMIT 1')
        row = c.fetchone()
        
        if row:
            return {
                'daily_target': row[1],
                'daily_actual': row[2],
                'weekly_target': row[3],
                'weekly_actual': row[4],
                'monthly_target': row[5],
                'monthly_actual': row[6],
                'oee': row[7],
                'availability': row[8],
                'performance': row[9],
                'quality': row[10]
            }
        else:
            # 기본값 반환
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
    except Exception as e:
        # 오류 시 기본값 반환
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
    finally:
        conn.close()

# 시뮬레이터용 생산성 KPI POST 엔드포인트
@app.post("/api/production_kpi")
def post_production_kpi(data: dict):
    # DB에 KPI 데이터 저장
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('''INSERT INTO production_kpi 
                    (daily_target, daily_actual, weekly_target, weekly_actual, 
                     monthly_target, monthly_actual, oee, availability, performance, quality, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                 (data.get('daily_target', 1300), data.get('daily_actual', 1247),
                  data.get('weekly_target', 9100), data.get('weekly_actual', 8727),
                  data.get('monthly_target', 39000), data.get('monthly_actual', 35420),
                  data.get('oee', 87.3), data.get('availability', 94.2),
                  data.get('performance', 92.8), data.get('quality', 97.6),
                  datetime.now().isoformat()))
        
        conn.commit()
        return {"status": "ok", "message": "생산성 KPI 데이터가 업데이트되었습니다."}
    except Exception as e:
        conn.rollback()
        return {"status": "error", "message": f"KPI 데이터 저장 실패: {str(e)}"}
    finally:
        conn.close()

# 데이터베이스 초기화 (기존 데이터 삭제) - 수정됨
@app.post("/clear_data")
def clear_data():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        # 모든 테이블 데이터 완전 삭제 (순서 중요)
        c.execute('DELETE FROM alerts')  # 알림 먼저 삭제
        print(f"[API] 알림 데이터 삭제 완료")
        c.execute('DELETE FROM sensor_data')  # 센서 데이터 삭제
        print(f"[API] 센서 데이터 삭제 완료")
        c.execute('DELETE FROM quality_trend')
        c.execute('DELETE FROM production_kpi')
        
        # 설비 상태도 완전히 삭제 후 재생성
        c.execute('DELETE FROM equipment_status')
        
        # 설비 상태 테이블 재생성 및 초기 데이터 삽입
        c.execute('DROP TABLE IF EXISTS equipment_status')
        c.execute('''CREATE TABLE equipment_status (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            status TEXT NOT NULL,
            efficiency REAL NOT NULL,
            type TEXT NOT NULL,
            last_maintenance TEXT NOT NULL
        )''')
        
        # 초기 설비 데이터 삽입 (시뮬레이터와 일치)
        initial_equipment = [
            ("press_001", "프레스기 #1", "정상", 95.0, "프레스", "2024-01-15"),
            ("press_002", "프레스기 #2", "정상", 95.0, "프레스", "2024-01-10"),
            ("press_003", "프레스기 #3", "정상", 95.0, "프레스", "2024-01-16"),
            ("press_004", "프레스기 #4", "정상", 95.0, "프레스", "2024-01-17"),
            ("weld_001", "용접기 #1", "정상", 95.0, "용접", "2024-01-12"),
            ("weld_002", "용접기 #2", "정상", 95.0, "용접", "2024-01-13"),
            ("weld_003", "용접기 #3", "정상", 95.0, "용접", "2024-01-11"),
            ("weld_004", "용접기 #4", "정상", 95.0, "용접", "2024-01-14"),
            ("assemble_001", "조립기 #1", "정상", 95.0, "조립", "2024-01-14"),
            ("assemble_002", "조립기 #2", "정상", 95.0, "조립", "2024-01-17"),
            ("assemble_003", "조립기 #3", "정상", 95.0, "조립", "2024-01-18"),
            ("inspect_001", "검사기 #1", "정상", 95.0, "검사", "2024-01-05"),
            ("inspect_002", "검사기 #2", "정상", 95.0, "검사", "2024-01-06"),
            ("inspect_003", "검사기 #3", "정상", 95.0, "검사", "2024-01-07"),
            ("pack_001", "포장기 #1", "정상", 95.0, "포장", "2024-01-19"),
            ("pack_002", "포장기 #2", "정상", 95.0, "포장", "2024-01-20")
        ]
        c.executemany('''INSERT INTO equipment_status 
            (id, name, status, efficiency, type, last_maintenance) VALUES (?, ?, ?, ?, ?, ?)''', initial_equipment)
        print(f"[API] 설비 데이터 삽입 완료: {len(initial_equipment)}개")
        
        # 테이블 재생성 (스키마 변경 대응)
        c.execute('DROP TABLE IF EXISTS quality_trend')
        c.execute('''CREATE TABLE quality_trend (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            days TEXT,
            quality_rates TEXT,
            defect_rates TEXT,
            production_volume TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )''')
        
        conn.commit()
        
        # 설비 개수 확인
        c.execute('SELECT COUNT(*) FROM equipment_status')
        equipment_count = c.fetchone()[0]
        print(f"[API] 최종 설비 개수 확인: {equipment_count}개")
        
        # 메모리 기반 데이터도 초기화
        global action_history, alert_history, recent_raw_alerts, action_tokens, alert_status_memory
        action_history = []
        alert_history = {}
        recent_raw_alerts = []
        action_tokens = {}
        alert_status_memory = {}
        
        return {"status": "ok", "message": "데이터베이스가 초기화되었습니다. 시뮬레이터를 시작하면 실제 데이터가 들어옵니다."}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"데이터베이스 초기화 실패: {str(e)}")
    finally:
        conn.close()

# 헬스체크
@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

# 대시보드용 통합 엔드포인트
@app.get("/dashboard/data")
async def get_dashboard_data():
    """대시보드용 모든 데이터를 한 번에 반환"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 센서 데이터 조회 (최근 100개)
        cursor.execute("""
            SELECT equipment, sensor_type, value, timestamp 
            FROM sensor_data 
            ORDER BY timestamp DESC 
            LIMIT 100
        """)
        sensor_results = cursor.fetchall()
        
        # 설비 상태 조회
        cursor.execute("SELECT id, name, status, efficiency, type, last_maintenance FROM equipment_status")
        equipment_results = cursor.fetchall()
        
        # 알림 데이터 조회 (최근 50개)
        cursor.execute("SELECT equipment, severity, message, timestamp FROM alerts ORDER BY timestamp DESC LIMIT 50")
        alerts_results = cursor.fetchall()
        
        conn.close()
        
        # 센서 데이터 변환
        sensor_data = {'temperature': [], 'pressure': [], 'vibration': []}
        for row in sensor_results:
            equipment, sensor_type, value, timestamp = row
            if sensor_type == 'temperature':
                sensor_data['temperature'].append({'timestamp': timestamp, 'value': value})
            elif sensor_type == 'pressure':
                sensor_data['pressure'].append({'timestamp': timestamp, 'value': value})
            elif sensor_type == 'vibration':
                sensor_data['vibration'].append({'timestamp': timestamp, 'value': value})
        
        # 설비 상태 변환
        equipment_status = []
        for row in equipment_results:
            equipment_status.append({
                'id': row[0],
                'name': row[1],
                'status': row[2],
                'efficiency': row[3],
                'type': row[4],
                'last_maintenance': row[5]
            })
        
        # 알림 데이터 변환
        alerts = []
        for row in alerts_results:
            alerts.append({
                'equipment': row[0],
                'severity': row[1],
                'message': row[2],
                'timestamp': row[3]
            })
        
        return {
            "sensors": sensor_data,
            "alerts": alerts,
            "equipment": equipment_status,
            "statistics": {
                "sensor_count": len(sensor_results),
                "alert_count": len(alerts_results),
                "equipment_count": len(equipment_results)
            },
            "timestamp": datetime.now().isoformat(),
            "status": "success"
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "status": "error",
            "timestamp": datetime.now().isoformat()
        }

@app.post("/dashboard/reset")
async def reset_dashboard():
    """대시보드 및 데이터베이스 완전 초기화"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 모든 테이블 데이터 클리어
        cursor.execute("DELETE FROM sensor_data")
        cursor.execute("DELETE FROM alerts")
        cursor.execute("DELETE FROM ai_predictions")
        cursor.execute("DELETE FROM maintenance_history")
        cursor.execute("DELETE FROM audit_logs")
        cursor.execute("DELETE FROM quality_trend")
        cursor.execute("DELETE FROM production_kpi")
        
        # 설비 상태는 초기화하되 기본 데이터는 유지
        cursor.execute("UPDATE equipment_status SET status='정상', efficiency=95.0")
        
        conn.commit()
        conn.close()
        
        return {
            "message": "시스템이 완전히 초기화되었습니다",
            "status": "success",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "error": str(e), 
            "status": "error",
            "timestamp": datetime.now().isoformat()
        }

@app.get("/dashboard/status")
async def get_dashboard_status():
    """대시보드 연결 상태 및 데이터 현황 확인"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 각 테이블의 데이터 개수 확인
        cursor.execute("SELECT COUNT(*) FROM sensor_data")
        sensor_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM alerts")
        alert_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM equipment_status")
        equipment_count = cursor.fetchone()[0]
        
        conn.close()
        
        return {
            "sensor_count": sensor_count,
            "alert_count": alert_count,
            "equipment_count": equipment_count,
            "last_update": datetime.now().isoformat(),
            "status": "connected"
        }
        
    except Exception as e:
        return {
            "error": str(e),
            "status": "disconnected",
            "timestamp": datetime.now().isoformat()
        }

# 웹 링크 처리 엔드포인트들 추가
@app.get("/action/{token}")
async def show_action_page(token: str):
    """처리 페이지 표시"""
    
    token_data = action_tokens.get(token)
    if not token_data:
        return HTMLResponse("""
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
        """)
    
    if datetime.now() > token_data["expires_at"]:
        del action_tokens[token]
        return HTMLResponse("""
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
        """)
    
    if token_data["processed"]:
        return HTMLResponse("""
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
        """)
    
    alert = token_data["alert_data"]
    sensor_map = {
        'temperature': '온도',
        'pressure': '압력',
        'vibration': '진동',
        'power': '전력'
    }
    sensor_ko = sensor_map.get(alert['sensor_type'], alert['sensor_type'])
    
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
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(html_content)

@app.get("/action/{token}/process")
async def process_action(token: str, action: str):
    """실제 처리 실행"""
    
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
    
    alert = token_data["alert_data"]
    
    if action == "interlock":
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
    
    # 조치 이력 저장
    action_record = {
        "action_id": f"action_{len(action_history) + 1}",
        "alert_id": f"{alert['equipment']}_{alert['sensor_type']}_{alert['timestamp']}",
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
    
    token_data["processed"] = True
    token_data["processed_at"] = datetime.now()
    token_data["action"] = action_type
    
    logger.info(f"✅ 웹 링크 처리 완료: {alert['equipment']} → {action_text}")
    
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
        </style>
    </head>
    <body>
        <div class="container">
            <div class="result-emoji">{result_emoji}</div>
            <h2>처리 완료</h2>
            <p class="result-text">{result_text}</p>
            <p style="color: #666;">이 창은 닫으셔도 됩니다.</p>
        </div>
    </body>
    </html>
    """
    
    return HTMLResponse(html_content)

# 조치 이력 관련 엔드포인트들
@app.get("/action_history")
def get_action_history(limit: int = 20):
    """인터락/바이패스 조치 이력 조회"""
    sorted_history = sorted(action_history, key=lambda x: x['action_time'], reverse=True)
    return sorted_history[:limit]

@app.get("/action_stats")
def get_action_stats():
    """조치 통계"""
    interlock_count = sum(1 for a in action_history if a['action_type'] == 'interlock')
    bypass_count = sum(1 for a in action_history if a['action_type'] == 'bypass')
    
    equipment_stats = {}
    for action in action_history:
        eq = action['equipment']
        if eq not in equipment_stats:
            equipment_stats[eq] = {'interlock': 0, 'bypass': 0}
        equipment_stats[eq][action['action_type']] += 1
    
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

@app.get("/link_stats")
def get_link_stats():
    """웹 링크 처리 통계"""
    active_links = sum(1 for t in action_tokens.values() if not t["processed"])
    processed_links = sum(1 for t in action_tokens.values() if t["processed"])
    
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

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)