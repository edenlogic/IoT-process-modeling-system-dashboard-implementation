from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
from typing import List

app = FastAPI()

# 데이터 모델
class SensorData(BaseModel):
    equipment: str
    value: float
    time: str

class AlertData(BaseModel):
    equipment: str
    issue: str
    severity: str
    time: str

def init_db():
    conn = sqlite3.connect('iot.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS sensor_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipment TEXT,
        value REAL,
        time TEXT
    )''')
    c.execute('SELECT COUNT(*) FROM sensor_data')
    if c.fetchone()[0] == 0:
        c.execute('INSERT INTO sensor_data (equipment, value, time) VALUES ("프레스기 A", 52.5, "2025-07-17 15:00")')
        c.execute('INSERT INTO sensor_data (equipment, value, time) VALUES ("용접기 1", 88.7, "2025-07-17 15:00")')
    conn.commit()
    conn.close()

def init_alerts_db():
    conn = sqlite3.connect('iot.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipment TEXT,
        issue TEXT,
        severity TEXT,
        time TEXT
    )''')
    c.execute('SELECT COUNT(*) FROM alerts')
    if c.fetchone()[0] == 0:
        c.execute('INSERT INTO alerts (equipment, issue, severity, time) VALUES ("프레스기 B", "온도 임계값 초과", "error", "2025-07-17 15:10")')
        c.execute('INSERT INTO alerts (equipment, issue, severity, time) VALUES ("용접기 1", "비상 정지", "error", "2025-07-17 15:05")')
    conn.commit()
    conn.close()

@app.on_event("startup")
def startup():
    init_db()
    init_alerts_db()

@app.get("/sensors", response_model=List[SensorData])
def get_sensors():
    conn = sqlite3.connect('iot.db')
    c = conn.cursor()
    c.execute("SELECT equipment, value, time FROM sensor_data")
    rows = c.fetchall()
    conn.close()
    return [SensorData(equipment=row[0], value=row[1], time=row[2]) for row in rows]

@app.post("/sensors")
def post_sensor(data: SensorData):
    conn = sqlite3.connect('iot.db')
    c = conn.cursor()
    c.execute('INSERT INTO sensor_data (equipment, value, time) VALUES (?, ?, ?)',
              (data.equipment, data.value, data.time))
    conn.commit()
    conn.close()
    return {"status": "ok"}

@app.get("/alerts", response_model=List[AlertData])
def get_alerts():
    conn = sqlite3.connect('iot.db')
    c = conn.cursor()
    c.execute("SELECT equipment, issue, severity, time FROM alerts ORDER BY time DESC")
    rows = c.fetchall()
    conn.close()
    return [AlertData(equipment=row[0], issue=row[1], severity=row[2], time=row[3]) for row in rows]

@app.post("/alerts")
def post_alert(data: AlertData):
    conn = sqlite3.connect('iot.db')
    c = conn.cursor()
    c.execute('INSERT INTO alerts (equipment, issue, severity, time) VALUES (?, ?, ?, ?)',
              (data.equipment, data.issue, data.severity, data.time))
    conn.commit()
    conn.close()
    return {"status": "ok"}

