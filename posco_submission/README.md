# POSCO MOBILITY IoT 플랫폼

**프로젝트명**: POSCO Mobility IoT 플랫폼  
**개발 상태**: 데모 버전 (실제 운영 환경 연동 전 단계)  
**개발 기간**: 2024년 1월 ~ 현재  

## 📋 프로젝트 개요

### 목적
- **제조 설비 IoT 데이터 수집, 실시간 모니터링 및 AI 기반 이상 탐지**
- **SMS 알림 및 사용자/설비 관리 기능 제공**
- **대시보드 UI + 음성 AI 인터페이스 + 시뮬레이터 기반 데모 지원**

### 개발 지연 사유 및 진행 상황
- **담당자 연락 부재**: POSCO MOBILITY 담당자와의 연락이 지연되어 2주간 기업 요청사항만을 기반으로 자의적으로 진행
- **현재 단계**: 발표 시점에는 데모 수준까지만 완성

### 향후 필요 작업
- **기업 세부 공정도 매칭**: 실제 POSCO MOBILITY 공정도와 시스템 연동
- **AI 모델링 튜닝**: 현장 데이터 기반 AI 모델 튜닝

## 🚀 주요 기능

### 📊 실시간 데이터 처리
- **FastAPI 기반 REST API 서버**: 설비 센서 데이터 저장/조회, 알림 데이터 관리
- **SQLite 기반 데이터베이스**: `posco_iot.db` 및 `posco_iot_DDL.sql`
- **실시간 데이터 시뮬레이션**: `realtime_simulator.py`를 통한 가상 설비 데이터 발생

### 🖥️ 대시보드 (Streamlit 기반)
- **설비 현황 시각화**: 16개 설비의 상태, 효율, 정비 이력 모니터링
- **센서 데이터 차트**: 온도, 압력, 진동 등 실시간 센서 데이터 시각화
- **알림 모니터링**: 실시간 알림 현황 및 처리 상태 관리
- **품질 관리**: 일별 품질률, 불량률, 생산량 추세 분석

### 🤖 AI 이상탐지 (데모용)
- **LSTM 기반 기계 고장 진단 모델**: `ai_model/abnormal_detec/` 폴더
- **유압 시스템 전용 이상탐지 모델**: 15개 핵심 피처 기반 (`ai_model/hydraulic_rf/` 폴더)
- **정적 예측 결과 표시**: 현재는 미리 학습된 모델의 결과만 표시 (실시간 학습 미지원)

### 🚨 알림 시스템
- **CoolSMS API 기반 SMS 발송**: `coolsms_bot.py` 모듈
- **알림 구독/설비별 담당자 관리**: 우선순위 기반 알림 전송
- **중복 알림 방지**: 쿨다운 시스템 및 변화율 기반 필터링
- **웹 링크 처리**: SMS 내 처리 링크로 즉시 조치 가능

### 🎤 음성 인터페이스 (데모용)
- **Google Cloud Speech + VertexAI 기반**: 음성 인식 및 대화형 응답
- **음성 AI 어시스턴트**: 음성으로 대시보드 상태 질문 및 AI 응답
- **실시간 분석**: 설비 상태, 알림 현황, KPI 데이터 등 실시간 정보 제공

### 📊 보고서/레포트
- **종합 리포트 생성**: 대시보드 상태 기반 PDF/CSV 보고서
- **7조 과제수행 보고서**: 프로젝트 배경 및 수행 결과 정리 (별도 PDF 파일)

## 🏗️ 시스템 아키텍처

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   시뮬레이터    │    │   API 서버      │    │   데이터베이스  │
│   (데모용)      │───▶│   (FastAPI)     │───▶│   (SQLite)      │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                       │
                                                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   AI 분석 결과  │───▶│   대시보드      │◀───│   SMS 서비스    │
│   (정적 데이터) │    │   (Streamlit)   │    │   (CoolSMS)     │
│   (데모용)      │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

