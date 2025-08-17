# Architecture

## Overview

Streamlit Dashboard ↔ FastAPI ↔ Inference Modules (SVDL abnormal detection, RF RUL) ↔ (optional) SQLite DB

## Components

- **FastAPI** (`app/src/api_server.py`): REST API, inference orchestration
- **Streamlit** (`app/src/dashboard.py`): KPI/알람/예측 시각화
- **Simulator** (`app/src/realtime_simulator.py`): 더미데이터로 실시간 유입
- **SMS Bot** (`app/src/coolsms_bot.py`): 알림 발송(키는 .env 주입)
- **Voice AI** (`app/src/voice_ai.py`): 음성 인터페이스(선택)

## Data Flow

1. `dummy_data/` 또는 `data/` → 2) scaler 전처리 → 3) 모델 추론 → 4) API 응답/알림 → 5) 대시보드 반영

## Models

- **SVDL** (`app/ai_model/abnormal_detec`): inputs: scaled features, outputs: anomaly score / label
- **RF Hydraulic** (`app/ai_model/hydraulic_rf`): inputs: 15 features, outputs: 상태/잔여수명

## Ops Notes

- Secrets via .env
- Ports: API 8000, Dashboard 8501
- Python 3.11 venv, requirements.txt
