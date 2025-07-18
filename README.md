# POSCO Mobility IoT 대시보드

## 프로젝트 개요
POSCO Mobility의 IoT 설비 모니터링을 위한 실시간 대시보드입니다.

## 주요 기능
- 실시간 센서 데이터 모니터링 (온도, 압력)
- 설비 상태 실시간 추적
- 이상 알림 시스템
- 품질 추세 분석
- 자동 새로고침 (10초~30분 간격 선택)
- 실제 API 연동 지원

## 기술 스택
- **Frontend**: Streamlit
- **Backend**: FastAPI (`api_server.py`)
- **Data Visualization**: Plotly
- **Data Processing**: Pandas, NumPy
- **API Integration**: Requests

## 설치 방법

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 실행
```bash
streamlit run dashboard.py
```

## 사용 방법

### 사이드바 설정
- **필터**: 공정 및 설비 선택
- **날짜 선택**: 모니터링 기간 설정
- **데이터 소스**: 실제 API / 더미 데이터 토글
- **자동 새로고침**: 10초~30분 간격 선택

### 주요 화면
1. **KPI 카드**: 전체 가동률, 불량률, 알림 수
2. **실시간 센서 데이터**: 온도 및 압력 그래프
3. **설비 상태**: 2x2 그리드 레이아웃
4. **이상 알림**: 실시간 알림 테이블
5. **품질 추세**: 일별 품질률 차트

## API 연동

### 실제 API 사용 시
`dashboard.py`의 `get_alerts_data()` 함수에서 **FastAPI 서버 엔드포인트**를 아래와 같이 설정하세요:

```python
def get_alerts_data():
    response = requests.get('http://localhost:8000/alerts')  # FastAPI 실행 시 기본 주소
    return response.json()

## 보안 및 성능

### CSP (Content Security Policy)
- `.streamlit/config.toml` 파일로 CSP 설정 최적화
- 기업 환경에서 안전한 실행 보장

### 성능 최적화
- 자동 새로고침 간격 조절 가능
- 리소스 효율적인 데이터 처리
- 실시간 모니터링 최적화

## 개발 환경
- Python 3.8+
- Streamlit 1.28.0+
- 모든 의존성은 requirements.txt에 명시

## 라이선스
기업 내부 사용을 위한 프로젝트입니다.
