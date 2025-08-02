# POSCO MOBILITY IoT 대시보드

POSCO MOBILITY의 IoT 설비 모니터링 및 알림 관리 시스템입니다.

## 🚀 주요 기능

### 📊 실시간 모니터링
- **설비 상태 실시간 추적**: 16개 설비의 상태, 효율, 정비 이력 모니터링
- **센서 데이터 시각화**: 온도, 압력, 진동 등 실시간 센서 데이터 차트
- **AI 분석 결과**: 미리 학습된 모델의 설비 이상 및 유압 시스템 예측 결과
- **품질 관리**: 일별 품질률, 불량률, 생산량 추세 분석

### 🚨 스마트 알림 시스템
- **설비별 사용자 관리**: 각 설비에 담당자 할당 및 관리
- **우선순위 기반 SMS 알림**: 설비 담당자 우선, 일반 구독자 차순
- **중복 알림 방지**: 쿨다운 시스템 및 변화율 기반 필터링
- **웹 링크 처리**: SMS 내 처리 링크로 즉시 조치 가능
- **알림 이력 관리**: 처리 상태 추적 및 통계

### 👥 사용자 관리 시스템
- **설비별 담당자 할당**: 주담당자, 일반 담당자 역할 구분
- **사용자 등록/관리**: 전화번호 기반 사용자 계정 관리
- **알림 구독 설정**: 설비별, 심각도별 알림 구독 관리
- **할당 현황 통계**: 설비별 사용자 할당 현황 대시보드

### 🔧 설비 관리
- **설비 상태 변경**: 실시간 상태 업데이트
- **정비 이력 관리**: 정비 일정 및 이력 추적
- **효율성 분석**: 설비별 가동률 및 성능 분석

## 🏗️ 시스템 아키텍처

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   시뮬레이터    │    │   API 서버      │    │   데이터베이스  │
│   (실시간 데이터)│───▶│   (FastAPI)     │───▶│   (SQLite)      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
                                                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   대시보드      │◀───│   SMS 서비스    │◀───│   AI 분석 결과  │
│   (Streamlit)   │    │   (CoolSMS)     │    │   (정적 데이터) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 실제 데이터 흐름
1. **시뮬레이터** (`realtime_simulator.py`) - 실시간 센서 데이터 생성
2. **API 서버** (`api_server.py`) - 데이터 수집, 처리, 저장
3. **대시보드** (`dashboard.py`) - 데이터 시각화 및 사용자 인터페이스
4. **SMS 봇** (`coolsms_bot.py`) - 알림 모니터링 및 SMS 전송
5. **AI 분석 결과** (`ai_model/`) - 미리 학습된 모델의 정적 예측 결과 표시

## 📋 데이터베이스 스키마

### 핵심 테이블
- **equipment_status**: 설비 상태 및 정보
- **sensor_data**: 실시간 센서 데이터
- **alerts**: 알림/이상 이력
- **users**: 사용자 계정 정보
- **equipment_users**: 설비별 사용자 할당
- **alert_subscriptions**: 알림 구독 설정
- **sms_history**: SMS 전송 이력

## 🔧 설치 및 실행

### 1. 환경 설정
```bash
# 가상환경 생성 및 활성화
conda create -n posco_iot python=3.9
conda activate posco_iot

# 의존성 설치
pip install -r requirements.txt
```

### 2. 환경변수 설정
`.env` 파일을 생성하고 다음 내용을 설정:
```env
# CoolSMS 설정
COOLSMS_API_KEY=your_api_key
COOLSMS_API_SECRET=your_api_secret
COOLSMS_SENDER=your_sender_number

# 서버 설정
PUBLIC_BASE_URL=http://localhost:8000

# 알림 쿨다운 설정 (초)
ERROR_COOLDOWN_SECONDS=30
WARNING_COOLDOWN_SECONDS=60
INFO_COOLDOWN_SECONDS=120
```

### 3. 데이터베이스 초기화
```bash
# API 서버 실행 (자동으로 DB 초기화)
python api_server.py
```

### 4. 서비스 실행
```bash
# 1. API 서버 실행 (백그라운드)
python api_server.py

# 2. 대시보드 실행 (새 터미널)
streamlit run dashboard.py

# 3. 시뮬레이터 실행 (선택사항, 새 터미널)
python realtime_simulator.py

# 4. SMS 봇 실행 (선택사항, 새 터미널)
python coolsms_bot.py
```

**실행 순서**: API 서버 → 대시보드 → (선택) 시뮬레이터 → (선택) SMS 봇

## 📱 SMS 알림 시스템