### 실제 데이터 흐름 (데모 환경)
1. **시뮬레이터** (`realtime_simulator.py`) - 가상 센서 데이터 생성
2. **API 서버** (`api_server.py`) - 데이터 수집, 처리, 저장, SMS 알림 전송
3. **대시보드** (`dashboard.py`) - 데이터 시각화 및 사용자 인터페이스
4. **SMS 봇** (`coolsms_bot.py`) - 알림 모니터링 및 웹 링크 포함 SMS 전송
5. **AI 분석 결과** (`ai_model/`) - 미리 학습된 모델의 정적 예측 결과 표시

## 🔧 설치 및 실행

### 1. 환경 설정
```bash
# 저장소 클론
git clone <repo-url>
cd posco

# 가상환경 생성 및 활성화
conda create -n posco python=3.9
conda activate posco

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

# Google Cloud AI 설정 (음성 인식용)
GOOGLE_APPLICATION_CREDENTIALS=./gen-lang-client-0696719372-0f0c03eabd08.json
GOOGLE_CLOUD_PROJECT=gen-lang-client-0696719372
```

### 3. 서비스 실행 (데모 환경)
```bash
# 1. API 서버 실행 (백그라운드)
uvicorn api_server:app --reload --host 0.0.0.0 --port 8000

# 2. 대시보드 실행 (새 터미널)
streamlit run dashboard.py

# 3. 시뮬레이터 실행 (선택사항, 새 터미널)
python realtime_simulator.py

# 4. SMS 봇 실행 (선택사항, 새 터미널)
python coolsms_bot.py
```

**실행 순서**: API 서버 → 대시보드 → (선택) 시뮬레이터 → (선택) SMS 봇

## 🎭 데모 시나리오

### 기본 데모 플로우
1. **시뮬레이터 실행** → 센서 데이터 자동 생성
2. **FastAPI 서버**로 데이터 수집 및 저장
3. **대시보드**에서 실시간 설비 상태 확인
4. **임계값 초과 시 Alert 발생** → SMS 전송 확인
5. **AI 모델**을 통해 정상/이상 상태 예측 확인
6. **음성 인터페이스**를 통해 특정 설비 상태 조회/제어

### 데모 시나리오 예시
1. **설비 이상 발생 시**
   - 시뮬레이터에서 이상 데이터 생성
   - API 서버에 알림 생성
   - 설비 담당자에게 우선 SMS 전송
   - 담당자가 웹 링크로 즉시 조치
   - 조치 이력 자동 기록

2. **새 사용자 등록 시**
   - 관리자가 대시보드에서 사용자 등록
   - 설비별 담당자 할당
   - 알림 구독 설정 자동 적용
   - 해당 설비 알림 수신 시작

3. **음성 AI 인터페이스 테스트**
   - "현재 설비 상태는 어떤가요?"
   - "오늘 생산량은 얼마나 되나요?"
   - "알림이 몇 개나 발생했나요?"

## 📁 폴더 구조 (제출용)

```
📦 posco
 ┣ 📂 ai_model            # AI 모델 (이상탐지, 유압 시스템)
 ┃ ┣ 📂 abnormal_detec    # LSTM 기반 기계 고장 진단 모델
 ┃ ┗ 📂 hydraulic_rf      # 유압 시스템 이상탐지 모델 (15개 핵심 피처)
 ┣ 📂 dummy_data          # 데모용 더미 데이터
 ┣ 📂 .streamlit          # 대시보드 설정
 ┣ 📜 api_server.py       # 메인 API 서버 (FastAPI)
 ┣ 📜 dashboard.py        # Streamlit 대시보드
 ┣ 📜 realtime_simulator.py # 가상 센서 데이터 시뮬레이터
 ┣ 📜 voice_ai.py         # 음성 AI (Google Cloud 연동)
 ┣ 📜 coolsms_bot.py      # SMS 모듈 (CoolSMS API)
 ┣ 📜 requirements.txt    # Python 의존성
 ┣ 📜 README.md           # 기업 제출용 문서
 ┣ 📜 posco_iot.db       # SQLite 데이터베이스
 ┗ 📜 posco_iot_DDL.sql  # 데이터베이스 스키마
```

