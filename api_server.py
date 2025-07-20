from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
from typing import List, Optional
import os
from datetime import datetime, timedelta
import json

app = FastAPI(title="POSCO MOBILITY IoT API", version="1.0.0")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 템플릿 설정
templates = Jinja2Templates(directory="templates")

# 데이터 모델
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

def init_db():
    """데이터베이스 초기화"""
    conn = sqlite3.connect('iot.db')
    c = conn.cursor()
    
    # 센서 데이터 테이블
    c.execute('''CREATE TABLE IF NOT EXISTS sensor_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipment TEXT NOT NULL,
        sensor_type TEXT,
        value REAL NOT NULL,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # 알림 테이블
    c.execute('''CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipment TEXT NOT NULL,
        sensor_type TEXT,
        value REAL,
        threshold REAL,
        severity TEXT NOT NULL,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        message TEXT,
        status TEXT DEFAULT '미처리'
    )''')
    
    # 설비 상태 테이블
    c.execute('''CREATE TABLE IF NOT EXISTS equipment_status (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        status TEXT NOT NULL,
        efficiency REAL NOT NULL,
        type TEXT NOT NULL,
        last_maintenance TEXT
    )''')
    
    # 초기 설비 데이터
    initial_equipment = [
        ("press_001", "프레스기 #001", "정상", 98.2, "프레스", "2024-01-15"),
        ("press_002", "프레스기 #002", "주의", 78.5, "프레스", "2024-01-10"),
        ("weld_001", "용접기 #001", "정상", 89.3, "용접", "2024-01-12"),
        ("weld_002", "용접기 #002", "오류", 0.0, "용접", "2024-01-08"),
        ("assemble_001", "조립기 #001", "정상", 96.1, "조립", "2024-01-14"),
        ("inspect_001", "검사기 #001", "오류", 0.0, "검사", "2024-01-05")
    ]
    
    c.executemany('''INSERT OR REPLACE INTO equipment_status 
                     (id, name, status, efficiency, type, last_maintenance) 
                     VALUES (?, ?, ?, ?, ?, ?)''', initial_equipment)
    
    conn.commit()
    conn.close()

@app.on_event("startup")
def startup():
    init_db()

# 웹 페이지 라우트
@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    """메인 대시보드 페이지"""
    return templates.TemplateResponse("dashboard.html", {"request": request})

# 센서 데이터 API
@app.get("/sensors", response_model=List[SensorData])
def get_sensors(equipment: Optional[str] = None, sensor_type: Optional[str] = None, limit: int = 100):
    """센서 데이터 조회"""
    conn = sqlite3.connect('iot.db')
    c = conn.cursor()
    
    query = "SELECT equipment, sensor_type, value, timestamp FROM sensor_data"
    params = []
    
    if equipment or sensor_type:
        query += " WHERE"
        if equipment:
            query += " equipment = ?"
            params.append(equipment)
        if sensor_type:
            if equipment:
                query += " AND"
            query += " sensor_type = ?"
            params.append(sensor_type)
    
    query += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    
    return [SensorData(equipment=row[0], sensor_type=row[1], value=row[2], timestamp=row[3]) for row in rows]

@app.post("/sensors")
def post_sensor(data: SensorData):
    """센서 데이터 저장"""
    conn = sqlite3.connect('iot.db')
    c = conn.cursor()
    
    timestamp = data.timestamp or datetime.now().isoformat()
    
    c.execute('''INSERT INTO sensor_data (equipment, sensor_type, value, timestamp) 
                 VALUES (?, ?, ?, ?)''',
              (data.equipment, data.sensor_type, data.value, timestamp))
    
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "센서 데이터가 저장되었습니다."}

# 알림 API
@app.get("/alerts", response_model=List[AlertData])
def get_alerts(equipment: Optional[str] = None, severity: Optional[str] = None, status: Optional[str] = None, limit: int = 50):
    """알림 데이터 조회"""
    conn = sqlite3.connect('iot.db')
    c = conn.cursor()
    
    query = "SELECT equipment, sensor_type, value, threshold, severity, timestamp, message, status FROM alerts"
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

@app.post("/alerts")
def post_alert(data: AlertData):
    """알림 데이터 저장"""
    conn = sqlite3.connect('iot.db')
    c = conn.cursor()
    
    timestamp = data.timestamp or datetime.now().isoformat()
    
    c.execute('''INSERT INTO alerts (equipment, sensor_type, value, threshold, severity, timestamp, message) 
                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
              (data.equipment, data.sensor_type, data.value, data.threshold, 
               data.severity, timestamp, data.message))
    
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "알림이 저장되었습니다."}

