# POSCO MOBILITY IoT 대시보드

실시간 IoT 센서 데이터 모니터링 및 설비 관리 대시보드입니다.

## 🚀 설치 및 실행

### 시스템 요구사항
- **Python**: 3.10 또는 3.11 (3.13 미지원)
- **OS**: Windows, macOS, Linux

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. API 서버 실행
```bash
python api_server.py
```

### 3. 대시보드 실행
```bash
streamlit run dashboard.py
```

### 4. 시뮬레이터 실행 (선택사항)
```bash
python realtime_simulator.py
```

## 📦 주요 기능

### 🔄 자동 새로고침
- `streamlit-autorefresh` 라이브러리를 사용한 안정적인 자동 새로고침
- 5초, 10초, 15초, 30초, 60초 간격 선택 가능
- 실시간 데이터 연동 시 자동 업데이트

### 📊 실시간 데이터 연동
- 토글 ON: 시뮬레이터에서 생성되는 실시간 데이터 표시
- 토글 OFF: 샘플 데이터 표시
- FastAPI 서버와 직접 연동

### 🚨 알림 시스템
- 실시간 알림 감지 및 팝업 표시
- 설비별 알림 관리
- 처리 상태 업데이트

### 📈 상세 분석
- 일별/월별/기간별 리포트 생성
- 설비별 성능 분석
- CSV 다운로드 기능

## 🔧 기술 스택

- **Frontend**: Streamlit
- **Backend**: FastAPI
- **Database**: SQLite
- **Charts**: Plotly
- **Auto-refresh**: streamlit-autorefresh

## 📁 파일 구조

```
posco/
├── dashboard.py              # 메인 대시보드
├── api_server.py            # FastAPI 서버
├── realtime_simulator.py    # 데이터 시뮬레이터
├── posco_iot.db            # SQLite 데이터베이스
├── posco_iot_DDL.sql       # 데이터베이스 스키마
├── requirements.txt         # Python 의존성
└── README.md               # 프로젝트 문서
```
