from flask import Flask, jsonify, request
import sqlite3

app = Flask(__name__)

# SQLite 연결 및 더미 테이블/데이터 생성 (최초 1회)
def init_db():
    conn = sqlite3.connect('iot.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS sensor_data (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        equipment TEXT,
        value REAL,
        time TEXT
    )''')
    # 샘플 데이터 중복 방지
    c.execute('SELECT COUNT(*) FROM sensor_data')
    if c.fetchone()[0] == 0:
        c.execute('INSERT INTO sensor_data (equipment, value, time) VALUES ("프레스기 A", 52.5, "2025-07-17 15:00")')
        c.execute('INSERT INTO sensor_data (equipment, value, time) VALUES ("용접기 1", 88.7, "2025-07-17 15:00")')
    conn.commit()
    conn.close()


@app.route("/sensors", methods=["GET"])
def get_sensors():
    conn = sqlite3.connect('iot.db')
    c = conn.cursor()
    c.execute("SELECT equipment, value, time FROM sensor_data")
    data = [{"equipment": row[0], "value": row[1], "time": row[2]} for row in c.fetchall()]
    conn.close()
    return jsonify(data)

# POST 예시 (대시보드에서 새 데이터 입력 테스트용)
@app.route("/sensors", methods=["POST"])
def post_sensor():
    data = request.get_json()
    conn = sqlite3.connect('iot.db')
    c = conn.cursor()
    c.execute('INSERT INTO sensor_data (equipment, value, time) VALUES (?, ?, ?)',
              (data["equipment"], data["value"], data["time"]))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

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
    # 중복 방지: 기존 알림 데이터가 없을 때만 샘플 삽입
    c.execute('SELECT COUNT(*) FROM alerts')
    if c.fetchone()[0] == 0:
        c.execute('INSERT INTO alerts (equipment, issue, severity, time) VALUES ("프레스기 B", "온도 임계값 초과", "error", "2025-07-17 15:10")')
        c.execute('INSERT INTO alerts (equipment, issue, severity, time) VALUES ("용접기 1", "비상 정지", "error", "2025-07-17 15:05")')
    conn.commit()
    conn.close()


@app.route("/alerts", methods=["GET"])
def get_alerts():
    conn = sqlite3.connect('iot.db')
    c = conn.cursor()
    c.execute("SELECT equipment, issue, severity, time FROM alerts ORDER BY time DESC")
    data = [{"equipment": row[0], "issue": row[1], "severity": row[2], "time": row[3]} for row in c.fetchall()]
    conn.close()
    return jsonify(data)

@app.route("/alerts", methods=["POST"])
def post_alert():
    data = request.get_json()
    conn = sqlite3.connect('iot.db')
    c = conn.cursor()
    c.execute('INSERT INTO alerts (equipment, issue, severity, time) VALUES (?, ?, ?, ?)',
              (data["equipment"], data["issue"], data["severity"], data["time"]))
    conn.commit()
    conn.close()
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    init_db()
    init_alerts_db()  # 알림 테이블도 초기화
    app.run(port=5001, debug=True)