## 🎯 AI 모델 상세 명세

### 1. 설비 이상 탐지 모델 (`ai_model/abnormal_detec/`)
- **모델 타입**: LSTM (Long Short-Term Memory)
- **학습 데이터**: 설비 센서 시계열 데이터
- **출력**: 정상/이상 확률 (0~1)
- **현재 상태**: 데모용 정적 모델 (실시간 학습 미지원)

### 2. 유압 시스템 이상 탐지 모델 (`ai_model/hydraulic_rf/`)
- **모델 타입**: Random Forest
- **핵심 피처**: 15개 설비 상태 지표
- **출력**: 유압 시스템 이상 여부
- **현재 상태**: 데모용 정적 모델 (실시간 학습 미지원)

### 3. 모델 성능 (데모 환경 기준)
- **정확도**: 85% 이상
- **응답 시간**: < 1초
- **데이터 요구사항**: 정규화된 센서 데이터

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

## 🎤 음성 AI 어시스턴트

### 기능 소개
- **음성 질문**: 마이크를 통해 대시보드 상태에 대한 질문 가능
- **AI 응답**: Gemini AI가 현재 대시보드 데이터를 분석하여 답변
- **실시간 분석**: 설비 상태, 알림 현황, KPI 데이터 등 실시간 정보 제공

### 사용 방법
1. **마이크 권한 허용**: Chrome 브라우저에서 마이크 접근 권한 허용
2. **음성 녹음**: "음성으로 질문하세요" 버튼 클릭 후 질문
3. **음성 분석**: "음성 분석" 버튼으로 음성 인식 시작
4. **AI 응답**: 팝업으로 AI 어시스턴트의 답변 확인

### 예시 질문
- "현재 설비 상태는 어떤가요?"
- "오늘 생산량은 얼마나 되나요?"
- "알림이 몇 개나 발생했나요?"
- "어떤 설비에 문제가 있나요?"

### 설정 요구사항
- **Google Cloud 프로젝트**: `gen-lang-client-0696719372`
- **인증 파일**: `gen-lang-client-0696719372-0f0c03eabd08.json`
- **브라우저**: Chrome 권장 (마이크 권한 지원)
- **Streamlit**: 1.28.0 이상 버전

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
- **Frontend**: Streamlit (1.28.0+)
- **AI/ML**: scikit-learn, pandas, numpy
- **SMS**: CoolSMS API
- **음성 AI**: Google Cloud Speech-to-Text, Vertex AI Gemini
- **데이터 시각화**: Plotly, Streamlit Charts

### 개발 도구
- **IDE**: VS Code, jupyter notebook
- **버전 관리**: Git
- **가상환경**: Conda
- **API 테스트**: Postman, curl


## ⚠️ 주의사항

### 데모 환경 제한사항
- **현재 상태**: 데모 버전으로 실제 운영 환경과는 다름
- **AI 모델**: 정적 모델로 실시간 학습 미지원
- **데이터**: 시뮬레이션 데이터 기반
- **성능**: 개발 환경 기준으로 실제 운영 환경과 차이 있음

### 운영 환경 전환 시 고려사항
- **데이터베이스**: PostgreSQL, MySQL 등 엔터프라이즈급 DB로 전환
- **보안**: 인증/인가 시스템 강화
- **모니터링**: 로깅 및 성능 모니터링 시스템 구축
- **백업**: 데이터 백업 및 복구 시스템 구축

## 📞 지원 및 문의

- **개발팀**: 천안형 글로벌 인재 양성 중급반 7팀
- **팀장 이메일**: ziayo02@gmail.com
- **프로젝트 관리**: https://github.com/edenlogic/IoT-process-modeling-system-dashboard-implementation.git

## 📋 프로젝트 문서

- **README.md**: 현재 문서 (기업 제출용)
- **posco_iot_DDL.sql**: 데이터베이스 스키마 정의
- **requirements.txt**: Python 패키지 의존성 목록

---