### 알림 우선순위
1. **설비 담당자**: 해당 설비에 할당된 사용자 (주담당자 우선)
2. **일반 구독자**: 알림 구독 설정이 있는 사용자

### SMS 메시지 형식
```
[POSCO IoT 알림]
설비: press_001
센서: 압력
측정값: 125.5
임계값: 120.0
심각도: ERROR
담당자: 홍길동 (담당자)

처리링크: https://tinyurl.com/xxx
```

### 알림 필터링
- **중복 방지**: 동일한 알림 타입에 대한 쿨다운 적용
- **변화율 체크**: 5% 미만 변화는 스킵
- **값 반복 체크**: 동일한 값 반복 시 스킵

## 👥 사용자 관리

### 설비별 사용자 할당
- **주담당자**: 설비당 1명, 최우선 알림 수신
- **일반 담당자**: 설비당 다수 가능, 보조 알림 수신
- **역할 구분**: 담당자, 관리자, 감시자

### 사용자 등록
1. **설정 → 사용자 관리 → 새 사용자 등록**
2. 필수 정보: 이름, 전화번호
3. 선택 정보: 부서, 권한, 기본 알림 설정

### 설비 할당
1. **설비 관리 → 설비 선택 → 사용자 관리 탭**
2. 사용자 선택 및 역할 지정
3. 주담당자 설정 (선택사항)

## 🔄 API 엔드포인트

### 설비별 사용자 관리
- `GET /equipment/{equipment_id}/users` - 설비별 사용자 조회
- `POST /equipment/{equipment_id}/users` - 사용자 할당
- `PUT /equipment/{equipment_id}/users/{user_id}` - 할당 정보 수정
- `DELETE /equipment/{equipment_id}/users/{user_id}` - 할당 해제

### 사용자 관리
- `GET /users` - 사용자 목록 조회
- `POST /users` - 새 사용자 등록
- `PUT /users/{user_id}` - 사용자 정보 수정
- `DELETE /users/{user_id}` - 사용자 비활성화

### 알림 관리
- `GET /alerts` - 알림 목록 조회
- `POST /alerts` - 새 알림 생성
- `GET /sms/history` - SMS 전송 이력

## 🎯 사용 시나리오

### 1. 설비 이상 발생 시
1. 시뮬레이터에서 이상 데이터 생성
2. API 서버에 알림 생성
3. 설비 담당자에게 우선 SMS 전송
4. 담당자가 웹 링크로 즉시 조치
5. 조치 이력 자동 기록

### 2. 새 사용자 등록 시
1. 관리자가 대시보드에서 사용자 등록
2. 설비별 담당자 할당
3. 알림 구독 설정 자동 적용
4. 해당 설비 알림 수신 시작

### 3. 설비 담당자 변경 시
1. 기존 담당자 할당 해제
2. 새 담당자 할당
3. 주담당자 설정 변경
4. 알림 수신자 자동 업데이트

## 🔧 개발 환경

### 기술 스택
- **Backend**: FastAPI, SQLite
- **Frontend**: Streamlit
- **AI/ML**: scikit-learn, pandas, numpy
- **SMS**: CoolSMS API
- **데이터 시각화**: Plotly, Streamlit Charts

### 파일 구조
```
posco/
├── api_server.py          # FastAPI 서버 (데이터 API, 사용자 관리)
├── dashboard.py           # Streamlit 대시보드 (메인 UI)
├── realtime_simulator.py  # 데이터 시뮬레이터 (센서 데이터 생성)
├── coolsms_bot.py         # SMS 알림 서비스 (CoolSMS 연동)
├── posco_iot_DDL.sql     # 데이터베이스 스키마
├── posco_iot.db          # SQLite 데이터베이스
├── requirements.txt       # 의존성 목록
├── ai_model/             # AI 분석 결과 파일들
│   ├── abnormal_detec/   # 설비 이상 탐지 결과
│   └── hydraulic_rf/     # 유압 이상 탐지 결과
└── README.md             # 프로젝트 문서
```

## 🚀 향후 개선 계획

- [ ] 이메일 알림 기능 추가
- [ ] 모바일 앱 개발
- [ ] 고급 분석 대시보드
- [ ] 예측 정비 스케줄링
- [ ] 다국어 지원
- [ ] 실시간 협업 기능

## 📞 지원 및 문의

- **개발팀**: POSCO MOBILITY IT팀
- **이메일**: it@posco-mobility.com
- **문서**: [내부 위키](https://wiki.posco-mobility.com)

---

© 2024 POSCO MOBILITY. All rights reserved.
