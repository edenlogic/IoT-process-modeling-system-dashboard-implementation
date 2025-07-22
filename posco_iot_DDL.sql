-- 센서 데이터 테이블
CREATE TABLE IF NOT EXISTS sensor_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment TEXT NOT NULL,
    sensor_type TEXT,
    value REAL NOT NULL,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 알림 이력 테이블
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipment TEXT NOT NULL,
    sensor_type TEXT,
    value REAL,
    threshold REAL,
    severity TEXT NOT NULL,
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
    message TEXT,
    status TEXT DEFAULT '미처리'
);

-- 설비 상태 테이블
CREATE TABLE IF NOT EXISTS equipment_status (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    efficiency REAL NOT NULL,
    type TEXT NOT NULL,
    last_maintenance TEXT
);

-- AI 예측 테이블 (전용)
CREATE TABLE IF NOT EXISTS ai_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sensor_data_id INTEGER,
    prediction_result TEXT,
    prediction_score REAL,
    predicted_at TEXT,
    ai_model_version TEXT,
    FOREIGN KEY(sensor_data_id) REFERENCES sensor_data(id)
);