@app.put("/alerts/{alert_id}/status")
def update_alert_status(alert_id: int, status: str):
    """알림 상태 업데이트"""
    conn = sqlite3.connect('iot.db')
    c = conn.cursor()
    
    c.execute('UPDATE alerts SET status = ? WHERE id = ?', (status, alert_id))
    
    if c.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="알림을 찾을 수 없습니다.")
    
    conn.commit()
    conn.close()
    return {"status": "ok", "message": f"알림 상태가 '{status}'로 업데이트되었습니다."}

# 설비 상태 API
@app.get("/equipment", response_model=List[EquipmentStatus])
def get_equipment():
    """설비 상태 조회"""
    conn = sqlite3.connect('iot.db')
    c = conn.cursor()
    
    c.execute('SELECT id, name, status, efficiency, type, last_maintenance FROM equipment_status')
    rows = c.fetchall()
    conn.close()
    
    return [EquipmentStatus(
        id=row[0], name=row[1], status=row[2], efficiency=row[3], 
        type=row[4], last_maintenance=row[5]
    ) for row in rows]

@app.put("/equipment/{equipment_id}/status")
def update_equipment_status(equipment_id: str, status: str, efficiency: float):
    """설비 상태 업데이트"""
    conn = sqlite3.connect('iot.db')
    c = conn.cursor()
    
    c.execute('UPDATE equipment_status SET status = ?, efficiency = ? WHERE id = ?', 
              (status, efficiency, equipment_id))
    
    if c.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="설비를 찾을 수 없습니다.")
    
    conn.commit()
    conn.close()
    return {"status": "ok", "message": "설비 상태가 업데이트되었습니다."}

# 대시보드용 API 라우트들
@app.get("/api/sensor_data")
def get_sensor_data(equipment: Optional[str] = None, hours: int = 6):
    """대시보드용 센서 데이터 (시간별 집계)"""
    conn = sqlite3.connect('iot.db')
    c = conn.cursor()
    
    # 최근 N시간 데이터 조회
    since = datetime.now() - timedelta(hours=hours)
    
    if equipment:
        c.execute('''SELECT sensor_type, value, timestamp FROM sensor_data 
                     WHERE equipment = ? AND timestamp >= ? 
                     ORDER BY timestamp''', (equipment, since.isoformat()))
    else:
        c.execute('''SELECT sensor_type, value, timestamp FROM sensor_data 
                     WHERE timestamp >= ? ORDER BY timestamp''', (since.isoformat(),))
    
    rows = c.fetchall()
    conn.close()
    
    # 데이터 정리
    data = {}
    for row in rows:
        sensor_type = row[0]
        if sensor_type not in data:
            data[sensor_type] = []
        data[sensor_type].append({
            'value': row[1],
            'timestamp': row[2]
        })
    
    return data

@app.get("/api/equipment_status")
def get_equipment_status_api():
    """대시보드용 설비 상태"""
    conn = sqlite3.connect('iot.db')
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

@app.get("/api/quality_trend")
def get_quality_trend():
    """대시보드용 품질 추세"""
    # 실제 데이터가 없으므로 더미 데이터 반환
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

@app.get("/api/production_kpi")
def get_production_kpi():
    """대시보드용 생산성 KPI"""
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

# 헬스체크
@app.get("/health")
def health_check():
    """서버 상태 확인"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

