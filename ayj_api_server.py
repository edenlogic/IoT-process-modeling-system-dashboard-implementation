import os
import sqlite3
from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import urllib.parse
import re

DB_PATH = 'posco_iot.db'
DDL_PATH = 'posco_iot_DDL.sql'

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

class EquipmentStatus(BaseModel):
    id: str
    name: str
    status: str
    efficiency: float
    type: str
    last_maintenance: str

# 타임스탬프 정규화 함수
def normalize_timestamp(timestamp: str) -> str:
    """타임스탬프를 초 단위까지만 잘라서 정규화"""
    # ISO 형식에서 초 단위까지만 추출
    match = re.match(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})', timestamp)
    if match:
        return match.group(1)
    return timestamp

# DB 초기화 함수 (DDL 적용 및 장비 초기 데이터 삽입)
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # DDL 파일 실행
    with open(DDL_PATH, encoding='utf-8') as f:
        ddl = f.read()
    c.executescript(ddl)
    # 장비 초기 데이터
    initial_equipment = [
        ("press_001", "프레스기 #001", "정상", 98.2, "프레스", "2024-01-15"),
        ("press_002", "프레스기 #002", "주의", 78.5, "프레스", "2024-01-10"),
        ("weld_001", "용접기 #001", "정상", 89.3, "용접", "2024-01-12"),
        ("weld_002", "용접기 #002", "오류", 0.0, "용접", "2024-01-08"),
        ("assemble_001", "조립기 #001", "정상", 96.1, "조립", "2024-01-14"),
        ("inspect_001", "검사기 #001", "오류", 0.0, "검사", "2024-01-05")
    ]
    c.executemany('''INSERT OR IGNORE INTO equipment_status \
        (id, name, status, efficiency, type, last_maintenance) VALUES (?, ?, ?, ?, ?, ?)''', initial_equipment)
    conn.commit()
    conn.close()

@app.on_event("startup")
def startup():
    init_db()

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
    query = "SELECT equipment, sensor_type, value, threshold, severity, timestamp, message FROM alerts"
    params = []
    conditions = []
    if equipment:
        conditions.append("equipment = ?")
        params.append(equipment)
    if severity:
        conditions.append("severity = ?")
        params.append(severity)
    if status:
        conditions.append("status = ?")
        params.append(status)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return [AlertData(
        equipment=row[0], sensor_type=row[1], value=row[2], threshold=row[3],
        severity=row[4], timestamp=row[5], message=row[6]
    ) for row in rows]

