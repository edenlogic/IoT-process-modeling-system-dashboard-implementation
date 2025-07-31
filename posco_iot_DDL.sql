-- ======================
-- 설비 상태 테이블
-- (공장 내 설비별 상태, 가동률, 정비일 등 관리)
-- ======================
CREATE TABLE IF NOT EXISTS equipment_status (
    id TEXT PRIMARY KEY,                  -- 설비 고유 ID
    name TEXT NOT NULL,                   -- 설비명(예: 프레스기 #1)
    status TEXT NOT NULL,                 -- 상태(정상, 주의, 오류 등)
    efficiency REAL NOT NULL,             -- 가동률(%)
    type TEXT NOT NULL,                   -- 설비 타입(프레스, 용접 등)
    last_maintenance TEXT                 -- 마지막 정비일
);

-- ======================
-- 센서 데이터 테이블
-- (설비별 센서 측정값 실시간 기록)
-- ======================
CREATE TABLE IF NOT EXISTS sensor_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- 고유번호
    equipment TEXT NOT NULL,              -- 설비명
    sensor_type TEXT,                     -- 센서종류(온도, 압력 등)
    value REAL NOT NULL,                  -- 측정값
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP -- 기록 시각
);

-- ======================
-- 알림/이상 이력 테이블
-- (AI/운영자 알림, 이상징후 기록)
-- ======================
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- 고유번호
    equipment TEXT NOT NULL,              -- 설비명
    sensor_type TEXT,                     -- 센서종류
    value REAL,                           -- 측정값
    threshold REAL,                       -- 임계값(이상 기준)
    severity TEXT NOT NULL,               -- 심각도(error, warning, info 등)
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP, -- 발생 시각
    message TEXT,                         -- 알림 메시지
    status TEXT DEFAULT '미처리'          -- 처리상태(미처리, 처리중, 완료)
);

-- ======================
-- AI 예측 결과 테이블
-- (AI 모델이 분석한 예측 결과/점수/버전 등 저장)
-- ======================
CREATE TABLE IF NOT EXISTS ai_predictions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- 고유번호
    sensor_data_id INTEGER,               -- 원본 센서 데이터(id)
    prediction_result TEXT,               -- 예측 결과(정상/이상 등)
    prediction_score REAL,                -- 신뢰도/점수
    predicted_at TEXT,                    -- 예측 시각
    ai_model_version TEXT,                -- AI 모델 버전
    FOREIGN KEY(sensor_data_id) REFERENCES sensor_data(id)
);

-- ======================
-- 정비이력 테이블 (확장)
-- (설비별 정비 내역/조치 이력/담당자 기록 등)
-- ======================
CREATE TABLE IF NOT EXISTS maintenance_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- 고유번호
    equipment_id TEXT NOT NULL,           -- 설비 ID (equipment_status 참조)
    maintenance_date TEXT NOT NULL,       -- 정비일
    description TEXT,                     -- 정비 내용
    engineer_name TEXT,                   -- 담당자명
    action_taken TEXT,                    -- 조치 상세
    result TEXT,                          -- 결과(정상, 재정비 등)
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(equipment_id) REFERENCES equipment_status(id)
);

-- ======================
-- 로그/감사 기록 테이블 (확장)
-- (데이터 변경, 조회 등 기록/감사 용도)
-- ======================
CREATE TABLE IF NOT EXISTS audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- 고유번호
    user_id TEXT,                         -- 사용자 ID (users 참조)
    action TEXT,                          -- 동작(조회, 등록, 수정, 삭제 등)
    target_table TEXT,                    -- 대상 테이블명
    target_id INTEGER,                    -- 대상 데이터 PK
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP, -- 시각
    details TEXT                          -- 상세 내용/사유 등
);

-- ======================
-- 사용자(계정) 테이블 (확장)
-- (운영자/관리자/담당자 등 계정 관리)
-- ======================
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- 고유번호
    username TEXT UNIQUE NOT NULL,        -- 로그인 ID
    password_hash TEXT NOT NULL,          -- 패스워드(암호화 저장)
    display_name TEXT,                    -- 표시이름
    role TEXT,                            -- 역할(admin, operator 등)
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ======================
-- 품질 트렌드 테이블
-- (일별 품질률, 불량률, 생산량 추세)
-- ======================
CREATE TABLE IF NOT EXISTS quality_trend (
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- 고유번호
    days TEXT,                            -- 요일 배열 JSON (월, 화, 수, ...)
    quality_rates TEXT,                   -- 품질률 배열 JSON
    defect_rates TEXT,                    -- 불량률 배열 JSON
    production_volume TEXT,               -- 생산량 배열 JSON
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);

-- ======================
-- 생산성 KPI 테이블
-- (일일/주간/월간 생산성 지표)
-- ======================
CREATE TABLE IF NOT EXISTS production_kpi (
    id INTEGER PRIMARY KEY AUTOINCREMENT, -- 고유번호
    daily_target INTEGER NOT NULL,        -- 일일 목표
    daily_actual INTEGER NOT NULL,        -- 일일 실적
    weekly_target INTEGER NOT NULL,       -- 주간 목표
    weekly_actual INTEGER NOT NULL,       -- 주간 실적
    monthly_target INTEGER NOT NULL,      -- 월간 목표
    monthly_actual INTEGER NOT NULL,      -- 월간 실적
    oee REAL NOT NULL,                    -- OEE(%)
    availability REAL NOT NULL,           -- 가동률(%)
    performance REAL NOT NULL,            -- 성능률(%)
    quality REAL NOT NULL,                -- 품질률(%)
    timestamp TEXT DEFAULT CURRENT_TIMESTAMP
);
