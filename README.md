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

### 5. AI 모델 예측 실행 (선택사항)
```bash
# 설비 이상 예측 모델 실행
cd ai_model/abnormal_detec
python run_prediction.py

# 유압 이상 탐지 모델 실행
cd ai_model/hydraulic_rf
python run_prediction.py
```

**참고**: 
- AI 모델 예측 결과는 JSON 파일로 저장되며, 대시보드에서 자동으로 읽어와 표시됩니다.
- 유압 모델은 실제 데이터셋(`hydraulic_processed_data.csv`)에서 샘플을 추출하여 예측합니다.
- 설비 이상 예측 모델은 실제 데이터셋(`ai_modeling_data.csv`)을 기반으로 한 샘플 데이터를 사용합니다.

## 📦 주요 기능

### 🔄 자동 새로고침
- `streamlit-autorefresh` 라이브러리를 사용한 안정적인 자동 새로고침
- 5초, 10초, 15초, 30초, 60초 간격 선택 가능
- 실시간 데이터 연동 시 자동 업데이트

### 📊 실시간 데이터 연동
- 토글 ON: 시뮬레이터에서 생성되는 실시간 데이터 표시
- 토글 OFF: 샘플 데이터 표시
- FastAPI 서버와 직접 연동

### 🤖 AI 예측 시스템
- **설비 이상 예측**: LSTM 모델을 사용한 설비 고장 진단
- **유압 이상 탐지**: Random Forest 모델을 사용한 유압 시스템 이상 탐지
- 실시간 예측 결과를 대시보드에 표시
- 각 클래스별 확률 및 신뢰도 제공

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
- **AI/ML**: PyTorch, Scikit-learn

## 📁 파일 구조

```
posco/
├── dashboard.py              # 메인 대시보드
├── api_server.py            # FastAPI 서버
├── realtime_simulator.py    # 데이터 시뮬레이터
├── posco_iot.db            # SQLite 데이터베이스
├── posco_iot_DDL.sql       # 데이터베이스 스키마
├── requirements.txt         # Python 의존성
├── README.md               # 프로젝트 문서
└── ai_model/               # AI 모델 디렉토리
    ├── abnormal_detec/     # 설비 이상 예측 모델
    │   ├── SVDL_shin.py    # LSTM 모델 정의
    │   ├── run_prediction.py # 예측 실행 스크립트
    │   ├── best_model.pth  # 학습된 모델 가중치
    │   ├── scaler.pkl      # 데이터 스케일러
    │   └── last_prediction.json # 예측 결과
    └── hydraulic_rf/       # 유압 이상 탐지 모델
        ├── hydraulic_predictor_verified.py # Random Forest 모델
        ├── run_prediction.py # 예측 실행 스크립트
        ├── best_model.pkl  # 학습된 모델
        ├── scaler.pkl      # 데이터 스케일러
        └── last_prediction.json # 예측 결과
```