# 알림 데이터 저장 (시뮬레이터/AI)
@app.post("/alerts")
def post_alert(data: AlertData):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    timestamp = data.timestamp or datetime.now().isoformat()
    # 타임스탬프 정규화 (초 단위까지만 저장)
    normalized_timestamp = normalize_timestamp(timestamp)
    c.execute('''INSERT INTO alerts (equipment, sensor_type, value, threshold, severity, timestamp, message) \
        VALUES (?, ?, ?, ?, ?, ?, ?)''',
        (data.equipment, data.sensor_type, data.value, data.threshold, data.severity, normalized_timestamp, data.message))
    conn.commit()
    conn.close()
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
    print(f"[DEBUG] 받은 alert_id: {alert_id}")
    print(f"[DEBUG] status: {status}, assigned_to: {assigned_to}, action_type: {action_type}")
    
    # alert_id 파싱 - equipment_id가 press_001 형태일 수 있음을 고려
    parts = alert_id.split('_')
    equipment = sensor_type = timestamp = None
    alert_info = None
    
    # press_001_temperature_2025-07-24T20:16:26 형태 처리
    if len(parts) >= 4 and parts[0] == "press":
        equipment = f"{parts[0]}_{parts[1]}"  # press_001
        sensor_type = parts[2]  # temperature
        timestamp = '_'.join(parts[3:])  # 2025-07-24T20:16:26
        
        # URL 디코딩
        timestamp = urllib.parse.unquote(timestamp)
        print(f"[DEBUG] 파싱된 값 - equipment: {equipment}, sensor_type: {sensor_type}, timestamp: {timestamp}")
        
        # 타임스탬프 정규화 (초 단위까지만)
        normalized_timestamp = normalize_timestamp(timestamp)
        print(f"[DEBUG] 정규화된 timestamp: {normalized_timestamp}")
        
        # 정규화된 타임스탬프로 검색
        c.execute('''SELECT id, value, threshold, severity FROM alerts 
                    WHERE equipment = ? AND sensor_type = ? AND timestamp = ?''',
                 (equipment, sensor_type, normalized_timestamp))
        row = c.fetchone()
        
        if row:
            alert_id_db, value, threshold, severity = row
            alert_info = (value, threshold, severity)
            print(f"[DEBUG] 찾은 알림 ID: {alert_id_db}")
            
            # 상태 업데이트
            c.execute('UPDATE alerts SET status = ? WHERE id = ?', (status, alert_id_db))
            
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
                    print(f"[인터락] {equipment} 설비가 정지되었습니다.")
            
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
            print(f"[DEBUG] 유사한 알림들: {similar_rows}")
            
            conn.close()
            raise HTTPException(
                status_code=404, 
                detail=f"알림을 찾을 수 없습니다. equipment={equipment}, sensor_type={sensor_type}, timestamp={normalized_timestamp}"
            )
    elif len(parts) >= 3:
        # 다른 equipment 형태 처리 (예: weld_001, assemble_001 등)
        equipment = parts[0]
        sensor_type = parts[1]
        timestamp = '_'.join(parts[2:])
        
        # URL 디코딩
        timestamp = urllib.parse.unquote(timestamp)
        print(f"[DEBUG] 파싱된 값 - equipment: {equipment}, sensor_type: {sensor_type}, timestamp: {timestamp}")
        
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
            c.execute('UPDATE alerts SET status = ? WHERE id = ?', (status, alert_id_db))
            
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
                
            c.execute('UPDATE alerts SET status = ? WHERE id = ?', (status, numeric_id))
            
            if c.rowcount > 0:
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
    # 최신순으로 정렬하여 반환
    sorted_history = sorted(action_history, key=lambda x: x['action_time'], reverse=True)
    return sorted_history[:limit]

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
    
    return {
        "total_actions": len(action_history),
        "interlock_count": interlock_count,
        "bypass_count": bypass_count,
        "equipment_stats": equipment_stats,
        "last_action": action_history[-1] if action_history else None
    }

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
    
    equipment = "press_001"
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
    
    return post_alert(alert)

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
        
        # 장비 초기 데이터 다시 삽입
        initial_equipment = [
            ("press_001", "프레스기 #001", "정상", 98.2, "프레스", "2024-01-15"),
            ("press_002", "프레스기 #002", "주의", 78.5, "프레스", "2024-01-10"),
            ("weld_001", "용접기 #001", "정상", 89.3, "용접", "2024-01-12"),
            ("weld_002", "용접기 #002", "오류", 0.0, "용접", "2024-01-08"),
            ("assemble_001", "조립기 #001", "정상", 96.1, "조립", "2024-01-14"),
            ("inspect_001", "검사기 #001", "오류", 0.0, "검사", "2024-01-05")
        ]
        c.executemany('''INSERT OR IGNORE INTO equipment_status \
            (id, name, status, efficiency, type, last_maintenance) VALUES (?, ?, ?, ?, ?, ?)''', initial_equipment)
        
        conn.commit()
        
        # 메모리 기반 조치 이력도 초기화
        global action_history
        action_history = []
        
        return {"status": "ok", "message": "데이터베이스가 초기화되었습니다."}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"데이터베이스 초기화 실패: {str(e)}")
    finally:
        conn.close()

# 헬스체크
@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)