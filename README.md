# 🏭 POSCO MOBILITY IoT 대시보드

포스코 모빌리티 생산 공정의 실시간 모니터링을 위한 IoT 대시보드 시스템입니다.

## ✨ 주요 기능

### 📊 실시간 모니터링
- **실시간 센서 데이터** - 온도, 압력, 진동 등 다중 센서 데이터 시각화
- **설비 상태 현황** - 6개 설비의 실시간 상태 및 효율성 모니터링
- **KPI 대시보드** - 가동률, 불량률, 생산량 등 핵심 지표 실시간 표시

### 🚨 알림 시스템
- **실시간 알림** - 임계값 초과 시 즉시 알림 팝업
- **알림 처리 관리** - 미처리 → 처리중 → 완료 상태 전환
- **알림 이력** - CSV 다운로드 및 상세 이력 관리

### 🎨 현대적 UI/UX
- **다크 테마** - 클로드 디자인 기반 현대적인 인터페이스
- **반응형 디자인** - 다양한 화면 크기 대응
- **인터랙티브 차트** - Plotly 기반 고급 시각화

### 🔧 고급 기능
- **설비별 상세 정보** - 클릭 시 드릴다운 상세 정보
- **필터링 시스템** - 공정, 설비, 센서 타입별 필터링
- **실시간 데이터 업데이트** - 자동 새로고침 및 캐시 관리

## 🏗️ 시스템 아키텍처

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   IoT 센서      │    │   API 서버      │    │   대시보드      │
│   시뮬레이터     │───▶│   (FastAPI)     │───▶│   (Streamlit)   │
│                 │    │                 │    │                 │
│ • 6개 설비      │    │ • REST API      │    │ • 실시간 차트   │
│ • 10개 센서     │    │ • SQLite DB     │    │ • 알림 관리     │
│ • 실시간 데이터  │    │ • 알림 시스템   │    │ • KPI 대시보드  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚀 설치 및 실행

### 1. 환경 설정
```bash
# 가상환경 생성 (권장)
python -m venv posco_env
source posco_env/bin/activate  # Windows: posco_env\Scripts\activate

# 패키지 설치
pip install -r requirements.txt
```

### 2. 서버 실행

#### API 서버 시작
```bash
python api_server.py
```
- 서버 주소: http://localhost:8000
- API 문서: http://localhost:8000/docs

#### IoT 센서 시뮬레이터 시작 (선택사항)
```bash
python sensor_simulator.py
```
- 실시간 센서 데이터 생성
- 자동 알림 생성
- 5초마다 데이터 업데이트

#### 대시보드 실행
```bash
streamlit run dashboard.py
```
- 대시보드 주소: http://localhost:8501

## 📁 프로젝트 구조

```
PoscoMobility/
├── api_server.py          # FastAPI 서버
├── dashboard.py           # Streamlit 대시보드
├── sensor_simulator.py    # IoT 센서 시뮬레이터
├── iot.db                # SQLite 데이터베이스
├── requirements.txt      # Python 패키지 목록
├── README.md            # 프로젝트 문서
└── templates/           # HTML 템플릿
    └── dashboard.html   # 웹 대시보드 템플릿
```

## 🔌 API 엔드포인트

### 센서 데이터
- `GET /sensors` - 센서 데이터 조회
- `POST /sensors` - 센서 데이터 저장

### 알림 관리
- `GET /alerts` - 알림 목록 조회
- `POST /alerts` - 알림 생성
- `PUT /alerts/{id}/status` - 알림 상태 업데이트

### 설비 관리
- `GET /equipment` - 설비 상태 조회
- `PUT /equipment/{id}/status` - 설비 상태 업데이트

### 대시보드용 API
- `GET /api/sensor_data` - 차트용 센서 데이터
- `GET /api/equipment_status` - 설비 상태 데이터
- `GET /api/quality_trend` - 품질 추세 데이터
- `GET /api/production_kpi` - 생산성 KPI

## 🏭 시뮬레이션 설비

### 프레스 공정
- **프레스기 #001** - 온도, 압력, 진동 센서
- **프레스기 #002** - 온도, 압력, 진동 센서

### 용접 공정
- **용접기 #001** - 온도, 전류, 전압 센서
- **용접기 #002** - 온도, 전류, 전압 센서

### 조립 공정
- **조립기 #001** - 속도, 토크, 위치 센서

### 검사 공정
- **검사기 #001** - 정확도, 속도, 품질 센서

## 📊 센서 임계값

| 센서 타입 | 경고 임계값 | 임계값 초과 | 단위 |
|-----------|-------------|-------------|------|
| 온도 | 70°C | 85°C | °C |
| 압력 | 180 bar | 190 bar | bar |
| 진동 | 1.5 mm/s | 2.0 mm/s | mm/s |
| 전류 | 450A | 480A | A |
| 전압 | 45V | 48V | V |

## 🎯 사용 시나리오

### 1. 실시간 모니터링
1. API 서버 실행: `python api_server.py`
2. 센서 시뮬레이터 실행: `python sensor_simulator.py`
3. 대시보드 실행: `streamlit run dashboard.py`
4. 브라우저에서 http://localhost:8501 접속

### 2. 알림 처리
1. 알림 발생 시 우측 상단 팝업 표시
2. 알림 목록에서 "처리" 버튼 클릭
3. 상태가 "처리중" → "완료"로 변경
4. CSV 다운로드로 이력 관리

### 3. 설비 상세 분석
1. 설비 카드 클릭
2. 상세 정보 및 센서 데이터 차트 확인
3. 성능 지표 및 정비 이력 확인

## 🔧 개발 환경

- **Python**: 3.8+
- **FastAPI**: 0.104.1
- **Streamlit**: 1.28.1
- **SQLite**: 3.x
- **Plotly**: 5.17.0

## 📈 향후 개발 계획

- [ ] AI 예측 모델 연동
- [ ] 실시간 SMS 알림
- [ ] 모바일 앱 개발
- [ ] 다중 공장 지원
- [ ] 고급 분석 기능

## 🤝 기여하기

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다.

## 📞 문의

- **개발팀**: POSCO MOBILITY IoT Team
- **이메일**: iot@poscomobility.com
- **프로젝트**: https://github.com/poscomobility/iot-dashboard
