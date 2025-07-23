from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
from typing import List, Optional, Dict, Any
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

# 복잡한 센서 데이터를 위한 새로운 모델
class ComplexSensorData(BaseModel):
    timestamp: str
    sensors: Dict[str, float]
    fault_status: Optional[Dict[str, Any]] = None
    predictions: Optional[Dict[str, Any]] = None
    topic: str

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
    
    # 초기 설비 데이터 (유압 및 제조 설비 추가)
    initial_equipment = [
        ("press_001", "프레스기 #001", "정상", 98.2, "프레스", "2024-01-15"),
        ("press_002", "프레스기 #002", "주의", 78.5, "프레스", "2024-01-10"),
        ("weld_001", "용접기 #001", "정상", 89.3, "용접", "2024-01-12"),
        ("weld_002", "용접기 #002", "오류", 0.0, "용접", "2024-01-08"),
        ("assemble_001", "조립기 #001", "정상", 96.1, "조립", "2024-01-14"),
        ("inspect_001", "검사기 #001", "오류", 0.0, "검사", "2024-01-05"),
        ("hydraulic", "유압 시스템", "정상", 95.0, "유압", "2024-01-20"),
        ("manufacturing", "제조 라인", "정상", 92.0, "제조", "2024-01-18")
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
def post_sensor(data: dict):  # Any 대신 dict로 변경
    """센서 데이터 저장 (단순/복잡 구조 모두 지원)"""
    conn = sqlite3.connect('iot.db')
    c = conn.cursor()
    
    try:
        # 복잡한 구조인지 확인
        if 'sensors' in data and 'topic' in data:
            # ComplexSensorData 형식
            # 각 센서 값을 개별 레코드로 저장
            for sensor_type, value in data['sensors'].items():
                c.execute('''INSERT INTO sensor_data (equipment, sensor_type, value, timestamp) 
                             VALUES (?, ?, ?, ?)''',
                          (data['topic'], sensor_type, value, data['timestamp']))
            
            # 유압 시스템: 고장 상태 처리
            if data['topic'] == 'hydraulic' and data.get('fault_status'):
                if data['fault_status'].get('is_normal') == 0:
                    fault_component = data['fault_status'].get('fault_component')
                    fault_value = data['fault_status'].get('fault_value', 0)
                    normal_value = data['fault_status'].get('component_normal_value', 100)
                    
                    # fault_value를 기반으로 심각도 계산
                    if normal_value > 0 and fault_value is not None:
                        # 정상값과의 차이를 퍼센트로 계산
                        severity = abs((normal_value - fault_value) / normal_value * 100)
                    else:
                        severity = 50  # 기본값
                    
                    # 심각도에 따른 알림 레벨 결정
                    if severity > 80:
                        alert_severity = 'critical'
                    elif severity > 50:
                        alert_severity = 'warning'
                    else:
                        alert_severity = 'info'
                    
                    # 알림 메시지 개선
                    message = f"{fault_component} 고장 감지 (현재값: {fault_value:.1f}, 정상값: {normal_value}, 심각도: {severity:.1f}%)"
                    
                    c.execute('''INSERT INTO alerts (equipment, sensor_type, value, threshold, severity, timestamp, message) 
                                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
                              (data['topic'], fault_component, fault_value, normal_value, alert_severity, 
                               data['timestamp'], message))
                    
                    # 설비 상태 업데이트 - 효율성 계산 수정
                    efficiency = max(0, 100 - severity)
                    status = '오류' if severity > 80 else '주의' if severity > 50 else '정상'
                    c.execute('UPDATE equipment_status SET status = ?, efficiency = ? WHERE id = ?', 
                              (status, efficiency, data['topic']))
            
            # 제조 시스템: 예측 및 이상 감지 처리
            elif data['topic'] == 'manufacturing' and data.get('predictions'):
                # 에너지 이상 감지
                if data['predictions'].get('energy_anomaly'):
                    energy_value = data['sensors'].get('Energy Consumption (kWh)', 0)
                    c.execute('''INSERT INTO alerts (equipment, sensor_type, value, threshold, severity, timestamp, message) 
                                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
                              (data['topic'], 'energy', energy_value, None, 'warning', 
                               data['timestamp'], f"에너지 소비 이상 감지: {energy_value:.2f} kWh"))
                
                # 진동 스파이크 감지
                if data['predictions'].get('vibration_spike'):
                    vibration_value = data['sensors'].get('Vibration Level (mm/s)', 0)
                    c.execute('''INSERT INTO alerts (equipment, sensor_type, value, threshold, severity, timestamp, message) 
                                 VALUES (?, ?, ?, ?, ?, ?, ?)''',
                              (data['topic'], 'vibration', vibration_value, 0.08, 'warning', 
                               data['timestamp'], f"진동 스파이크 감지: {vibration_value:.3f} mm/s"))
                
                # 최적 조건 상태 업데이트
                optimal = data['predictions'].get('optimal_conditions', 0)
                efficiency = 95.0 if optimal else 75.0
                status = '정상' if optimal else '주의'
                c.execute('UPDATE equipment_status SET status = ?, efficiency = ? WHERE id = ?', 
                          (status, efficiency, data['topic']))
            else:
                # 정상 상태일 때도 설비 상태 업데이트
                if data['topic'] in ['hydraulic', 'manufacturing']:
                    if data.get('fault_status', {}).get('is_normal', 1) == 1:
                        # 정상 상태로 업데이트
                        c.execute('UPDATE equipment_status SET status = ?, efficiency = ? WHERE id = ?', 
                                  ('정상', 95.0, data['topic']))
        
        else:
            # 기존 SensorData 형식
            timestamp = data.get('timestamp') or datetime.now().isoformat()
            
            c.execute('''INSERT INTO sensor_data (equipment, sensor_type, value, timestamp) 
                         VALUES (?, ?, ?, ?)''',
                      (data['equipment'], data.get('sensor_type'), data['value'], timestamp))
        
        conn.commit()
        conn.close()
        return {"status": "ok", "message": "센서 데이터가 저장되었습니다."}
        
    except Exception as e:
        conn.close()
        raise HTTPException(status_code=400, detail=f"데이터 처리 오류: {str(e)}")

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
    conn = sqlite3.connect('iot.db')
    c = conn.cursor()
    
    # 제조 데이터에서 품질 점수 추출
    c.execute('''SELECT DATE(timestamp) as date, AVG(value) as avg_quality
                 FROM sensor_data 
                 WHERE equipment = 'manufacturing' AND sensor_type = 'Production Quality Score'
                 GROUP BY DATE(timestamp)
                 ORDER BY date DESC
                 LIMIT 7''')
    
    rows = c.fetchall()
    conn.close()
    
    if rows:
        days = [row[0] for row in reversed(rows)]
        quality_rates = [row[1] for row in reversed(rows)]
    else:
        # 데이터가 없으면 더미 데이터
        days = ['월', '화', '수', '목', '금', '토', '일']
        quality_rates = [98.1, 97.8, 95.5, 99.1, 98.2, 92.3, 94.7]
    
    production_volume = [1200, 1350, 1180, 1420, 1247, 980, 650]
    defect_rates = [100 - q for q in quality_rates]  # 품질률의 역
    
    return {
        'days': days,
        'quality_rates': quality_rates,
        'production_volume': production_volume,
        'defect_rates': defect_rates
    }

@app.get("/api/production_kpi")
def get_production_kpi():
    """대시보드용 생산성 KPI"""
    conn = sqlite3.connect('iot.db')
    c = conn.cursor()
    
    # 최근 데이터에서 KPI 계산
    c.execute('''SELECT AVG(efficiency) FROM equipment_status WHERE type IN ('제조', '유압')''')
    avg_efficiency = c.fetchone()[0] or 87.3
    
    conn.close()
    
    return {
        'daily_target': 1300,
        'daily_actual': 1247,
        'weekly_target': 9100,
        'weekly_actual': 8727,
        'monthly_target': 39000,
        'monthly_actual': 35420,
        'oee': avg_efficiency,
        'availability': 94.2,
        'performance': 92.8,
        'quality': 97.6
    }

# 유압 시스템 전용 엔드포인트
@app.get("/hydraulic")
def get_hydraulic_summary():
    """유압 시스템 요약 정보"""
    conn = sqlite3.connect('iot.db')
    c = conn.cursor()
    
    # 최근 유압 데이터 10개
    c.execute('''SELECT sensor_type, value, timestamp 
                 FROM sensor_data 
                 WHERE equipment = 'hydraulic' 
                 ORDER BY timestamp DESC 
                 LIMIT 10''')
    recent_data = c.fetchall()
    
    # 최근 알림
    c.execute('''SELECT message, severity, timestamp 
                 FROM alerts 
                 WHERE equipment = 'hydraulic' 
                 ORDER BY timestamp DESC 
                 LIMIT 5''')
    recent_alerts = c.fetchall()
    
    # 설비 상태
    c.execute('''SELECT status, efficiency 
                 FROM equipment_status 
                 WHERE id = 'hydraulic' ''')
    equipment_info = c.fetchone()
    
    conn.close()
    
    return {
        "system": "Hydraulic System",
        "status": equipment_info[0] if equipment_info else "Unknown",
        "efficiency": equipment_info[1] if equipment_info else 0,
        "recent_data": [
            {"sensor": row[0], "value": row[1], "time": row[2]} 
            for row in recent_data
        ],
        "recent_alerts": [
            {"message": row[0], "severity": row[1], "time": row[2]} 
            for row in recent_alerts
        ],
        "data_count": len(recent_data)
    }

# 제조 시스템 전용 엔드포인트
@app.get("/manufacturing")
def get_manufacturing_summary():
    """제조 시스템 요약 정보"""
    conn = sqlite3.connect('iot.db')
    c = conn.cursor()
    
    # 최근 제조 데이터 10개
    c.execute('''SELECT sensor_type, value, timestamp 
                 FROM sensor_data 
                 WHERE equipment = 'manufacturing' 
                 ORDER BY timestamp DESC 
                 LIMIT 10''')
    recent_data = c.fetchall()
    
    # 최근 알림
    c.execute('''SELECT message, severity, timestamp 
                 FROM alerts 
                 WHERE equipment = 'manufacturing' 
                 ORDER BY timestamp DESC 
                 LIMIT 5''')
    recent_alerts = c.fetchall()
    
    # 설비 상태
    c.execute('''SELECT status, efficiency 
                 FROM equipment_status 
                 WHERE id = 'manufacturing' ''')
    equipment_info = c.fetchone()
    
    # 주요 메트릭 계산
    energy_values = []
    quality_values = []
    for row in recent_data:
        if row[0] == 'Energy Consumption (kWh)':
            energy_values.append(row[1])
        elif row[0] == 'Production Quality Score':
            quality_values.append(row[1])
    
    conn.close()
    
    return {
        "system": "Manufacturing System",
        "status": equipment_info[0] if equipment_info else "Unknown",
        "efficiency": equipment_info[1] if equipment_info else 0,
        "recent_data": [
            {"sensor": row[0], "value": row[1], "time": row[2]} 
            for row in recent_data
        ],
        "recent_alerts": [
            {"message": row[0], "severity": row[1], "time": row[2]} 
            for row in recent_alerts
        ],
        "metrics": {
            "avg_energy": sum(energy_values) / len(energy_values) if energy_values else 0,
            "avg_quality": sum(quality_values) / len(quality_values) if quality_values else 0,
            "data_count": len(recent_data)
        }
    }

# 헬스체크
@app.get("/health")
def health_check():
    """서버 상태 확인"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)