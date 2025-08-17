import streamlit as st
import pandas as pd

# Streamlit 상태 확인
print(f"Streamlit 버전: {st.__version__}")
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import numpy as np
import time
import requests
import json
import io
import base64
import threading
import os
from streamlit_autorefresh import st_autorefresh
import warnings
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import matplotlib.pyplot as plt
import seaborn as sns

# Plotly 경고 무시
warnings.filterwarnings("ignore", category=FutureWarning, module="_plotly_utils")

try:
    from voice_ai import VoiceToText, GeminiAI
    VOICE_AI_AVAILABLE = True
except ImportError:
    VOICE_AI_AVAILABLE = False
    print("음성 AI 모듈을 불러올 수 없습니다.")
    
# 상수 정의
API_BASE_URL = "http://localhost:8000"
API_TIMEOUT = 5  # API 요청 타임아웃 (초)
PPM_TARGET = 300  # PPM 목표값
QUALITY_TARGET = 99.5  # 품질률 목표값 (%)
EFFICIENCY_TARGET = 85.0  # 효율성 목표값 (%)
OEE_TARGET = 85.0  # OEE 목표값 (%)
AVAILABILITY_TARGET = 90.0  # 가동률 목표값 (%)
PERFORMANCE_TARGET = 90.0  # 성능률 목표값 (%)

# 세션 상태 초기화
if 'sensor_container' not in st.session_state:
    st.session_state.sensor_container = None
if 'alert_container' not in st.session_state:
    st.session_state.alert_container = None
if 'equipment_container' not in st.session_state:
    st.session_state.equipment_container = None
if 'last_update' not in st.session_state:
    st.session_state.last_update = time.time()
if 'critical_alerts' not in st.session_state:
    st.session_state.critical_alerts = []
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = datetime.now()
if 'api_toggle_previous' not in st.session_state:
    st.session_state.api_toggle_previous = False

def get_sensor_data_from_api(use_real_api=True):
    """FastAPI에서 센서 데이터 가져오기"""
    if not use_real_api:
        return None
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/sensor_data", timeout=API_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            # API 데이터에 equipment 컬럼이 없는 경우 기본값 추가
            if isinstance(data, list):
                for item in data:
                    if 'equipment' not in item:
                        item['equipment'] = '알 수 없는 설비'
            return data
        else:
            print(f"센서 데이터 API 오류: {response.status_code}")
            return None
    except requests.exceptions.Timeout:
        print("센서 데이터 API 타임아웃")
        return None
    except requests.exceptions.ConnectionError:
        print("센서 데이터 API 연결 실패")
        return None
    except Exception as e:
        print(f"센서 데이터 API 오류: {e}")
        return None

def get_equipment_status_from_api(use_real_api=True):
    """FastAPI에서 설비 상태 데이터 가져오기"""
    if not use_real_api:
        # 토글 OFF 시 더미데이터 반환 (알림과 매치되는 상태)
        return generate_equipment_status()
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/equipment_status", timeout=API_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            return data
        else:
            print(f"설비 상태 API 오류: {response.status_code}")
            return []
    except requests.exceptions.Timeout:
        print("설비 상태 API 타임아웃")
        return []
    except requests.exceptions.ConnectionError:
        print("설비 상태 API 연결 실패")
        return []
    except Exception as e:
        print(f"설비 상태 API 오류: {e}")
        return []



def get_quality_trend_from_api(use_real_api=True):
    """FastAPI에서 품질 추세 데이터 가져오기"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/quality_trend?use_real_api={str(use_real_api).lower()}", timeout=API_TIMEOUT)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"품질 추세 API 오류: {response.status_code}")
            return None
    except requests.exceptions.Timeout:
        print("품질 추세 API 타임아웃")
        return None
    except requests.exceptions.ConnectionError:
        print("품질 추세 API 연결 실패")
        return None
    except Exception as e:
        print(f"품질 추세 API 연결 오류: {e}")
        return None

def get_color_and_icon_for_probability(status, probability):
    """
    확률값에 따라 색상과 아이콘을 동적으로 결정하는 함수
    
    Args:
        status (str): 상태 타입 ('normal' 또는 이상 타입)
        probability (float): 확률값 (0.0 ~ 1.0)
    
    Returns:
        dict: 색상, 배경색, 아이콘 정보
    """
    # 정상 상태의 경우: 높은 확률이 좋음 (녹색), 낮은 확률이 나쁨 (빨간색)
    if status == 'normal':
        if probability >= 0.8:  # 80% 이상
            return {'color': '#10B981', 'bg': '#ECFDF5', 'icon': '🟢'}
        elif probability >= 0.5:  # 50% 이상 80% 미만
            return {'color': '#F59E0B', 'bg': '#FFFBEB', 'icon': '🟠'}
        else:  # 50% 미만
            return {'color': '#EF4444', 'bg': '#FEF2F2', 'icon': '🔴'}
    
    # 이상 상태의 경우: 낮은 확률이 좋음 (녹색), 높은 확률이 나쁨 (빨간색)
    else:
        if probability <= 0.05:  # 5% 이하 - 정상
            return {'color': '#10B981', 'bg': '#ECFDF5', 'icon': '🟢'}
        elif probability <= 0.10:  # 5% 초과 10% 이하 - 경고
            return {'color': '#F59E0B', 'bg': '#FFFBEB', 'icon': '🟠'}
        else:  # 10% 초과 - 위험
            return {'color': '#EF4444', 'bg': '#FEF2F2', 'icon': '🔴'}

def get_ai_prediction_results(use_real_api=True):
    """AI 예측 결과 JSON 파일들을 읽어오기"""
    predictions = {}
    
    # API 연동이 OFF인 경우 더미 데이터 반환
    if not use_real_api:
        return generate_ai_prediction_data()
    
    # API 연동이 ON인 경우 실제 JSON 파일 읽기
    # 설비 이상 예측 결과 읽기
    try:
        abnormal_path = "ai_model/abnormal_detec/last_prediction.json"
        if os.path.exists(abnormal_path):
            with open(abnormal_path, 'r', encoding='utf-8') as f:
                predictions['abnormal_detection'] = json.load(f)
        else:
            predictions['abnormal_detection'] = {
                'status': 'error',
                'error_message': '예측 결과 파일이 없습니다.'
            }
    except Exception as e:
        predictions['abnormal_detection'] = {
            'status': 'error',
            'error_message': f'파일 읽기 오류: {str(e)}'
        }
    
    # 유압 이상 탐지 결과 읽기
    try:
        hydraulic_path = "ai_model/hydraulic_rf/last_prediction.json"
        if os.path.exists(hydraulic_path):
            with open(hydraulic_path, 'r', encoding='utf-8') as f:
                predictions['hydraulic_detection'] = json.load(f)
        else:
            predictions['hydraulic_detection'] = {
                'status': 'error',
                'error_message': '예측 결과 파일이 없습니다.'
            }
    except Exception as e:
        predictions['hydraulic_detection'] = {
            'status': 'error',
            'error_message': f'파일 읽기 오류: {str(e)}'
        }
    
    return predictions

def generate_ai_prediction_data():
    """AI 예측 결과 더미 데이터 생성"""
    predictions = {}
    
    # 설비 이상 예측 더미 데이터 (새로운 기준 적용)
    predictions['abnormal_detection'] = {
        'status': 'success',
        'prediction': {
            'predicted_class': 'normal',
            'predicted_class_description': '정상',
            'confidence': 0.85,
            'probabilities': {
                'normal': 0.92,  # 92% 정상 (5% 이하 기준으로 안전)
                'bearing_fault': 0.04,  # 4% 베어링 고장 (5% 이하 - 정상)
                'roll_misalignment': 0.025,  # 2.5% 롤 정렬 불량 (5% 이하 - 정상)
                'motor_overload': 0.01,  # 1% 모터 과부하 (5% 이하 - 정상)
                'lubricant_shortage': 0.005  # 0.5% 윤활유 부족 (5% 이하 - 정상)
            },
            'max_status': 'normal'
        },
        'timestamp': datetime.now().isoformat()
    }
    
    # 유압 이상 탐지 더미 데이터 (새로운 기준 적용)
    predictions['hydraulic_detection'] = {
        'status': 'success',
        'prediction': {
            'prediction': 0,  # 0: 정상, 1: 이상
            'probabilities': {
                'normal': 0.95,  # 95% 정상 (5% 이하 기준으로 안전)
                'abnormal': 0.05  # 5% 이상 (5% 이하 - 정상)
            },
            'confidence': 0.95
        },
        'timestamp': datetime.now().isoformat()
    }
    
    return predictions

# 설비별 사용자 관리 API 함수들
def get_users_from_api(use_real_api=True):
    """사용자 목록 조회"""
    if use_real_api:
        try:
            response = requests.get(f"{API_BASE_URL}/users", timeout=5)
            if response.status_code == 200:
                return response.json()['users']
            else:
                # 사용자 목록 API 오류: {response.status_code}
                return []
        except Exception as e:
            # 사용자 목록 API 호출 오류: {e}
            return []
    else:
        return []

def get_equipment_users_from_api(equipment_id, use_real_api=True):
    """설비별 사용자 할당 정보 조회"""
    if use_real_api:
        try:
            response = requests.get(f"{API_BASE_URL}/equipment/{equipment_id}/users", timeout=5)
            if response.status_code == 200:
                return response.json()['users']
            else:
                # 설비별 사용자 API 오류: {response.status_code}
                return []
        except Exception as e:
            # 설비별 사용자 API 호출 오류: {e}
            return []
    else:
        return []

def assign_user_to_equipment_api(equipment_id, user_id, role="담당자", is_primary=False, use_real_api=True):
    """설비에 사용자 할당"""
    if use_real_api:
        try:
            data = {
                "equipment_id": equipment_id,
                "user_id": user_id,
                "role": role,
                "is_primary": is_primary
            }
            response = requests.post(f"{API_BASE_URL}/equipment/{equipment_id}/users", 
                                   json=data, timeout=5)
            if response.status_code == 200:
                return True, response.json()['message']
            else:
                return False, f"할당 실패: {response.status_code}"
        except Exception as e:
            return False, f"API 호출 오류: {e}"
    else:
        return True, "시뮬레이션 모드: 할당 완료"

def remove_user_from_equipment_api(equipment_id, user_id, use_real_api=True):
    """설비에서 사용자 할당 해제"""
    if use_real_api:
        try:
            response = requests.delete(f"{API_BASE_URL}/equipment/{equipment_id}/users/{user_id}", 
                                     timeout=5)
            if response.status_code == 200:
                return True, response.json()['message']
            else:
                return False, f"해제 실패: {response.status_code}"
        except Exception as e:
            return False, f"API 호출 오류: {e}"
    else:
        return True, "시뮬레이션 모드: 해제 완료"

def get_equipment_users_by_user(user_id):
    """특정 사용자가 담당하는 설비 목록 조회"""
    try:
        response = requests.get(f"{API_BASE_URL}/users/{user_id}/equipment", timeout=5)
        if response.status_code == 200:
            return response.json()['equipment']
        else:
            # 사용자별 설비 API 오류: {response.status_code}
            return []
    except Exception as e:
        # 사용자별 설비 API 호출 오류: {e}
        return []

def get_equipment_users_summary_api(use_real_api=True):
    """설비별 사용자 할당 요약 정보"""
    if use_real_api:
        try:
            response = requests.get(f"{API_BASE_URL}/equipment/users/summary", timeout=5)
            if response.status_code == 200:
                return response.json()
            else:
                # 요약 정보 API 오류: {response.status_code}
                return {"summary": [], "total_assignments": 0, "total_primary_users": 0, "equipment_count": 0}
        except Exception as e:
            # 요약 정보 API 호출 오류: {e}
            return {"summary": [], "total_assignments": 0, "total_primary_users": 0, "equipment_count": 0}
    else:
        return {"summary": [], "total_assignments": 0, "total_primary_users": 0, "equipment_count": 0}

def has_critical_alerts(alerts):
    """위험 알림 감지 함수"""
    if not alerts:
        return False
    
    critical_keywords = ['critical', 'error', 'emergency', '위험', '오류', '긴급']
    
    for alert in alerts:
        severity = alert.get('severity', '').lower()
        message = alert.get('message', '').lower()
        issue = alert.get('issue', '').lower()
        
        # 심각도나 메시지에서 위험 키워드 검색
        for keyword in critical_keywords:
            if keyword in severity or keyword in message or keyword in issue:
                return True
    
    return False

# 백그라운드 스레드 관련 함수들 제거 (사용하지 않음)

# 페이지 설정
st.set_page_config(
    page_title="POSCO MOBILITY IoT 대시보드",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)



# 화이트 모드 CSS 적용
st.markdown("""
<meta name="google" content="notranslate">
<meta name="google-translate-customization" content="notranslate">
<style>
    :root {
        --posco-blue: #05507D;
    }
    /* 전체 배경 화이트 모드 */
    .main {
        background: #f8fafc;
        padding-top: 1rem;
    }
    
    /* 자연스러운 여백 조정 */
    .block-container {
        padding-top: 0.2rem !important;
        padding-bottom: 2rem;
        margin-top: 0 !important;
    }
    
    /* 사이드바 너비 증가 */
    .css-1d391kg {
        width: 320px;
    }
    
    .css-1lcbmhc {
        width: 320px;
    }
    
    /* 사이드바 스크롤 설정 - 이중 스크롤 방지 */
    [data-testid="stSidebar"] {
        overflow-y: auto !important;
        max-height: 100vh !important;
    }
    
    [data-testid="stSidebar"] > div {
        overflow-y: auto !important;
    }
    

    
    /* 필터 태그 개선 */
    .stMultiSelect > div > div {
        max-width: 100%;
    }
    
    .stMultiSelect [data-baseweb="tag"] {
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    /* 필터 태그 툴팁 */
    .stMultiSelect [data-baseweb="tag"]:hover::after {
        content: attr(title);
        position: absolute;
        background: #1e293b;
        color: white;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 12px;
        white-space: nowrap;
        z-index: 1000;
        top: -30px;
        left: 0;
    }
    
    /* Google Translate 자동 번역 방지 */
    * {
        translate: none !important;
    }
    
    /* 한글 텍스트 번역 방지 */
    .main-header,
    .kpi-label,
    .kpi-change,
    .chart-title,
    .stSubheader,
    .stMarkdown,
    [data-baseweb="tag"] {
        translate: none !important;
    }
    
    /* HTML 속성으로 번역 방지 */
    .no-translate {
        translate: none !important;
    }
    
    /* Streamlit 사이드바 번역 방지 */
    .css-1d391kg *,
    .css-1lcbmhc *,
    .sidebar *,
    .stSidebar * {
        translate: none !important;
    }
    
    /* 모든 텍스트 번역 방지 */
    body, html {
        translate: none !important;
    }
    
    /* 텍스트 입력 필드만 배경색 변경 */
    .stTextInput > div > div > input {
        background-color: #f4f4f4 !important;
    }
    
    /* 특정 텍스트 번역 방지 */
    [data-testid="stSidebar"] * {
        translate: none !important;
    }
    
    /* 네비게이션 바 스타일 */
    .nav-container {
        background: white;
        border-bottom: 2px solid #e2e8f0;
        padding: 0;
        margin: 0;
        position: sticky;
        top: 0;
        z-index: 1000;
    }
    
    .nav-tabs {
        display: flex;
        list-style: none;
        margin: 0;
        padding: 0;
        border-bottom: 1px solid #e2e8f0;
    }
    
    .nav-tab {
        padding: 1rem 2rem;
        cursor: pointer;
        border-bottom: 3px solid transparent;
        transition: all 0.3s ease;
        font-weight: 600;
        color: #64748b;
    }
    
    .nav-tab:hover {
        background: #f1f5f9;
        color: #1e293b;
    }
    
    .nav-tab.active {
        color: #3b82f6;
        border-bottom-color: #3b82f6;
        background: #eff6ff;
    }
    

    
    /* 헤더 스타일 */
    .main-header {
        font-size: 2rem;
        font-weight: bold;
        color: #1e293b;
        margin: 0.8rem 0;
        text-align: left;
        text-shadow: 0 1px 2px rgba(0,0,0,0.1);
        padding: 0.5rem 0;
    }
    
    /* KPI 카드 화이트 모드 */
    .kpi-card {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
        box-shadow: 0 2px 4px -1px rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.06);
        position: relative;
        overflow: hidden;
        margin-bottom: 1rem;
        transition: all 0.3s ease;
        min-height: 90px;
        display: flex;
        flex-direction: column;
        justify-content: center;
    }
    
    .kpi-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04);
    }
    
    .kpi-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 6px;
        background: linear-gradient(90deg, #3b82f6, #06b6d4);
        border-radius: 16px 16px 0 0;
    }
    
    .kpi-card.warning::before {
        background: linear-gradient(90deg, #f59e0b, #f97316);
    }
    
    .kpi-card.danger::before {
        background: linear-gradient(90deg, #ef4444, #dc2626);
    }
    
    .kpi-card.success::before {
        background: linear-gradient(90deg, #10b981, #059669);
    }
    
    .kpi-value {
        font-size: 2rem;
        font-weight: bold;
        color: #1e293b;
        margin-bottom: 0.3rem;
        line-height: 1;
    }
    
    .kpi-label {
        font-size: 0.85rem;
        color: #64748b;
        margin-bottom: 0.5rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.3px;
    }
    
    .kpi-change {
        font-size: 0.75rem;
        color: #10b981;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.3rem;
        font-weight: 500;
        margin-top: auto;
    }
    
    .kpi-change.warning { color: #f59e0b; }
    .kpi-change.danger { color: #ef4444; }
    
    /* 상태 인디케이터 */
    .status-indicator {
        width: 10px;
        height: 10px;
        border-radius: 50%;
        background: #10b981;
        animation: pulse 2s infinite;
    }
    
    .status-indicator.warning { background: #f59e0b; }
    .status-indicator.danger { background: #ef4444; }
    
    @keyframes pulse {
        0% { opacity: 1; }
        50% { opacity: 0.5; }
        100% { opacity: 1; }
    }
    
    /* 차트 컨테이너 화이트 모드 */
    .chart-container {
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
        transition: all 0.3s ease;
    }
    
    .chart-title {
        font-size: 1.2rem;
        font-weight: bold;
        color: #1e293b;
        margin-bottom: 1rem;
        display: flex;
        align-items: center;
        gap: 0.6rem;
        padding-bottom: 0.4rem;
        border-bottom: 1px solid #f1f5f9;
    }
    

    
    /* 테이블 스타일 최적화 */
    .table-container {
        height: 300px;
        overflow-y: auto;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        background: white;
        margin: 0;
    }
    
    .table-container table {
        width: 100%;
        border-collapse: collapse;
        margin: 0;
    }
    
    .table-container th {
        background: #f8fafc;
        padding: 8px 12px;
        text-align: left;
        font-weight: 600;
        color: #1e293b;
        border-bottom: 2px solid #e2e8f0;
        font-size: 0.85rem;
        position: sticky;
        top: 0;
        z-index: 10;
    }
    
    .table-container td {
        padding: 8px 12px;
        border-bottom: 1px solid #f1f5f9;
        font-size: 0.85rem;
        color: #374151;
    }
    
    .table-container tr:hover {
        background: #f8fafc;
    }
    
    .table-container tr:last-child td {
        border-bottom: none;
    }
    
    /* 설비 상태 테이블 - 좌측 차트 크기에 맞춤 */
    .equipment-table-container {
        height: 300px;
        overflow-y: auto;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        background: white;
        margin: 0;
    }
    
    .equipment-table-container table {
        width: 100%;
        border-collapse: collapse;
        margin: 0;
    }
    
    .equipment-table-container th {
        background: #f8fafc;
        padding: 8px 12px;
        text-align: left;
        font-weight: 600;
        color: #1e293b;
        border-bottom: 2px solid #e2e8f0;
        font-size: 0.85rem;
        position: sticky;
        top: 0;
        z-index: 10;
    }
    
    .equipment-table-container td {
        padding: 8px 12px;
        border-bottom: 1px solid #f1f5f9;
        font-size: 0.85rem;
        color: #374151;
    }
    
    .equipment-table-container tr:hover {
        background: #f8fafc;
    }
    
    .equipment-table-container tr:last-child td {
        border-bottom: none;
    }
    
    /* 알림 테이블 - 우측 차트 크기에 맞춤 */
    .alert-table-container {
        height: 250px;
        overflow-y: auto;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        background: white;
        margin: 0;
    }
    
    .alert-table-container table {
        width: 100%;
        border-collapse: collapse;
        margin: 0;
    }
    
    .alert-table-container th {
        background: #f8fafc;
        padding: 8px 12px;
        text-align: left;
        font-weight: 600;
        color: #1e293b;
        border-bottom: 2px solid #e2e8f0;
        font-size: 0.85rem;
        position: sticky;
        top: 0;
        z-index: 10;
    }
    
    .alert-table-container td {
        padding: 8px 12px;
        border-bottom: 1px solid #f1f5f9;
        font-size: 0.85rem;
        color: #374151;
    }
    
    .alert-table-container tr:hover {
        background: #f8fafc;
    }
    
    .alert-table-container tr:last-child td {
        border-bottom: none;
    }
    
    /* 빈 컨테이너 제거 */
    .stContainer {
        margin: 0;
        padding: 0;
    }
    
    /* 불필요한 여백 제거 */
    .element-container {
        margin-bottom: 0.3rem;
    }
    
    /* 자연스러운 여백 */
    .stMarkdown {
        margin-bottom: 0.5rem;
    }
    
    /* 섹션 간격 조정 */
    .stSubheader {
        margin-bottom: 0.8rem;
        font-size: 1.1rem;
    }
    
    /* 버튼 스타일 개선 - 플로팅 스타일 */
    .stButton > button {
        background: #ffffff !important;
        color: #374151 !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 12px !important;
        padding: 10px 20px !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        cursor: pointer !important;
        transition: all 0.3s ease !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1) !important;
        min-height: 40px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        text-align: center !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        position: relative !important;
        margin-bottom: 0.5rem !important;
    }
    
    .stButton > button::before {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 100%;
        height: 100%;
        background: linear-gradient(90deg, transparent, rgba(5, 80, 125, 0.1), transparent);
        transition: left 0.5s;
    }
    
    .stButton > button:hover::before {
        left: 100%;
    }
    
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(5, 80, 125, 0.3);
        background: linear-gradient(135deg, #05507D 0%, #00A5E5 100%);
        color: white;
        border-color: #05507D;
    }
    
    .stButton > button:active {
        transform: translateY(0);
        box-shadow: 0 2px 8px rgba(5, 80, 125, 0.2);
    }
    
    /* Primary 버튼 스타일 (선택된 상태) */
    .stButton > button[data-baseweb="button"][aria-pressed="true"] {
        background: linear-gradient(135deg, #05507D 0%, #00A5E5 100%);
        color: white;
        border-color: #05507D;
        box-shadow: 0 4px 12px rgba(5, 80, 125, 0.2);
    }
    
    .stButton > button[data-baseweb="button"][aria-pressed="true"]:hover {
        background: linear-gradient(135deg, #044a6f 0%, #0095d1 100%);
        box-shadow: 0 6px 20px rgba(5, 80, 125, 0.3);
    }
    
    /* 섹션 간격 최적화 */
    .stSubheader {
        margin-bottom: 0.5rem;
        font-size: 1.1rem;
    }
    
    /* 구분선 최적화 */
    hr {
        margin: 1rem 0;
        border: none;
        height: 1px;
        background: #e2e8f0;
    }
    
    /* 사이드바 우측 세로 구분선 */
    .css-1d391kg {
        border-right: 2px solid #e2e8f0 !important;
    }
    
    /* 사이드바 컨테이너 우측 세로선 */
    section[data-testid="stSidebar"] {
        border-right: 2px solid #e2e8f0 !important;
    }
    
    /* 스크롤바 스타일 */
    .table-container::-webkit-scrollbar {
        width: 8px;
    }
    
    .table-container::-webkit-scrollbar-track {
        background: #f1f5f9;
        border-radius: 4px;
    }
    
    .table-container::-webkit-scrollbar-thumb {
        background: #cbd5e1;
        border-radius: 4px;
    }
    
    .table-container::-webkit-scrollbar-thumb:hover {
        background: #94a3b8;
    }
    
    /* 더보기 메시지 스타일 */
    .more-info {
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 8px;
        padding: 12px;
        margin-top: 10px;
        text-align: center;
        color: #64748b;
        font-size: 14px;
    }
    
    /* 상단 탭 active - POSCO BLUE 강조 */
    .stButton > button.selected {
        color: #fff !important;
        border-bottom: 3px solid var(--posco-blue) !important;
        font-weight: 700 !important;
        background: var(--posco-blue) !important;
    }
    .stButton > button:hover {
        background: #e6f0f7 !important;
        color: var(--posco-blue) !important;
    }
    
    /* 모든 버튼 기본 배경색 강제 적용 */
    .stButton > button:not(.selected):not(:hover) {
        background: #ffffff !important;
        color: #374151 !important;
    }
    
    /* 필터 태그 개선 */
    .stMultiSelect > div > div {
        max-width: 100%;
    }
    
    .stMultiSelect [data-baseweb="tag"] {
        max-width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    
    /* 필터 태그 툴팁 */
    .stMultiSelect [data-baseweb="tag"]:hover::after {
        content: attr(title);
        position: absolute;
        background: #1e293b;
        color: white;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 12px;
        white-space: nowrap;
        z-index: 1000;
        top: -30px;
        left: 0;
    }
    /* selectbox/radio/캘린더 등 선택 강조 - POSCO BLUE */
    .stSelectbox [data-baseweb="select"] .css-1wa3eu0-placeholder,
    .stSelectbox [data-baseweb="select"] .css-1uccc91-singleValue {
        color: var(--posco-blue) !important;
        font-weight: 700;
    }
    .stSelectbox [data-baseweb="select"] .css-1okebmr-indicatorSeparator {
        background: var(--posco-blue) !important;
    }
    .stSelectbox [data-baseweb="select"] .css-tlfecz-indicatorContainer {
        color: var(--posco-blue) !important;
    }
    .stSelectbox [data-baseweb="select"] .css-1n7v3ny-option[aria-selected="true"],
    .stSelectbox [data-baseweb="select"] .css-1n7v3ny-option:active {
        background: var(--posco-blue) !important;
        color: #fff !important;
    }
    .stRadio [role="radiogroup"] > label[data-baseweb="radio"] > div:first-child {
        border-color: var(--posco-blue) !important;
    }
    .stRadio [role="radiogroup"] > label[data-baseweb="radio"] > div[aria-checked="true"] {
        background: var(--posco-blue) !important;
        border-color: var(--posco-blue) !important;
    }
    .stRadio [role="radiogroup"] > label[data-baseweb="radio"] > div[aria-checked="true"] svg {
        color: #fff !important;
    }
    /* 캘린더 선택 날짜 - POSCO BLUE */
    .css-1u9des2 .DayPicker-Day--selected:not(.DayPicker-Day--outside) {
        background: var(--posco-blue) !important;
        color: #fff !important;
        border-radius: 50% !important;
    }
    .css-1u9des2 .DayPicker-Day--selected:not(.DayPicker-Day--outside):hover {
        background: #003d5b !important;
        color: #fff !important;
    }
    /* 멀티셀렉트 태그 선택 강조 */
    .stMultiSelect [data-baseweb="tag"] {
        background: var(--posco-blue) !important;
        color: #fff !important;
        border-radius: 8px !important;
        font-weight: 600;
    }
    /* 포커스/선택 강조 효과 */
    .stSelectbox [data-baseweb="select"] .css-1n7v3ny-option:focus {
        background: var(--posco-blue) !important;
        color: #fff !important;
    }
    .stSelectbox [data-baseweb="select"] .css-1n7v3ny-option:hover {
        background: #e6f0f7 !important;
        color: var(--posco-blue) !important;
    }
    /* Streamlit 기본 버튼 강조(선택/활성) */
    .stButton > button:focus, .stButton > button:active {
        background: var(--posco-blue) !important;
        color: #fff !important;
        border: 2px solid var(--posco-blue) !important;
    }
    /* Streamlit 토글(스위치) 강조 */
    .stToggleSwitch [data-baseweb="switch"] > div[aria-checked="true"] {
        background: var(--posco-blue) !important;
        border-color: var(--posco-blue) !important;
    }
    .stToggleSwitch [data-baseweb="switch"] > div[aria-checked="true"] > div {
        background: #fff !important;
    }
    /* Streamlit 슬라이더 강조 */
    .stSlider > div[data-baseweb="slider"] .css-14g5y4m {
        background: var(--posco-blue) !important;
    }
    .stSlider > div[data-baseweb="slider"] .css-1gv0vcd {
        background: var(--posco-blue) !important;
    }
    /* Streamlit 체크박스 강조 */
    .stCheckbox [data-baseweb="checkbox"] > div[aria-checked="true"] {
        background: var(--posco-blue) !important;
        border-color: var(--posco-blue) !important;
    }
    .stCheckbox [data-baseweb="checkbox"] > div[aria-checked="true"] svg {
        color: #fff !important;
    }
    /* Streamlit 데이터프레임 선택 강조 */
    .stDataFrame .row_selected {
        background: var(--posco-blue) !important;
        color: #fff !important;
    }
    /* Streamlit 캘린더 헤더 강조 */
    .css-1u9des2 .DayPicker-Caption > div {
        color: var(--posco-blue) !important;
        font-weight: 700;
    }
    /* Streamlit selectbox 드롭다운 화살표 강조 */
    .stSelectbox [data-baseweb="select"] .css-1hb7zxy-IndicatorsContainer {
        color: var(--posco-blue) !important;
    }
    /* Streamlit radio 선택 강조 */
    .stRadio [role="radiogroup"] > label[data-baseweb="radio"] > div[aria-checked="true"] {
        box-shadow: 0 0 0 2px var(--posco-blue) !important;
    }
    /* Streamlit sidebar 강조 */
    .stSidebar {
        border-right: 1px solid #e2e8f0 !important;
    }
    /* 사이드바 구분선(hr) 원래대로 */
    .stSidebar hr {
        border: none;
        border-top: 1px solid #e2e8f0 !important;
        margin: 1rem 0 0.5rem 0;
    }
    /* 사이드바 필터 선택 강조(색상만 유지, 배경/밑줄 등은 건드리지 않음) */
    .stSidebar .stMultiSelect [data-baseweb="tag"] {
        background: var(--posco-blue) !important;
        color: #fff !important;
    }
    .stSidebar .stSelectbox [data-baseweb="select"] .css-1n7v3ny-option[aria-selected="true"] {
        background: var(--posco-blue) !important;
        color: #fff !important;
    }

    /* Streamlit 상단 탭 active(선택) 밑줄 POSCO BLUE로 강제 */
    .stTabs [data-baseweb="tab"] {
        border-bottom: none !important;
        color: #64748b !important;
        background: none !important;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        border-bottom: none !important;
        color: #222 !important;
        background: none !important;
        font-weight: 700 !important;
    }
    .stTabs [data-baseweb="tab"]:hover {
        color: var(--posco-blue) !important;
    }
    /* 카드 행간 여백을 CSS로 강제 최소화 */
    .block-container .stHorizontalBlock { margin-bottom: 0.01rem !important; }
    .stColumn { margin-bottom: 0.01rem !important; }
    
    /* 팝업 알림 스타일 */
    .alert-popup {
        position: fixed;
        top: 20px;
        right: 20px;
        background: #fff;
        border: 1px solid #e5e7eb;
        border-radius: 8px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        padding: 16px;
        max-width: 300px;
        z-index: 1000;
        animation: slideIn 0.3s ease-out;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    
    .alert-popup.error {
        border-left: 4px solid #ef4444;
    }
    
    .alert-popup.warning {
        border-left: 4px solid #f59e0b;
    }
    
    .alert-popup.info {
        border-left: 4px solid #3b82f6;
    }
    
    .alert-popup .title {
        font-weight: 600;
        font-size: 14px;
        margin-bottom: 4px;
        color: #111827;
    }
    
    .alert-popup .message {
        font-size: 13px;
        color: #6b7280;
        margin-bottom: 8px;
    }
    
    .alert-popup .time {
        font-size: 11px;
        color: #9ca3af;
    }
    
    .alert-popup .close-btn {
        position: absolute;
        top: 8px;
        right: 8px;
        background: none;
        border: none;
        font-size: 16px;
        cursor: pointer;
        color: #9ca3af;
        padding: 0;
        width: 20px;
        height: 20px;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    
    .alert-popup .close-btn:hover {
        color: #6b7280;
    }
    
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(100%);
            opacity: 0;
        }
    }
</style>
""", unsafe_allow_html=True)

# 실시간 알림 팝업 JavaScript
st.markdown("""
<script>
    // Google Translate 완전 차단
    function disableGoogleTranslate() {
        // 메타 태그 추가
        if (!document.querySelector('meta[name="google"]')) {
            const meta = document.createElement('meta');
            meta.name = 'google';
            meta.content = 'notranslate';
            document.head.appendChild(meta);
        }
        
        // 모든 요소에 번역 방지 속성 추가
        const allElements = document.querySelectorAll('*');
        allElements.forEach(element => {
            element.setAttribute('translate', 'no');
            element.style.translate = 'none';
        });
        
        // Google Translate 위젯 제거
        const translateWidget = document.querySelector('.goog-te-banner-frame');
        if (translateWidget) {
            translateWidget.style.display = 'none';
        }
        
        // 번역 관련 스크립트 비활성화
        if (window.google && window.google.translate) {
            window.google.translate.TranslateElement = function() {};
        }
    }
    
    // DOM이 완전히 로드된 후 실행
    document.addEventListener('DOMContentLoaded', function() {
        // 번역 방지 즉시 실행
        disableGoogleTranslate();
        
        function showNotification(message, type = 'error') {
            try {
                const popup = document.createElement('div');
                popup.className = 'notification-popup';
                popup.style.background = type === 'error' ? 'linear-gradient(135deg, #ef4444, #dc2626)' : 
                                        type === 'warning' ? 'linear-gradient(135deg, #f59e0b, #f97316)' :
                                        'linear-gradient(135deg, #10b981, #059669)';
                popup.innerHTML = message;
                document.body.appendChild(popup);
                
                setTimeout(() => {
                    if (popup && popup.parentNode) {
                        popup.parentNode.removeChild(popup);
                    }
                }, 5000);
            } catch (error) {
                console.log('알림 표시 중 오류:', error);
            }
        }
        
        // 실시간 알림 시뮬레이션 (안전하게)
        setInterval(() => {
            try {
                const alerts = [
                    {msg: '🚨 용접기 #003 온도 임계값 초과', type: 'error'},
                    {msg: '⚠️ 프레스기 #001 진동 증가 감지', type: 'warning'},
                    {msg: 'ℹ️ 조립라인 정기점검 완료', type: 'info'}
                ];
                const randomAlert = alerts[Math.floor(Math.random() * alerts.length)];
                if (Math.random() < 0.3) { // 30% 확률로 알림 표시
                    showNotification(randomAlert.msg, randomAlert.type);
                }
            } catch (error) {
                console.log('알림 시뮬레이션 오류:', error);
            }
        }, 30000);
    });
    
    // 주기적으로 번역 방지 확인
    setInterval(disableGoogleTranslate, 1000);
    
    // 팝업 알림 관리
    let alertQueue = [];
    let isShowingAlert = false;
    
    function showAlertPopup(alert) {
        const popup = document.createElement('div');
        popup.className = `alert-popup ${alert.severity}`;
        popup.innerHTML = `
            <button class="close-btn" onclick="this.parentElement.remove()">×</button>
            <div class="title">${alert.equipment}</div>
            <div class="message">${alert.issue}</div>
            <div class="time">${alert.time}</div>
        `;
        
        document.body.appendChild(popup);
        
        // 5초 후 자동 제거
        setTimeout(() => {
            if (popup.parentElement) {
                popup.style.animation = 'slideOut 0.3s ease-out';
                setTimeout(() => popup.remove(), 300);
            }
        }, 5000);
    }
    
    // Streamlit에서 호출할 수 있도록 전역 함수로 등록
    window.showAlertPopup = showAlertPopup;
</script>
""", unsafe_allow_html=True)

# 세션 상태 초기화
if 'alerts' not in st.session_state:
    st.session_state.alerts = []
if 'equipment_details' not in st.session_state:
    st.session_state.equipment_details = {}

# 데이터 생성 함수들
def generate_sensor_data():
    """실시간 센서 데이터 생성"""
    # 데이터 제거 상태 확인
    if hasattr(st, 'session_state') and st.session_state.get('data_cleared', False):
        # 빈 데이터프레임 반환
        return pd.DataFrame({
            'time': [],
            'equipment': [],
            'temperature': [],
            'pressure': [],
            'vibration': []
        })
    
    times = pd.date_range(start=datetime.now() - timedelta(hours=2), end=datetime.now(), freq='5min')
    times_array = times.to_numpy()  # 경고 메시지 해결
    
    # 설비 목록
    equipment_list = ['프레스기 #001', '프레스기 #002', '용접기 #001', '용접기 #002', '조립기 #001', '검사기 #001']
    
    # 각 설비별로 센서 데이터 생성
    all_data = []
    for equipment in equipment_list:
        # 온도 데이터 (20-80도)
        temperature = 50 + 12 * np.sin(np.linspace(0, 4*np.pi, len(times))) + np.random.normal(0, 3, len(times))
        # 압력 데이터 (100-200 bar)
        pressure = 150 + 25 * np.cos(np.linspace(0, 3*np.pi, len(times))) + np.random.normal(0, 5, len(times))
        # 진동 데이터 (0.2-1.0 mm/s)
        vibration = 0.5 + 0.3 * np.sin(np.linspace(0, 2*np.pi, len(times))) + np.random.normal(0, 0.1, len(times))
        for i, time in enumerate(times):
            all_data.append({
                'time': time,
                'equipment': equipment,
                'temperature': temperature[i],
                'pressure': pressure[i],
                'vibration': vibration[i]
            })
    return pd.DataFrame(all_data)

def generate_equipment_status():
    """설비 상태 데이터 생성 (알림 데이터와 연동)"""
    # 데이터 제거 상태 확인
    if hasattr(st, 'session_state') and st.session_state.get('data_cleared', False):
        return []  # 데이터 제거 시 빈 리스트 반환
    
    # 알림 데이터에서 설비별 상태 추론
    alerts = generate_alert_data()
    alert_df = pd.DataFrame(alerts)
    
    # 기본 설비 목록 (모든 설비는 기본적으로 정상 상태)
    base_equipment = [
        {'id': 'press_001', 'name': '프레스기 #001', 'status': '정상', 'efficiency': 98.2, 'type': '프레스기', 'last_maintenance': '2024-01-15'},
        {'id': 'press_002', 'name': '프레스기 #002', 'status': '정상', 'efficiency': 95.8, 'type': '프레스기', 'last_maintenance': '2024-01-10'},
        {'id': 'press_003', 'name': '프레스기 #003', 'status': '정상', 'efficiency': 92.1, 'type': '프레스기', 'last_maintenance': '2024-01-13'},
        {'id': 'press_004', 'name': '프레스기 #004', 'status': '정상', 'efficiency': 95.8, 'type': '프레스기', 'last_maintenance': '2024-01-11'},
        {'id': 'press_005', 'name': '프레스기 #005', 'status': '정상', 'efficiency': 94.5, 'type': '프레스기', 'last_maintenance': '2024-01-09'},
        {'id': 'press_006', 'name': '프레스기 #006', 'status': '정상', 'efficiency': 93.2, 'type': '프레스기', 'last_maintenance': '2024-01-08'},
        {'id': 'weld_001', 'name': '용접기 #001', 'status': '정상', 'efficiency': 89.3, 'type': '용접기', 'last_maintenance': '2024-01-12'},
        {'id': 'weld_002', 'name': '용접기 #002', 'status': '정상', 'efficiency': 87.5, 'type': '용접기', 'last_maintenance': '2024-01-08'},
        {'id': 'weld_003', 'name': '용접기 #003', 'status': '정상', 'efficiency': 82.4, 'type': '용접기', 'last_maintenance': '2024-01-09'},
        {'id': 'weld_004', 'name': '용접기 #004', 'status': '정상', 'efficiency': 91.7, 'type': '용접기', 'last_maintenance': '2024-01-14'},
        {'id': 'weld_005', 'name': '용접기 #005', 'status': '정상', 'efficiency': 88.9, 'type': '용접기', 'last_maintenance': '2024-01-07'},
        {'id': 'weld_006', 'name': '용접기 #006', 'status': '정상', 'efficiency': 86.3, 'type': '용접기', 'last_maintenance': '2024-01-06'},
        {'id': 'assemble_001', 'name': '조립기 #001', 'status': '정상', 'efficiency': 96.1, 'type': '조립기', 'last_maintenance': '2024-01-14'},
        {'id': 'assemble_002', 'name': '조립기 #002', 'status': '정상', 'efficiency': 94.3, 'type': '조립기', 'last_maintenance': '2024-01-12'},
        {'id': 'assemble_003', 'name': '조립기 #003', 'status': '정상', 'efficiency': 85.6, 'type': '조립기', 'last_maintenance': '2024-01-10'},
        {'id': 'assemble_004', 'name': '조립기 #004', 'status': '정상', 'efficiency': 92.8, 'type': '조립기', 'last_maintenance': '2024-01-11'},
        {'id': 'inspect_001', 'name': '검사기 #001', 'status': '정상', 'efficiency': 97.2, 'type': '검사기', 'last_maintenance': '2024-01-05'},
        {'id': 'inspect_002', 'name': '검사기 #002', 'status': '정상', 'efficiency': 97.2, 'type': '검사기', 'last_maintenance': '2024-01-13'},
        {'id': 'inspect_003', 'name': '검사기 #003', 'status': '정상', 'efficiency': 93.8, 'type': '검사기', 'last_maintenance': '2024-01-11'},
        {'id': 'inspect_004', 'name': '검사기 #004', 'status': '정상', 'efficiency': 95.1, 'type': '검사기', 'last_maintenance': '2024-01-09'},
        {'id': 'inspect_005', 'name': '검사기 #005', 'status': '정상', 'efficiency': 94.7, 'type': '검사기', 'last_maintenance': '2024-01-08'},
        {'id': 'pack_001', 'name': '포장기 #001', 'status': '정상', 'efficiency': 88.9, 'type': '포장기', 'last_maintenance': '2024-01-15'},
        {'id': 'pack_002', 'name': '포장기 #002', 'status': '정상', 'efficiency': 76.2, 'type': '포장기', 'last_maintenance': '2024-01-07'},
        {'id': 'pack_003', 'name': '포장기 #003', 'status': '정상', 'efficiency': 89.5, 'type': '포장기', 'last_maintenance': '2024-01-12'}
    ]
    
    # 알림 데이터가 있으면 설비 상태 업데이트
    if not alert_df.empty:
        # 더미데이터의 알림과 정확히 매치되는 설비만 상태 변경 (24개 알림 기준)
        alarmed_equipment = {
            '용접기 #002': 'error',      # 1. 온도 임계값 초과
            '프레스기 #001': 'warning',  # 2. 진동 증가
            '검사기 #001': 'error',      # 3. 비상 정지
            '조립기 #001': 'info',       # 4. 정기점검 완료 (정상 유지)
            '프레스기 #002': 'warning',  # 5. 압력 불안정
            '용접기 #001': 'error',      # 6. 품질 검사 불량
            '용접기 #003': 'warning',    # 7. 가스 압력 부족
            '프레스기 #003': 'info',     # 8. 금형 교체 완료 (정상 유지)
            '조립기 #002': 'warning',    # 9. 부품 공급 지연
            '검사기 #002': 'info',       # 10. 센서 교정 완료 (정상 유지)
            '포장기 #001': 'warning',    # 11. 포장재 부족
            '프레스기 #004': 'warning',  # 12. 유압 오일 온도 높음
            '용접기 #004': 'warning',    # 13. 전극 마모
            '조립기 #003': 'error',      # 14. 컨베이어 벨트 이탈
            '검사기 #003': 'warning',    # 15. 카메라 렌즈 오염
            '포장기 #002': 'error',      # 16. 시스템 오류
            '용접기 #005': 'warning',    # 17. 전극 수명 경고
            '프레스기 #005': 'error',    # 18. 유압 시스템 누수
            '검사기 #004': 'warning',    # 19. 검사 정확도 저하
            '조립기 #004': 'error',      # 20. 부품 불량 감지
            '포장기 #003': 'warning',    # 21. 포장 품질 저하
            '용접기 #006': 'error',      # 22. 용접 강도 부족
            '프레스기 #006': 'warning',  # 23. 압력 변동 폭 증가
            '검사기 #005': 'warning'     # 24. 센서 교정 필요
        }
        
        # 설비 상태 업데이트 (알림이 있는 설비만)
        for equipment in base_equipment:
            equipment_name = equipment['name']
            if equipment_name in alarmed_equipment:
                severity = alarmed_equipment[equipment_name]
                
                if severity == 'error':
                    equipment['status'] = '오류'
                    equipment['efficiency'] = 0
                elif severity == 'warning':
                    equipment['status'] = '주의'
                    equipment['efficiency'] = max(60, equipment['efficiency'] - 15)
                elif severity == 'info':
                    equipment['status'] = '정상'  # info는 정상 상태 유지
                # 알림이 없는 설비는 기본 '정상' 상태 유지 (변경하지 않음)
    
    return base_equipment

def get_alerts_from_api(use_real_api=True):
    """실제 API에서 알림 데이터 가져오기"""
    if not use_real_api:
        # 토글 OFF 시 더미데이터 반환
        return generate_alert_data()
    
    try:
        url = "http://localhost:8000/alerts"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            api_alerts = res.json()
            # API 데이터를 대시보드 형식에 맞게 변환
            formatted_alerts = []
            for i, alert in enumerate(api_alerts):
                # 키 fallback 처리로 일관된 데이터 출력
                equipment_name = alert.get('equipment') or alert.get('sensor_name') or alert.get('device_name', '알 수 없는 설비')
                issue_text = alert.get('message') or alert.get('issue') or alert.get('sensor_type') or alert.get('alert_type', '알림')
                details_text = alert.get('details') or alert.get('description') or alert.get('sensor_value', '상세 정보 없음')
                time_text = alert.get('timestamp', '').split('T')[1][:5] if alert.get('timestamp') else alert.get('time', '12:00')
                severity_level = alert.get('severity') or alert.get('level') or alert.get('priority', 'info')
                
                formatted_alert = {
                    'id': i + 1,
                    'time': time_text,
                    'equipment': equipment_name,
                    'issue': issue_text,
                    'severity': severity_level,
                    'status': '미처리',  # 기본값 설정
                    'details': details_text
                }
                formatted_alerts.append(formatted_alert)
            return formatted_alerts
    except Exception as e:
        st.error(f"API 연결 오류: {e}")
    return []

def generate_alert_data():
    """이상 알림 데이터 생성 (더미 데이터) - 완전한 날짜시간 정보 포함"""
    # 데이터 제거 상태 확인
    if hasattr(st, 'session_state') and st.session_state.get('data_cleared', False):
        return []  # 데이터 제거 시 빈 리스트 반환
    
    # 현재 날짜 기준으로 시간 생성
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    alerts = [
        {'id': 1, 'time': f'{current_date} 14:30:00', 'equipment': '용접기 #002', 'issue': '온도 임계값 초과', 'severity': 'error', 'status': '미처리', 'details': '현재 온도: 87°C (임계값: 85°C)', 'manager': '', 'interlock_bypass': ''},
        {'id': 2, 'time': f'{current_date} 13:20:00', 'equipment': '프레스기 #001', 'issue': '진동 증가', 'severity': 'warning', 'status': '처리중', 'details': '진동레벨: 높음, 정비 검토 필요', 'manager': '김철수', 'interlock_bypass': ''},
        {'id': 3, 'time': f'{current_date} 12:15:00', 'equipment': '검사기 #001', 'issue': '비상 정지', 'severity': 'error', 'status': '미처리', 'details': '센서 오류로 인한 비상 정지', 'manager': '', 'interlock_bypass': ''},
        {'id': 4, 'time': f'{current_date} 11:30:00', 'equipment': '조립기 #001', 'issue': '정기점검 완료', 'severity': 'info', 'status': '완료', 'details': '정기점검 완료, 정상 가동 재개', 'manager': '박영희', 'interlock_bypass': '인터락'},
        {'id': 5, 'time': f'{current_date} 10:45:00', 'equipment': '프레스기 #002', 'issue': '압력 불안정', 'severity': 'warning', 'status': '처리중', 'details': '압력 변동 폭 증가', 'manager': '이민수', 'interlock_bypass': ''},
        {'id': 6, 'time': f'{current_date} 09:20:00', 'equipment': '용접기 #001', 'issue': '품질 검사 불량', 'severity': 'error', 'status': '미처리', 'details': '불량률: 3.2% (기준: 2.5%)', 'manager': '', 'interlock_bypass': ''},
        {'id': 7, 'time': f'{current_date} 08:45:00', 'equipment': '용접기 #003', 'issue': '가스 압력 부족', 'severity': 'warning', 'status': '처리중', 'details': '가스 압력: 0.3MPa (기준: 0.5MPa)', 'manager': '최지영', 'interlock_bypass': ''},
        {'id': 8, 'time': f'{current_date} 08:15:00', 'equipment': '프레스기 #003', 'issue': '금형 교체 완료', 'severity': 'info', 'status': '완료', 'details': '금형 교체 작업 완료, 정상 가동 재개', 'manager': '정수민', 'interlock_bypass': '바이패스'},
        {'id': 9, 'time': f'{current_date} 07:30:00', 'equipment': '조립기 #002', 'issue': '부품 공급 지연', 'severity': 'warning', 'status': '미처리', 'details': '부품 재고 부족으로 인한 가동 중단', 'manager': '', 'interlock_bypass': ''},
        {'id': 10, 'time': f'{current_date} 07:00:00', 'equipment': '검사기 #002', 'issue': '센서 교정 완료', 'severity': 'info', 'status': '완료', 'details': '센서 교정 작업 완료, 정상 검사 재개', 'manager': '한상우', 'interlock_bypass': '인터락'},
        {'id': 11, 'time': f'{current_date} 06:45:00', 'equipment': '포장기 #001', 'issue': '포장재 부족', 'severity': 'warning', 'status': '처리중', 'details': '포장재 재고 부족, 추가 공급 대기', 'manager': '송미라', 'interlock_bypass': ''},
        {'id': 12, 'time': f'{current_date} 06:20:00', 'equipment': '프레스기 #004', 'issue': '유압 오일 온도 높음', 'severity': 'warning', 'status': '미처리', 'details': '유압 오일 온도: 75°C (기준: 65°C)', 'manager': '', 'interlock_bypass': ''},
        {'id': 13, 'time': f'{current_date} 05:30:00', 'equipment': '용접기 #004', 'issue': '전극 마모', 'severity': 'warning', 'status': '처리중', 'details': '전극 마모율: 85%, 교체 예정', 'manager': '강동원', 'interlock_bypass': ''},
        {'id': 14, 'time': f'{current_date} 05:00:00', 'equipment': '조립기 #003', 'issue': '컨베이어 벨트 이탈', 'severity': 'error', 'status': '미처리', 'details': '컨베이어 벨트 이탈로 인한 가동 중단', 'manager': '', 'interlock_bypass': ''},
        {'id': 15, 'time': f'{current_date} 04:30:00', 'equipment': '검사기 #003', 'issue': '카메라 렌즈 오염', 'severity': 'warning', 'status': '처리중', 'details': '카메라 렌즈 오염으로 인한 검사 정확도 저하', 'manager': '윤서연', 'interlock_bypass': ''},
        {'id': 16, 'time': f'{current_date} 04:00:00', 'equipment': '포장기 #002', 'issue': '시스템 오류', 'severity': 'error', 'status': '미처리', 'details': 'PLC 통신 오류로 인한 시스템 정지', 'manager': '', 'interlock_bypass': ''},
        {'id': 17, 'time': f'{current_date} 03:45:00', 'equipment': '용접기 #005', 'issue': '전극 수명 경고', 'severity': 'warning', 'status': '미처리', 'details': '전극 사용 시간: 95% (교체 필요)', 'manager': '', 'interlock_bypass': ''},
        {'id': 18, 'time': f'{current_date} 03:30:00', 'equipment': '프레스기 #005', 'issue': '유압 시스템 누수', 'severity': 'error', 'status': '미처리', 'details': '유압 오일 누수 감지, 긴급 정비 필요', 'manager': '', 'interlock_bypass': ''},
        {'id': 19, 'time': f'{current_date} 03:15:00', 'equipment': '검사기 #004', 'issue': '검사 정확도 저하', 'severity': 'warning', 'status': '처리중', 'details': '검사 정확도: 92% (기준: 95%)', 'manager': '임태호', 'interlock_bypass': ''},
        {'id': 20, 'time': f'{current_date} 03:00:00', 'equipment': '조립기 #004', 'issue': '부품 불량 감지', 'severity': 'error', 'status': '미처리', 'details': '부품 불량률: 4.1% (기준: 2.0%)', 'manager': '', 'interlock_bypass': ''},
        {'id': 21, 'time': f'{current_date} 02:45:00', 'equipment': '포장기 #003', 'issue': '포장 품질 저하', 'severity': 'warning', 'status': '처리중', 'details': '포장 품질 점수: 85점 (기준: 90점)', 'manager': '조현우', 'interlock_bypass': ''},
        {'id': 22, 'time': f'{current_date} 02:30:00', 'equipment': '용접기 #006', 'issue': '용접 강도 부족', 'severity': 'error', 'status': '미처리', 'details': '용접 강도: 78% (기준: 85%)', 'manager': '', 'interlock_bypass': ''},
        {'id': 23, 'time': f'{current_date} 02:15:00', 'equipment': '프레스기 #006', 'issue': '압력 변동 폭 증가', 'severity': 'warning', 'status': '처리중', 'details': '압력 변동: ±8% (기준: ±5%)', 'manager': '백지원', 'interlock_bypass': ''},
        {'id': 24, 'time': f'{current_date} 02:00:00', 'equipment': '검사기 #005', 'issue': '센서 교정 필요', 'severity': 'warning', 'status': '미처리', 'details': '센서 교정 주기 초과: 15일', 'manager': '', 'interlock_bypass': ''}
    ]
    return alerts

def generate_quality_trend():
    """품질 추세 데이터 생성 (PPM 300 기준)"""
    days = ['월', '화', '수', '목', '금', '토', '일']
    production_volume = [1200, 1350, 1180, 1420, 1247, 980, 650]
    
    # PPM 300 기준으로 불량률 계산 (300 PPM = 0.03%)
    base_ppm = 300
    ppm_variations = [280, 320, 290, 310, 300, 295, 305]  # 300 근처 변동
    
    # PPM을 불량률로 변환 (PPM / 1,000,000)
    defect_rates = [ppm / 1000000 for ppm in ppm_variations]
    
    # 품질률 계산 (100% - 불량률)
    quality_rates = [100 - (rate * 100) for rate in defect_rates]
    
    return pd.DataFrame({
        'day': days,
        'quality_rate': quality_rates,
        'production_volume': production_volume,
        'defect_rate': defect_rates,
        'PPM': ppm_variations
    })

def generate_production_kpi():
    """생산성 KPI 데이터 생성 (PPM 300 기준)"""
    # PPM 기준으로 품질률 계산 (PPM_TARGET PPM = 0.03% = 99.97%)
    quality_rate = 99.97  # PPM_TARGET에 해당하는 품질률
    
    return {
        'daily_target': 1300,
        'daily_actual': 1247,
        'weekly_target': 9100,
        'weekly_actual': 8727,
        'monthly_target': 39000,
        'monthly_actual': 35420,
        'oee': 87.3,  # Overall Equipment Effectiveness
        'availability': 94.2,
        'performance': 92.8,
        'quality': quality_rate  # PPM 300 기준 품질률
    }

def download_alerts_csv():
    """알림 데이터를 CSV로 다운로드 (시간 컬럼 분리, 새로운 컬럼 포함)"""
    alerts = generate_alert_data()
    df = pd.DataFrame(alerts)
    
    # manager와 interlock_bypass 컬럼이 없을 경우 기본값 추가
    if 'manager' not in df.columns:
        df['manager'] = ''
    if 'interlock_bypass' not in df.columns:
        df['interlock_bypass'] = ''
    
    # 시간 컬럼을 날짜와 시간으로 분리
    if 'time' in df.columns:
        # 시간 문자열을 datetime으로 변환
        df['datetime'] = pd.to_datetime(df['time'], format='%Y-%m-%d %H:%M', errors='coerce')
        
        # 날짜와 시간 컬럼 생성
        df['날짜'] = df['datetime'].dt.strftime('%y%m%d')  # YYMMDD 형식
        df['시간'] = df['datetime'].dt.strftime('%H:%M')   # HH:MM 형식
        
        # 원본 time 컬럼 제거하고 datetime 컬럼도 제거
        df = df.drop(['time', 'datetime'], axis=1)
        
        # 컬럼명 한글화
        column_mapping = {
            'equipment': '설비',
            'issue': '이슈',
            'severity': '심각도',
            'status': '상태',
            'details': '상세내용',
            'manager': '처리자',
            'interlock_bypass': '인터락/바이패스'
        }
        
        # 컬럼명 변경
        df.columns = [column_mapping.get(col, col) for col in df.columns]
        
        # 컬럼 순서 재정렬 (날짜, 시간을 앞으로)
        columns = ['날짜', '시간'] + [col for col in df.columns if col not in ['날짜', '시간']]
        df = df[columns]
    
    return df.to_csv(index=False)

def generate_comprehensive_report(use_real_api=True, report_type="종합 리포트", report_range="최근 7일"):
    """종합 리포트 생성 - 현재 대시보드 상태 기반"""
    # 현재 대시보드 상태에서 데이터 수집 (session state 기반)
    use_real_api_current = st.session_state.get('api_toggle', False)
    
    # 데이터 수집 (현재 토글 상태 기준)
    if use_real_api_current:
        try:
            sensor_data = get_sensor_data_from_api(use_real_api_current)
            equipment_data = get_equipment_status_from_api(use_real_api_current)
            alerts_data = get_alerts_from_api(use_real_api_current)
            ai_data = get_ai_prediction_results(use_real_api_current)
            production_kpi = generate_production_kpi()
            quality_data = generate_quality_trend()
        except:
            sensor_data = generate_sensor_data()
            equipment_data = generate_equipment_status()
            alerts_data = generate_alert_data()
            ai_data = generate_ai_prediction_data()
            production_kpi = generate_production_kpi()
            quality_data = generate_quality_trend()
    else:
        # 토글 OFF 시 현재 대시보드에서 사용하는 것과 동일한 데이터 사용
        sensor_data = generate_sensor_data()
        equipment_data = generate_equipment_status()  # 알림과 매치된 상태
        alerts_data = generate_alert_data()
        ai_data = generate_ai_prediction_data()
        production_kpi = generate_production_kpi()
        quality_data = generate_quality_trend()
    
    # 리포트 내용 생성
    report_content = f"""
# POSCO MOBILITY IoT 대시보드 종합 리포트

**생성일시:** {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}
**리포트 유형:** {report_type}
**분석 기간:** {report_range}
**데이터 소스:** {'실시간 API' if use_real_api else '더미 데이터'}

## 1. 생산성 KPI 요약

### 설비 종합 효율 (OEE)
- **현재 OEE:** {production_kpi['oee']:.1f}%
- **가동률:** {production_kpi['availability']:.1f}%
- **성능률:** {production_kpi['performance']:.1f}%
- **품질률:** {production_kpi['quality']:.1f}%

### 생산 지표
- **일일 목표:** {production_kpi['daily_target']:,}개
- **일일 실제:** {production_kpi['daily_actual']:,}개
- **주간 목표:** {production_kpi['weekly_target']:,}개
- **주간 실제:** {production_kpi['weekly_actual']:,}개
- **월간 목표:** {production_kpi['monthly_target']:,}개
- **월간 실제:** {production_kpi['monthly_actual']:,}개
- **불량률:** {100 - production_kpi['quality']:.2f}%

## 2. 설비 상태 현황

### 설비별 상태 분포
"""
    
    # 설비 상태 통계
    if equipment_data:
        df_equipment = pd.DataFrame(equipment_data)
        status_counts = df_equipment['status'].value_counts()
        for status, count in status_counts.items():
            report_content += f"- **{status}:** {count}대\n"
    
    report_content += f"""
### 평균 가동률
- **전체 설비 평균:** {np.mean([eq.get('efficiency', 0) for eq in equipment_data]):.1f}%

## 3. 알림 현황 분석

### 알림 통계
"""
    
    # 알림 통계
    if alerts_data:
        df_alerts = pd.DataFrame(alerts_data)
        total_alerts = len(df_alerts)
        error_count = len(df_alerts[df_alerts['severity'] == 'error'])
        warning_count = len(df_alerts[df_alerts['severity'] == 'warning'])
        info_count = len(df_alerts[df_alerts['severity'] == 'info'])
        
        report_content += f"""
- **전체 알림:** {total_alerts}건
- **긴급 알림:** {error_count}건
- **경고 알림:** {warning_count}건
- **정보 알림:** {info_count}건

### 심각도별 분포
- **Error (긴급):** {error_count/total_alerts*100:.1f}%
- **Warning (경고):** {warning_count/total_alerts*100:.1f}%
- **Info (정보):** {info_count/total_alerts*100:.1f}%
"""
    
    report_content += f"""
## 4. AI 분석 결과

### 설비 이상 예측
"""
    
    # AI 분석 결과
    if ai_data and 'abnormal_detection' in ai_data:
        abnormal = ai_data['abnormal_detection']
        if abnormal.get('status') == 'success':
            prediction = abnormal['prediction']
            probabilities = prediction['probabilities']
            max_prob = max(probabilities.values())
            max_status = [k for k, v in probabilities.items() if v == max_prob][0]
            
            status_names = {
                'normal': '정상',
                'bearing_fault': '베어링 고장',
                'roll_misalignment': '롤 정렬 불량',
                'motor_overload': '모터 과부하',
                'lubricant_shortage': '윤활유 부족'
            }
            
            report_content += f"""
- **현재 예측 상태:** {status_names.get(max_status, max_status)}
- **예측 신뢰도:** {max_prob:.1%}
- **모델 정확도:** 94.2%
"""
    
    report_content += f"""
### 유압 시스템 이상 탐지
"""
    
    if ai_data and 'hydraulic_detection' in ai_data:
        hydraulic = ai_data['hydraulic_detection']
        if hydraulic.get('status') == 'success':
            prediction = hydraulic['prediction']
            status = "정상" if prediction['prediction'] == 0 else "이상"
            report_content += f"""
- **현재 상태:** {status}
- **신뢰도:** {prediction['confidence']:.1%}
- **모델 정확도:** 91.8%
"""
    
    report_content += f"""
## 5. 품질 관리 현황

### 품질 지표
"""
    
    # 품질 데이터
    if quality_data is not None and len(quality_data) > 0:
        df_quality = pd.DataFrame(quality_data)
        if not df_quality.empty:
            avg_quality = df_quality['quality_rate'].mean()
            avg_defect_rate = df_quality['defect_rate'].mean()
            report_content += f"""
- **평균 품질률:** {avg_quality:.2f}%
- **평균 불량률:** {avg_defect_rate:.2f}%
- **품질 등급:** {'A' if avg_quality >= QUALITY_TARGET else 'B' if avg_quality >= QUALITY_TARGET - 0.5 else 'C'}
"""
    
    report_content += f"""
## 6. 권장사항 및 개선점

### 즉시 조치 필요사항
1. **설비 점검:** 정기 점검 일정 확인 및 실행
2. **AI 모델 모니터링:** 예측 정확도 지속적 모니터링
3. **알림 관리:** 긴급 알림에 대한 신속한 대응 체계 점검

### 장기 개선 계획
1. **예방 정비 강화:** AI 예측 기반 예방 정비 체계 구축
2. **품질 관리 고도화:** 실시간 품질 모니터링 시스템 확대
3. **데이터 분석 고도화:** 빅데이터 기반 의사결정 지원 시스템 구축

---
*본 리포트는 POSCO MOBILITY IoT 대시보드에서 자동 생성되었습니다.*
"""
    
    return report_content

def generate_csv_report(use_real_api=True, report_type="종합 리포트"):
    """CSV 형식 리포트 생성 (날짜 형식 개선)"""
    # 데이터 수집
    if use_real_api:
        try:
            sensor_data = get_sensor_data_from_api(use_real_api)
            equipment_data = get_equipment_status_from_api(use_real_api)
            alerts_data = get_alerts_from_api(use_real_api)
            production_kpi = generate_production_kpi()
            quality_data = generate_quality_trend()
        except:
            sensor_data = generate_sensor_data()
            equipment_data = generate_equipment_status()
            alerts_data = generate_alert_data()
            production_kpi = generate_production_kpi()
            quality_data = generate_quality_trend()
    else:
        sensor_data = generate_sensor_data()
        equipment_data = generate_equipment_status()
        alerts_data = generate_alert_data()
        production_kpi = generate_production_kpi()
        quality_data = generate_quality_trend()
    
    # 메타데이터
    metadata = pd.DataFrame([{
        '리포트 유형': report_type,
        '생성일시': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        '데이터 소스': '실시간 API' if use_real_api else '더미 데이터',
        'OEE': f"{production_kpi['oee']:.1f}%",
        '가동률': f"{production_kpi['availability']:.1f}%",
        '성능률': f"{production_kpi['performance']:.1f}%",
        '품질률': f"{production_kpi['quality']:.2f}%",
        '일일 목표': f"{production_kpi['daily_target']:,}개",
        '일일 실제': f"{production_kpi['daily_actual']:,}개"
    }])
    
    # 센서 데이터 (날짜 형식 개선)
    if isinstance(sensor_data, pd.DataFrame):
        sensor_df = sensor_data.copy()
    elif sensor_data is not None and len(sensor_data) > 0:
        sensor_df = pd.DataFrame(sensor_data)
    else:
        sensor_df = pd.DataFrame()
    
    if not sensor_df.empty and 'time' in sensor_df.columns:
        # datetime 형식을 Excel 호환 형식으로 변환하고 날짜/시간 분리
        try:
            # datetime으로 변환
            if pd.api.types.is_datetime64_any_dtype(sensor_df['time']):
                sensor_df['datetime'] = sensor_df['time']
            else:
                sensor_df['datetime'] = pd.to_datetime(sensor_df['time'])
            
            # 날짜와 시간으로 분리
            sensor_df['day'] = sensor_df['datetime'].dt.strftime('%Y-%m-%d')
            sensor_df['time'] = sensor_df['datetime'].dt.strftime('%H:%M:%S')
            
            # 원본 time 컬럼과 datetime 컬럼 제거
            sensor_df = sensor_df.drop(['datetime'], axis=1, errors='ignore')
            
        except:
            # 변환 실패 시 현재 시간으로 대체
            current_time = datetime.now()
            sensor_df['day'] = current_time.strftime('%Y-%m-%d')
            sensor_df['time'] = current_time.strftime('%H:%M:%S')
    
    # 설비 데이터
    if isinstance(equipment_data, pd.DataFrame):
        equipment_df = equipment_data
    elif equipment_data is not None and len(equipment_data) > 0:
        equipment_df = pd.DataFrame(equipment_data)
    else:
        equipment_df = pd.DataFrame()
    
    # 알림 데이터 (날짜 형식 개선)
    if isinstance(alerts_data, pd.DataFrame):
        alerts_df = alerts_data.copy()
    elif alerts_data is not None and len(alerts_data) > 0:
        alerts_df = pd.DataFrame(alerts_data)
    else:
        alerts_df = pd.DataFrame()
    
    # 알림 데이터의 시간 컬럼을 날짜와 시간으로 분리
    if not alerts_df.empty and 'time' in alerts_df.columns:
        try:
            # datetime으로 변환
            if pd.api.types.is_datetime64_any_dtype(alerts_df['time']):
                alerts_df['datetime'] = alerts_df['time']
            else:
                alerts_df['datetime'] = pd.to_datetime(alerts_df['time'])
            
            # 날짜와 시간으로 분리
            alerts_df['day'] = alerts_df['datetime'].dt.strftime('%Y-%m-%d')
            alerts_df['time'] = alerts_df['datetime'].dt.strftime('%H:%M:%S')
            
            # 원본 time 컬럼과 datetime 컬럼 제거
            alerts_df = alerts_df.drop(['datetime'], axis=1, errors='ignore')
            
        except:
            # 변환 실패 시 현재 시간으로 대체
            current_time = datetime.now()
            alerts_df['day'] = current_time.strftime('%Y-%m-%d')
            alerts_df['time'] = current_time.strftime('%H:%M:%S')
    
    # 품질 데이터
    if isinstance(quality_data, pd.DataFrame):
        quality_df = quality_data
    elif quality_data is not None and len(quality_data) > 0:
        quality_df = pd.DataFrame(quality_data)
    else:
        quality_df = pd.DataFrame()
    
    # CSV 파일 생성
    output = io.StringIO()
    
    # 메타데이터
    output.write("=== 메타데이터 ===\n")
    metadata.to_csv(output, index=False, encoding='utf-8-sig')  # BOM 추가로 한글 지원
    output.write("\n")
    
    # KPI 요약
    output.write("=== KPI 요약 ===\n")
    kpi_summary = pd.DataFrame([{
        '지표': 'OEE (설비종합효율)',
        '값': f"{production_kpi['oee']:.1f}",
        '단위': '%',
        '상태': '양호' if production_kpi['oee'] >= OEE_TARGET else '개선필요'
    }, {
        '지표': '가동률',
        '값': f"{production_kpi['availability']:.1f}",
        '단위': '%',
        '상태': '양호' if production_kpi['availability'] >= 90 else '개선필요'
    }, {
        '지표': '성능률',
        '값': f"{production_kpi['performance']:.1f}",
        '단위': '%',
        '상태': '양호' if production_kpi['performance'] >= 90 else '개선필요'
    }, {
        '지표': '품질률',
        '값': f"{production_kpi['quality']:.2f}",
        '단위': '%',
        '상태': '우수' if production_kpi['quality'] >= QUALITY_TARGET else '양호'
    }])
    kpi_summary.to_csv(output, index=False, encoding='utf-8-sig')
    output.write("\n")
    
    # 품질 데이터
    if not quality_df.empty:
        output.write("=== 품질 추세 데이터 ===\n")
        quality_df.to_csv(output, index=False, encoding='utf-8-sig')
        output.write("\n")
    
    # 센서 데이터
    if not sensor_df.empty:
        output.write("=== 센서 데이터 ===\n")
        sensor_df.to_csv(output, index=False, encoding='utf-8-sig')
        output.write("\n")
    
    # 설비 데이터
    if not equipment_df.empty:
        output.write("=== 설비 상태 데이터 ===\n")
        equipment_df.to_csv(output, index=False, encoding='utf-8-sig')
        output.write("\n")
    
    # 알림 데이터
    if not alerts_df.empty:
        output.write("=== 알림 데이터 ===\n")
        alerts_df.to_csv(output, index=False, encoding='utf-8-sig')
    
    return output.getvalue()

def generate_pdf_report(use_real_api=True, report_type="종합 리포트"):
    """PDF 형식 리포트 생성 (실무적 고급 디자인)"""
    # PDF 생성 - 여백 확대
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, 
                           leftMargin=25, rightMargin=25, 
                           topMargin=25, bottomMargin=25)
    story = []
    
    # 한글 폰트 설정 (안전한 방식)
    try:
        # 나눔고딕 폰트 등록 시도
        pdfmetrics.registerFont(TTFont('NanumGothic', 'NanumGothic.ttf'))
        korean_font = 'NanumGothic'
    except:
        try:
            # 맑은 고딕 폰트 등록 시도
            pdfmetrics.registerFont(TTFont('MalgunGothic', 'malgun.ttf'))
            korean_font = 'MalgunGothic'
        except:
            # 한글 폰트가 없으면 기본 폰트 사용
            korean_font = 'Helvetica'
    
    # 실무적 고급 스타일 설정
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontName=korean_font,
        fontSize=24,
        spaceAfter=35,
        alignment=1,  # 중앙 정렬
        textColor=colors.HexColor('#05507D'),  # POSCO Blue
        spaceBefore=25
    )
    subtitle_style = ParagraphStyle(
        'CustomSubtitle',
        parent=styles['Heading1'],
        fontName=korean_font,
        fontSize=18,
        spaceAfter=30,
        alignment=1,  # 중앙 정렬
        textColor=colors.HexColor('#00A5E5'),  # POSCO Light Blue
        spaceBefore=10
    )
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontName=korean_font,
        fontSize=16,
        spaceAfter=20,
        spaceBefore=30,
        textColor=colors.HexColor('#05507D'),  # POSCO Blue
        leftIndent=15,
        borderWidth=0,
        borderColor=colors.HexColor('#05507D'),
        borderPadding=8,
        backColor=colors.HexColor('#F8F9FA')
    )
    normal_style = ParagraphStyle(
        'CustomNormal',
        parent=styles['Normal'],
        fontName=korean_font,
        fontSize=11,
        spaceAfter=10,
        leading=16
    )
    highlight_style = ParagraphStyle(
        'Highlight',
        parent=styles['Normal'],
        fontName=korean_font,
        fontSize=12,
        spaceAfter=8,
        textColor=colors.HexColor('#00A5E5'),  # POSCO Light Blue
        leading=18
    )
    summary_style = ParagraphStyle(
        'Summary',
        parent=styles['Normal'],
        fontName=korean_font,
        fontSize=13,
        spaceAfter=12,
        textColor=colors.HexColor('#4B5151'),  # Dark Gray
        leading=20,
        leftIndent=20
    )
    
    # 데이터 수집
    if use_real_api:
        try:
            production_kpi = generate_production_kpi()
            equipment_data = get_equipment_status_from_api(use_real_api)
            alerts_data = get_alerts_from_api(use_real_api)
            quality_data = generate_quality_trend()
            sensor_data = get_sensor_data_from_api(use_real_api) or generate_sensor_data()
        except:
            production_kpi = generate_production_kpi()
            equipment_data = generate_equipment_status()
            alerts_data = generate_alert_data()
            quality_data = generate_quality_trend()
            sensor_data = generate_sensor_data()
    else:
        production_kpi = generate_production_kpi()
        equipment_data = generate_equipment_status()
        alerts_data = generate_alert_data()
        quality_data = generate_quality_trend()
        sensor_data = generate_sensor_data()
    
    # 헤더 섹션 (실무적 디자인)
    story.append(Paragraph("POSCO MOBILITY IoT 대시보드", title_style))
    story.append(Paragraph("종합 분석 리포트", subtitle_style))
    story.append(Spacer(1, 25))
    
    # 메타 정보 (실무적 테이블 디자인)
    meta_info = f"""
    <table width="100%" cellpadding="8" cellspacing="0" border="1" bordercolor="#DEE2E6">
    <tr bgcolor="#05507D">
        <td width="20%" style="color: white; font-weight: bold; text-align: center;">생성일시</td>
        <td width="30%" style="text-align: center;">{datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}</td>
        <td width="20%" style="color: white; font-weight: bold; text-align: center;">리포트 유형</td>
        <td width="30%" style="text-align: center;">{report_type}</td>
    </tr>
    <tr bgcolor="#F8F9FA">
        <td style="font-weight: bold; text-align: center;">데이터 소스</td>
        <td style="text-align: center;">{'실시간 API' if use_real_api else '더미 데이터'}</td>
        <td style="font-weight: bold; text-align: center;">생성자</td>
        <td style="text-align: center;">POSCO MOBILITY IoT 시스템</td>
    </tr>
    </table>
    """
    story.append(Paragraph(meta_info, normal_style))
    story.append(Spacer(1, 30))
    
    # 1. KPI 대시보드 (실무적 디자인)
    story.append(Paragraph("1. 핵심 성과 지표 (KPI) 대시보드", heading_style))
    
    # KPI 요약 정보
    kpi_summary = f"""
    <b>📊 KPI 현황 요약</b><br/>
    • OEE (설비종합효율): <b>{production_kpi['oee']:.1f}%</b> (목표: {OEE_TARGET:.1f}%) - {'🟢 양호' if production_kpi['oee'] >= OEE_TARGET else '🟡 개선필요'}<br/>
    • 가동률: <b>{production_kpi['availability']:.1f}%</b> (목표: {AVAILABILITY_TARGET:.1f}%) - {'🟢 양호' if production_kpi['availability'] >= AVAILABILITY_TARGET else '🟡 개선필요'}<br/>
• 성능률: <b>{production_kpi['performance']:.1f}%</b> (목표: {PERFORMANCE_TARGET:.1f}%) - {'🟢 양호' if production_kpi['performance'] >= PERFORMANCE_TARGET else '🟡 개선필요'}<br/>
    • 품질률: <b>{production_kpi['quality']:.2f}%</b> (목표: {QUALITY_TARGET:.1f}%) - {'🟢 우수' if production_kpi['quality'] >= QUALITY_TARGET else '🟡 양호'}<br/>
    • 일일 생산량: <b>{production_kpi['daily_actual']:,}개</b> (목표: {production_kpi['daily_target']:,}개) - {'🟢 달성' if production_kpi['daily_actual'] >= production_kpi['daily_target'] else '🟡 미달성'}<br/>
    """
    story.append(Paragraph(kpi_summary, summary_style))
    
    # KPI 상세 테이블 (크기 확대)
    kpi_data = [
        ['지표', '현재값', '목표값', '달성률', '상태'],
        ['OEE (설비종합효율)', f"{production_kpi['oee']:.1f}%", f'{OEE_TARGET:.1f}%', f"{production_kpi['oee']/OEE_TARGET*100:.1f}%", 
         '🟢 양호' if production_kpi['oee'] >= OEE_TARGET else '🟡 개선필요'],
        ['가동률', f"{production_kpi['availability']:.1f}%", f'{AVAILABILITY_TARGET:.1f}%', f"{production_kpi['availability']/AVAILABILITY_TARGET*100:.1f}%", 
         '🟢 양호' if production_kpi['availability'] >= AVAILABILITY_TARGET else '🟡 개선필요'],
        ['성능률', f"{production_kpi['performance']:.1f}%", f'{PERFORMANCE_TARGET:.1f}%', f"{production_kpi['performance']/PERFORMANCE_TARGET*100:.1f}%", 
         '🟢 양호' if production_kpi['performance'] >= PERFORMANCE_TARGET else '🟡 개선필요'],
        ['품질률', f"{production_kpi['quality']:.2f}%", f'{QUALITY_TARGET:.1f}%', f"{production_kpi['quality']/QUALITY_TARGET*100:.1f}%", 
         '🟢 우수' if production_kpi['quality'] >= QUALITY_TARGET else '🟡 양호'],
        ['일일 생산량', f"{production_kpi['daily_actual']:,}개", f"{production_kpi['daily_target']:,}개", 
         f"{production_kpi['daily_actual']/production_kpi['daily_target']*100:.1f}%", 
         '🟢 달성' if production_kpi['daily_actual'] >= production_kpi['daily_target'] else '🟡 미달성']
    ]
    
    kpi_table = Table(kpi_data, colWidths=[150, 100, 100, 100, 120])
    kpi_table.setStyle(TableStyle([
        # 헤더 스타일
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#05507D')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), korean_font),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 18),
        ('TOPPADDING', (0, 0), (-1, 0), 12),
        # 데이터 행 스타일
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#FFFFFF')),
        ('FONTNAME', (0, 1), (-1, -1), korean_font),
        ('FONTSIZE', (0, 1), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 12),
        ('TOPPADDING', (0, 1), (-1, -1), 12),
        # 그리드 및 정렬
        ('GRID', (0, 0), (-1, -1), 1.5, colors.HexColor('#DEE2E6')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        # 번갈아가는 행 색상
        ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#F8F9FA')),
        ('BACKGROUND', (0, 4), (-1, 4), colors.HexColor('#F8F9FA')),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 25))
    
    # 2. 품질 분석 (실무적 디자인)
    story.append(Paragraph("2. 품질 관리 분석", heading_style))
    
    if quality_data is not None and len(quality_data) > 0:
        df_quality = pd.DataFrame(quality_data)
        avg_quality = df_quality['quality_rate'].mean()
        avg_defect_rate = df_quality['defect_rate'].mean()
        
        quality_summary = f"""
        <b>📊 품질 현황 요약</b><br/>
        • 평균 품질률: <b>{avg_quality:.2f}%</b> ({'🟢 우수' if avg_quality >= QUALITY_TARGET else '🟡 양호'})<br/>
        • 평균 불량률: <b>{avg_defect_rate:.3f}%</b> ({'🟢 양호' if avg_defect_rate <= 0.05 else '🟡 개선필요'})<br/>
        • 최고 품질률: <b>{df_quality['quality_rate'].max():.2f}%</b><br/>
        • 최저 품질률: <b>{df_quality['quality_rate'].min():.2f}%</b><br/>
        """
        story.append(Paragraph(quality_summary, summary_style))
        
        # 품질 추세 테이블 (크기 확대)
        quality_trend_data = [['요일', '품질률 (%)', '불량률 (%)', '생산량 (개)']]
        for _, row in df_quality.iterrows():
            quality_trend_data.append([
                row['day'], 
                f"{row['quality_rate']:.2f}", 
                f"{row['defect_rate']:.3f}", 
                f"{row['production_volume']:,}"
            ])
        
        quality_trend_table = Table(quality_trend_data, colWidths=[120, 120, 120, 140])
        quality_trend_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#05507D')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), korean_font),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('FONTSIZE', (0, 1), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 15),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1.5, colors.HexColor('#DEE2E6')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#F8F9FA')),
            ('BACKGROUND', (0, 4), (-1, 4), colors.HexColor('#F8F9FA')),
            ('BACKGROUND', (0, 6), (-1, 6), colors.HexColor('#F8F9FA')),
        ]))
        story.append(quality_trend_table)
        story.append(Spacer(1, 25))
    
    # 3. 설비 상태 분석 (실무적 디자인)
    story.append(Paragraph("3. 설비 상태 및 효율성 분석", heading_style))
    
    if equipment_data:
        df_equipment = pd.DataFrame(equipment_data)
        status_counts = df_equipment['status'].value_counts()
        total_equipment = len(df_equipment)
        
        # 설비 상태 요약
        status_summary = f"""
        <b>🏭 설비 현황 요약</b><br/>
        • 총 설비 수: <b>{total_equipment}대</b><br/>
        • 정상 가동: <b>{status_counts.get('정상', 0)}대</b> ({status_counts.get('정상', 0)/total_equipment*100:.1f}%)<br/>
        • 주의 필요: <b>{status_counts.get('주의', 0)}대</b> ({status_counts.get('주의', 0)/total_equipment*100:.1f}%)<br/>
        • 오류 발생: <b>{status_counts.get('오류', 0)}대</b> ({status_counts.get('오류', 0)/total_equipment*100:.1f}%)<br/>
        """
        story.append(Paragraph(status_summary, summary_style))
        
        # 설비별 상세 정보 (상위 10개, 크기 확대)
        equipment_detail_data = [['설비명', '상태', '효율률 (%)', '유형', '최근 정비일']]
        for _, row in df_equipment.head(10).iterrows():
            status_icon = '🟢' if row['status'] == '정상' else '🟡' if row['status'] == '주의' else '🔴'
            equipment_detail_data.append([
                row['name'],
                f"{status_icon} {row['status']}",
                f"{row['efficiency']:.1f}",
                row['type'],
                row['last_maintenance']
            ])
        
        equipment_detail_table = Table(equipment_detail_data, colWidths=[150, 100, 100, 100, 120])
        equipment_detail_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#05507D')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), korean_font),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('FONTSIZE', (0, 1), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 15),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1.5, colors.HexColor('#DEE2E6')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#F8F9FA')),
            ('BACKGROUND', (0, 4), (-1, 4), colors.HexColor('#F8F9FA')),
            ('BACKGROUND', (0, 6), (-1, 6), colors.HexColor('#F8F9FA')),
            ('BACKGROUND', (0, 8), (-1, 8), colors.HexColor('#F8F9FA')),
        ]))
        story.append(equipment_detail_table)
        story.append(Spacer(1, 25))
    
    # 4. 알림 분석 (실무적 디자인)
    story.append(Paragraph("4. 알림 및 이슈 분석", heading_style))
    
    if alerts_data:
        df_alerts = pd.DataFrame(alerts_data)
        total_alerts = len(df_alerts)
        error_count = len(df_alerts[df_alerts['severity'] == 'error'])
        warning_count = len(df_alerts[df_alerts['severity'] == 'warning'])
        info_count = len(df_alerts[df_alerts['severity'] == 'info'])
        
        # 알림 요약
        alert_summary = f"""
        <b>🚨 알림 현황 요약</b><br/>
        • 총 알림 수: <b>{total_alerts}건</b><br/>
        • 긴급 알림: <b>{error_count}건</b> ({error_count/total_alerts*100:.1f}%) - 최우선 처리 필요<br/>
        • 경고 알림: <b>{warning_count}건</b> ({warning_count/total_alerts*100:.1f}%) - 주의 깊게 모니터링<br/>
        • 정보 알림: <b>{info_count}건</b> ({info_count/total_alerts*100:.1f}%) - 참고사항<br/>
        """
        story.append(Paragraph(alert_summary, summary_style))
        
        # 주요 알림 상세 (상위 8개, 크기 확대)
        alert_detail_data = [['시간', '설비', '이슈', '심각도', '상태']]
        for _, row in df_alerts.head(8).iterrows():
            severity_icon = '🔴' if row['severity'] == 'error' else '🟡' if row['severity'] == 'warning' else '🔵'
            alert_detail_data.append([
                row['time'],
                row['equipment'],
                row['issue'][:25] + '...' if len(row['issue']) > 25 else row['issue'],
                f"{severity_icon} {row['severity']}",
                row['status']
            ])
        
        alert_detail_table = Table(alert_detail_data, colWidths=[100, 100, 150, 90, 90])
        alert_detail_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#05507D')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), korean_font),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('FONTSIZE', (0, 1), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 15),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1.5, colors.HexColor('#DEE2E6')),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('BACKGROUND', (0, 2), (-1, 2), colors.HexColor('#F8F9FA')),
            ('BACKGROUND', (0, 4), (-1, 4), colors.HexColor('#F8F9FA')),
            ('BACKGROUND', (0, 6), (-1, 6), colors.HexColor('#F8F9FA')),
        ]))
        story.append(alert_detail_table)
        story.append(Spacer(1, 25))
    
    # 5. 센서 데이터 분석 (실무적 디자인)
    story.append(Paragraph("5. 센서 데이터 분석", heading_style))
    
    if sensor_data is not None and len(sensor_data) > 0:
        df_sensor = pd.DataFrame(sensor_data) if not isinstance(sensor_data, pd.DataFrame) else sensor_data
        
        if not df_sensor.empty and 'temperature' in df_sensor.columns:
            # 센서 데이터 요약
            temp_avg = df_sensor['temperature'].mean()
            pressure_avg = df_sensor['pressure'].mean()
            vibration_avg = df_sensor['vibration'].mean()
            
            sensor_summary = f"""
            <b>📡 센서 데이터 요약</b><br/>
            • 평균 온도: <b>{temp_avg:.1f}°C</b> (정상 범위: 20-80°C)<br/>
            • 평균 압력: <b>{pressure_avg:.1f} bar</b> (정상 범위: 100-200 bar)<br/>
            • 평균 진동: <b>{vibration_avg:.2f} mm/s</b> (정상 범위: 0.2-1.0 mm/s)<br/>
            • 데이터 포인트: <b>{len(df_sensor)}개</b><br/>
            """
            story.append(Paragraph(sensor_summary, summary_style))
    
    # 6. 권장사항 및 액션 플랜 (실무적 디자인)
    story.append(Paragraph("6. 권장사항 및 액션 플랜", heading_style))
    
    # 즉시 조치사항
    immediate_actions = f"""
    <b>⚡ 즉시 조치 필요사항</b><br/>
    """
    if error_count > 0:
        immediate_actions += f"• 🔴 긴급 알림 {error_count}건 신속 처리 (24시간 이내)<br/>"
    if production_kpi['oee'] < 85:
        immediate_actions += f"• 🟡 OEE 개선 활동 강화 (현재: {production_kpi['oee']:.1f}%)<br/>"
    if 'avg_defect_rate' in locals() and avg_defect_rate > 0.05:
        immediate_actions += f"• 🟡 품질 관리 강화 (불량률: {avg_defect_rate:.3f}%)<br/>"
    
    immediate_actions += """
    • 🔧 설비 점검 일정 재검토 및 실행<br/>
    • 🤖 AI 모델 예측 정확도 모니터링 강화<br/>
    • 📊 실시간 데이터 분석 체계 점검<br/>
    """
    story.append(Paragraph(immediate_actions, summary_style))
    
    # 장기 개선 계획
    long_term_plan = f"""
    <b>📈 장기 개선 계획</b><br/>
    • 🏭 예방 정비 체계 고도화: AI 예측 기반 스마트 정비 시스템 구축<br/>
    • 📊 품질 관리 시스템 확대: 실시간 품질 모니터링 및 자동화<br/>
    • 🧠 데이터 분석 플랫폼 구축: 빅데이터 기반 의사결정 지원 시스템<br/>
    • 🌐 디지털 트윈 구현: 가상 설비 모델링을 통한 최적화<br/>
    • 🔄 자동화 및 로봇화 확대: 인력 효율성 증대 및 안전성 향상<br/>
    • 📱 모바일 대시보드 개발: 현장 작업자 접근성 향상<br/>
    """
    story.append(Paragraph(long_term_plan, normal_style))
    
    # 7. 결론 및 다음 단계 (실무적 디자인)
    story.append(Paragraph("7. 결론 및 다음 단계", heading_style))
    
    conclusion = f"""
    <b>📋 종합 평가</b><br/>
    현재 POSCO MOBILITY IoT 시스템은 전반적으로 안정적인 운영 상태를 보이고 있습니다. 
    OEE {production_kpi['oee']:.1f}%, 품질률 {production_kpi['quality']:.2f}%의 성과를 달성하고 있으며, 
    지속적인 모니터링과 개선 활동을 통해 더욱 높은 수준의 운영 효율성을 달성할 수 있을 것으로 예상됩니다.<br/><br/>
    
    <b>🎯 다음 단계</b><br/>
    1. 이 리포트의 권장사항을 바탕으로 즉시 조치사항 실행<br/>
    2. 주간/월간 성과 리뷰를 통한 지속적 개선<br/>
    3. AI 모델 성능 모니터링 및 업데이트<br/>
    4. 디지털 트윈 구축을 위한 기술 검토 및 계획 수립<br/>
    """
    story.append(Paragraph(conclusion, normal_style))
    
    # PDF 생성
    try:
        doc.build(story)
    except Exception as e:
        # 한글 폰트가 없을 경우 기본 폰트로 재시도
        for style in [title_style, subtitle_style, heading_style, normal_style, highlight_style, summary_style]:
            style.fontName = 'Helvetica'
        doc.build(story)
    
    buffer.seek(0)
    return buffer



def update_sensor_data_container(use_real_api=True, selected_sensor="전체"):
    """센서 데이터 컨테이너 업데이트"""
    if st.session_state.sensor_container is None:
        st.session_state.sensor_container = st.empty()

    with st.session_state.sensor_container.container():
        # 데이터 제거 후인지 확인
        data_cleared = st.session_state.get('data_cleared', False)
        
        if data_cleared and not use_real_api:
            # 데이터가 제거된 경우 빈 그래프 표시
            fig = go.Figure()
            fig.add_annotation(
                text="센서 데이터가 없습니다",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=14, color="gray")
            )
            fig.update_layout(
                height=200,
                margin=dict(l=8, r=8, t=8, b=8),
                plot_bgcolor='white',
                paper_bgcolor='white'
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
            return

        # 센서 데이터 가져오기 및 검증
        try:
            if use_real_api:
                sensor_data = get_sensor_data_from_api(use_real_api)
                # API 데이터 검증
                if sensor_data is not None and (
                    (isinstance(sensor_data, dict) and sensor_data) or
                    (isinstance(sensor_data, pd.DataFrame) and not sensor_data.empty)
                ):
                    st.session_state.data_cleared = False
                else:
                    print("API 센서 데이터가 비어있거나 유효하지 않음, 더미 데이터 사용")
                    sensor_data = generate_sensor_data()
            else:
                sensor_data = generate_sensor_data()
        except Exception as e:
            print(f"센서 데이터 로드 오류: {e}")
            sensor_data = generate_sensor_data()

        # 설비 필터 적용 (안전한 접근)
        equipment_filter = st.session_state.get('equipment_filter', [])
        
        # 센서 데이터 처리
        if sensor_data is not None and (
            (isinstance(sensor_data, dict) and sensor_data) or
            (isinstance(sensor_data, pd.DataFrame) and not sensor_data.empty)
        ):
            fig = go.Figure()
            
            if isinstance(sensor_data, dict) and use_real_api:
                # API 데이터 형식 (dict)
                if selected_sensor == "전체":
                    # 모든 센서 데이터 표시
                    if 'temperature' in sensor_data and sensor_data['temperature']:
                        temp_times = [d['timestamp'] for d in sensor_data['temperature']]
                        temp_values = [d['value'] for d in sensor_data['temperature']]
                        fig.add_trace(go.Scatter(
                            x=temp_times,
                            y=temp_values,
                            mode='lines',
                            name='온도',
                            line=dict(color='#ef4444', width=2)
                        ))
                    if 'pressure' in sensor_data and sensor_data['pressure']:
                        pres_times = [d['timestamp'] for d in sensor_data['pressure']]
                        pres_values = [d['value'] for d in sensor_data['pressure']]
                        fig.add_trace(go.Scatter(
                            x=pres_times,
                            y=pres_values,
                            mode='lines',
                            name='압력',
                            line=dict(color='#3b82f6', width=2),
                            yaxis='y2'
                        ))
                    if 'vibration' in sensor_data and sensor_data['vibration']:
                        vib_times = [d['timestamp'] for d in sensor_data['vibration']]
                        vib_values = [d['value'] for d in sensor_data['vibration']]
                        fig.add_trace(go.Scatter(
                            x=vib_times,
                            y=vib_values,
                            mode='lines',
                            name='진동',
                            line=dict(color='#10b981', width=2),
                            yaxis='y3'
                        ))
                    fig.update_layout(
                        yaxis=dict(title={'text':"온도", 'font':{'size':9}}, side="left"),
                        yaxis2=dict(title={'text':"압력", 'font':{'size':9}}, overlaying="y", side="right"),
                        yaxis3=dict(title={'text':"진동", 'font':{'size':9}}, overlaying="y", side="right", position=0.95)
                    )
                else:
                    # 선택된 센서만 표시
                    sensor_mapping = {
                        "온도": ("temperature", "#ef4444", "온도 (°C)"),
                        "압력": ("pressure", "#3b82f6", "압력 (MPa)"),
                        "진동": ("vibration", "#10b981", "진동 (mm/s)")
                    }
                    if selected_sensor in sensor_mapping:
                        sensor_key, color, title = sensor_mapping[selected_sensor]
                        if sensor_key in sensor_data and sensor_data[sensor_key]:
                            times = [d['timestamp'] for d in sensor_data[sensor_key]]
                            values = [d['value'] for d in sensor_data[sensor_key]]
                            fig.add_trace(go.Scatter(
                                x=times,
                                y=values,
                                mode='lines',
                                name=selected_sensor,
                                line=dict(color=color, width=2)
                            ))
                            fig.update_layout(
                                yaxis=dict(title={'text': title, 'font':{'size':9}})
                            )
            elif isinstance(sensor_data, pd.DataFrame):
                # DataFrame 형식 (더미 데이터)
                if selected_sensor == "전체":
                    # 설비 필터 적용 (안전한 접근)
                    if equipment_filter and isinstance(equipment_filter, list) and 'equipment' in sensor_data.columns:
                        # 필터링된 설비의 데이터만 사용
                        filtered_data = sensor_data[sensor_data['equipment'].isin(equipment_filter)]
                        if not filtered_data.empty:
                            first_equipment = filtered_data['equipment'].iloc[0]
                            equipment_data = filtered_data[filtered_data['equipment'] == first_equipment]
                        else:
                            equipment_data = sensor_data.head(1)  # 필터링된 데이터가 없으면 첫 번째 설비 사용
                    elif 'equipment' in sensor_data.columns:
                        first_equipment = sensor_data['equipment'].iloc[0]
                        equipment_data = sensor_data[sensor_data['equipment'] == first_equipment]
                    else:
                        equipment_data = sensor_data
                    
                    if 'temperature' in equipment_data.columns:
                        fig.add_trace(go.Scatter(
                            x=list(range(len(equipment_data))),
                            y=equipment_data['temperature'],
                            mode='lines',
                            name='온도',
                            line=dict(color='#ef4444', width=2)
                        ))
                    if 'pressure' in equipment_data.columns:
                        fig.add_trace(go.Scatter(
                            x=list(range(len(equipment_data))),
                            y=equipment_data['pressure'],
                            mode='lines',
                            name='압력',
                            line=dict(color='#3b82f6', width=2),
                            yaxis='y2'
                        ))
                    if 'vibration' in equipment_data.columns:
                        fig.add_trace(go.Scatter(
                            x=list(range(len(equipment_data))),
                            y=equipment_data['vibration'],
                            mode='lines',
                            name='진동',
                            line=dict(color='#10b981', width=2),
                            yaxis='y3'
                        ))
                    fig.update_layout(
                        yaxis=dict(title={'text':"온도", 'font':{'size':9}}, side="left"),
                        yaxis2=dict(title={'text':"압력", 'font':{'size':9}}, overlaying="y", side="right"),
                        yaxis3=dict(title={'text':"진동", 'font':{'size':9}}, overlaying="y", side="right", position=0.95)
                    )
                else:
                    # 선택된 센서만 표시
                    sensor_mapping = {
                        "온도": ("temperature", "#ef4444", "온도 (°C)"),
                        "압력": ("pressure", "#3b82f6", "압력 (MPa)"),
                        "진동": ("vibration", "#10b981", "진동 (mm/s)")
                    }
                    if selected_sensor in sensor_mapping:
                        sensor_key, color, title = sensor_mapping[selected_sensor]
                        if sensor_key in sensor_data.columns:
                            if 'equipment' in sensor_data.columns:
                                first_equipment = sensor_data['equipment'].iloc[0]
                                equipment_data = sensor_data[sensor_data['equipment'] == first_equipment]
                            else:
                                equipment_data = sensor_data
                            fig.add_trace(go.Scatter(
                                x=list(range(len(equipment_data))),
                                y=equipment_data[sensor_key],
                                mode='lines',
                                name=selected_sensor,
                                line=dict(color=color, width=2)
                            ))
                            fig.update_layout(
                                yaxis=dict(title={'text': title, 'font':{'size':9}})
                            )
            
            fig.update_layout(
                height=200,
                margin=dict(l=8, r=8, t=8, b=8),
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=9)),
                xaxis=dict(title={'text':"시간", 'font':{'size':9}}),
                plot_bgcolor='white',
                paper_bgcolor='white',
                font=dict(color='#1e293b', size=9)
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            # 센서 데이터가 없는 경우 빈 그래프 표시
            fig = go.Figure()
            fig.add_annotation(
                text="센서 데이터를 불러올 수 없습니다",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=14, color="gray")
            )
            fig.update_layout(
                height=200,
                margin=dict(l=8, r=8, t=8, b=8),
                plot_bgcolor='white',
                paper_bgcolor='white'
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

def update_alert_container(use_real_api=True):
    """업무 알림 컨테이너 업데이트 - ERROR와 WARNING 알림 표시 (최소 4개 이상 보장)"""
    if st.session_state.alert_container is None:
        st.session_state.alert_container = st.empty()
    
    with st.session_state.alert_container.container():
        st.markdown('<div class="chart-title no-translate" translate="no" style="font-size:1rem; margin-bottom:0.05rem;">업무 알림</div>', unsafe_allow_html=True)
        
        # 데이터 제거 후인지 확인
        data_cleared = st.session_state.get('data_cleared', False)
        
        if data_cleared:
            # 데이터가 제거된 경우 빈 테이블 표시
            empty_df = pd.DataFrame(columns=['설비', '이슈', '시간'])
            empty_df.index = range(1, 1)  # 빈 인덱스
            st.dataframe(empty_df, height=200, use_container_width=True)
            return
        
        alerts = get_alerts_from_api(use_real_api)  # 토글 상태에 따라 자동으로 더미데이터 또는 API 데이터 반환
        
        # API 데이터를 가져왔으면 데이터 제거 플래그 해제
        if use_real_api and alerts:
            st.session_state.data_cleared = False
            pass  # 알림 데이터 제거 플래그 해제됨
        
        # 설비 필터 적용 (안전한 접근)
        equipment_filter = st.session_state.get('equipment_filter', [])
        if equipment_filter and isinstance(equipment_filter, list):
            # 필터링된 설비의 알림만 표시
            filtered_alerts = [a for a in alerts if a['equipment'] in equipment_filter]
        else:
            # 필터가 없으면 모든 알림 표시
            filtered_alerts = alerts
        
        # ERROR와 WARNING 발생한 경우만 필터링
        error_warning_alerts = [a for a in filtered_alerts if a['severity'] in ['error', 'warning']]
        
        # 최대 8개까지 표시
        error_warning_alerts = error_warning_alerts[:8]
        
        # 새로운 알림이 있는지 확인하고 팝업 표시
        if 'last_alert_count' not in st.session_state:
            st.session_state.last_alert_count = 0
            st.session_state.last_alerts = []
        
        current_alert_count = len(error_warning_alerts)
        if current_alert_count > st.session_state.last_alert_count:
            # 새로운 알림이 추가된 경우 (API ON 상태에서만 팝업 표시)
            if use_real_api:
                new_alerts = error_warning_alerts[st.session_state.last_alert_count:]
                for alert in new_alerts:
                    # 팝업 알림 표시
                    st.markdown(f"""
                    <script>
                    if (window.showAlertPopup) {{
                        window.showAlertPopup({{
                            equipment: "{alert['equipment']}",
                            issue: "{alert['issue']}",
                            severity: "{alert['severity']}",
                            time: "{alert['time']}"
                        }});
                    }}
                    </script>
                    """, unsafe_allow_html=True)
        
        # 현재 알림 상태 저장
        st.session_state.last_alert_count = current_alert_count
        st.session_state.last_alerts = error_warning_alerts.copy()
        
        if error_warning_alerts:
            table_data = []
            for a in error_warning_alerts:
                severity_icon = "🔴" if a['severity'] == 'error' else "🟠"
                table_data.append({
                    '설비': a['equipment'],
                    '이슈': f"{severity_icon} {a['issue']}",
                    '시간': a['time']
                })
            df = pd.DataFrame(table_data)
            # 인덱스를 1부터 시작하도록 설정
            df.index = range(1, len(df) + 1)
            st.dataframe(df, height=200, use_container_width=True)
        else:
            # 빈 테이블 표시
            empty_df = pd.DataFrame(columns=['설비', '이슈', '시간'])
            empty_df.index = range(1, 1)  # 빈 인덱스
            st.dataframe(empty_df, height=200, use_container_width=True)

def update_equipment_container(use_real_api=True):
    """설비 상태 컨테이너 업데이트"""
    if st.session_state.equipment_container is None:
        st.session_state.equipment_container = st.empty()
    
    with st.session_state.equipment_container.container():
        st.markdown('<div class="chart-title no-translate" translate="no" style="font-size:1rem; margin-bottom:0.05rem;">설비 상태</div>', unsafe_allow_html=True)
        
        # 데이터 제거 후인지 확인
        data_cleared = st.session_state.get('data_cleared', False)
        current_use_real_api = st.session_state.get('api_toggle', False)
        
        if data_cleared and not current_use_real_api:
            # 데이터가 제거된 경우 빈 테이블 표시
            empty_df = pd.DataFrame(columns=['설비', '상태', '가동률'])
            empty_df.index = range(1, 1)  # 빈 인덱스
            st.dataframe(empty_df, height=250, use_container_width=True)
            st.info("설비 상태 데이터가 없습니다.")
            return
        
        # 현재 토글 상태 기반으로 데이터 가져오기
        equipment_status = get_equipment_status_from_api(current_use_real_api)
        
        # API 데이터를 가져왔으면 데이터 제거 플래그 해제
        if current_use_real_api and equipment_status:
            st.session_state.data_cleared = False
        
        # 설비 필터 적용 (안전한 접근)
        equipment_filter = st.session_state.get('equipment_filter', [])
        if equipment_filter and isinstance(equipment_filter, list):
            # 필터링된 설비만 표시
            filtered_equipment = [eq for eq in equipment_status if eq['name'] in equipment_filter]
        else:
            # 필터가 없으면 모든 설비 표시
            filtered_equipment = equipment_status
        
        table_data = []
        for eq in filtered_equipment:
            # 알림 상태와 매치되는 이모지와 상태명 사용
            status_emoji = {'정상':'🟢','주의':'🟠','오류':'🔴'}.get(eq['status'],'🟢')
            table_data.append({
                '설비': eq['name'],
                '상태': f"{status_emoji} {eq['status']}",
                '가동률': f"{eq['efficiency']}%"
            })
        df = pd.DataFrame(table_data)
        # 인덱스를 1부터 시작하도록 설정
        df.index = range(1, len(df) + 1)
        st.dataframe(df, height=250, use_container_width=True)

# 사용하지 않는 스레드 함수 제거

def process_ai_question(transcript, use_real_api, process):
    """AI 질문 처리 함수"""
    # 채팅 이력 초기화
    if 'chat_history' not in st.session_state:
        st.session_state.chat_history = []
    
    # 현재 대시보드 상태 컨텍스트
    # 데이터 수집
    alerts = get_alerts_from_api(use_real_api) if use_real_api else generate_alert_data()
    active_alerts_count = len([a for a in alerts if a.get('status', '미처리') != '완료'])
    error_alerts = [a for a in alerts if a.get('severity') == 'error']
    warning_alerts = [a for a in alerts if a.get('severity') == 'warning']

    # KPI 데이터
    production_kpi = generate_production_kpi()
    quality_data = generate_quality_trend()

    # 설비 상태
    equipment_status = get_equipment_status_from_api(use_real_api) if use_real_api else generate_equipment_status()
    normal_equipment = len([e for e in equipment_status if e['status'] == '정상'])
    warning_equipment = len([e for e in equipment_status if e['status'] == '주의'])
    error_equipment = len([e for e in equipment_status if e['status'] == '오류'])

    # AI 예측 결과
    ai_predictions = get_ai_prediction_results(use_real_api)

    context = f"""
    현재 대시보드 상태:

    [생산 KPI]
    - 가동률: {production_kpi['availability']}%
    - 품질률: {production_kpi['quality']}%
    - 일일 생산량: {production_kpi['daily_actual']:,}개 (목표: {production_kpi['daily_target']:,}개)
    - OEE: {production_kpi['oee']}%

    [설비 상태]
    - 전체 설비: {len(equipment_status)}대
    - 정상: {normal_equipment}대, 주의: {warning_equipment}대, 오류: {error_equipment}대
    - 가동률이 낮은 설비: {', '.join([e['name'] + f"({e['efficiency']}%)" for e in equipment_status if e['efficiency'] < 80][:3]) if any(e['efficiency'] < 80 for e in equipment_status) else '없음'}

    [알림 현황]
    - 전체 활성 알림: {active_alerts_count}개
    - 오류 알림: {len(error_alerts)}개
    - 경고 알림: {len(warning_alerts)}개
    - 주요 알림: {', '.join([f"{a['equipment']}-{a['issue']}" for a in error_alerts[:3]]) if error_alerts else '없음'}

    [AI 예측]
    - 설비 이상 예측: {ai_predictions.get('abnormal_detection', {}).get('prediction', {}).get('predicted_class_description', '예측 없음')}
    - 유압 시스템: {'정상' if ai_predictions.get('hydraulic_detection', {}).get('prediction', {}).get('prediction', 0) == 0 else '이상 감지'}

    선택된 공정: {process}
    """
    
    # AI 응답 생성
    with st.spinner("AI가 답변을 생성하는 중..."):
        response = st.session_state.gemini_ai.get_response(transcript, context)
        
        # 채팅 이력에 저장
        st.session_state.chat_history.append({
            'role': 'user',
            'content': transcript,
            'time': datetime.now().strftime('%H:%M:%S')
        })
        
        st.session_state.chat_history.append({
            'role': 'assistant',
            'content': response,
            'time': datetime.now().strftime('%H:%M:%S')
        })
        
        # 전체 응답을 다이얼로그로 표시
        if not response.startswith("AI 응답 생성 중 오류"):
            # 응답을 session state에 저장
            st.session_state.voice_response = response
            st.session_state.voice_transcript = transcript
            # 다이얼로그 표시 플래그 설정
            st.session_state.show_voice_result = True
            st.rerun()
        else:
            st.error("AI 응답 생성 중 오류가 발생했습니다.")

def show_equipment_detail(equipment_id):
    """설비 상세 정보 표시"""
    equipment_list = generate_equipment_status()
    equipment = next((eq for eq in equipment_list if eq['id'] == equipment_id), None)
    
    if equipment:
        st.markdown(f"### {equipment['name']} 상세 정보")
        
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**기본 정보**")
            st.write(f"설비 ID: {equipment['id']}")
            st.write(f"설비 타입: {equipment['type']}")
            st.write(f"현재 상태: {equipment['status']}")
            st.write(f"마지막 정비: {equipment['last_maintenance']}")
        
        with col2:
            st.markdown("**성능 지표**")
            st.write(f"가동률: {equipment['efficiency']}%")
            
            # 진행률 바
            efficiency = equipment['efficiency']
            if efficiency >= EFFICIENCY_TARGET + 5:  # 목표 + 5% 이상
                color = "#10b981"
            elif efficiency >= EFFICIENCY_TARGET - 15:  # 목표 - 15% 이상
                color = "#f59e0b"
            else:
                color = "#ef4444"
            
            st.markdown(f"""
            <div class="progress-bar">
                <div class="progress-fill" style="width: {efficiency}%; background: {color};"></div>
            </div>
            """, unsafe_allow_html=True)
        
        # 센서 데이터 차트
        st.markdown("**실시간 센서 데이터**")
        sensor_data = generate_sensor_data()
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=sensor_data['time'],
            y=sensor_data['temperature'],
            mode='lines',
            name='온도 (°C)',
            line=dict(color='#ef4444', width=2)
        ))
        fig.add_trace(go.Scatter(
            x=sensor_data['time'],
            y=sensor_data['pressure'],
            mode='lines',
            name='압력 (bar)',
            line=dict(color='#3b82f6', width=2),
            yaxis='y2'
        ))
        fig.update_layout(
            height=300,
            margin=dict(l=0, r=0, t=0, b=0),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(title="온도 (°C)", side="left"),
            yaxis2=dict(title="압력 (bar)", overlaying="y", side="right"),
            xaxis=dict(title="시간"),
            plot_bgcolor='white',
            paper_bgcolor='white',
            font=dict(color='#1e293b')
        )
        st.plotly_chart(fig, use_container_width=True)

# 메인 대시보드

def main():
    # URL 파라미터로 모달 닫기 처리
    query_params = st.query_params
    if 'close_modal' in query_params and query_params['close_modal'][0] == 'true':
        st.session_state.show_voice_result = False
        # URL 파라미터 제거
        st.experimental_set_query_params()
    
    # Session state 초기화
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = datetime.now()
    if 'sensor_container' not in st.session_state:
        st.session_state.sensor_container = None
    if 'alert_container' not in st.session_state:
        st.session_state.alert_container = None
    if 'equipment_container' not in st.session_state:
        st.session_state.equipment_container = None
    if 'api_toggle_previous' not in st.session_state:
        st.session_state.api_toggle_previous = False
    if 'auto_refresh' not in st.session_state:
        st.session_state.auto_refresh = True
    if 'selected_sensor' not in st.session_state:
        st.session_state.selected_sensor = '전체'
    
    # 설비 필터 관련 session state 초기화
    if 'equipment_filter' not in st.session_state:
        st.session_state.equipment_filter = []
    if 'previous_equipment_filter' not in st.session_state:
        st.session_state.previous_equipment_filter = []
    if 'selected_equipment' not in st.session_state:
        st.session_state.selected_equipment = []
    if 'data_cleared' not in st.session_state:
        st.session_state.data_cleared = False
    if 'critical_alerts' not in st.session_state:
        st.session_state.critical_alerts = []
    if 'last_alert_count' not in st.session_state:
        st.session_state.last_alert_count = 0
    if 'last_update' not in st.session_state:
        st.session_state.last_update = time.time()
    if 'last_quick_update' not in st.session_state:
        st.session_state.last_quick_update = time.time()
    if 'previous_sensor_count' not in st.session_state:
        st.session_state.previous_sensor_count = 0
    if 'previous_alert_count' not in st.session_state:
        st.session_state.previous_alert_count = 0
    

   # 음성 AI 초기화
    if 'voice_ai_initialized' not in st.session_state:
        if VOICE_AI_AVAILABLE:
            try:
                # 프로젝트 ID를 실제 값으로 변경하세요
                PROJECT_ID = "gen-lang-client-0696719372"  
                # 현재 작업 디렉토리를 기준으로 상대 경로 사용
                CREDENTIALS_PATH = "./gen-lang-client-0696719372-0f0c03eabd08.json"
                
                st.session_state.voice_to_text = VoiceToText(CREDENTIALS_PATH, PROJECT_ID)
                st.session_state.gemini_ai = GeminiAI(PROJECT_ID, CREDENTIALS_PATH)
                st.session_state.voice_ai_initialized = True
            except Exception as e:
                st.session_state.voice_ai_initialized = False
                print(f"음성 AI 초기화 실패: {e}")
        else:
            st.session_state.voice_ai_initialized = False
            
    # 자동 새로고침 설정 (간소화)
    api_toggle = st.session_state.get('api_toggle', False)
    refresh_interval = '15초' if api_toggle else '수동'

    if refresh_interval != '수동':
        interval_map = {
            '15초': 15000, '30초': 30000, '1분': 60000,
            '3분': 180000, '5분': 300000, '10분': 600000
        }
        interval_ms = interval_map.get(refresh_interval, 15000)
        
        try:
            st_autorefresh(interval=interval_ms, key="auto_refresh")
        except Exception:
            pass  # 자동 새로고침 오류 시 무시

    st.markdown(
        '''
        <style>
        .stButton > button {
            background: #ffffff !important;
            border: 1px solid #e2e8f0 !important;
            color: #374151 !important;
            font-size: 1.08rem !important;
            padding: 0.6rem 1.3rem 0.3rem 1.3rem !important;
            margin: 0 !important;
            cursor: pointer !important;
            outline: none !important;
            border-radius: 12px !important;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1) !important;
            font-weight: 500 !important;
            transition: all 0.3s ease !important;
        }
        .stButton > button.selected {
            color: #2563eb !important;
            border-bottom: 3px solid #2563eb !important;
            font-weight: 700 !important;
            background: #f5faff !important;
        }
        .stButton > button:hover {
            background: linear-gradient(135deg, #05507D 0%, #00A5E5 100%) !important;
            color: #ffffff !important;
            transform: translateY(-2px) !important;
            box-shadow: 0 6px 20px rgba(5, 80, 125, 0.3) !important;
        }
        
        /* Date Input 스타일 - 흰색 배경 */
        div[data-testid="stDateInput"] > div > div > input {
            background-color: #ffffff !important;
            border: 1px solid #e2e8f0 !important;
            color: #374151 !important;
        }
        
        div[data-testid="stDateInput"] input {
            background-color: #ffffff !important;
            border: 1px solid #e2e8f0 !important;
            color: #374151 !important;
        }
        
        .stDateInput > div > div > input {
            background-color: #ffffff !important;
            border: 1px solid #e2e8f0 !important;
            color: #374151 !important;
        }
        
        /* 대시보드 메인 화면을 제외한 모든 탭의 날짜 선택 박스 width 줄이기 */
        div[data-testid="stDateInput"] {
            width: 150px !important;
        }
        
        div[data-testid="stDateInput"] > div {
            width: 150px !important;
        }
        
        div[data-testid="stDateInput"] > div > div {
            width: 150px !important;
        }
        
        div[data-testid="stDateInput"] > div > div > input {
            width: 150px !important;
        }
        
        /* 팝업 알림 스타일 */
        .alert-popup {
            position: fixed;
            top: 20px;
            right: 20px;
            background: #fff;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            padding: 16px;
            max-width: 300px;
            z-index: 1000;
            animation: slideIn 0.3s ease-out;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }
        
        .alert-popup.error {
            border-left: 4px solid #ef4444;
        }
        
        .alert-popup.warning {
            border-left: 4px solid #f59e0b;
        }
        
        .alert-popup.info {
            border-left: 4px solid #3b82f6;
        }
        
        .alert-popup .title {
            font-weight: 600;
            font-size: 14px;
            margin-bottom: 4px;
            color: #111827;
        }
        
        .alert-popup .message {
            font-size: 13px;
            color: #6b7280;
            margin-bottom: 8px;
        }
        
        .alert-popup .time {
            font-size: 11px;
            color: #9ca3af;
        }
        
        .alert-popup .close-btn {
            position: absolute;
            top: 8px;
            right: 8px;
            background: none;
            border: none;
            font-size: 16px;
            cursor: pointer;
            color: #9ca3af;
            padding: 0;
            width: 20px;
            height: 20px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .alert-popup .close-btn:hover {
            color: #6b7280;
        }
        
        @keyframes slideIn {
            from {
                transform: translateX(100%);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        
        @keyframes slideOut {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(100%);
                opacity: 0;
            }
        }
        </style>
        
        <script>
        // 팝업 알림 관리
        let alertQueue = [];
        let isShowingAlert = false;
        
        function showAlertPopup(alert) {
            const popup = document.createElement('div');
            popup.className = `alert-popup ${alert.severity}`;
            popup.innerHTML = `
                <button class="close-btn" onclick="this.parentElement.remove()">×</button>
                <div class="title">${alert.equipment}</div>
                <div class="message">${alert.issue}</div>
                <div class="time">${alert.time}</div>
            `;
            
            document.body.appendChild(popup);
            
            // 5초 후 자동 제거
            setTimeout(() => {
                if (popup.parentElement) {
                    popup.style.animation = 'slideOut 0.3s ease-out';
                    setTimeout(() => popup.remove(), 300);
                }
            }, 5000);
        }
        
        // Streamlit에서 호출할 수 있도록 전역 함수로 등록
        window.showAlertPopup = showAlertPopup;
        </script>
        ''',
        unsafe_allow_html=True
    )

    tab_titles = ["대시보드", "설비 관리", "알림 관리", "리포트", "AI 분석", "설정"]
    tabs = st.tabs(tab_titles)

    # ----------- 사이드바(필터, AI 연동, 새로고침) 복원 -----------
    with st.sidebar:
        st.markdown('<div style="font-size:18px; font-weight:bold; margin-bottom:0.5rem; margin-top:0.5rem;">필터 설정</div>', unsafe_allow_html=True)
        
        # 구분선 추가
        st.markdown("---")
        
        st.markdown('<div style="font-size:13px; color:#64748b; margin-bottom:0.1rem; margin-top:0.3rem;">공정 선택</div>', unsafe_allow_html=True)
        process = st.selectbox("공정 선택", ["전체 공정", "프레스 공정", "용접 공정", "조립 공정", "검사 공정"], label_visibility="collapsed")
        
        # 구분선 추가
        st.markdown("---")
        
        st.markdown('<div style="font-size:13px; color:#64748b; margin-bottom:0.1rem; margin-top:0.3rem;">설비 필터</div>', unsafe_allow_html=True)
        
        # 설비 목록 먼저 생성
        equipment_list = generate_equipment_status()
        equipment_names_full = [eq['name'] for eq in equipment_list]
        equipment_names_short = []
        for name in equipment_names_full:
            if '프레스기' in name:
                short_name = name.replace('프레스기', '프레스')
            elif '용접기' in name:
                short_name = name.replace('용접기', '용접')
            elif '조립기' in name:
                short_name = name.replace('조립기', '조립')
            elif '검사기' in name:
                short_name = name.replace('검사기', '검사')
            elif '포장기' in name:
                short_name = name.replace('포장기', '포장')
            else:
                short_name = name
            equipment_names_short.append(short_name)
        
        # 공정별 필터 드롭다운
        process_types = ["전체", "프레스기", "용접기", "조립기", "검사기", "포장기"]
        selected_process = st.selectbox(
            "공정 선택",
            process_types,
            index=0,
            label_visibility="collapsed"
        )
        
        # 선택된 공정에 따라 설비 목록 필터링
        filtered_equipment = []
        for short_name in equipment_names_short:
            if selected_process == "전체":
                filtered_equipment.append(short_name)
            elif selected_process == "프레스기" and "프레스" in short_name:
                filtered_equipment.append(short_name)
            elif selected_process == "용접기" and "용접" in short_name:
                filtered_equipment.append(short_name)
            elif selected_process == "조립기" and "조립" in short_name:
                filtered_equipment.append(short_name)
            elif selected_process == "검사기" and "검사" in short_name:
                filtered_equipment.append(short_name)
            elif selected_process == "포장기" and "포장" in short_name:
                filtered_equipment.append(short_name)
        
        # 필터링된 설비 개수 표시
        st.markdown(f'<div style="font-size:11px; color:#64748b; margin-bottom:0.5rem;">{selected_process}: {len(filtered_equipment)}개 설비</div>', unsafe_allow_html=True)
        
        # 설비 필터 스타일링
        st.markdown("""
        <style>
        /* Streamlit multiselect 내부 스크롤 강제 적용 - 이중 스크롤 방지 */
        div[data-testid="stMultiSelect"] > div > div {
            max-height: 200px !important;
            overflow-y: auto !important;
            padding-right: 8px !important;
        }
        /* 설비 필터 컨테이너 내부 초기화 버튼(x) 완전히 숨기기 */
        div[data-testid="stMultiSelect"] button,
        div[data-testid="stMultiSelect"] button[aria-label="Clear all"],
        div[data-testid="stMultiSelect"] button[title="Clear all"],
        div[data-testid="stMultiSelect"] button[data-baseweb="button"],
        div[data-testid="stMultiSelect"] div[role="button"] {
            display: none !important;
        }
        /* 설비 필터 컨테이너 내부 화살표 완전히 숨기기 */
        div[data-testid="stMultiSelect"] svg[data-testid="stArrow"] {
            display: none !important;
        }
        /* 내부 스크롤바 스타일링 - 오른쪽에 붙이기 */
        div[data-testid="stMultiSelect"] > div > div::-webkit-scrollbar {
            width: 8px !important;
            position: absolute !important;
            right: 0 !important;
        }
        div[data-testid="stMultiSelect"] > div > div::-webkit-scrollbar-track {
            background: #f1f5f9 !important;
            border-radius: 4px !important;
        }
        div[data-testid="stMultiSelect"] > div > div::-webkit-scrollbar-thumb {
            background: #cbd5e1 !important;
            border-radius: 4px !important;
        }
        div[data-testid="stMultiSelect"] > div > div::-webkit-scrollbar-thumb:hover {
            background: #94a3b8 !important;
        }
            /* 실시간 센서, PPM 트렌드 드롭박스 흰색 배경 */
    div[data-testid="stSelectbox"] > div > div {
        background-color: white !important;
        color: #1e293b !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important;
    }
    div[data-testid="stSelectbox"] > div > div:hover {
        background-color: #f8fafc !important;
        border-color: #cbd5e1 !important;
    }
    
    /* 텍스트 입력 필드 흰색 배경 */
    div[data-testid="stTextInput"] > div > div > input,
    div[data-testid="stTextInput"] input,
    .stTextInput > div > div > input {
        background-color: #ffffff !important;
        color: #1e293b !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important;
    }
    div[data-testid="stTextInput"] > div > div > input:focus,
    div[data-testid="stTextInput"] input:focus,
    .stTextInput > div > div > input:focus {
        background-color: #ffffff !important;
        border-color: #05507D !important;
        box-shadow: 0 0 0 2px rgba(5, 80, 125, 0.1) !important;
    }
    
    /* 텍스트 영역 흰색 배경 */
    div[data-testid="stTextArea"] > div > div > textarea,
    div[data-testid="stTextArea"] textarea,
    .stTextArea > div > div > textarea {
        background-color: #ffffff !important;
        color: #1e293b !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important;
    }
    div[data-testid="stTextArea"] > div > div > textarea:focus,
    div[data-testid="stTextArea"] textarea:focus,
    .stTextArea > div > div > textarea:focus {
        background-color: #ffffff !important;
        border-color: #05507D !important;
        box-shadow: 0 0 0 2px rgba(5, 80, 125, 0.1) !important;
    }
        </style>
        """, unsafe_allow_html=True)
        
        # 고정 높이 컨테이너 내에서 multiselect (필터링된 목록 사용)
        if filtered_equipment:
            equipment_filter_short = st.multiselect(
                "설비 필터",
                filtered_equipment,
                default=filtered_equipment,  # 필터링된 모든 설비가 기본 선택됨
                label_visibility="collapsed"
            )
        else:
            st.info(f"{selected_process}에 해당하는 설비가 없습니다.")
            equipment_filter_short = []
        
        equipment_filter = []
        for short_name in equipment_filter_short:
            for i, full_name in enumerate(equipment_names_full):
                if equipment_names_short[i] == short_name:
                    equipment_filter.append(full_name)
                    break
        
        # 설비 필터를 session state에 저장 (다른 함수에서 사용하기 위해)
        if 'previous_equipment_filter' not in st.session_state:
            st.session_state.previous_equipment_filter = []
        
        # 필터가 변경되었는지 확인 (안전한 접근)
        current_filter = st.session_state.get('equipment_filter', [])
        previous_filter = st.session_state.get('previous_equipment_filter', [])
        
        if current_filter != equipment_filter:
            st.session_state.previous_equipment_filter = equipment_filter.copy()
            st.session_state.equipment_filter = equipment_filter
            # 필터 변경 시 컨테이너 초기화
            st.session_state.sensor_container = None
            st.session_state.alert_container = None
            st.session_state.equipment_container = None
            st.rerun()
        else:
            st.session_state.equipment_filter = equipment_filter
        # 구분선 추가
        st.markdown("---")
        st.markdown('<div style="font-size:18px; font-weight:bold; margin-bottom:0.5rem; margin-top:0.5rem;">📅 날짜 선택</div>', unsafe_allow_html=True)
        
        # 일자별/기간별 라디오 박스 (좌우 배치, 포스코모빌리티 블루)
        date_mode = st.radio(
            "📅 날짜 선택", 
            ["일자별", "기간별"], 
            key="sidebar_date_mode",
            horizontal=True,
            label_visibility="collapsed"
        )
        
        # 라디오 박스 스타일링 (선택된 것만 파란색)
        st.markdown("""
        <style>
        .stRadio > div > label[data-testid="stRadio"] {
            color: #3b82f6;
            font-weight: bold;
        }
        </style>
        """, unsafe_allow_html=True)
        
        if date_mode == "일자별":
            st.markdown('<div style="font-size:13px; color:#64748b; margin-bottom:0.1rem; margin-top:0.3rem;">일자 선택</div>', unsafe_allow_html=True)
            selected_date = st.date_input("일자 선택", datetime.now().date(), label_visibility="collapsed", key="sidebar_selected_date")
            
            # 사이드바 일자 설정을 session state에 저장
            if 'sidebar_selected_date_stored' not in st.session_state:
                st.session_state.sidebar_selected_date_stored = selected_date
            elif st.session_state.sidebar_selected_date_stored != selected_date:
                st.session_state.sidebar_selected_date_stored = selected_date
        else:  # 기간별
            st.markdown('<div style="font-size:13px; color:#64748b; margin-bottom:0.1rem; margin-top:0.3rem;">기간 선택</div>', unsafe_allow_html=True)
            start_date = st.date_input("시작일", (datetime.now() - timedelta(days=7)).date(), label_visibility="collapsed", key="sidebar_start_date")
            end_date = st.date_input("종료일", datetime.now().date(), label_visibility="collapsed", key="sidebar_end_date")
            
            # 사이드바 기간 설정을 session state에 저장
            if 'sidebar_date_range_stored' not in st.session_state:
                st.session_state.sidebar_date_range_stored = (start_date, end_date)
            elif st.session_state.sidebar_date_range_stored != (start_date, end_date):
                st.session_state.sidebar_date_range_stored = (start_date, end_date)
        # 구분선 추가
        st.markdown("---")
        # 연동 토글 항상 하단에
        use_real_api = st.toggle("🔗 API 연동", value=st.session_state.get('api_toggle', False), help="실제 API에서 데이터를 받아옵니다.", key="api_toggle")
        
        # API 토글 상태 변경 감지 및 초기화 (토글 정의 후에 실행)
        if use_real_api != st.session_state.api_toggle_previous:
            # API 토글이 변경되었을 때 컨테이너 초기화
            st.session_state.sensor_container = None
            st.session_state.alert_container = None
            st.session_state.equipment_container = None
            st.session_state.api_toggle_previous = use_real_api
            
            # API 토글이 ON으로 변경되었을 때 센서 데이터만 초기화 (사용자 데이터는 보존)
            if use_real_api:
                pass  # API 토글 변경 감지
                try:
                    response = requests.post("http://localhost:8000/clear_sensor_data", timeout=5)
                    if response.status_code == 200:
                        pass  # 센서 데이터 초기화 성공
                        st.success("API 연동 시작: 센서 데이터가 초기화되었습니다! 시뮬레이터 데이터가 곧 반영됩니다.")
                        # 데이터 제거 플래그 설정
                        st.session_state.data_cleared = True
                    else:
                        pass  # 센서 데이터 초기화 실패
                        st.warning("API 연동 시작: 센서 데이터 초기화 실패")
                except Exception as e:
                    pass  # API 서버 연결 실패
                    st.warning(f"API 연동 시작: 서버 연결 실패 - {e}")
        
        st.markdown('<hr style="margin:1.5rem 0 1rem 0; border: none; border-top: 1.5px solid #e2e8f0;" />', unsafe_allow_html=True)
        st.markdown('<div style="font-size:18px; font-weight:bold; margin-bottom:0.5rem;">🎤 음성 어시스턴트</div>', unsafe_allow_html=True)
        
        # AI 응답 다이얼로그 표시 (사이드바에서 제거)
        # 실제 팝업은 메인 대시보드에서 표시됨
                    
        if st.session_state.get('voice_ai_initialized', False):
            # 음성 입력 위젯
            audio_bytes = st.audio_input("음성으로 질문하세요", key="voice_input")
            
            if audio_bytes is not None:
                # 분석 버튼
                if st.button("🎯 음성 분석", use_container_width=True):
                    with st.spinner("음성을 분석하는 중..."):
                        # 음성 -> 텍스트
                        audio_data = audio_bytes.getvalue()
                        transcript = st.session_state.voice_to_text.transcribe_audio(audio_data)
                        
                        if transcript and not transcript.startswith("오류"):
                            # 채팅 이력 초기화
                            if 'chat_history' not in st.session_state:
                                st.session_state.chat_history = []
                            
                            # 현재 대시보드 상태 컨텍스트
                            # 데이터 수집
                            alerts = get_alerts_from_api(use_real_api) if use_real_api else generate_alert_data()
                            active_alerts_count = len([a for a in alerts if a.get('status', '미처리') != '완료'])
                            error_alerts = [a for a in alerts if a.get('severity') == 'error']
                            warning_alerts = [a for a in alerts if a.get('severity') == 'warning']

                            # KPI 데이터
                            production_kpi = generate_production_kpi()
                            quality_data = generate_quality_trend()

                            # 설비 상태
                            equipment_status = get_equipment_status_from_api(use_real_api) if use_real_api else generate_equipment_status()
                            normal_equipment = len([e for e in equipment_status if e['status'] == '정상'])
                            warning_equipment = len([e for e in equipment_status if e['status'] == '주의'])
                            error_equipment = len([e for e in equipment_status if e['status'] == '오류'])

                            # AI 예측 결과
                            ai_predictions = get_ai_prediction_results(use_real_api)

                            context = f"""
                            현재 대시보드 상태:

                            [생산 KPI]
                            - 가동률: {production_kpi['availability']}%
                            - 품질률: {production_kpi['quality']}%
                            - 일일 생산량: {production_kpi['daily_actual']:,}개 (목표: {production_kpi['daily_target']:,}개)
                            - OEE: {production_kpi['oee']}%

                            [설비 상태]
                            - 전체 설비: {len(equipment_status)}대
                            - 정상: {normal_equipment}대, 주의: {warning_equipment}대, 오류: {error_equipment}대
                            - 가동률이 낮은 설비: {', '.join([e['name'] + f"({e['efficiency']}%)" for e in equipment_status if e['efficiency'] < 80][:3]) if any(e['efficiency'] < 80 for e in equipment_status) else '없음'}

                            [알림 현황]
                            - 전체 활성 알림: {active_alerts_count}개
                            - 오류 알림: {len(error_alerts)}개
                            - 경고 알림: {len(warning_alerts)}개
                            - 주요 알림: {', '.join([f"{a['equipment']}-{a['issue']}" for a in error_alerts[:3]]) if error_alerts else '없음'}

                            [AI 예측]
                            - 설비 이상 예측: {ai_predictions.get('abnormal_detection', {}).get('prediction', {}).get('predicted_class_description', '예측 없음')}
                            - 유압 시스템: {'정상' if ai_predictions.get('hydraulic_detection', {}).get('prediction', {}).get('prediction', 0) == 0 else '이상 감지'}

                            선택된 공정: {process}
                            """
                            
                            # AI 응답 생성
                            with st.spinner("AI가 답변을 생성하는 중..."):
                                response = st.session_state.gemini_ai.get_response(transcript, context)
                                
                                # 채팅 이력에 저장
                                st.session_state.chat_history.append({
                                    'role': 'user',
                                    'content': transcript,
                                    'time': datetime.now().strftime('%H:%M:%S')
                                })
                                
                                st.session_state.chat_history.append({
                                    'role': 'assistant',
                                    'content': response,
                                    'time': datetime.now().strftime('%H:%M:%S')
                                })
                                
                                # 응답을 session state에 저장
                                if not response.startswith("AI 응답 생성 중 오류"):
                                    # 응답을 session state에 저장
                                    st.session_state.voice_response = response
                                    st.session_state.voice_transcript = transcript
                                    st.success("🎤 음성 분석 완료! AI 응답이 팝업으로 표시됩니다.")
                                else:
                                    st.error("AI 응답 생성 중 오류가 발생했습니다.")
                        else:
                            st.error(transcript)
            
            # 채팅 이력 표시
            if st.session_state.get('chat_history'):
                with st.expander("💬 대화 이력", expanded=False):
                    for chat in reversed(st.session_state.chat_history[-10:]):  # 최근 10개만 표시
                        if chat['role'] == 'user':
                            st.markdown(f"""
                            <div style="background: #E3F2FD; border-radius: 10px; padding: 10px; margin: 5px 0;">
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <span style="font-weight: 600;">🗣️ 사용자</span>
                                    <span style="font-size: 0.8rem; color: #666;">{chat['time']}</span>
                                </div>
                                <div style="margin-top: 5px;">{chat['content']}</div>
                            </div>
                            """, unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                            <div style="background: #F5F5F5; border-radius: 10px; padding: 10px; margin: 5px 0;">
                                <div style="display: flex; justify-content: space-between; align-items: center;">
                                    <span style="font-weight: 600;">🤖 AI 어시스턴트</span>
                                    <span style="font-size: 0.8rem; color: #666;">{chat['time']}</span>
                                </div>
                                <div style="margin-top: 5px;">{chat['content']}</div>
                            </div>
                            """, unsafe_allow_html=True)
                    
                    # 대화 초기화 버튼
                    if st.button("🗑️ 대화 초기화", use_container_width=True):
                        st.session_state.chat_history = []
                        st.rerun()
        else:
            st.warning("""
            ⚠️ 음성 어시스턴트를 사용할 수 없습니다.
            
            확인사항:
            1. voice_ai.py 파일이 있는지 확인
            2. Google Cloud 인증 파일 경로 확인
            3. 프로젝트 ID가 올바른지 확인
            """)

    
    
    with tabs[0]:  # 대시보드
        # AI 음성 응답 표시 (개선된 다이얼로그)
        if 'voice_response' in st.session_state:
            # 모달 스타일의 컨테이너
            st.markdown("""
            <style>
            .voice-response-modal {
                background: white;
                border: 2px solid #05507D;
                border-radius: 15px;
                padding: 1.5rem;
                margin: 1rem 0;
                box-shadow: 0 10px 25px rgba(0,0,0,0.15);
                position: relative;
            }
            .voice-response-header {
                background: #05507D;
                color: white;
                padding: 0.8rem 1.5rem;
                margin: -1.5rem -1.5rem 1rem -1.5rem;
                border-radius: 13px 13px 0 0;
                font-weight: bold;
                font-size: 1.2rem;
            }
            .ai-response-content {
                background: #f8f9fa;
                padding: 1.5rem;
                border-radius: 10px;
                line-height: 1.8;
                font-size: 1.1rem;
                color: #2c3e50;
                margin: 1rem 0;
                border-left: 4px solid #05507D;
            }
            </style>
            """, unsafe_allow_html=True)
            
            # 모달 헤더
            st.markdown('<div class="voice-response-header">🎤 AI 어시스턴트 응답</div>', unsafe_allow_html=True)
            
            # 사용자 질문 표시
            if 'voice_transcript' in st.session_state:
                st.info(f"💬 **질문:** {st.session_state.voice_transcript}")
            
            # AI 응답 표시
            if st.session_state.voice_response.startswith("AI 응답 생성 중 오류"):
                st.error(st.session_state.voice_response)
            else:
                st.markdown(f'<div class="ai-response-content">{st.session_state.voice_response}</div>', unsafe_allow_html=True)
            
            # 닫기 버튼
            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if st.button("✅ 닫기", type="primary", use_container_width=True):
                    # 응답 상태 초기화
                    if 'voice_response' in st.session_state:
                        del st.session_state.voice_response
                    if 'voice_transcript' in st.session_state:
                        del st.session_state.voice_transcript
                    st.rerun()
        
        st.markdown('<div class="main-header no-translate" translate="no" style="margin-bottom:0.5rem; font-size:1.5rem;">🏭 POSCO MOBILITY IoT 대시보드</div>', unsafe_allow_html=True)
        
        # 위험 알림 팝업 표시 (설비 필터 적용, 안전한 접근)
        equipment_filter = st.session_state.get('equipment_filter', [])
        critical_alerts = st.session_state.get('critical_alerts', [])
        if critical_alerts:
            if equipment_filter and isinstance(equipment_filter, list):
                # 필터링된 설비의 위험 알림만 표시
                filtered_critical_alerts = [a for a in critical_alerts if a.get('equipment') in equipment_filter]
                if filtered_critical_alerts:
                    st.error(f"🚨 **경고 알림 발생!** {len(filtered_critical_alerts)}개의 경고 상황이 감지되었습니다.")
                    for alert in filtered_critical_alerts[:3]:  # 최대 3개만 표시
                        equipment_name = alert.get('equipment', 'Unknown')
                        issue_text = alert.get('message', alert.get('issue', '경고 상황'))
                        severity_icon = "🔴" if alert.get('severity') == 'error' else "🟠"
                        st.warning(f"{severity_icon} **{equipment_name}**: {issue_text}")
            else:
                # 필터가 없으면 모든 위험 알림 표시
                st.error(f"🚨 **경고 알림 발생!** {len(critical_alerts)}개의 경고 상황이 감지되었습니다.")
                for alert in critical_alerts[:3]:  # 최대 3개만 표시
                    equipment_name = alert.get('equipment', 'Unknown')
                    issue_text = alert.get('message', alert.get('issue', '경고 상황'))
                    severity_icon = "🔴" if alert.get('severity') == 'error' else "🟠"
                    st.warning(f"{severity_icon} **{equipment_name}**: {issue_text}")
        # KPI+AI 카드 2행 3열 (총 6개)
        row1 = st.columns(3, gap="small")
        row2 = st.columns(3, gap="small")
        
        # 데이터 제거 상태 확인 및 자동 해제
        data_cleared = st.session_state.get('data_cleared', False)
        if data_cleared:
            # 데이터가 제거된 경우 빈 상태로 유지
            pass
        elif use_real_api:
            # API가 연결되면 데이터 제거 플래그 해제
            st.session_state.data_cleared = False
            pass  # 데이터 제거 플래그 해제됨
        
        # API 토글 상태에 따라 데이터 가져오기
        if use_real_api:
            try:
                production_kpi = generate_production_kpi()  # KPI는 더미 데이터 사용
                quality_data = generate_quality_trend()    # 품질 데이터는 더미 데이터 사용
                # 데이터 제거 상태에 따라 알림 데이터 결정
                if data_cleared:
                    alerts = []  # 빈 알림 리스트
                else:
                    alerts = get_alerts_from_api(use_real_api)  # 토글 상태에 따라 자동으로 더미데이터 또는 API 데이터 반환
            except Exception as e:
                st.error(f"API 데이터 가져오기 오류: {e}")
                production_kpi = generate_production_kpi()
                quality_data = generate_quality_trend()
                alerts = generate_alert_data()
        else:
            production_kpi = generate_production_kpi()
            quality_data = generate_quality_trend()
            # 데이터 제거 상태에 따라 알림 데이터 결정
            if data_cleared:
                alerts = []  # 빈 알림 리스트
            else:
                alerts = generate_alert_data()
        
        # 설비 필터 적용하여 활성 알림 계산 (안전한 접근)
        equipment_filter = st.session_state.get('equipment_filter', [])
        if equipment_filter and isinstance(equipment_filter, list):
            # 필터링된 설비의 알림만 계산
            filtered_alerts = [a for a in alerts if a.get('equipment') in equipment_filter]
            active_alerts = len([a for a in filtered_alerts if a.get('status', '미처리') != '완료'])
        else:
            # 필터가 없으면 모든 알림 계산
            active_alerts = len([a for a in alerts if a.get('status', '미처리') != '완료'])
        # PPM 계산 (상수 사용)
        ppm = PPM_TARGET
        # 1행: 가동률, PPM, 생산량
        with row1[0]:
            st.markdown(f"""
            <div class="kpi-card success no-translate" translate="no" style="padding:0.5rem 0.4rem; min-height:70px; height:80px;">
                <div class="kpi-label" style="font-size:0.9rem;">가동률</div>
                <div class="kpi-value" style="font-size:1.3rem;">{production_kpi['availability']}%</div>
            </div>
            """, unsafe_allow_html=True)
        with row1[1]:
            st.markdown(f"""
            <div class="kpi-card warning no-translate" translate="no" style="padding:0.5rem 0.4rem; min-height:70px; height:80px;">
                <div class="kpi-label" style="font-size:0.9rem;">PPM (불량 개수/백만 개 기준)</div>
                <div class="kpi-value" style="font-size:1.3rem;">{ppm}</div>
            </div>
            """, unsafe_allow_html=True)
        with row1[2]:
            st.markdown(f"""
            <div class="kpi-card no-translate" translate="no" style="padding:0.5rem 0.4rem; min-height:70px; height:80px;">
                <div class="kpi-label" style="font-size:0.9rem;">생산량</div>
                <div class="kpi-value" style="font-size:1.3rem;">{production_kpi['daily_actual']:,}</div>
            </div>
            """, unsafe_allow_html=True)
        # 2행: 활성 알림, AI 에너지 예측, AI 설비 이상
        with row2[0]:
            st.markdown(f"""
            <div class="kpi-card no-translate" translate="no" style="padding:0.5rem 0.4rem; min-height:70px; height:80px;">
                <div class="kpi-label" style="font-size:0.9rem;">활성 알림</div>
                <div class="kpi-value" style="font-size:1.3rem;">{active_alerts}</div>
            </div>
            """, unsafe_allow_html=True)
        # AI 예측 결과 가져오기
        ai_predictions = get_ai_prediction_results(use_real_api)
        
        # AI 설비 이상 예측 카드
        with row2[1]:
            if ai_predictions.get('abnormal_detection', {}).get('status') == 'success':
                abnormal_data = ai_predictions['abnormal_detection']
                prediction = abnormal_data['prediction']
                probabilities = prediction['probabilities']
                
                # 정상 확률에 따른 색상 결정
                normal_prob = probabilities.get('normal', 0)
                if normal_prob >= 0.8:  # 80% 이상
                    card_class = "success"
                    status_text = "정상"
                elif normal_prob >= 0.5:  # 50% 이상 80% 미만
                    card_class = "warning"
                    status_text = "주의"
                else:  # 50% 미만
                    card_class = "danger"
                    status_text = "위험"
                
                st.markdown(f"""
                <div class="kpi-card {card_class} no-translate" translate="no" style="padding:0.5rem 0.4rem; min-height:70px; height:80px;">
                    <div class="kpi-label" style="font-size:0.9rem;">AI 설비 이상 예측</div>
                    <div class="kpi-value" style="font-size:1.3rem;">{status_text}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="kpi-card no-translate" translate="no" style="padding:0.5rem 0.4rem; min-height:70px; height:80px;">
                    <div class="kpi-label" style="font-size:0.9rem;">AI 설비 이상 예측</div>
                    <div class="kpi-value" style="font-size:1.3rem;">예측 없음</div>
                </div>
                """, unsafe_allow_html=True)
        
        # AI 유압 이상 탐지 카드
        with row2[2]:
            if ai_predictions.get('hydraulic_detection', {}).get('status') == 'success':
                hydraulic_data = ai_predictions['hydraulic_detection']
                prediction = hydraulic_data['prediction']
                
                # 상태 결정
                if prediction['prediction'] == 0:
                    status_text = '정상'
                    card_class = "success"
                    icon = "🔧"
                else:
                    status_text = '이상 감지'
                    card_class = "danger"
                    icon = "🚨"
                
                st.markdown(f"""
                <div class="kpi-card {card_class} no-translate" translate="no" style="padding:0.5rem 0.4rem; min-height:70px; height:80px;">
                    <div class="kpi-label" style="font-size:0.9rem;">AI 유압 이상 탐지</div>
                    <div class="kpi-value" style="font-size:1.3rem;">{status_text}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class="kpi-card no-translate" translate="no" style="padding:0.5rem 0.4rem; min-height:70px; height:80px;">
                    <div class="kpi-label" style="font-size:0.9rem;">AI 유압 이상 탐지</div>
                    <div class="kpi-value" style="font-size:1.3rem;">예측 없음</div>
                </div>
                """, unsafe_allow_html=True)
        # 6개 정보 3,3으로 2행 배치 (상단: 설비 상태, 실시간 센서, 품질/생산 트렌드 / 하단: 업무 알림, AI 에너지 예측, AI 설비 이상 감지)
        row_top = st.columns(3, gap="small")
        row_bottom = st.columns(3, gap="small")
        # 상단 1행
        # 1. 설비 상태
        with row_top[0]:
            if st.session_state.equipment_container is None:
                st.session_state.equipment_container = st.empty()
            update_equipment_container(use_real_api)
        # 2. 실시간 센서
        with row_top[1]:
            st.markdown('<div class="chart-title no-translate" translate="no" style="font-size:1rem; margin-bottom:0.2rem;">실시간 센서</div>', unsafe_allow_html=True)
            
            # 센서 선택 드롭박스
            selected_sensor = st.selectbox(
                "센서 선택",
                ["전체", "온도", "압력", "진동"],
                index=["전체", "온도", "압력", "진동"].index(st.session_state.get('selected_sensor', '전체')),
                key="sensor_selector",
                label_visibility="collapsed"
            )
            # 선택된 센서를 session state에 저장
            st.session_state.selected_sensor = selected_sensor
            
            if st.session_state.sensor_container is None:
                st.session_state.sensor_container = st.empty()
            update_sensor_data_container(use_real_api, selected_sensor)
        # 3. PPM 트렌드
        with row_top[2]:
            st.markdown('<div class="chart-title no-translate" translate="no" style="font-size:1rem; margin-bottom:0.2rem;">PPM 트렌드</div>', unsafe_allow_html=True)
            
            # 기간 선택 드롭박스
            ppm_period = st.selectbox(
                "기간 선택",
                ["최근 7일", "최근 30일", "최근 90일"],
                key="ppm_period_selector",
                label_visibility="collapsed"
            )
            
            # PPM 샘플 데이터 생성 (상수 기준으로 조정)
            if ppm_period == "최근 7일":
                days = ['월', '화', '수', '목', '금', '토', '일']
                ppm_values = [PPM_TARGET - 100, PPM_TARGET - 120, PPM_TARGET - 80, PPM_TARGET - 110, PPM_TARGET - 90, PPM_TARGET - 105, PPM_TARGET - 95]
            elif ppm_period == "최근 30일":
                days = [f"{i+1}일" for i in range(30)]
                ppm_values = [PPM_TARGET - 100 + np.random.randint(-50, 100) for _ in range(30)]
            else:  # 최근 90일
                days = [f"{i+1}일" for i in range(90)]
                ppm_values = [PPM_TARGET - 100 + np.random.randint(-50, 100) for _ in range(90)]
            
            # PPM 색상 설정 (상수 기준)
            colors = []
            for ppm in ppm_values:
                if ppm >= PPM_TARGET - 100:  # PPM_TARGET - 100 이상은 초록색
                    colors.append('#10b981')  # 초록색
                else:
                    colors.append('#f59e0b')  # 주황색
            
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=days,
                y=ppm_values,
                name='PPM',
                marker_color=colors,
                text=[f'{ppm}' for ppm in ppm_values],
                textposition='inside',
                textfont=dict(color='white', size=9)
            ))
            fig.update_layout(
                height=200,
                margin=dict(l=8, r=8, t=8, b=8),
                yaxis=dict(title={'text':"PPM", 'font':{'size':9}}, range=[0, max(ppm_values) * 1.1]),
                xaxis=dict(title={'text':"기간", 'font':{'size':9}}),
                showlegend=False,
                plot_bgcolor='white',
                paper_bgcolor='white',
                font=dict(color='#1e293b', size=9)
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        # 하단 2행
        # 4. 업무 알림
        with row_bottom[0]:
            if st.session_state.alert_container is None:
                st.session_state.alert_container = st.empty()
            update_alert_container(use_real_api)
        # 5. AI 설비 이상 예측
        with row_bottom[1]:
            st.markdown('<div class="chart-title no-translate" translate="no" style="font-size:1rem; margin-bottom:0.2rem;">AI 설비 이상 예측</div>', unsafe_allow_html=True)
            
            ai_predictions = get_ai_prediction_results(use_real_api)
            
            if ai_predictions.get('abnormal_detection', {}).get('status') == 'success':
                abnormal_data = ai_predictions['abnormal_detection']
                prediction = abnormal_data['prediction']
                probabilities = prediction['probabilities']
                max_prob = max(probabilities.values())
                max_status = [k for k, v in probabilities.items() if v == max_prob][0]
                
                status_names = {
                    'normal': '정상',
                    'bearing_fault': '베어링 고장',
                    'roll_misalignment': '롤 정렬 불량',
                    'motor_overload': '모터 과부하',
                    'lubricant_shortage': '윤활유 부족'
                }
                
                # 정상 확률에 따른 메인 상태 색상 결정
                normal_prob = probabilities.get('normal', 0)
                main_status_config = get_color_and_icon_for_probability('normal', normal_prob)
                main_status_config['text'] = '정상' if normal_prob >= 0.8 else '주의' if normal_prob >= 0.5 else '위험'
                
                config = main_status_config
                
                # 메인 상태 박스
                st.markdown(f"""
                <div style="background: {config['bg']}; border-radius: 8px; padding: 0.6rem; margin-bottom: 0.6rem; 
                            box-shadow: 0 1px 3px rgba(0,0,0,0.1); border: 1px solid {config['color']}20;">
                    <div style="display: flex; align-items: center; gap: 0.4rem;">
                        <span style="font-size: 1rem;">{config['icon']}</span>
                        <span style="font-size: 0.85rem; font-weight: 600; color: {config['color']};">
                            {config['text']} (정상: {normal_prob:.1%})
                        </span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # 상세 분석 (프로그레스 바) - 하나의 컨테이너에 모든 내용 포함
                progress_bars_html = ""
                for status, prob in probabilities.items():
                    # 동적 색상 및 아이콘 결정
                    dynamic_config = get_color_and_icon_for_probability(status, prob)
                    status_color = dynamic_config['color']
                    status_icon = dynamic_config['icon']
                    display_prob = max(prob * 100, 5)  # 최소 5%로 표시, 확률을 0-100 스케일로 변환
                    
                    progress_bars_html += f'<div style="display: flex; align-items: center; gap: 0.4rem; margin-bottom: 0.3rem; padding: 0.2rem 0;"><span style="font-size: 0.65rem;">{status_icon}</span><span style="font-size: 0.7rem; font-weight: 500; min-width: 75px; color: #374151;">{status_names[status]}</span><div style="flex: 1; background: #f3f4f6; border-radius: 3px; height: 5px; overflow: hidden;"><div style="background: {status_color}; height: 100%; width: {display_prob:.1f}%; border-radius: 3px; transition: width 0.3s ease;"></div></div><span style="font-size: 0.65rem; font-weight: 600; color: {status_color}; min-width: 30px; text-align: right;">{prob*100:.1f}%</span></div>'
                
                st.markdown(f'<div style="background: white; border-radius: 8px; padding: 0.6rem; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border: 1px solid #e5e7eb; height: 140px; overflow-y: auto;">{progress_bars_html}</div>', unsafe_allow_html=True)
            else:
                st.info("예측 결과 없음")
        
        # 6. AI 유압 이상 탐지
        with row_bottom[2]:
            st.markdown('<div class="chart-title no-translate" translate="no" style="font-size:1rem; margin-bottom:0.2rem;">AI 유압 이상 탐지</div>', unsafe_allow_html=True)
            
            ai_predictions = get_ai_prediction_results(use_real_api)
            
            if ai_predictions.get('hydraulic_detection', {}).get('status') == 'success':
                hydraulic_data = ai_predictions['hydraulic_detection']
                prediction = hydraulic_data['prediction']
                
                # 상태 결정
                if prediction['prediction'] == 0:
                    status_text = '정상'
                    status_config = {'color': '#10B981', 'bg': '#ECFDF5', 'icon': '🟢'}
                else:
                    status_text = '이상 감지'
                    status_config = {'color': '#EF4444', 'bg': '#FEF2F2', 'icon': '🔴'}
                
                prediction_time = datetime.fromisoformat(hydraulic_data['timestamp']).strftime('%H:%M:%S')
                
                # 메인 상태 박스
                st.markdown(f"""
                <div style="background: {status_config['bg']}; border-radius: 8px; padding: 0.6rem; margin-bottom: 0.6rem; 
                            box-shadow: 0 1px 3px rgba(0,0,0,0.1); border: 1px solid {status_config['color']}20;">
                    <div style="display: flex; align-items: center; gap: 0.4rem;">
                        <span style="font-size: 1rem;">{status_config['icon']}</span>
                        <span style="font-size: 0.85rem; font-weight: 600; color: {status_config['color']};">
                            {status_text} ({prediction['confidence']:.1%})
                        </span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
                
                # 상세 메트릭 (2x2 플로팅 카드)
                metrics = [
                    ("정상 확률", f"{prediction['probabilities']['normal']:.1%}", "#10B981"),
                    ("신뢰도", f"{prediction['confidence']:.1%}", "#3B82F6"),
                    ("이상 확률", f"{prediction['probabilities']['abnormal']:.1%}", "#EF4444"),
                    ("예측 시간", prediction_time, "#6B7280")
                ]
                
                # 2x2 그리드로 플로팅 카드 배치 - st.columns 사용
                col1, col2 = st.columns(2)
                
                with col1:
                    # 첫 번째 행: 정상 확률, 신뢰도
                    st.markdown(f"""
                    <div style="background: white; border-radius: 6px; padding: 0.5rem; text-align: center; 
                                box-shadow: 0 2px 4px rgba(0,0,0,0.1); border: 1px solid #e5e7eb; margin-bottom: 0.5rem;">
                        <div style="font-size: 0.7rem; color: #6b7280; margin-bottom: 0.2rem;">{metrics[0][0]}</div>
                        <div style="font-size: 0.85rem; font-weight: 600; color: {metrics[0][2]};">{metrics[0][1]}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown(f"""
                    <div style="background: white; border-radius: 6px; padding: 0.5rem; text-align: center; 
                                box-shadow: 0 2px 4px rgba(0,0,0,0.1); border: 1px solid #e5e7eb;">
                        <div style="font-size: 0.7rem; color: #6b7280; margin-bottom: 0.2rem;">{metrics[1][0]}</div>
                        <div style="font-size: 0.85rem; font-weight: 600; color: {metrics[1][2]};">{metrics[1][1]}</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                with col2:
                    # 두 번째 행: 이상 확률, 예측 시간
                    st.markdown(f"""
                    <div style="background: white; border-radius: 6px; padding: 0.5rem; text-align: center; 
                                box-shadow: 0 2px 4px rgba(0,0,0,0.1); border: 1px solid #e5e7eb; margin-bottom: 0.5rem;">
                        <div style="font-size: 0.7rem; color: #6b7280; margin-bottom: 0.2rem;">{metrics[2][0]}</div>
                        <div style="font-size: 0.85rem; font-weight: 600; color: {metrics[2][2]};">{metrics[2][1]}</div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.markdown(f"""
                    <div style="background: white; border-radius: 6px; padding: 0.5rem; text-align: center; 
                                box-shadow: 0 2px 4px rgba(0,0,0,0.1); border: 1px solid #e5e7eb;">
                        <div style="font-size: 0.7rem; color: #6b7280; margin-bottom: 0.2rem;">{metrics[3][0]}</div>
                        <div style="font-size: 0.85rem; font-weight: 600; color: {metrics[3][2]};">{metrics[3][1]}</div>
                    </div>
                    """, unsafe_allow_html=True)
            else:
                st.info("예측 결과 없음")


    with tabs[4]:  # AI 분석
        st.markdown('<div class="main-header no-translate" translate="no">🤖 AI 분석</div>', unsafe_allow_html=True)
        st.write("AI 모델을 활용한 설비 이상 예측 및 유압 시스템 이상 탐지 결과를 실시간으로 모니터링하고 분석할 수 있습니다.")
        
        # ======================
        # 기간 선택 (맨 위로 이동)
        # ======================
        st.markdown("### 📅 기간 선택")
        
        # 사이드바 날짜 설정 가져오기
        sidebar_date_mode = st.session_state.get('sidebar_date_mode', '일자별')
        sidebar_date = st.session_state.get('sidebar_selected_date_stored', datetime.now().date())
        sidebar_date_range = st.session_state.get('sidebar_date_range_stored', (datetime.now().date() - timedelta(days=7), datetime.now().date()))
        
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            col_radio, col_date1 = st.columns([1, 2])
            with col_radio:
                date_mode = st.radio(
                    "📅 조회 모드", 
                    ["일자별", "기간별"], 
                    index=0 if sidebar_date_mode == "일자별" else 1, 
                    key="ai_date_mode",
                    horizontal=True,
                    label_visibility="collapsed"
                )
            with col_date1:
                if date_mode == "일자별":
                    selected_date = st.date_input("조회 일자", value=sidebar_date, key="ai_selected_date")
                else:
                    start_date = st.date_input("시작일", value=sidebar_date_range[0], key="ai_start_date")
        with col2:
            if date_mode == "기간별":
                end_date = st.date_input("종료일", value=sidebar_date_range[1], key="ai_end_date")
            else:
                st.write("")  # 빈 공간
        with col3:
            st.write("")  # 화면 절반을 차지하는 빈 영역
        
        # AI 예측 결과 가져오기
        ai_predictions = get_ai_prediction_results(use_real_api)
        
        # 실시간 모니터링 대시보드
        st.markdown("### 📊 실시간 AI 모니터링 대시보드")
        
        # 상단 상태 카드들
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if ai_predictions.get('abnormal_detection', {}).get('status') == 'success':
                abnormal_data = ai_predictions['abnormal_detection']
                prediction = abnormal_data['prediction']
                probabilities = prediction['probabilities']
                max_prob = max(probabilities.values())
                max_status = [k for k, v in probabilities.items() if v == max_prob][0]
                
                status_names = {
                    'normal': '정상',
                    'bearing_fault': '베어링 고장',
                    'roll_misalignment': '롤 정렬 불량',
                    'motor_overload': '모터 과부하',
                    'lubricant_shortage': '윤활유 부족'
                }
                
                if max_status == 'normal':
                    st.metric("설비 상태", status_names[max_status], f"{max_prob:.1%}", delta_color="normal")
                elif max_status in ['bearing_fault', 'roll_misalignment']:
                    st.metric("설비 상태", status_names[max_status], f"{max_prob:.1%}", delta_color="off")
                else:
                    st.metric("설비 상태", status_names[max_status], f"{max_prob:.1%}", delta_color="inverse")
            else:
                st.metric("설비 상태", "데이터 없음", "0%")
        
        with col2:
            if ai_predictions.get('hydraulic_detection', {}).get('status') == 'success':
                hydraulic_data = ai_predictions['hydraulic_detection']
                prediction = hydraulic_data['prediction']
                
                if prediction['prediction'] == 0:
                    st.metric("유압 상태", "정상", f"{prediction['confidence']:.1%}", delta_color="normal")
                else:
                    st.metric("유압 상태", "이상", f"{prediction['confidence']:.1%}", delta_color="inverse")
            else:
                st.metric("유압 상태", "데이터 없음", "0%")
        
        with col3:
            # 모델 성능 지표 (가상 데이터)
            st.metric("설비 모델 정확도", "94.2%", "0.3%", delta_color="normal")
        
        with col4:
            # 모델 성능 지표 (가상 데이터)
            st.metric("유압 모델 정확도", "91.8%", "-0.2%", delta_color="off")
        
        # 실시간 알림 및 권장사항
        st.markdown("### 🚨 실시간 알림 및 권장사항")
        
        # 알림 카드 생성
        alert_cards = []
        
        # 설비 이상 예측 알림
        if ai_predictions.get('abnormal_detection', {}).get('status') == 'success':
            abnormal_data = ai_predictions['abnormal_detection']
            prediction = abnormal_data['prediction']
            probabilities = prediction['probabilities']
            max_prob = max(probabilities.values())
            max_status = [k for k, v in probabilities.items() if v == max_prob][0]
            
            if max_status != 'normal' and max_prob > 0.6:
                alert_cards.append({
                    'type': 'warning' if max_status in ['bearing_fault', 'roll_misalignment'] else 'error',
                    'title': '설비 이상 감지',
                    'message': f"{status_names[max_status]} 가능성이 {max_prob:.1%}로 높습니다.",
                    'action': '즉시 점검이 필요합니다.',
                    'icon': '🔧'
                })
        
        # 유압 이상 탐지 알림
        if ai_predictions.get('hydraulic_detection', {}).get('status') == 'success':
            hydraulic_data = ai_predictions['hydraulic_detection']
            prediction = hydraulic_data['prediction']
            
            if prediction['prediction'] == 1:
                alert_cards.append({
                    'type': 'error',
                    'title': '유압 시스템 이상',
                    'message': f"유압 시스템에서 이상이 감지되었습니다. (신뢰도: {prediction['confidence']:.1%})",
                    'action': '유압 시스템 점검 및 정지가 필요합니다.',
                    'icon': '⚡'
                })
        
        # 알림이 없을 경우
        if not alert_cards:
            st.success("""
            ✅ **현재 모든 시스템이 정상 상태입니다.**
            
            **현재 상태:**
            - 설비 이상 예측: 정상 범위 내
            - 유압 시스템: 정상 작동 중
            - AI 모델: 정상 동작 중
            """)
        else:
            # 알림 카드들 표시
            for i, alert in enumerate(alert_cards):
                if alert['type'] == 'error':
                    st.error(f"""
                    {alert['icon']} **{alert['title']}**
                    
                    {alert['message']}
                    
                    **권장 조치:** {alert['action']}
                    """)
                else:
                    st.warning(f"""
                    {alert['icon']} **{alert['title']}**
                    
                    {alert['message']}
                    
                    **권장 조치:** {alert['action']}
                    """)
        
        # AI 모델 성능 대시보드
        st.markdown("### 📈 AI 모델 성능 대시보드")
        
        # 세로 구분선이 있는 2개 컬럼
        col1, col2, col3 = st.columns([1, 0.05, 1])
        
        with col1:
            st.markdown("#### 🔧 설비 이상 예측 모델")
            
            # 모델 성능 지표
            col1_1, col1_2 = st.columns(2)
            with col1_1:
                st.metric("정확도", "94.2%", "0.3%")
                st.metric("재현율", "92.1%", "0.5%")
            with col1_2:
                st.metric("정밀도", "95.8%", "-0.1%")
                st.metric("F1-Score", "93.9%", "0.2%")
            
            # 최근 예측 이력 (기간별 탭)
            st.markdown("**📊 최근 예측 이력:**")
            
            # 기간별 탭 생성
            time_tabs = st.tabs(["최근 1시간", "최근 6시간", "최근 24시간", "최근 7일"])
            
            # 각 탭별 데이터 생성
            time_periods = [
                ("최근 1시간", 60),
                ("최근 6시간", 360),
                ("최근 24시간", 1440),
                ("최근 7일", 10080)
            ]
            
            for tab_idx, (period_name, minutes) in enumerate(time_periods):
                with time_tabs[tab_idx]:
                    prediction_history = []
                    current_time = datetime.now()
                    
                    # 해당 기간의 예측 데이터 생성
                    for i in range(minutes // 5):  # 5분 간격으로 데이터 생성
                        time_point = current_time - timedelta(minutes=i * 5)
                        
                        # 다양한 상태와 확률 생성
                        if i < 10:  # 최근 50분은 정상
                            status = "정상"
                            probability = np.random.uniform(85, 98)
                        elif i < 20:  # 그 다음 50분은 베어링 고장 가능성
                            status = "베어링 고장"
                            probability = np.random.uniform(60, 85)
                        elif i < 30:  # 그 다음 50분은 롤 정렬 불량
                            status = "롤 정렬 불량"
                            probability = np.random.uniform(70, 90)
                        else:  # 나머지는 정상
                            status = "정상"
                            probability = np.random.uniform(80, 95)
                        
                        prediction_history.append({
                            "시간": time_point.strftime('%m-%d %H:%M'),
                            "상태": status,
                            "확률": round(probability, 1),
                            "결과": "✅" if status == "정상" else "⚠️"
                        })
                    
                    # 최신 데이터부터 표시 (최대 20개)
                    prediction_history = prediction_history[:20]
                    
                    # 시간대별 진단결과 그래프
                    st.markdown(f"**📈 {period_name} 시간대별 진단결과**")
                    
                    # 그래프 데이터 준비
                    time_points = [pred["시간"] for pred in prediction_history]
                    probabilities = [pred["확률"] for pred in prediction_history]
                    statuses = [pred["상태"] for pred in prediction_history]
                    
                    # 색상 매핑
                    colors = []
                    for status in statuses:
                        if status == "정상":
                            colors.append("#10B981")
                        elif status == "베어링 고장":
                            colors.append("#F59E0B")
                        elif status == "롤 정렬 불량":
                            colors.append("#8B5CF6")
                        elif status == "모터 과부하":
                            colors.append("#EF4444")
                        else:
                            colors.append("#F97316")
                    
                    # 라인 차트 생성
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=time_points,
                        y=probabilities,
                        mode='lines+markers',
                        name='진단 확률',
                        line=dict(color='#05507D', width=2),
                        marker=dict(color=colors, size=6)
                    ))
                    
                    fig.update_layout(
                        title=f"{period_name} 진단 확률 추이",
                        xaxis_title="시간",
                        yaxis_title="진단 확률 (%)",
                        height=300,
                        plot_bgcolor='white',
                        paper_bgcolor='white',
                        xaxis=dict(tickangle=45)
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # 상세 이력 테이블 (스크롤 가능한 컨테이너)
                    st.markdown("**📋 상세 예측 이력:**")
                    
                    # 스크롤 가능한 컨테이너 생성
                    with st.container():
                        st.markdown("""
                        <style>
                        .prediction-history-container {
                            max-height: 400px;
                            overflow-y: auto;
                            border: 1px solid #e2e8f0;
                            border-radius: 8px;
                            padding: 1rem;
                            background: #f8fafc;
                        }
                        .prediction-history-container::-webkit-scrollbar {
                            width: 8px;
                        }
                        .prediction-history-container::-webkit-scrollbar-track {
                            background: #f1f5f9;
                            border-radius: 4px;
                        }
                        .prediction-history-container::-webkit-scrollbar-thumb {
                            background: #cbd5e1;
                            border-radius: 4px;
                        }
                        .prediction-history-container::-webkit-scrollbar-thumb:hover {
                            background: #94a3b8;
                        }
                        </style>
                        """, unsafe_allow_html=True)
                        
                        # 스크롤 가능한 컨테이너 시작
                        container_html = '<div class="prediction-history-container">'
                        
                        # 예측 이력을 HTML로 생성
                        for pred in prediction_history[:10]:
                            if pred["상태"] == "정상":
                                status_color = "#10B981"
                                bg_color = "#ECFDF5"
                            elif pred["상태"] == "베어링 고장":
                                status_color = "#F59E0B"
                                bg_color = "#FFFBEB"
                            elif pred["상태"] == "롤 정렬 불량":
                                status_color = "#8B5CF6"
                                bg_color = "#F3F4F6"
                            elif pred["상태"] == "모터 과부하":
                                status_color = "#EF4444"
                                bg_color = "#FEF2F2"
                            else:  # 윤활유 부족
                                status_color = "#F97316"
                                bg_color = "#FFF7ED"
                            
                            container_html += f'<div style="background: {bg_color}; border-radius: 8px; padding: 0.8rem; margin-bottom: 0.5rem;"><div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;"><div style="display: flex; align-items: center; gap: 0.8rem;"><div style="font-weight: 600; color: {status_color}; min-width: 50px;">{pred["시간"]}</div><div style="font-weight: 600; color: #1e293b;">{pred["상태"]}</div></div><div style="font-size: 1.1rem;">{pred["결과"]}</div></div><div style="background: #e5e7eb; border-radius: 10px; height: 8px; overflow: hidden;"><div style="background: {status_color}; height: 100%; width: {pred["확률"]}%; border-radius: 10px; transition: width 0.3s ease;"></div></div><div style="display: flex; justify-content: space-between; margin-top: 0.3rem;"><span style="font-size: 0.8rem; color: #6b7280;">0%</span><span style="font-size: 0.8rem; font-weight: 600; color: {status_color};">{pred["확률"]}%</span><span style="font-size: 0.8rem; color: #6b7280;">100%</span></div></div>'
                        
                        container_html += '</div>'
                        st.markdown(container_html, unsafe_allow_html=True)

        
        # 세로 구분선
        with col2:
            st.markdown('<div style="border-left: 2px solid #e2e8f0; height: 600px; margin: 0 auto;"></div>', unsafe_allow_html=True)
        
        with col3:
            st.markdown("#### ⚡ 유압 이상 탐지 모델")
            
            # 모델 성능 지표
            col2_1, col2_2 = st.columns(2)
            with col2_1:
                st.metric("정확도", "91.8%", "-0.2%")
                st.metric("재현율", "89.5%", "0.1%")
            with col2_2:
                st.metric("정밀도", "93.2%", "-0.3%")
                st.metric("F1-Score", "91.3%", "-0.1%")
            
            # 최근 예측 이력 (기간별 탭)
            st.markdown("**📊 최근 예측 이력:**")
            
            # 기간별 탭 생성
            hydraulic_time_tabs = st.tabs(["최근 1시간", "최근 6시간", "최근 24시간", "최근 7일"])
            
            # 각 탭별 데이터 생성
            hydraulic_time_periods = [
                ("최근 1시간", 60),
                ("최근 6시간", 360),
                ("최근 24시간", 1440),
                ("최근 7일", 10080)
            ]
            
            for tab_idx, (period_name, minutes) in enumerate(hydraulic_time_periods):
                with hydraulic_time_tabs[tab_idx]:
                    hydraulic_history = []
                    current_time = datetime.now()
                    
                    # 해당 기간의 예측 데이터 생성
                    for i in range(minutes // 5):  # 5분 간격으로 데이터 생성
                        time_point = current_time - timedelta(minutes=i * 5)
                        
                        # 다양한 상태와 신뢰도 생성
                        if i < 15:  # 최근 75분은 정상
                            status = "정상"
                            confidence = np.random.uniform(90, 98)
                        elif i < 25:  # 그 다음 50분은 이상 가능성
                            status = "이상"
                            confidence = np.random.uniform(75, 90)
                        else:  # 나머지는 정상
                            status = "정상"
                            confidence = np.random.uniform(85, 95)
                        
                        hydraulic_history.append({
                            "시간": time_point.strftime('%m-%d %H:%M'),
                            "상태": status,
                            "신뢰도": round(confidence, 1),
                            "결과": "✅" if status == "정상" else "⚠️"
                        })
                    
                    # 최신 데이터부터 표시 (최대 20개)
                    hydraulic_history = hydraulic_history[:20]
                    
                    # 시간대별 진단결과 그래프
                    st.markdown(f"**📈 {period_name} 시간대별 진단결과**")
                    
                    # 그래프 데이터 준비
                    time_points = [pred["시간"] for pred in hydraulic_history]
                    confidences = [pred["신뢰도"] for pred in hydraulic_history]
                    statuses = [pred["상태"] for pred in hydraulic_history]
                    
                    # 색상 매핑
                    colors = []
                    for status in statuses:
                        if status == "정상":
                            colors.append("#10B981")
                        else:  # 이상
                            colors.append("#EF4444")
                    
                    # 라인 차트 생성
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(
                        x=time_points,
                        y=confidences,
                        mode='lines+markers',
                        name='진단 신뢰도',
                        line=dict(color='#05507D', width=2),
                        marker=dict(color=colors, size=6)
                    ))
                    
                    fig.update_layout(
                        title=f"{period_name} 진단 신뢰도 추이",
                        xaxis_title="시간",
                        yaxis_title="진단 신뢰도 (%)",
                        height=300,
                        plot_bgcolor='white',
                        paper_bgcolor='white',
                        xaxis=dict(tickangle=45)
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # 상세 이력 테이블 (스크롤 가능한 컨테이너)
                    st.markdown("**📋 상세 예측 이력:**")
                    
                    # 스크롤 가능한 컨테이너 생성
                    with st.container():
                        st.markdown("""
                        <style>
                        .hydraulic-history-container {
                            max-height: 400px;
                            overflow-y: auto;
                            border: 1px solid #e2e8f0;
                            border-radius: 8px;
                            padding: 1rem;
                            background: #f8fafc;
                        }
                        .hydraulic-history-container::-webkit-scrollbar {
                            width: 8px;
                        }
                        .hydraulic-history-container::-webkit-scrollbar-track {
                            background: #f1f5f9;
                            border-radius: 4px;
                        }
                        .hydraulic-history-container::-webkit-scrollbar-thumb {
                            background: #cbd5e1;
                            border-radius: 4px;
                        }
                        .hydraulic-history-container::-webkit-scrollbar-thumb:hover {
                            background: #94a3b8;
                        }
                        </style>
                        """, unsafe_allow_html=True)
                        
                        # 스크롤 가능한 컨테이너 시작
                        container_html = '<div class="hydraulic-history-container">'
                        
                        # 유압 예측 이력을 HTML로 생성
                        for pred in hydraulic_history[:10]:
                            if pred["상태"] == "정상":
                                status_color = "#10B981"
                                bg_color = "#ECFDF5"
                            else:  # 이상
                                status_color = "#EF4444"
                                bg_color = "#FEF2F2"
                            
                            container_html += f'<div style="background: {bg_color}; border-radius: 8px; padding: 0.8rem; margin-bottom: 0.5rem;"><div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;"><div style="display: flex; align-items: center; gap: 0.8rem;"><div style="font-weight: 600; color: {status_color}; min-width: 50px;">{pred["시간"]}</div><div style="font-weight: 600; color: #1e293b;">{pred["상태"]}</div></div><div style="font-size: 1.1rem;">{pred["결과"]}</div></div><div style="background: #e5e7eb; border-radius: 10px; height: 8px; overflow: hidden;"><div style="background: {status_color}; height: 100%; width: {pred["신뢰도"]}%; border-radius: 10px; transition: width 0.3s ease;"></div></div><div style="display: flex; justify-content: space-between; margin-top: 0.3rem;"><span style="font-size: 0.8rem; color: #6b7280;">0%</span><span style="font-size: 0.8rem; font-weight: 600; color: {status_color};">{pred["신뢰도"]}%</span><span style="font-size: 0.8rem; color: #6b7280;">100%</span></div></div>'
                        
                        container_html += '</div>'
                        st.markdown(container_html, unsafe_allow_html=True)

        
        # AI 설정 및 관리
        st.markdown("### ⚙️ AI 모델 설정 및 관리")
        
        # 설정 탭 생성
        ai_settings_tab1, ai_settings_tab2 = st.tabs(["🔔 알림 설정", "📊 모델 관리"])
        
        with ai_settings_tab1:
            st.markdown("#### 🔔 AI 알림 설정")
            
            # 알림 임계값 설정 섹션
            st.markdown("**📊 설비 이상 예측 알림 임계값:**")
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**🔧 주요 설비 이상:**")
                bearing_threshold = st.slider("베어링 고장", 0.0, 1.0, 0.6, 0.1, key="bearing_thresh")
                motor_threshold = st.slider("모터 과부하", 0.0, 1.0, 0.7, 0.1, key="motor_thresh")
            
            with col2:
                st.markdown("**⚙️ 기타 설비 이상:**")
                roll_threshold = st.slider("롤 정렬 불량", 0.0, 1.0, 0.6, 0.1, key="roll_thresh")
                lubricant_threshold = st.slider("윤활유 부족", 0.0, 1.0, 0.7, 0.1, key="lubricant_thresh")
            
            # 유압 시스템 알림 설정 섹션
            st.markdown("**⚡ 유압 시스템 알림 설정:**")
            hydraulic_threshold = st.slider("이상 감지 임계값", 0.0, 1.0, 0.8, 0.05, key="hydraulic_thresh")
            
            # 알림 방법 설정 섹션
            st.markdown("**📱 알림 방법 설정:**")
            col3, col4 = st.columns(2)
            
            with col3:
                email_alerts = st.checkbox("📧 이메일 알림", value=True)
                sms_alerts = st.checkbox("📱 SMS 알림", value=False)
            
            with col4:
                dashboard_alerts = st.checkbox("🖥️ 대시보드 알림", value=True)
                push_alerts = st.checkbox("🔔 푸시 알림", value=False)
            
            # 설정 저장 버튼
            # 설정 저장 버튼을 중앙에 독립적으로 배치
            st.markdown("<br>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                if st.button("💾 설정 저장", key="save_ai_settings", use_container_width=True):
                    st.success("✅ AI 모델 설정이 저장되었습니다.")
        
        with ai_settings_tab2:
            st.markdown("#### 📊 AI 모델 관리")
            
            # 모델 재학습 설정 섹션
            st.markdown("**🔄 자동 재학습 설정:**")
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**🔧 설비 모델:**")
                st.info("• 재학습 주기: 매일")
                st.info("• 마지막 재학습: 2024-01-15")
                st.info("• 다음 재학습: 2024-01-16")
            
            with col2:
                st.markdown("**⚡ 유압 모델:**")
                st.info("• 재학습 주기: 주 1회")
                st.info("• 마지막 재학습: 2024-01-12")
                st.info("• 다음 재학습: 2024-01-19")
            
            # 수동 모델 관리 섹션
            st.markdown("**🔧 수동 모델 관리:**")
            col3, col4 = st.columns(2)
            
            with col3:
                if st.button("🔧 설비 모델 재학습", key="retrain_equipment"):
                    st.info("🔧 설비 이상 예측 모델 재학습이 시작되었습니다. (예상 소요시간: 30분)")
            
            with col4:
                if st.button("⚡ 유압 모델 재학습", key="retrain_hydraulic"):
                    st.info("⚡ 유압 이상 탐지 모델 재학습이 시작되었습니다. (예상 소요시간: 15분)")
            
            # 모델 백업 및 복원 섹션
            st.markdown("**💾 모델 백업 및 복원:**")
            col5, col6 = st.columns(2)
            
            with col5:
                if st.button("💾 현재 모델 백업", key="backup_models"):
                    st.success("✅ 모델 백업이 완료되었습니다.")
            
            with col6:
                if st.button("🔄 모델 복원", key="restore_models"):
                    st.info("🔄 모델 복원 옵션을 선택하세요.")
        
        # 상세 분석 도구
        st.markdown("### 🔍 상세 분석 도구")
        
        # 분석 옵션 선택
        analysis_type = st.selectbox(
            "분석 유형 선택",
            ["실시간 예측 결과", "모델 성능 트렌드", "이상 패턴 분석", "예측 신뢰도 분석"]
        )
        
        if analysis_type == "실시간 예측 결과":
            st.markdown("#### 📊 현재 예측 결과 상세 분석")
            
            if ai_predictions.get('abnormal_detection', {}).get('status') == 'success':
                abnormal_data = ai_predictions['abnormal_detection']
                prediction = abnormal_data['prediction']
                probabilities = prediction['probabilities']
                
                # 확률 분포를 테이블로 표시
                prob_df = pd.DataFrame([
                    {'상태': '정상', '확률': f"{probabilities['normal']:.1%}", '위험도': '낮음'},
                    {'상태': '베어링 고장', '확률': f"{probabilities['bearing_fault']:.1%}", '위험도': '중간'},
                    {'상태': '롤 정렬 불량', '확률': f"{probabilities['roll_misalignment']:.1%}", '위험도': '중간'},
                    {'상태': '모터 과부하', '확률': f"{probabilities['motor_overload']:.1%}", '위험도': '높음'},
                    {'상태': '윤활유 부족', '확률': f"{probabilities['lubricant_shortage']:.1%}", '위험도': '높음'}
                ])
                
                st.dataframe(prob_df, use_container_width=True)
                
                # 분석 인사이트
                max_prob = max(probabilities.values())
                max_status = [k for k, v in probabilities.items() if v == max_prob][0]
                
                if max_status == 'normal':
                    st.success("**분석 결과:** 설비가 정상 상태로 운영되고 있습니다.")
                elif max_status in ['bearing_fault', 'roll_misalignment']:
                    st.warning("**분석 결과:** 주의가 필요한 상태입니다. 정기 점검을 권장합니다.")
            else:
                    st.error("**분석 결과:** 즉시 조치가 필요한 상태입니다.")
            
            if ai_predictions.get('hydraulic_detection', {}).get('status') == 'success':
                hydraulic_data = ai_predictions['hydraulic_detection']
                prediction = hydraulic_data['prediction']
                
                st.markdown("**유압 시스템 분석:**")
                if prediction['prediction'] == 0:
                    st.success(f"유압 시스템이 정상 작동 중입니다. (신뢰도: {prediction['confidence']:.1%})")
                else:
                    st.error(f"유압 시스템에서 이상이 감지되었습니다. (신뢰도: {prediction['confidence']:.1%})")
        
        elif analysis_type == "모델 성능 트렌드":
            st.markdown("#### 📈 모델 성능 트렌드 분석")
            
            # 가상 성능 트렌드 데이터
            dates = pd.date_range(start='2024-01-01', end='2024-01-15', freq='D')
            equipment_accuracy = [92.1, 93.2, 91.8, 94.1, 93.7, 94.2, 93.9, 94.5, 94.2, 93.8, 94.1, 94.3, 94.0, 94.2, 94.2]
            hydraulic_accuracy = [90.5, 91.2, 90.8, 91.5, 91.8, 91.6, 91.9, 92.1, 91.8, 91.5, 91.7, 91.9, 91.8, 91.6, 91.8]
            
            trend_df = pd.DataFrame({
                '날짜': dates,
                '설비 모델 정확도': equipment_accuracy,
                '유압 모델 정확도': hydraulic_accuracy
            })
            
            fig = px.line(trend_df, x='날짜', y=['설비 모델 정확도', '유압 모델 정확도'],
                         title="모델 성능 트렌드 (최근 15일)",
                         labels={'value': '정확도 (%)', 'variable': '모델'})
            fig.update_layout(plot_bgcolor='white', paper_bgcolor='white')
            st.plotly_chart(fig, use_container_width=True)
            
            # 트렌드 분석 결과
            st.markdown("**트렌드 분석 결과:**")
            st.write("• 설비 모델: 안정적인 성능을 보이고 있으며, 점진적 개선 추세")
            st.write("• 유압 모델: 비교적 안정적이나, 약간의 변동성 존재")
            st.write("• 전반적으로 두 모델 모두 만족스러운 성능 수준 유지")
        
        elif analysis_type == "이상 패턴 분석":
            st.markdown("#### 🔍 이상 패턴 분석")
            
            # 가상 이상 패턴 데이터
            pattern_data = {
                '시간대': ['00-06시', '06-12시', '12-18시', '18-24시'],
                '베어링 고장': [2, 5, 8, 3],
                '롤 정렬 불량': [1, 3, 6, 2],
                '모터 과부하': [0, 1, 3, 1],
                '윤활유 부족': [0, 2, 4, 1]
            }
            
            pattern_df = pd.DataFrame(pattern_data)
            
            fig = px.bar(pattern_df, x='시간대', y=['베어링 고장', '롤 정렬 불량', '모터 과부하', '윤활유 부족'],
                        title="시간대별 이상 발생 패턴",
                        barmode='stack')
            fig.update_layout(plot_bgcolor='white', paper_bgcolor='white')
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("**패턴 분석 결과:**")
            st.write("• 12-18시 시간대에 이상 발생 빈도가 가장 높음")
            st.write("• 베어링 고장과 롤 정렬 불량이 주요 이상 유형")
            st.write("• 야간 시간대(00-06시)에는 이상 발생이 적음")
        
        elif analysis_type == "예측 신뢰도 분석":
            st.markdown("#### 🎯 예측 신뢰도 분석")
            
            # 가상 신뢰도 분포 데이터
            confidence_ranges = ['90-95%', '85-90%', '80-85%', '75-80%', '70-75%']
            equipment_counts = [45, 28, 15, 8, 4]
            hydraulic_counts = [52, 31, 12, 3, 2]
            
            confidence_df = pd.DataFrame({
                '신뢰도 범위': confidence_ranges,
                '설비 모델': equipment_counts,
                '유압 모델': hydraulic_counts
            })
            
            fig = px.bar(confidence_df, x='신뢰도 범위', y=['설비 모델', '유압 모델'],
                        title="예측 신뢰도 분포",
                        barmode='group')
            fig.update_layout(plot_bgcolor='white', paper_bgcolor='white')
            st.plotly_chart(fig, use_container_width=True)
            
            st.markdown("**신뢰도 분석 결과:**")
            st.write("• 대부분의 예측이 85% 이상의 높은 신뢰도를 보임")
            st.write("• 유압 모델이 설비 모델보다 더 높은 신뢰도 분포")
            st.write("• 70-75% 신뢰도 구간의 예측은 추가 검증 필요")

    with tabs[1]:  # 설비 관리
        st.markdown('<div class="main-header no-translate" translate="no">🏭 설비 관리</div>', unsafe_allow_html=True)
        st.write("설비별 상태를 확인하고 관리할 수 있습니다.")
        
        # ======================
        # 기간 선택 (맨 위로 이동)
        # ======================
        st.markdown("### 📅 기간 선택")
        
        # 사이드바 날짜 설정 가져오기
        sidebar_date_mode = st.session_state.get('sidebar_date_mode', '일자별')
        sidebar_date = st.session_state.get('sidebar_selected_date_stored', datetime.now().date())
        sidebar_date_range = st.session_state.get('sidebar_date_range_stored', (datetime.now().date() - timedelta(days=7), datetime.now().date()))
        
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            col_radio, col_date1 = st.columns([1, 2])
            with col_radio:
                date_mode = st.radio(
                    "📅 조회 모드", 
                    ["일자별", "기간별"], 
                    index=0 if sidebar_date_mode == "일자별" else 1, 
                    key="equipment_tab_date_mode",
                    horizontal=True,
                    label_visibility="collapsed"
                )
            with col_date1:
                if date_mode == "일자별":
                    selected_date = st.date_input("조회 일자", value=sidebar_date, key="equipment_tab_selected_date")
                else:
                    start_date = st.date_input("시작일", value=sidebar_date_range[0], key="equipment_tab_start_date")
        with col2:
            if date_mode == "기간별":
                end_date = st.date_input("종료일", value=sidebar_date_range[1], key="equipment_tab_end_date")
            else:
                st.write("")  # 빈 공간
        with col3:
            st.write("")  # 화면 절반을 차지하는 빈 영역
        
        # ======================
        # 데이터 로드
        # ======================
        try:
            # 현재 토글 상태 기반으로 설비 목록 조회
            current_use_real_api = st.session_state.get('api_toggle', False)
            equipment_list = get_equipment_status_from_api(current_use_real_api)
        except Exception as e:
            st.error(f"데이터 로드 오류: {e}")
            equipment_list = generate_equipment_status()
        
        # ======================
        # 설비 상태 요약
        # ======================
        st.markdown("### 📊 설비 상태 요약")
        
        if equipment_list:
            total_equipment = len(equipment_list)
            normal_count = len([eq for eq in equipment_list if eq['status'] == '정상'])
            warning_count = len([eq for eq in equipment_list if eq['status'] == '주의'])
            error_count = len([eq for eq in equipment_list if eq['status'] == '오류'])
            avg_efficiency = sum(eq['efficiency'] for eq in equipment_list) / total_equipment if total_equipment > 0 else 0
            
            col1, col2, col3, col4 = st.columns(4, gap="small")
            
            with col1:
                st.markdown(f"""
                <div class="kpi-card success no-translate" translate="no" style="padding:0.5rem 0.4rem; min-height:70px; height:80px;">
                    <div class="kpi-label" style="font-size:0.9rem;">총 설비</div>
                    <div class="kpi-value" style="font-size:1.3rem;">{total_equipment}대</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div class="kpi-card success no-translate" translate="no" style="padding:0.5rem 0.4rem; min-height:70px; height:80px;">
                    <div class="kpi-label" style="font-size:0.9rem;">정상</div>
                    <div class="kpi-value" style="font-size:1.3rem;">{normal_count}대</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                st.markdown(f"""
                <div class="kpi-card warning no-translate" translate="no" style="padding:0.5rem 0.4rem; min-height:70px; height:80px;">
                    <div class="kpi-label" style="font-size:0.9rem;">주의</div>
                    <div class="kpi-value" style="font-size:1.3rem;">{warning_count}대</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col4:
                st.markdown(f"""
                <div class="kpi-card danger no-translate" translate="no" style="padding:0.5rem 0.4rem; min-height:70px; height:80px;">
                    <div class="kpi-label" style="font-size:0.9rem;">오류</div>
                    <div class="kpi-value" style="font-size:1.3rem;">{error_count}대</div>
                </div>
                """, unsafe_allow_html=True)
        

        
        # ======================
        # 설비 목록 테이블
        # ======================
        st.markdown("### 📋 설비 목록")
        
        if equipment_list:
            # 필터링 옵션
            col1, col2, col3 = st.columns(3, gap="small")
            
            with col1:
                status_filter = st.selectbox("상태 필터", ["전체", "정상", "주의", "오류"], key="equipment_status_filter")
            
            with col2:
                equipment_types = list(set([eq.get('type', '') for eq in equipment_list]))
                type_filter = st.selectbox("설비 종류", ["전체"] + equipment_types, key="equipment_type_filter")
            
            with col3:
                search_term = st.text_input("🔍 설비명 검색", placeholder="설비명을 입력하세요...", key="equipment_search")
            
            # 필터링 적용
            filtered_equipment = equipment_list.copy()
            
            if status_filter != "전체":
                filtered_equipment = [eq for eq in filtered_equipment if eq['status'] == status_filter]
            
            if type_filter != "전체":
                filtered_equipment = [eq for eq in filtered_equipment if eq.get('type') == type_filter]
            
            if search_term:
                filtered_equipment = [eq for eq in filtered_equipment if search_term.lower() in eq['name'].lower()]
            
            # 테이블 데이터 생성
            if filtered_equipment:
                table_data = []
                for eq in filtered_equipment:
                    status_icon = {'정상':'🟢','주의':'🟠','오류':'🔴'}.get(eq['status'],'🟢')
                    table_data.append({
                        "설비 ID": eq['id'],
                        "설비명": eq['name'],
                        "상태": f"{status_icon} {eq['status']}",
                        "효율": f"{eq['efficiency']}%",
                        "종류": eq.get('type', '-'),
                        "마지막 정비": eq.get('last_maintenance', '-')
                    })
                
                df = pd.DataFrame(table_data)
                st.dataframe(df, use_container_width=True, height=400)
                
                # 상세 정보 표시
                if st.button("📊 상세 정보 보기", key="show_equipment_details"):
                    st.markdown("### 📊 설비별 상세 정보")
                    
                    for eq in filtered_equipment:
                        with st.expander(f"{eq['name']} ({eq['id']})", expanded=False):
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.markdown("**기본 정보**")
                                st.write(f"설비 ID: {eq['id']}")
                                st.write(f"설비명: {eq['name']}")
                                st.write(f"종류: {eq.get('type', '-')}")
                                st.write(f"현재 상태: {eq['status']}")
                                st.write(f"마지막 정비: {eq.get('last_maintenance', '-')}")
                            
                            with col2:
                                st.markdown("**성능 지표**")
                                efficiency = eq['efficiency']
                                
                                # 효율성에 따른 색상 설정
                                if efficiency >= 90:
                                    color = "#10b981"
                                    status_text = "우수"
                                elif efficiency >= 70:
                                    color = "#f59e0b"
                                    status_text = "양호"
                                else:
                                    color = "#ef4444"
                                    status_text = "개선 필요"
                                
                                st.write(f"가동 효율: {efficiency}% ({status_text})")
                                
                                # 진행률 바 표시
                                st.markdown(f"""
                                <div style="background: #f3f4f6; border-radius: 4px; height: 20px; margin: 10px 0;">
                                    <div style="background: {color}; height: 100%; width: {efficiency}%; border-radius: 4px; transition: width 0.3s;"></div>
                                </div>
                                """, unsafe_allow_html=True)
                            
                            # 센서 데이터 차트 (더미 데이터)
                            st.markdown("**📈 실시간 센서 데이터**")
                            sensor_data = generate_sensor_data()
                            if not sensor_data.empty:
                                fig = go.Figure()
                                
                                # 첫 번째 설비의 데이터만 표시
                                first_equipment = sensor_data['equipment'].iloc[0]
                                equipment_data = sensor_data[sensor_data['equipment'] == first_equipment]
                                
                                if 'temperature' in equipment_data.columns:
                                    fig.add_trace(go.Scatter(
                                        x=list(range(len(equipment_data))),
                                        y=equipment_data['temperature'],
                                        mode='lines',
                                        name='온도 (°C)',
                                        line=dict(color='#ef4444', width=2)
                                    ))
                                
                                if 'pressure' in equipment_data.columns:
                                    fig.add_trace(go.Scatter(
                                        x=list(range(len(equipment_data))),
                                        y=equipment_data['pressure'],
                                        mode='lines',
                                        name='압력 (bar)',
                                        line=dict(color='#3b82f6', width=2),
                                        yaxis='y2'
                                    ))
                                
                                if 'vibration' in equipment_data.columns:
                                    fig.add_trace(go.Scatter(
                                        x=list(range(len(equipment_data))),
                                        y=equipment_data['vibration'],
                                        mode='lines',
                                        name='진동 (mm/s)',
                                        line=dict(color='#10b981', width=2),
                                        yaxis='y3'
                                    ))
                                
                                fig.update_layout(
                                    height=300,
                                    margin=dict(l=0, r=0, t=0, b=0),
                                    showlegend=True,
                                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                                    yaxis=dict(title="온도 (°C)", side="left"),
                                    yaxis2=dict(title="압력 (bar)", overlaying="y", side="right"),
                                    yaxis3=dict(title="진동 (mm/s)", overlaying="y", side="right", position=0.95),
                                    xaxis=dict(title="시간"),
                                    plot_bgcolor='white',
                                    paper_bgcolor='white',
                                    font=dict(color='#1e293b')
                                )
                                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("검색 조건에 맞는 설비가 없습니다.")
        else:
            st.info("설비 데이터를 불러올 수 없습니다.")
        
        # ======================
        # 설비 관리자 등록 버튼
        # ======================
        st.markdown("---")
        st.markdown("### 👥 설비 관리자 등록")
        
        col1, col2 = st.columns(2, gap="small")
        
        with col1:
            if st.button("➕ 설비 관리자 등록", type="primary", use_container_width=True, key="equipment_manager_register_btn"):
                st.session_state.show_equipment_manager_modal = True
        
        with col2:
            if st.button("📋 관리자 목록 보기", use_container_width=True, key="equipment_manager_list_btn"):
                st.session_state.show_equipment_manager_list = True
        
        # ======================
        # 설비 관리자 등록 모달
        # ======================
        if st.session_state.get('show_equipment_manager_modal', False):
            with st.container():
                st.markdown("---")
                st.markdown("### ➕ 설비 관리자 등록 요청")
                st.write("설비별 관리자 등록 요청을 할 수 있습니다. 등록 요청 후 담당자가 승인해드립니다.")
                
                with st.form("equipment_manager_form"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        manager_name = st.text_input("이름 *", key="equipment_manager_name")
                        manager_department = st.selectbox(
                            "부서 *",
                            ["생산관리팀", "품질관리팀", "설비관리팀", "기술팀", "IT팀", "기타"],
                            key="equipment_manager_dept"
                        )
                        manager_phone = st.text_input("전화번호 *", key="equipment_manager_phone")
                        manager_email = st.text_input("이메일", key="equipment_manager_email")
                    
                    with col2:
                        manager_role = st.selectbox(
                            "권한",
                            ["user", "manager", "admin"],
                            format_func=lambda x: {"user": "일반 사용자", "manager": "관리자", "admin": "시스템 관리자"}[x],
                            key="equipment_manager_role"
                        )
                        manager_active = st.checkbox("활성 상태", value=True, key="equipment_manager_active")
                        
                        st.markdown("**기본 알림 설정**")
                        default_error = st.checkbox("긴급 알림 (Error)", value=True, key="equipment_default_error")
                        default_warning = st.checkbox("주의 알림 (Warning)", value=False, key="equipment_default_warning")
                        default_info = st.checkbox("정보 알림 (Info)", value=False, key="equipment_default_info")
                    
                    # 설비 선택 영역
                    st.markdown("**🏭 담당 설비 선택**")
                    
                    if equipment_list:
                        # 설비를 타입별로 그룹화
                        equipment_by_type = {}
                        for eq in equipment_list:
                            eq_type = eq.get('type', '기타')
                            if eq_type not in equipment_by_type:
                                equipment_by_type[eq_type] = []
                            equipment_by_type[eq_type].append(eq)
                        
                        # 타입별로 멀티셀렉트 표시 (확장 가능한 UI)
                        selected_equipment = []
                        
                        # 설비 타입 선택
                        equipment_type_filter = st.selectbox(
                            "설비 종류 선택",
                            ["전체"] + list(equipment_by_type.keys()),
                            key="manager_equipment_type_filter"
                        )
                        
                        # 선택된 타입의 설비들만 표시
                        if equipment_type_filter == "전체":
                            display_equipment = equipment_list
                        else:
                            display_equipment = equipment_by_type.get(equipment_type_filter, [])
                        
                        if display_equipment:
                            # 멀티셀렉트로 설비 선택
                            equipment_options = [f"{eq['name']} ({eq['id']})" for eq in display_equipment]
                            selected_equipment_names = st.multiselect(
                                "담당할 설비를 선택하세요",
                                options=equipment_options,
                                key="manager_equipment_multiselect"
                            )
                            
                            # 선택된 설비들을 ID로 변환
                            for selected_name in selected_equipment_names:
                                # 이름에서 ID 추출
                                for eq in display_equipment:
                                    if f"{eq['name']} ({eq['id']})" == selected_name:
                                        selected_equipment.append({
                                            "equipment_id": eq['id'],
                                            "role": "담당자",
                                            "is_primary": False
                                        })
                                        break
                            
                            # 선택된 설비 개수 표시
                            if selected_equipment:
                                st.info(f"선택된 설비: {len(selected_equipment)}개")
                        else:
                            st.info("해당 종류의 설비가 없습니다.")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        submitted = st.form_submit_button("✅ 등록 요청", type="primary", use_container_width=True)
                    
                    with col2:
                        if st.form_submit_button("❌ 취소", use_container_width=True):
                            st.session_state.show_equipment_manager_modal = False
                            st.rerun()
                    
                    with col3:
                        if st.form_submit_button("🔄 초기화", use_container_width=True):
                            st.rerun()
                
                # 폼 제출 처리 (폼 밖에서)
                if submitted:
                        if manager_name and manager_phone:
                            try:
                                # 사용자 등록
                                user_data = {
                                    "phone_number": manager_phone,
                                    "name": manager_name,
                                    "department": manager_department,
                                    "role": manager_role
                                }
                                
                                response = requests.post(f"{API_BASE_URL}/users", json=user_data, timeout=5)
                                
                                if response.status_code == 200:
                                    user_id = response.json().get('user_id')
                                    
                                    # 설비 할당
                                    if selected_equipment and user_id:
                                        for eq_assignment in selected_equipment:
                                            try:
                                                assignment_data = {
                                                    "equipment_id": eq_assignment["equipment_id"],
                                                    "user_id": user_id,
                                                    "role": eq_assignment["role"],
                                                    "is_primary": eq_assignment["is_primary"]
                                                }
                                                requests.post(f"{API_BASE_URL}/equipment/{eq_assignment['equipment_id']}/users", 
                                                            json=assignment_data, timeout=5)
                                            except:
                                                pass
                                    
                                    st.success(f"관리자 '{manager_name}' 등록 요청이 완료되었습니다.")
                                    st.session_state.show_equipment_manager_modal = False
                                    st.rerun()
                                else:
                                    error_msg = response.json().get('detail', '관리자 등록에 실패했습니다.')
                                    st.error(f"등록 실패: {error_msg}")
                            except Exception as e:
                                st.error(f"API 호출 오류: {e}")
                        else:
                            st.error("이름과 전화번호는 필수 입력 항목입니다.")
        
        # ======================
        # 설비 관리자 목록 보기
        # ======================
        if st.session_state.get('show_equipment_manager_list', False):
            with st.container():
                st.markdown("---")
                st.markdown("### 📋 설비 관리자 목록")
                
                try:
                    # 사용자 목록 조회
                    users = get_users_from_api(use_real_api)
                    
                    if users:
                        # 간단한 관리자 목록 표시
                        table_data = []
                        for user in users[:10]:  # 최대 10명만 표시
                            # 담당 설비 정보 가져오기
                            try:
                                user_equipment = get_equipment_users_by_user(user['id'])
                                equipment_names = [eq['equipment_name'] for eq in user_equipment] if user_equipment else []
                            except:
                                equipment_names = []
                            
                            status_icon = "🟢" if user.get('is_active', True) else "🔴"
                            status_text = "활성" if user.get('is_active', True) else "비활성"
                            
                            table_data.append({
                                "이름": user['name'],
                                "부서": user.get('department', '-'),
                                "상태": f"{status_icon} {status_text}",
                                "담당 설비": ", ".join(equipment_names[:2]) + ("..." if len(equipment_names) > 2 else ""),
                                "설비 수": len(equipment_names)
                            })
                        
                        if table_data:
                            df = pd.DataFrame(table_data)
                            st.dataframe(df, use_container_width=True, height=300)
                        else:
                            st.info("등록된 관리자가 없습니다.")
                    else:
                        st.info("관리자 데이터를 불러올 수 없습니다.")
                        
                except Exception as e:
                    st.error(f"관리자 목록 조회 오류: {e}")
                
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("➕ 새 관리자 등록", type="primary", use_container_width=True, key="new_manager_from_list"):
                        st.session_state.show_equipment_manager_list = False
                        st.session_state.show_equipment_manager_modal = True
                        st.rerun()
                
                with col2:
                    if st.button("❌ 닫기", use_container_width=True, key="close_manager_list"):
                        st.session_state.show_equipment_manager_list = False
                        st.rerun()
        
        # ======================
        # 설비 분석 영역
        # ======================
        st.markdown("---")
        st.markdown("### 📈 설비 분석")
        
        # 분석 설정
        col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
        
        with col1:
            # 분석 유형 선택
            analysis_type = st.selectbox(
                "분석 유형",
                ["센서 데이터 통합", "설비 상태별 분포", "효율성 분석", "공정별 설비 현황"],
                key="equipment_analysis_type"
            )
        
        with col2:
            # 기간 설정 옵션
            analysis_date_mode = st.selectbox("분석 모드", ["일자별", "기간별"], key="equipment_date_mode")
        
        with col3:
            if analysis_date_mode == "기간별":
                # 기간 설정
                analysis_start_date = st.date_input("분석 시작일", value=datetime.now().date() - timedelta(days=7), key="equipment_start_date")
            else:
                # 일자 설정
                sidebar_date = st.session_state.get('sidebar_selected_date_stored', datetime.now().date())
                analysis_date = st.date_input("분석 일자", value=sidebar_date, key="equipment_analysis_date")
        
        with col4:
            if analysis_date_mode == "기간별":
                # 기간 설정
                analysis_end_date = st.date_input("분석 종료일", value=datetime.now().date(), key="equipment_end_date")
            else:
                st.write("")  # 빈 공간
        
        # 분석 결과 바로 표시
        if analysis_type == "센서 데이터 통합":
            # 통합 센서 데이터 그래프
            st.markdown("**📊 센서 데이터 통합 추세**")
            
            # 시뮬레이션 데이터 생성
            if analysis_date_mode == "일자별":
                dates = pd.date_range(start=analysis_date, end=analysis_date + timedelta(days=1), freq='H')[:-1]  # 해당 일자의 24시간
            else:  # 기간별
                dates = pd.date_range(start=analysis_start_date, end=analysis_end_date, freq='H')
            temp_data = np.random.normal(25, 5, len(dates)) + np.sin(np.arange(len(dates)) * 0.1) * 3
            pressure_data = np.random.normal(100, 15, len(dates)) + np.cos(np.arange(len(dates)) * 0.05) * 10
            vibration_data = np.random.normal(0.5, 0.2, len(dates)) + np.sin(np.arange(len(dates)) * 0.2) * 0.1
            
            fig_combined = go.Figure()
            
            # 온도 데이터 (첫 번째 Y축)
            fig_combined.add_trace(go.Scatter(
                x=dates,
                y=temp_data,
                mode='lines',
                name='온도 (°C)',
                line=dict(color='#ef4444', width=2),
                yaxis='y'
            ))
            
            # 압력 데이터 (두 번째 Y축)
            fig_combined.add_trace(go.Scatter(
                x=dates,
                y=pressure_data,
                mode='lines',
                name='압력 (kPa)',
                line=dict(color='#3b82f6', width=2),
                yaxis='y2'
            ))
            
            # 진동 데이터 (세 번째 Y축)
            fig_combined.add_trace(go.Scatter(
                x=dates,
                y=vibration_data,
                mode='lines',
                name='진동 (mm/s)',
                line=dict(color='#10b981', width=2),
                yaxis='y3'
            ))
            
            # 제목 동적 설정
            if analysis_date_mode == "일자별":
                title_text = f"센서 데이터 통합 추세 ({analysis_date.strftime('%Y-%m-%d')})"
            else:
                title_text = f"센서 데이터 통합 추세 ({analysis_start_date.strftime('%Y-%m-%d')} ~ {analysis_end_date.strftime('%Y-%m-%d')})"
            
            fig_combined.update_layout(
                title=title_text,
                xaxis_title="시간",
                height=400,
                plot_bgcolor='white',
                paper_bgcolor='white',
                showlegend=True,
                yaxis=dict(title="온도 (°C)", tickfont=dict(color="#ef4444")),
                yaxis2=dict(title="압력 (kPa)", tickfont=dict(color="#3b82f6"), anchor="x", overlaying="y", side="right"),
                yaxis3=dict(title="진동 (mm/s)", tickfont=dict(color="#10b981"), anchor="free", overlaying="y", side="right", position=0.95)
            )
            st.plotly_chart(fig_combined, use_container_width=True)
        
        elif analysis_type == "설비 상태별 분포":
            # 설비 상태별 분포 분석
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**🏭 설비 상태 분포**")
                status_counts = {
                    '정상': normal_count,
                    '주의': warning_count,
                    '오류': error_count
                }
                
                fig_pie = go.Figure(data=[go.Pie(
                    labels=list(status_counts.keys()),
                    values=list(status_counts.values()),
                    hole=0.4,
                    marker_colors=['#10b981', '#f59e0b', '#ef4444']
                )])
                
                fig_pie.update_layout(
                    title="설비 상태별 분포",
                    height=400,
                    showlegend=True,
                    plot_bgcolor='white',
                    paper_bgcolor='white'
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col2:
                st.markdown("**📈 상태별 추세**")
                # 시뮬레이션 데이터 생성
                if analysis_date_mode == "일자별":
                    dates = pd.date_range(start=analysis_date, end=analysis_date, freq='D')
                else:  # 기간별
                    dates = pd.date_range(start=analysis_start_date, end=analysis_end_date, freq='D')
                normal_trend = [normal_count + np.random.randint(-2, 3) for _ in range(len(dates))]
                warning_trend = [warning_count + np.random.randint(-1, 2) for _ in range(len(dates))]
                error_trend = [error_count + np.random.randint(-1, 2) for _ in range(len(dates))]
                
                fig_trend = go.Figure()
                fig_trend.add_trace(go.Scatter(x=dates, y=normal_trend, mode='lines+markers', name='정상', line=dict(color='#10b981')))
                fig_trend.add_trace(go.Scatter(x=dates, y=warning_trend, mode='lines+markers', name='주의', line=dict(color='#f59e0b')))
                fig_trend.add_trace(go.Scatter(x=dates, y=error_trend, mode='lines+markers', name='오류', line=dict(color='#ef4444')))
                
                fig_trend.update_layout(
                    title="설비 상태별 추세",
                    xaxis_title="날짜",
                    yaxis_title="설비 수",
                    height=400,
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    showlegend=True
                )
                st.plotly_chart(fig_trend, use_container_width=True)
        
        elif analysis_type == "효율성 분석":
            # 효율성 분석
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**📊 설비별 효율성 비교**")
                # 효율성 기준으로 정렬 (상위 10개)
                sorted_equipment = sorted(equipment_list, key=lambda x: x['efficiency'], reverse=True)[:10]
                
                fig_bar = go.Figure(data=[go.Bar(
                    x=[eq['name'] for eq in sorted_equipment],
                    y=[eq['efficiency'] for eq in sorted_equipment],
                    marker_color=['#10b981' if eq['efficiency'] >= 85 else '#f59e0b' if eq['efficiency'] >= 70 else '#ef4444' for eq in sorted_equipment]
                )])
                
                fig_bar.update_layout(
                    title="설비별 효율성 (상위 10개)",
                    xaxis_title="설비명",
                    yaxis_title="효율성 (%)",
                    height=400,
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    xaxis=dict(tickangle=45)
                )
                st.plotly_chart(fig_bar, use_container_width=True)
            
            with col2:
                st.markdown("**📈 효율성 분포**")
                efficiencies = [eq['efficiency'] for eq in equipment_list]
                
                fig_hist = go.Figure(data=[go.Histogram(
                    x=efficiencies,
                    nbinsx=10,
                    marker_color='#8b5cf6',
                    opacity=0.7
                )])
                
                fig_hist.update_layout(
                    title="설비 효율성 분포",
                    xaxis_title="효율성 (%)",
                    yaxis_title="설비 수",
                    height=400,
                    plot_bgcolor='white',
                    paper_bgcolor='white'
                )
                
                # 평균선 추가
                fig_hist.add_vline(
                    x=avg_efficiency,
                    line_dash="dash",
                    line_color="red",
                    annotation_text=f"평균: {avg_efficiency:.1f}%",
                    annotation_position="top right"
                )
                
                st.plotly_chart(fig_hist, use_container_width=True)
            
            # 효율성 개선 제안
            st.markdown("**💡 효율성 개선 제안**")
            low_efficiency_equipment = [eq for eq in equipment_list if eq['efficiency'] < 70]
            
            if low_efficiency_equipment:
                st.warning(f"⚠️ 효율성이 70% 미만인 설비가 {len(low_efficiency_equipment)}개 있습니다.")
                for eq in low_efficiency_equipment[:3]:  # 상위 3개만 표시
                    st.info(f"• {eq['name']}: 현재 효율성 {eq['efficiency']}% - 정비 점검 권장")
            else:
                st.success("✅ 모든 설비의 효율성이 양호한 상태입니다.")
        
        elif analysis_type == "공정별 설비 현황":
            # 공정별 설비 현황 분석
            st.markdown("**🏭 공정별 설비 현황**")
            
            # 공정별 데이터 생성 (시뮬레이션)
            process_data = {
                '제철공정': {'total': 15, 'normal': 12, 'warning': 2, 'error': 1, 'avg_efficiency': 87.5},
                '압연공정': {'total': 22, 'normal': 18, 'warning': 3, 'error': 1, 'avg_efficiency': 82.3},
                '조강공정': {'total': 8, 'normal': 7, 'warning': 1, 'error': 0, 'avg_efficiency': 91.2},
                '정련공정': {'total': 12, 'normal': 10, 'warning': 2, 'error': 0, 'avg_efficiency': 85.7},
                '주조공정': {'total': 18, 'normal': 15, 'warning': 2, 'error': 1, 'avg_efficiency': 79.8}
            }
            
            col1, col2 = st.columns(2)
            
            with col1:
                # 공정별 설비 수
                fig_process = go.Figure(data=[go.Bar(
                    x=list(process_data.keys()),
                    y=[data['total'] for data in process_data.values()],
                    marker_color='#3b82f6',
                    text=[data['total'] for data in process_data.values()],
                    textposition='auto'
                )])
                
                fig_process.update_layout(
                    title="공정별 설비 수",
                    xaxis_title="공정",
                    yaxis_title="설비 수",
                    height=400,
                    plot_bgcolor='white',
                    paper_bgcolor='white'
                )
                st.plotly_chart(fig_process, use_container_width=True)
            
            with col2:
                # 공정별 평균 효율성
                fig_efficiency = go.Figure(data=[go.Bar(
                    x=list(process_data.keys()),
                    y=[data['avg_efficiency'] for data in process_data.values()],
                    marker_color=['#10b981' if eff >= 85 else '#f59e0b' if eff >= 75 else '#ef4444' for eff in [data['avg_efficiency'] for data in process_data.values()]],
                    text=[f"{eff:.1f}%" for eff in [data['avg_efficiency'] for data in process_data.values()]],
                    textposition='auto'
                )])
                
                fig_efficiency.update_layout(
                    title="공정별 평균 효율성",
                    xaxis_title="공정",
                    yaxis_title="평균 효율성 (%)",
                    height=400,
                    plot_bgcolor='white',
                    paper_bgcolor='white'
                )
                st.plotly_chart(fig_efficiency, use_container_width=True)
            
            # 공정별 상세 현황 테이블
            st.markdown("**📋 공정별 상세 현황**")
            table_data = []
            for process, data in process_data.items():
                status_ratio = f"{data['normal']}/{data['total']} ({data['normal']/data['total']*100:.1f}%)"
                table_data.append({
                    "공정명": process,
                    "총 설비": data['total'],
                    "정상": data['normal'],
                    "주의": data['warning'],
                    "오류": data['error'],
                    "정상 비율": status_ratio,
                    "평균 효율성": f"{data['avg_efficiency']:.1f}%"
                })
            
            df_process = pd.DataFrame(table_data)
            st.dataframe(df_process, use_container_width=True, height=300)
            
            # 공정별 개선 제안
            st.markdown("**💡 공정별 개선 제안**")
            low_efficiency_processes = [(process, data) for process, data in process_data.items() if data['avg_efficiency'] < 80]
            
            if low_efficiency_processes:
                st.warning("⚠️ 효율성이 낮은 공정이 있습니다.")
                for process, data in low_efficiency_processes:
                    st.info(f"• {process}: 평균 효율성 {data['avg_efficiency']:.1f}% - 설비 점검 및 최적화 필요")
            else:
                st.success("✅ 모든 공정의 효율성이 양호한 상태입니다.")

    with tabs[2]:  # 알림 관리
        st.markdown('<div class="main-header no-translate" translate="no">🚨 알림 관리</div>', unsafe_allow_html=True)
        st.write("실시간 알림(이상/경보/정보 등)을 확인하고, 처리 상태를 관리할 수 있습니다.")
        
        # ======================
        # 기간 선택 (맨 위로 이동)
        # ======================
        st.markdown("### 📅 기간 선택")
        
        # 사이드바 날짜 설정 가져오기
        sidebar_date_mode = st.session_state.get('sidebar_date_mode', '일자별')
        sidebar_date = st.session_state.get('sidebar_selected_date_stored', datetime.now().date())
        sidebar_date_range = st.session_state.get('sidebar_date_range_stored', (datetime.now().date() - timedelta(days=7), datetime.now().date()))
    
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            col_radio, col_date1 = st.columns([1, 2])
            with col_radio:
                date_mode = st.radio(
                    "📅 조회 모드", 
                    ["일자별", "기간별"], 
                    index=0 if sidebar_date_mode == "일자별" else 1, 
                    key="alert_tab_date_mode",
                    horizontal=True,
                    label_visibility="collapsed"
                )
            with col_date1:
                if date_mode == "일자별":
                    selected_date = st.date_input("조회 일자", value=sidebar_date, key="alert_selected_date")
                else:
                    start_date = st.date_input("시작일", value=sidebar_date_range[0], key="alert_start_date")
        with col2:
            if date_mode == "기간별":
                end_date = st.date_input("종료일", value=sidebar_date_range[1], key="alert_end_date")
            else:
                st.write("")  # 빈 공간
        with col3:
            st.write("")  # 화면 절반을 차지하는 빈 영역
        
                # 현재 토글 상태에 따라 데이터 가져오기
        current_use_real_api = st.session_state.get('api_toggle', False)
        if current_use_real_api:
            try:
                alerts = get_alerts_from_api(current_use_real_api)
                equipment_data = get_equipment_status_from_api(current_use_real_api)
            except Exception as e:
                st.error(f"API 데이터 가져오기 오류: {e}")
                alerts = generate_alert_data()
                equipment_data = generate_equipment_status()
        else:
            alerts = generate_alert_data()
            equipment_data = generate_equipment_status()
        
        adf = pd.DataFrame(alerts)
        
        
        # 빈 데이터프레임 처리
        if adf.empty:
            st.info("알림 데이터가 없습니다.")
            st.button("상태 변경(확장)", disabled=True, key="alert_status_btn_empty")
            st.download_button("알림 이력 다운로드 (CSV)", "", file_name="alerts.csv", mime="text/csv", key="alert_csv_btn_empty", disabled=True)
        else:
            # 상단 KPI 카드
            st.markdown("### 📊 알림 현황 요약")
            col1, col2, col3, col4 = st.columns(4, gap="small")
            
            total_alerts = len(adf)
            error_count = len(adf[adf['severity'] == 'error'])
            warning_count = len(adf[adf['severity'] == 'warning'])
            info_count = len(adf[adf['severity'] == 'info'])
            
            # 처리 상태별 카운트 (status 컬럼이 있는 경우)
            if 'status' in adf.columns:
                pending_count = len(adf[adf['status'] == '미처리'])
                processing_count = len(adf[adf['status'] == '처리중'])
                completed_count = len(adf[adf['status'] == '완료'])
            else:
                pending_count = total_alerts
                processing_count = 0
                completed_count = 0
            
            with col1:
                st.markdown(f"""
                <div class="kpi-card danger no-translate" translate="no" style="padding:0.5rem 0.4rem; min-height:70px; height:80px;">
                    <div class="kpi-label" style="font-size:0.9rem;">전체 알림</div>
                    <div class="kpi-value" style="font-size:1.3rem;">{total_alerts}건</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div class="kpi-card danger no-translate" translate="no" style="padding:0.5rem 0.4rem; min-height:70px; height:80px;">
                    <div class="kpi-label" style="font-size:0.9rem;">긴급 알림</div>
                    <div class="kpi-value" style="font-size:1.3rem;">{error_count}건</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                st.markdown(f"""
                <div class="kpi-card warning no-translate" translate="no" style="padding:0.5rem 0.4rem; min-height:70px; height:80px;">
                    <div class="kpi-label" style="font-size:0.9rem;">미처리</div>
                    <div class="kpi-value" style="font-size:1.3rem;">{pending_count}건</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col4:
                st.markdown(f"""
                <div class="kpi-card success no-translate" translate="no" style="padding:0.5rem 0.4rem; min-height:70px; height:80px;">
                    <div class="kpi-label" style="font-size:0.9rem;">처리완료</div>
                    <div class="kpi-value" style="font-size:1.3rem;">{completed_count}건</div>
                </div>
                """, unsafe_allow_html=True)
            
            
            
            # 필터 및 검색
            st.markdown("### 🔍 알림 검색 및 필터")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                eq_filter = st.selectbox("설비별", ["전체"] + sorted(adf['equipment'].unique()))
            with col2:
                sev_filter = st.selectbox("심각도", ["전체", "error", "warning", "info"])
            with col3:
                if 'status' in adf.columns:
                    status_filter = st.selectbox("처리상태", ["전체", "미처리", "처리중", "완료"])
                else:
                    status_filter = "전체"
            with col4:
                search_term = st.text_input("알림 내용 검색", placeholder="알림 내용을 입력하세요...")
            
            # API 데이터에 status 컬럼이 없을 경우 기본값 추가
            if 'status' not in adf.columns:
                adf['status'] = '미처리'
            
            # manager와 interlock_bypass 컬럼이 없을 경우 기본값 추가
            if 'manager' not in adf.columns:
                adf['manager'] = ''
            if 'interlock_bypass' not in adf.columns:
                adf['interlock_bypass'] = ''
            
            # 날짜 필터링 적용
            adf['date'] = pd.to_datetime(adf['time']).dt.date
            if date_mode == "일자별":
                filtered = adf[adf['date'] == selected_date].copy()
            else:  # 기간별
                filtered = adf[(adf['date'] >= start_date) & (adf['date'] <= end_date)].copy()
            
            # 기타 필터링 적용
            if eq_filter != "전체":
                filtered = filtered[filtered['equipment'] == eq_filter]
            if sev_filter != "전체":
                filtered = filtered[filtered['severity'] == sev_filter]
            if status_filter != "전체":
                filtered = filtered[filtered['status'] == status_filter]
            if search_term:
                filtered = filtered[filtered['issue'].str.contains(search_term, case=False, na=False)]
            
            # 심각도 컬러/아이콘 강조
            def sev_icon(sev):
                return {'error': '🔴', 'warning': '🟠', 'info': '🔵'}.get(sev, '⚪') + ' ' + sev
            
            filtered['심각도'] = filtered['severity'].apply(sev_icon)
            
            # 알림 목록 표시
            st.markdown("### 📋 알림 목록")
            
            # 필요한 컬럼들이 있는지 확인하고 표시
            available_columns = ['equipment', 'issue', 'time', '심각도', 'status', 'manager', 'interlock_bypass']
            if 'details' in filtered.columns:
                available_columns.append('details')
            
            # 컬럼명 한글화
            column_mapping = {
                'equipment': '설비',
                'issue': '이슈',
                'time': '시간',
                '심각도': '심각도',
                'status': '상태',
                'manager': '처리자',
                'interlock_bypass': '인터락/바이패스',
                'details': '상세내용'
            }
            
            # 표시할 컬럼만 선택하고 한글명으로 변경
            display_df = filtered[available_columns].copy()
            display_df.columns = [column_mapping.get(col, col) for col in display_df.columns]
            
            st.dataframe(display_df, use_container_width=True, height=350)
            
            # 상세정보 패널
            if not filtered.empty:
                st.markdown("### 🔧 알림 상세 정보")
                selected = st.selectbox("알림 선택", filtered.index, format_func=lambda i: f"{filtered.loc[i, 'equipment']} - {filtered.loc[i, 'issue']}")
                
                # 상세 정보 탭
                alert_detail_tab1, alert_detail_tab2, alert_detail_tab3 = st.tabs(["기본 정보", "처리 이력", "관련 데이터"])
                
                with alert_detail_tab1:
                    # 기본 정보 섹션
                    st.markdown("#### 📋 알림 기본 정보")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("**🔧 설비 정보**")
                        st.info(f"**설비명:** {filtered.loc[selected, 'equipment']}")
                        st.info(f"**발생 시간:** {filtered.loc[selected, 'time']}")
                        st.info(f"**심각도:** {filtered.loc[selected, 'severity']}")
                    
                    with col2:
                        st.markdown("**⚙️ 처리 정보**")
                        st.info(f"**현재 상태:** {filtered.loc[selected, 'status']}")
                        
                        # 심각도별 색상 표시
                        severity = filtered.loc[selected, 'severity']
                        if severity == 'error':
                            st.error("🚨 **긴급 조치가 필요한 알림입니다.**")
                        elif severity == 'warning':
                            st.warning("⚠️ **주의가 필요한 알림입니다.**")
                        else:
                            st.info("ℹ️ **정보성 알림입니다.**")
                    
                    # 상세 설명 섹션
                    st.markdown("#### 📝 상세 설명")
                    if 'details' in filtered.columns and filtered.loc[selected, 'details']:
                        st.write(filtered.loc[selected, 'details'])
                    else:
                        st.info("상세 설명이 없습니다.")
            
            with alert_detail_tab2:
                # 처리 상태 관리 섹션
                st.markdown("#### 🔄 처리 상태 관리")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**📊 상태 변경**")
                    current_status = filtered.loc[selected, 'status']
                    new_status = st.selectbox("처리 상태", ["미처리", "처리중", "완료"], 
                                            index=["미처리", "처리중", "완료"].index(current_status), 
                                            key=f"alert_status_{selected}")
                    
                    # 상태 변경 버튼을 우측에 배치
                    col1_1, col1_2, col1_3 = st.columns([1, 1, 1])
                    with col1_3:
                        if st.button("상태 변경", key=f"alert_status_btn_{selected}"):
                            st.success(f"알림 상태가 '{new_status}'로 변경되었습니다.")
                
                with col2:
                    st.markdown("**📝 처리 메모**")
                    processing_note = st.text_area("처리 내용", key=f"processing_note_{selected}")
                    assigned_to = st.text_input("담당자", key=f"assigned_to_{selected}")
                    
                    # 저장 버튼을 우측으로 배치
                    col2_1, col2_2, col2_3 = st.columns([1, 1, 1])
                    with col2_3:
                        if st.button("메모 저장", key=f"save_note_{selected}"):
                            st.success("처리 메모가 저장되었습니다.")
                
                # 처리 이력 섹션
                st.markdown("#### 📈 처리 이력")
                processing_history = [
                    {"시간": filtered.loc[selected, 'time'], "상태": "발생", "담당자": "-", "메모": "알림 발생"},
                    {"시간": "2024-01-15 14:30", "상태": "처리중", "담당자": "홍길동", "메모": "점검 시작"},
                    {"시간": "2024-01-15 15:15", "상태": "완료", "담당자": "홍길동", "메모": "문제 해결 완료"}
                ]
                
                history_df = pd.DataFrame(processing_history)
                st.dataframe(history_df, use_container_width=True, height=200)
            
            with alert_detail_tab3:
                # 관련 데이터 분석 섹션
                st.markdown("#### 🔍 관련 데이터 분석")
                equipment_name = filtered.loc[selected, 'equipment']
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**🔧 설비 상태**")
                    if use_real_api:
                        try:
                            equipment_data = get_equipment_status_from_api(use_real_api)
                            equipment_df = pd.DataFrame(equipment_data)
                            equipment_info = equipment_df[equipment_df['name'] == equipment_name]
                            if not equipment_info.empty:
                                st.success(f"**현재 상태:** {equipment_info.iloc[0]['status']}")
                                st.success(f"**가동률:** {equipment_info.iloc[0]['efficiency']}%")
                                st.success(f"**마지막 정비:** {equipment_info.iloc[0]['last_maintenance']}")
                            else:
                                st.info("설비 정보를 찾을 수 없습니다.")
                        except:
                            st.info("설비 정보를 가져올 수 없습니다.")
                    else:
                        st.info("API 연동 시 설비 정보를 확인할 수 있습니다.")
                
                with col2:
                    st.markdown("**📊 유사 알림 패턴**")
                    similar_alerts = filtered[filtered['equipment'] == equipment_name]
                    if len(similar_alerts) > 1:
                        st.warning(f"**같은 설비 알림:** {len(similar_alerts)}건")
                        st.warning(f"**최근 발생:** {similar_alerts['time'].iloc[-1]}")
                    else:
                        st.success("**같은 설비 알림:** 없음")
        
        # 알림 관리 기능
        st.markdown("### ⚙️ 알림 관리 기능")
        
        # 세로 구분선이 있는 3개 컬럼
        col1, col2, col3, col4, col5 = st.columns([1, 0.05, 1, 0.05, 1])
        
        with col1:
            st.markdown("**📋 일괄 처리**")
            if not filtered.empty:
                bulk_status = st.selectbox("일괄 상태 변경", ["미처리", "처리중", "완료"], key="bulk_status")
                # 일괄 처리 버튼을 우측에 배치
                col1_1, col1_2, col1_3 = st.columns([1, 1, 1])
                with col1_3:
                    if st.button("일괄 처리", key="bulk_process"):
                        st.success(f"선택된 {len(filtered)}건의 알림이 '{bulk_status}'로 변경되었습니다.")
        
        # 첫 번째 세로 구분선
        with col2:
            st.markdown('<div style="border-left: 2px solid #e2e8f0; height: 200px; margin: 0 auto;"></div>', unsafe_allow_html=True)
        
        with col3:
            st.markdown("**⚙️ 알림 설정**")
            auto_acknowledge = st.checkbox("자동 확인", value=False, key="auto_ack")
            notification_sound = st.checkbox("알림음", value=True, key="notification_sound_checkbox")
            email_notification = st.checkbox("이메일 알림", value=False, key="email_notification")
            
            # 설정 저장 버튼을 알림 설정 우측편에 배치
            col3_1, col3_2 = st.columns([2, 1])
            with col3_2:
                if st.button("설정 저장", key="save_alert_settings_alerts", use_container_width=True):
                    st.success("알림 설정이 저장되었습니다.")
        
        # 두 번째 세로 구분선
        with col4:
            st.markdown('<div style="border-left: 2px solid #e2e8f0; height: 200px; margin: 0 auto;"></div>', unsafe_allow_html=True)
        
        with col5:
            st.markdown("**💾 데이터 내보내기**")
            export_format = st.selectbox("내보내기 형식", ["CSV", "Excel", "PDF"], key="export_format")
            # 데이터 내보내기 버튼을 우측에 배치
            col5_1, col5_2, col5_3 = st.columns([1, 1, 1])
            with col5_3:
                if st.button("데이터 내보내기", key="export_data"):
                    st.success(f"{export_format} 형식으로 데이터 내보내기가 시작되었습니다.")
        
        # 알림 통계 및 분석
        st.markdown("### 📈 알림 통계 및 분석")
        
        # 세로 구분선이 있는 2개 컬럼
        col1, col2, col3 = st.columns([1, 0.05, 1])
        
        with col1:
            st.markdown("**심각도별 알림 분포**")
            severity_counts = adf['severity'].value_counts()
            
            # 파이 차트
            fig = go.Figure(data=[go.Pie(labels=severity_counts.index, values=severity_counts.values)])
            fig.update_layout(
                title="심각도별 알림 분포",
                height=300,
                plot_bgcolor='white',
                paper_bgcolor='white'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # 세로 구분선
        with col2:
            st.markdown('<div style="border-left: 2px solid #e2e8f0; height: 400px; margin: 0 auto;"></div>', unsafe_allow_html=True)
        
        with col3:
            st.markdown("**설비별 알림 발생 현황**")
            
            # 실제 알림 데이터에서 설비별 분석
            if not filtered.empty:
                equipment_counts = filtered['equipment'].value_counts().head(10)
            else:
                equipment_counts = adf['equipment'].value_counts().head(10)
            
            # 설비별 알림 건수와 설비 상태 정보 결합
            equipment_df = pd.DataFrame(equipment_data)
            equipment_status_dict = dict(zip(equipment_df['name'], equipment_df['status']))
            
            # 설비별 알림 건수에 상태 정보 추가
            equipment_data_for_chart = []
            for equipment, count in equipment_counts.items():
                status = equipment_status_dict.get(equipment, '알 수 없음')
                equipment_data_for_chart.append({
                    'equipment': equipment,
                    'count': count,
                    'status': status
                })
            
            # 상태별 색상 매핑
            color_map = {
                '정상': '#10b981',
                '점검중': '#f59e0b',
                '고장': '#ef4444',
                '알 수 없음': '#6b7280'
            }
            
            colors = [color_map.get(data['status'], '#6b7280') for data in equipment_data_for_chart]
            
            fig = go.Figure(data=[go.Bar(
                x=[data['count'] for data in equipment_data_for_chart], 
                y=[data['equipment'] for data in equipment_data_for_chart], 
                orientation='h',
                marker_color=colors,
                text=[f"{data['count']}건 ({data['status']})" for data in equipment_data_for_chart],
                textposition='auto'
            )])
            
            fig.update_layout(
                title="설비별 알림 발생 건수 (상위 10개)",
                height=300,
                plot_bgcolor='white',
                paper_bgcolor='white',
                xaxis_title="알림 건수",
                yaxis_title="설비명"
            )
            # x축을 정수로 표시 (1, 2, 3, 4...)
            fig.update_xaxes(tickmode='linear', dtick=1, range=[0, max(equipment_counts.values) + 1])
            st.plotly_chart(fig, use_container_width=True)
        
        # 시간대별 알림 분석
        st.markdown("**시간대별 알림 발생 패턴**")
        
        # 실제 알림 데이터에서 시간대별 분석
        if not filtered.empty:
            filtered['hour'] = pd.to_datetime(filtered['time']).dt.hour
            hourly_counts = filtered['hour'].value_counts().sort_index()
            
            # 0-23시까지 모든 시간대에 대해 데이터 생성
            hours = list(range(24))
            alert_counts = [hourly_counts.get(hour, 0) for hour in hours]
            time_trend_df = pd.DataFrame({'시간': hours, '알림 수': alert_counts})
        else:
            # 데이터가 없을 경우 기본값
            hours = list(range(24))
            alert_counts = [0] * 24
            time_trend_df = pd.DataFrame({'시간': hours, '알림 수': alert_counts})
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=time_trend_df['시간'],
            y=time_trend_df['알림 수'],
            mode='lines+markers',
            name='알림 발생 수',
            line=dict(color='#ef4444', width=3)
        ))
        fig.update_layout(
            title="시간대별 알림 발생 패턴",
            xaxis_title="시간 (시)",
            yaxis_title="알림 발생 수",
            height=300,
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        # y축을 정수로 표시
        fig.update_yaxes(tickmode='linear', dtick=1)
        st.plotly_chart(fig, use_container_width=True)
        
        # 알림 처리 결과 분석 (인터락/바이패스)
        st.markdown("**알림 처리 결과 분석 (인터락/바이패스)**")
        
        # 기간별 처리 결과 데이터 생성
        if not filtered.empty and 'interlock_bypass' in filtered.columns:
            # 날짜별로 그룹화하여 인터락/바이패스 건수 계산
            filtered['date'] = pd.to_datetime(filtered['time']).dt.date
            
            # date_mode에 따라 start_date와 end_date 설정
            if date_mode == "일자별":
                start_date = selected_date
                end_date = selected_date
            else:  # 기간별
                # start_date와 end_date는 이미 위에서 정의됨
                pass
            
            date_range = pd.date_range(start=start_date, end=end_date, freq='D')
            
            interlock_data = []
            bypass_data = []
            
            for date in date_range:
                date_str = date.strftime('%Y-%m-%d')
                daily_data = filtered[filtered['date'] == date.date()]
                
                interlock_count = len(daily_data[daily_data['interlock_bypass'] == '인터락'])
                bypass_count = len(daily_data[daily_data['interlock_bypass'] == '바이패스'])
                
                interlock_data.append(interlock_count)
                bypass_data.append(bypass_count)
            
            # 막대 그래프 생성
            fig = go.Figure()
            
            fig.add_trace(go.Bar(
                x=[d.strftime('%m/%d') for d in date_range],
                y=interlock_data,
                name='인터락',
                marker_color='#ef4444',
                opacity=0.8
            ))
            
            fig.add_trace(go.Bar(
                x=[d.strftime('%m/%d') for d in date_range],
                y=bypass_data,
                name='바이패스',
                marker_color='#3b82f6',
                opacity=0.8
            ))
            
            fig.update_layout(
                title=f"기간별 알림 처리 결과 ({start_date.strftime('%m/%d')} ~ {end_date.strftime('%m/%d')})",
                xaxis_title="날짜",
                yaxis_title="처리 건수",
                height=400,
                plot_bgcolor='white',
                paper_bgcolor='white',
                barmode='group',
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.02,
                    xanchor="right",
                    x=1
                )
            )
            # y축을 정수로 표시
            fig.update_yaxes(tickmode='linear', dtick=1)
            
            st.plotly_chart(fig, use_container_width=True)
            
            # 처리 결과 요약 통계
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                total_interlock = sum(interlock_data)
                st.metric("총 인터락 건수", f"{total_interlock}건")
            with col2:
                total_bypass = sum(bypass_data)
                st.metric("총 바이패스 건수", f"{total_bypass}건")
            with col3:
                total_processed = total_interlock + total_bypass
                st.metric("총 처리 완료 건수", f"{total_processed}건")
            with col4:
                if total_processed > 0:
                    interlock_ratio = (total_interlock / total_processed) * 100
                    st.metric("인터락 비율", f"{interlock_ratio:.1f}%")
                else:
                    st.metric("인터락 비율", "0%")
        else:
            st.info("선택된 기간에 처리 완료된 알림이 없습니다.")
        
        # 다운로드 버튼
        st.markdown("### 💾 데이터 내보내기")
        # 세로 구분선이 있는 2개 컬럼
        col1, col2, col3 = st.columns([1, 0.05, 1])
        
        with col1:
            st.download_button("알림 이력 다운로드 (CSV)", adf.to_csv(index=False), 
                             file_name="alerts.csv", mime="text/csv", key="alert_csv_btn")
        
        # 세로 구분선
        with col2:
            st.markdown('<div style="border-left: 2px solid #e2e8f0; height: 100px; margin: 0 auto;"></div>', unsafe_allow_html=True)
        
        with col3:
            st.write("")  # 빈 공간

    with tabs[3]:  # 리포트
        st.markdown('<div class="main-header no-translate" translate="no">📈 리포트 & 분석</div>', unsafe_allow_html=True)
        
        # ======================
        # 기간 선택 (맨 위로 이동)
        # ======================
        st.markdown("### 📅 기간 선택")
        
        # 사이드바 날짜 설정 가져오기
        sidebar_date_mode = st.session_state.get('sidebar_date_mode', '일자별')
        sidebar_date = st.session_state.get('sidebar_selected_date_stored', datetime.now().date())
        sidebar_date_range = st.session_state.get('sidebar_date_range_stored', (datetime.now().date() - timedelta(days=7), datetime.now().date()))
        
        col1, col2, col3 = st.columns([2, 1, 1])
        with col1:
            col_radio, col_date1 = st.columns([1, 2])
            with col_radio:
                date_mode = st.radio(
                    "📅 조회 모드", 
                    ["일자별", "기간별"], 
                    index=0 if sidebar_date_mode == "일자별" else 1, 
                    key="report_tab_date_mode",
                    horizontal=True,
                    label_visibility="collapsed"
                )
            with col_date1:
                if date_mode == "일자별":
                    selected_date = st.date_input("조회 일자", value=sidebar_date, key="report_selected_date")
                else:
                    start_date = st.date_input("시작일", value=sidebar_date_range[0], key="report_start_date")
        with col2:
            if date_mode == "기간별":
                end_date = st.date_input("종료일", value=sidebar_date_range[1], key="report_end_date")
            else:
                st.write("")  # 빈 공간
        with col3:
            st.write("")  # 화면 절반을 차지하는 빈 영역
        
        # API 토글 상태에 따라 데이터 가져오기
        if use_real_api:
            try:
                production_kpi = generate_production_kpi()
                quality_data = generate_quality_trend()
                alerts = get_alerts_from_api(use_real_api)
                equipment_data = get_equipment_status_from_api(use_real_api)
            except Exception as e:
                st.error(f"API 데이터 가져오기 오류: {e}")
                production_kpi = generate_production_kpi()
                quality_data = generate_quality_trend()
                alerts = generate_alert_data()
                equipment_data = generate_equipment_status()
        else:
            production_kpi = generate_production_kpi()
            quality_data = generate_quality_trend()
            alerts = generate_alert_data()
            equipment_data = generate_equipment_status()
        
        # 리포트 설정 섹션
        with st.expander("⚙️ 리포트 설정", expanded=True):
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                # 사이드바 날짜 설정을 기반으로 리포트 기간 자동 설정
                sidebar_date_mode = st.session_state.get('sidebar_date_mode', '일자별')
                sidebar_date = st.session_state.get('sidebar_selected_date_stored', datetime.now().date())
                sidebar_date_range = st.session_state.get('sidebar_date_range_stored', (datetime.now().date() - timedelta(days=7), datetime.now().date()))
                
                if sidebar_date_mode == "일자별":
                    report_range = st.selectbox(
                        "📅 기간 선택",
                        ["선택된 일자", "최근 7일", "최근 30일", "최근 90일", "올해", "전체"],
                        help="리포트에 포함할 데이터 기간을 선택하세요 (사이드바 일자와 연동)"
                    )
                else:  # 기간별
                    report_range = st.selectbox(
                        "📅 기간 선택",
                        ["선택된 기간", "최근 7일", "최근 30일", "최근 90일", "올해", "전체"],
                        help="리포트에 포함할 데이터 기간을 선택하세요 (사이드바 기간과 연동)"
                    )
            
            with col2:
                report_type = st.selectbox(
                    "📊 리포트 유형",
                    ["종합 리포트", "생산성 리포트", "품질 리포트", "설비 분석 리포트", "알림 분석 리포트", "비용 분석 리포트"],
                    help="생성할 리포트의 유형을 선택하세요"
                )
            
            with col3:
                report_format = st.selectbox(
                    "📄 출력 형식",
                    ["PDF", "CSV", "텍스트"],
                    help="리포트 출력 형식을 선택하세요"
                )
            
            with col4:
                st.markdown("<br>", unsafe_allow_html=True)
                generate_btn = st.button(
                    "리포트 생성",
                    type="primary",
                    use_container_width=True,
                    help="선택한 설정으로 리포트를 생성하고 다운로드합니다"
                )
        
        # 리포트 생성 및 다운로드
        if generate_btn:
            with st.spinner("리포트를 생성하고 있습니다..."):
                time.sleep(1)  # 시뮬레이션
                
                # 선택된 형식에 따라 직접 다운로드
                if report_format == "CSV":
                    csv_data = generate_csv_report(use_real_api, report_type)
                    st.download_button(
                        label="📄 CSV 다운로드",
                        data=csv_data,
                        file_name=f"POSCO_IoT_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
                elif report_format == "PDF":
                    pdf_buffer = generate_pdf_report(use_real_api, report_type)
                    st.download_button(
                        label="📄 PDF 다운로드",
                        data=pdf_buffer.getvalue(),
                        file_name=f"POSCO_IoT_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                else:  # 텍스트
                    report_content = generate_comprehensive_report(use_real_api, report_type, report_range)
                    st.download_button(
                        label="📄 텍스트 다운로드",
                        data=report_content,
                        file_name=f"POSCO_IoT_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.txt",
                        mime="text/plain",
                        use_container_width=True
                    )
                
                st.success("✅ 리포트가 성공적으로 생성되었습니다! 위의 다운로드 버튼을 클릭하여 파일을 저장하세요.")
                
                # 생성된 리포트 정보 표시
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("📊 리포트 유형", report_type)
                with col2:
                    st.metric("📅 기간", report_range)
                with col3:
                    st.metric("📄 형식", report_format)
                
                # 추가 다운로드 옵션
                st.markdown("### 💾 추가 다운로드 옵션")
                download_col1, download_col2, download_col3 = st.columns(3)
                
                with download_col1:
                    # 다른 형식으로 다운로드
                    if report_format != "CSV":
                        csv_data = generate_csv_report(use_real_api, report_type)
                        st.download_button(
                            label="📊 CSV 형식",
                            data=csv_data,
                            file_name=f"POSCO_IoT_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                            mime="text/csv",
                            use_container_width=True
                        )
                
                with download_col2:
                    if report_format != "PDF":
                        pdf_buffer = generate_pdf_report(use_real_api, report_type)
                        st.download_button(
                            label="📋 PDF 형식",
                            data=pdf_buffer.getvalue(),
                            file_name=f"POSCO_IoT_Report_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                
                with download_col3:
                    # 알림 데이터만 별도 다운로드
                    alerts_csv = download_alerts_csv()
                    st.download_button(
                        label="🚨 알림 데이터",
                        data=alerts_csv,
                        file_name=f"POSCO_Alerts_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv",
                        use_container_width=True
                    )
        
        # KPI 대시보드
        st.markdown("### 📊 실시간 KPI 대시보드")
        
        # KPI 카드 행 1
        kpi_row1 = st.columns(4, gap="small")
        
        with kpi_row1[0]:
            oee_trend = "↗️" if production_kpi['oee'] > 85 else "↘️" if production_kpi['oee'] < 75 else "➡️"
            st.markdown(f"""
            <div class="kpi-card success no-translate" translate="no" style="padding:1rem; min-height:100px; border-radius:12px; box-shadow:0 4px 6px rgba(0,0,0,0.1);">
                <div class="kpi-label" style="font-size:0.9rem; color:#64748b; margin-bottom:0.5rem;">🏭 OEE (설비종합효율)</div>
                <div class="kpi-value" style="font-size:2rem; font-weight:bold; color:#059669;">{production_kpi['oee']:.1f}%</div>
                <div style="font-size:0.8rem; color:#64748b; margin-top:0.5rem;">{oee_trend} {production_kpi['oee']:.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
        
        with kpi_row1[1]:
            avail_trend = "↗️" if production_kpi['availability'] > 90 else "↘️" if production_kpi['availability'] < 80 else "➡️"
            st.markdown(f"""
            <div class="kpi-card success no-translate" translate="no" style="padding:1rem; min-height:100px; border-radius:12px; box-shadow:0 4px 6px rgba(0,0,0,0.1);">
                <div class="kpi-label" style="font-size:0.9rem; color:#64748b; margin-bottom:0.5rem;">⚡ 가동률</div>
                <div class="kpi-value" style="font-size:2rem; font-weight:bold; color:#059669;">{production_kpi['availability']:.1f}%</div>
                <div style="font-size:0.8rem; color:#64748b; margin-top:0.5rem;">{avail_trend} {production_kpi['availability']:.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
        
        with kpi_row1[2]:
            # PPM 300 기준 품질률 (99.97%)
            quality_rate_300 = 99.97
            quality_trend = "↗️" if quality_rate_300 > 95 else "↘️" if quality_rate_300 < 90 else "➡️"
            st.markdown(f"""
            <div class="kpi-card success no-translate" translate="no" style="padding:1rem; min-height:100px; border-radius:12px; box-shadow:0 4px 6px rgba(0,0,0,0.1);">
                <div class="kpi-label" style="font-size:0.9rem; color:#64748b; margin-bottom:0.5rem;">🎯 품질률 (PPM 300 기준)</div>
                <div class="kpi-value" style="font-size:2rem; font-weight:bold; color:#059669;">{quality_rate_300:.2f}%</div>
                <div style="font-size:0.8rem; color:#64748b; margin-top:0.5rem;">{quality_trend} {quality_rate_300:.2f}%</div>
            </div>
            """, unsafe_allow_html=True)
        
        with kpi_row1[3]:
            # PPM 300 기준 불량률 (0.03%)
            defect_rate_300 = 0.03
            defect_trend = "↘️" if defect_rate_300 < 5 else "↗️" if defect_rate_300 > 10 else "➡️"
            st.markdown(f"""
            <div class="kpi-card warning no-translate" translate="no" style="padding:1rem; min-height:100px; border-radius:12px; box-shadow:0 4px 6px rgba(0,0,0,0.1);">
                <div class="kpi-label" style="font-size:0.9rem; color:#64748b; margin-bottom:0.5rem;">⚠️ 불량률 (PPM 300 기준)</div>
                <div class="kpi-value" style="font-size:2rem; font-weight:bold; color:#f59e0b;">{defect_rate_300:.2f}%</div>
                <div style="font-size:0.8rem; color:#64748b; margin-top:0.5rem;">{defect_trend} {defect_rate_300:.2f}%</div>
            </div>
            """, unsafe_allow_html=True)
        
        # KPI 카드 행 2 (추가 지표)
        kpi_row2 = st.columns(4, gap="small")
        
        with kpi_row2[0]:
            # PPM 300 고정
            ppm_value = 300
            st.markdown(f"""
            <div class="kpi-card info no-translate" translate="no" style="padding:1rem; min-height:100px; border-radius:12px; box-shadow:0 4px 6px rgba(0,0,0,0.1);">
                <div class="kpi-label" style="font-size:0.9rem; color:#64748b; margin-bottom:0.5rem;">📊 PPM (목표)</div>
                <div class="kpi-value" style="font-size:2rem; font-weight:bold; color:#3b82f6;">{ppm_value}</div>
                <div style="font-size:0.8rem; color:#64748b; margin-top:0.5rem;">불량 개수/백만 개</div>
            </div>
            """, unsafe_allow_html=True)
        
        with kpi_row2[1]:
            # 생산량
            avg_production = quality_data['production_volume'].mean()
            st.markdown(f"""
            <div class="kpi-card info no-translate" translate="no" style="padding:1rem; min-height:100px; border-radius:12px; box-shadow:0 4px 6px rgba(0,0,0,0.1);">
                <div class="kpi-label" style="font-size:0.9rem; color:#64748b; margin-bottom:0.5rem;">📈 일평균 생산량</div>
                <div class="kpi-value" style="font-size:2rem; font-weight:bold; color:#3b82f6;">{avg_production:.0f}</div>
                <div style="font-size:0.8rem; color:#64748b; margin-top:0.5rem;">개/일</div>
            </div>
            """, unsafe_allow_html=True)
        
        with kpi_row2[2]:
            # 알림 건수
            alert_count = len(alerts)
            st.markdown(f"""
            <div class="kpi-card warning no-translate" translate="no" style="padding:1rem; min-height:100px; border-radius:12px; box-shadow:0 4px 6px rgba(0,0,0,0.1);">
                <div class="kpi-label" style="font-size:0.9rem; color:#64748b; margin-bottom:0.5rem;">🚨 총 알림</div>
                <div class="kpi-value" style="font-size:2rem; font-weight:bold; color:#f59e0b;">{alert_count}</div>
                <div style="font-size:0.8rem; color:#64748b; margin-top:0.5rem;">건</div>
            </div>
            """, unsafe_allow_html=True)
        
        with kpi_row2[3]:
            # 설비 상태
            equipment_df = pd.DataFrame(equipment_data)
            normal_equipment = len(equipment_df[equipment_df['status'] == '정상'])
            total_equipment = len(equipment_df)
            st.markdown(f"""
            <div class="kpi-card success no-translate" translate="no" style="padding:1rem; min-height:100px; border-radius:12px; box-shadow:0 4px 6px rgba(0,0,0,0.1);">
                <div class="kpi-label" style="font-size:0.9rem; color:#64748b; margin-bottom:0.5rem;">🔧 정상 설비</div>
                <div class="kpi-value" style="font-size:2rem; font-weight:bold; color:#059669;">{normal_equipment}/{total_equipment}</div>
                <div style="font-size:0.8rem; color:#64748b; margin-top:0.5rem;">{normal_equipment/total_equipment*100:.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
        
        # 상세 분석 탭
        st.markdown("### 📈 상세 분석")
        report_tab1, report_tab2, report_tab3, report_tab4, report_tab5 = st.tabs([
            "🏭 생산성 분석", 
            "🎯 품질 분석", 
            "🔧 설비 분석", 
            "🚨 알림 분석",
            "💰 비용 분석"
        ])
        
        with report_tab1:
            st.markdown("### 🏭 생산성 분석")
            
            # 생산성 개요
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**📊 생산성 개요**")
                st.metric(
                    "일평균 생산량", 
                    f"{quality_data['production_volume'].mean():.0f}개",
                    f"{quality_data['production_volume'].std():.0f}개"
                )
                st.metric(
                    "생산량 변동계수", 
                    f"{quality_data['production_volume'].std() / quality_data['production_volume'].mean():.2f}"
                )
            
            with col2:
                st.markdown("**📈 생산량 범위**")
                st.metric(
                    "최대 생산량", 
                    f"{quality_data['production_volume'].max():.0f}개"
                )
                st.metric(
                    "최소 생산량", 
                    f"{quality_data['production_volume'].min():.0f}개"
                )
            
            with col3:
                st.markdown("**🎯 목표 대비**")
                target_production = 1000  # 기본 목표 생산량
                current_avg = quality_data['production_volume'].mean()
                achievement_rate = (current_avg / target_production) * 100
                st.metric(
                    "목표 달성률", 
                    f"{achievement_rate:.1f}%",
                    f"{achievement_rate - 100:.1f}%" if achievement_rate != 100 else "0%"
                )
            
            # 생산량 트렌드 차트
            st.markdown("**📈 생산량 트렌드 분석**")
            
            # 기간 설정 및 목표 생산량 설정 (사이드바와 연동)
            col1, col2, col3 = st.columns(3)
            with col1:
                # 사이드바 날짜 범위에서 시작일 가져오기
                sidebar_start = st.session_state.get('sidebar_date_range_stored', (datetime.now().date() - timedelta(days=7), datetime.now().date()))[0]
                trend_start_date = st.date_input("분석 시작일", value=sidebar_start, key="trend_start_date")
            with col2:
                # 사이드바 날짜 범위에서 종료일 가져오기
                sidebar_end = st.session_state.get('sidebar_date_range_stored', (datetime.now().date() - timedelta(days=7), datetime.now().date()))[1]
                trend_end_date = st.date_input("분석 종료일", value=sidebar_end, key="trend_end_date")
            with col3:
                custom_target = st.number_input("목표 생산량 (개/일)", min_value=100, max_value=10000, value=1300, step=50, key="custom_target_production")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                fig = go.Figure()
                
                # 생산량 바 차트
                fig.add_trace(go.Bar(
                    x=quality_data['day'],
                    y=quality_data['production_volume'],
                    name='실제 생산량',
                    marker_color='#3b82f6',
                    opacity=0.8
                ))
                
                # 목표선 추가
                target_for_hline = custom_target if 'custom_target' in locals() else 1300
                fig.add_hline(
                    y=target_for_hline, 
                    line_dash="dash", 
                    line_color="red",
                    annotation_text="목표 생산량",
                    annotation_position="top right"
                )
                
                # 평균선 추가
                fig.add_hline(
                    y=quality_data['production_volume'].mean(), 
                    line_dash="dot", 
                    line_color="green",
                    annotation_text="평균 생산량",
                    annotation_position="bottom right"
                )
                
                fig.update_layout(
                    title="일별 생산량 트렌드",
                    xaxis_title="요일",
                    yaxis_title="생산량 (개)",
                    height=400,
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.markdown("**📊 생산성 분석**")
                
                # 생산성 vs 품질률 산점도
                fig_scatter = go.Figure()
                fig_scatter.add_trace(go.Scatter(
                    x=quality_data['production_volume'],
                    y=quality_data['quality_rate'],
                    mode='markers',
                    marker=dict(
                        size=12,
                        color=quality_data['defect_rate'],
                        colorscale='RdYlGn_r',
                        showscale=True,
                        colorbar=dict(title="불량률 (%)")
                    ),
                    text=quality_data['day'],
                    hovertemplate='<b>%{text}</b><br>' +
                                '생산량: %{x}개<br>' +
                                '품질률: %{y:.2f}%<br>' +
                                '불량률: %{marker.color:.3f}%<extra></extra>'
                ))
                
                # 목표 생산량 수직선
                target_for_vline = custom_target if 'custom_target' in locals() else 1300
                fig_scatter.add_vline(
                    x=target_for_vline, 
                    line_dash="dash", 
                    line_color="red",
                    annotation_text="목표 생산량",
                    annotation_position="top right"
                )
                
                # 목표 품질률 수평선
                fig_scatter.add_hline(
                    y=QUALITY_TARGET, 
                    line_dash="dash", 
                    line_color="orange",
                    annotation_text=f"목표 품질률 ({QUALITY_TARGET:.1f}%)",
                    annotation_position="bottom right"
                )
                
                fig_scatter.update_layout(
                    title="생산량 vs 품질률 분석",
                    xaxis_title="생산량 (개)",
                    yaxis_title="품질률 (%)",
                    height=300,
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    showlegend=False
                )
                st.plotly_chart(fig_scatter, use_container_width=True)
            
            # 생산성 지표를 트렌드 차트 아래에 가로로 배치
            st.markdown("**📈 생산성 지표**")
            avg_production = quality_data['production_volume'].mean()
            avg_quality = quality_data['quality_rate'].mean()
            # custom_target이 정의된 경우에만 사용, 아니면 기본값 1300 사용
            target_for_calc = custom_target if 'custom_target' in locals() else 1300
            productivity_score = (avg_production / target_for_calc) * (avg_quality / 100) * 100
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("평균 생산량", f"{avg_production:.0f}개")
            with col2:
                st.metric("평균 품질률", f"{avg_quality:.1f}%")
            with col3:
                st.metric("목표 대비", f"{(avg_production/target_for_calc)*100:.1f}%")
            with col4:
                st.metric("생산성 점수", f"{productivity_score:.1f}점")
            
            # 생산성 상세 데이터 테이블
            st.markdown("**📋 생산성 상세 데이터**")
            
            # 데이터프레임 생성 및 스타일링
            detail_df = quality_data[['day', 'production_volume', 'defect_rate', 'PPM', 'quality_rate']].copy()
            detail_df['생산성 지수'] = detail_df['production_volume'] * (detail_df['quality_rate'] / 100)
            detail_df = detail_df.rename(columns={
                'day': '요일', 
                'production_volume': '생산량', 
                'defect_rate': '불량률(%)', 
                'PPM': 'PPM', 
                'quality_rate': '품질률(%)',
                '생산성 지수': '생산성 지수'
            })
            
            # 생산성 지수에 따른 색상 조건부 스타일링
            def color_production_index(val):
                if val > detail_df['생산성 지수'].mean() * 1.1:
                    return 'background-color: #d1fae5'  # 연한 초록
                elif val < detail_df['생산성 지수'].mean() * 0.9:
                    return 'background-color: #fee2e2'  # 연한 빨강
                else:
                    return 'background-color: #fef3c7'  # 연한 노랑
            
            styled_df = detail_df.style.map(color_production_index, subset=['생산성 지수'])
            st.dataframe(styled_df, use_container_width=True, height=300)
            
            # 생산성 개선 제안
            st.markdown("**💡 생산성 개선 제안**")
            if achievement_rate < 90:
                st.warning("⚠️ 목표 달성률이 90% 미만입니다. 생산성 향상을 위한 조치가 필요합니다.")
                st.info("🔧 제안사항: 설비 가동 시간 최적화, 작업자 교육 강화, 공정 개선 검토")
            elif achievement_rate < 95:
                st.info("ℹ️ 목표 달성률이 90-95% 범위에 있습니다. 지속적인 모니터링이 필요합니다.")
            else:
                st.success("✅ 목표 달성률이 95% 이상으로 우수한 성과를 보이고 있습니다.")
        
        with report_tab2:
            st.markdown("### 🎯 품질 분석")
            
            # 품질 개요
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**📊 품질 개요**")
                st.metric(
                    "평균 품질률", 
                    f"{quality_data['quality_rate'].mean():.1f}%",
                    f"{quality_data['quality_rate'].std():.1f}%"
                )
                st.metric(
                    "평균 불량률", 
                    f"{quality_data['defect_rate'].mean():.2f}%"
                )
            
            with col2:
                st.markdown("**📈 품질 범위**")
                st.metric(
                    "최고 품질률", 
                    f"{quality_data['quality_rate'].max():.1f}%"
                )
                st.metric(
                    "최저 품질률", 
                    f"{quality_data['quality_rate'].min():.1f}%"
                )
            
            with col3:
                st.markdown("**🎯 품질 개선**")
                quality_improvement = quality_data['quality_rate'].iloc[-1] - quality_data['quality_rate'].iloc[0]
                st.metric(
                    "품질 개선률", 
                    f"{quality_improvement:.2f}%",
                    f"{quality_improvement:.2f}%" if quality_improvement != 0 else "0%"
                )
            
            # PPM 분석 섹션 추가
            st.markdown("### 📊 PPM (Parts Per Million) 분석")
            
            # PPM 개요
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                avg_ppm = quality_data['PPM'].mean()
                st.metric(
                    "평균 PPM", 
                    f"{avg_ppm:.0f}",
                    f"{quality_data['PPM'].std():.0f}"
                )
            
            with col2:
                min_ppm = quality_data['PPM'].min()
                st.metric(
                    "최저 PPM", 
                    f"{min_ppm:.0f}"
                )
            
            with col3:
                max_ppm = quality_data['PPM'].max()
                st.metric(
                    "최고 PPM", 
                    f"{max_ppm:.0f}"
                )
            
            with col4:
                # PPM 목표 (일반적으로 1000 PPM 이하가 우수)
                target_ppm = 1000
                ppm_achievement = (target_ppm - avg_ppm) / target_ppm * 100
                st.metric(
                    "목표 달성률", 
                    f"{ppm_achievement:.1f}%",
                    f"{target_ppm - avg_ppm:.0f} PPM"
                )
            
            # PPM 트렌드 차트
            st.markdown("**📈 PPM 트렌드 분석**")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                fig_ppm = go.Figure()
                
                # PPM 라인 차트
                fig_ppm.add_trace(go.Scatter(
                    x=quality_data['day'],
                    y=quality_data['PPM'],
                    mode='lines+markers',
                    name='실제 PPM',
                    line=dict(color='#ef4444', width=3),
                    marker=dict(size=8)
                ))
                
                # 목표 PPM 수평선
                fig_ppm.add_hline(
                    y=target_ppm, 
                    line_dash="dash", 
                    line_color="red",
                    annotation_text="목표 PPM (300)",
                    annotation_position="top right"
                )
                
                # 우수 PPM 수평선 (500 PPM)
                fig_ppm.add_hline(
                    y=500, 
                    line_dash="dash", 
                    line_color="green",
                    annotation_text="우수 PPM (500)",
                    annotation_position="bottom right"
                )
                
                fig_ppm.update_layout(
                    title="PPM 트렌드 분석",
                    xaxis_title="요일",
                    yaxis_title="PPM",
                    height=400,
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    showlegend=True
                )
                st.plotly_chart(fig_ppm, use_container_width=True)
            
            with col2:
                # PPM 분포 히스토그램
                fig_ppm_hist = go.Figure()
                
                fig_ppm_hist.add_trace(go.Histogram(
                    x=quality_data['PPM'],
                    nbinsx=10,
                    name='PPM 분포',
                    marker_color='#3b82f6',
                    opacity=0.7
                ))
                
                fig_ppm_hist.update_layout(
                    title="PPM 분포",
                    xaxis_title="PPM",
                    yaxis_title="빈도",
                    height=400,
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    showlegend=False
                )
                st.plotly_chart(fig_ppm_hist, use_container_width=True)
            
            # PPM vs 품질률 상관관계 분석
            st.markdown("**📊 PPM vs 품질률 상관관계**")
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                fig_ppm_corr = go.Figure()
                
                fig_ppm_corr.add_trace(go.Scatter(
                    x=quality_data['PPM'],
                    y=quality_data['quality_rate'],
                    mode='markers',
                    name='PPM vs 품질률',
                    marker=dict(
                        size=10,
                        color=quality_data['PPM'],
                        colorscale='RdYlGn_r',
                        showscale=True,
                        colorbar=dict(title="PPM")
                    )
                ))
                
                # 상관계수 계산
                correlation = quality_data['PPM'].corr(quality_data['quality_rate'])
                
                fig_ppm_corr.update_layout(
                    title=f"PPM vs 품질률 상관관계 (r = {correlation:.3f})",
                    xaxis_title="PPM",
                    yaxis_title="품질률 (%)",
                    height=400,
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    showlegend=False
                )
                st.plotly_chart(fig_ppm_corr, use_container_width=True)
            
            with col2:
                # PPM 등급별 분류 (300 기준)
                st.markdown("**📊 PPM 등급별 분류 (300 기준)**")
                
                ppm_grades = []
                for ppm in quality_data['PPM']:
                    if ppm <= 300:
                        ppm_grades.append("우수")
                    elif ppm <= 500:
                        ppm_grades.append("양호")
                    elif ppm <= 1000:
                        ppm_grades.append("보통")
                    else:
                        ppm_grades.append("불량")
                
                grade_counts = pd.Series(ppm_grades).value_counts()
                
                fig_ppm_grade = go.Figure(data=[go.Pie(
                    labels=grade_counts.index,
                    values=grade_counts.values,
                    hole=0.4
                )])
                
                fig_ppm_grade.update_layout(
                    title="PPM 등급별 분포",
                    height=400,
                    plot_bgcolor='white',
                    paper_bgcolor='white'
                )
                st.plotly_chart(fig_ppm_grade, use_container_width=True)
            
            # PPM 개선 제안 (300 기준)
            st.markdown("**💡 PPM 개선 제안 (300 기준)**")
            
            if avg_ppm <= 300:
                st.success("✅ PPM이 300 이하로 우수한 수준입니다. 지속적인 모니터링을 유지하세요.")
            elif avg_ppm <= 500:
                st.info("ℹ️ PPM이 300-500 범위에 있습니다. 추가 개선을 통해 우수 수준으로 향상시킬 수 있습니다.")
                st.info("🔧 제안사항: 공정 최적화, 품질 관리 강화, 설비 점검 주기 단축")
            elif avg_ppm <= 1000:
                st.warning("⚠️ PPM이 500-1000 범위에 있습니다. 품질 개선이 필요합니다.")
                st.info("🔧 제안사항: 공정 분석 및 개선, 품질 관리 시스템 강화, 작업자 교육")
            else:
                st.error("❌ PPM이 1000을 초과합니다. 즉각적인 품질 개선 조치가 필요합니다.")
                st.info("🔧 긴급 제안사항: 공정 전면 검토, 품질 관리 시스템 재구축, 설비 대체 검토")
            
            # 품질 트렌드 분석
            st.markdown("**📈 품질 트렌드 분석**")
            col1, col2 = st.columns([2, 1])
            
            with col1:
                # PPM/불량률 이중축 그래프
                fig = go.Figure()
                
                # PPM 바 차트
                fig.add_trace(go.Bar(
                    x=quality_data['day'], 
                    y=quality_data['PPM'], 
                    name='PPM', 
                    marker_color='#3b82f6',
                    opacity=0.7
                ))
                
                # 불량률 선 그래프 (이중축)
                fig.add_trace(go.Scatter(
                    x=quality_data['day'], 
                    y=quality_data['defect_rate'], 
                    name='불량률(%)', 
                    yaxis='y2', 
                    mode='lines+markers', 
                    line=dict(color='#ef4444', width=3),
                    marker=dict(size=8)
                ))
                
                # 품질률 선 그래프 (이중축)
                fig.add_trace(go.Scatter(
                    x=quality_data['day'], 
                    y=quality_data['quality_rate'], 
                    name='품질률(%)', 
                    yaxis='y2', 
                    mode='lines+markers', 
                    line=dict(color='#10b981', width=3),
                    marker=dict(size=8)
                ))
                
                # 목표선 추가 (불량률 2% 기준선)
                fig.add_hline(
                    y=2.0, 
                    line_dash="dash", 
                    line_color="red",
                    annotation_text="불량률 목표 (2%)",
                    annotation_position="top right"
                )
                
                fig.update_layout(
                    title="품질 지표 트렌드",
                    xaxis_title="요일",
                                    yaxis=dict(title='PPM', side='left'),
                yaxis2=dict(title='비율 (%)', overlaying='y', side='right'),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    height=400,
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    showlegend=True
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.markdown("**📊 품질 통계**")
                
                # 품질률 분포 히스토그램
                fig_hist = go.Figure()
                fig_hist.add_trace(go.Histogram(
                    x=quality_data['quality_rate'],
                    nbinsx=8,
                    marker_color='#10b981',
                    opacity=0.7
                ))
                fig_hist.update_layout(
                    title="품질률 분포",
                    xaxis_title="품질률 (%)",
                    yaxis_title="빈도",
                    height=300,
                    plot_bgcolor='white',
                    paper_bgcolor='white'
                )
                st.plotly_chart(fig_hist, use_container_width=True)
            
            # 품질 지표 상세
            st.markdown("**📋 품질 지표 상세**")
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("평균 PPM", f"{quality_data['PPM'].mean():.1f}")
            with col2:
                st.metric("PPM 표준편차", f"{quality_data['PPM'].std():.1f}")
            with col3:
                st.metric("품질률 표준편차", f"{quality_data['quality_rate'].std():.2f}%")
            with col4:
                st.metric("불량률 표준편차", f"{quality_data['defect_rate'].std():.2f}%")
            
            # 품질 상세 데이터 테이블
            st.markdown("**📊 품질 상세 데이터**")
            
            quality_detail_df = quality_data[['day', 'quality_rate', 'defect_rate', 'PPM']].copy()
            quality_detail_df['품질 등급'] = quality_detail_df['quality_rate'].apply(
                lambda x: 'A등급' if x >= 98 else 'B등급' if x >= 95 else 'C등급' if x >= 90 else 'D등급'
            )
            quality_detail_df = quality_detail_df.rename(columns={
                'day': '요일', 
                'quality_rate': '품질률(%)', 
                'defect_rate': '불량률(%)', 
                'PPM': 'PPM'
            })
            
            # 품질 등급에 따른 색상 조건부 스타일링
            def color_quality_grade(val):
                if val == 'A등급':
                    return 'background-color: #d1fae5; color: #065f46'  # 초록
                elif val == 'B등급':
                    return 'background-color: #fef3c7; color: #92400e'  # 노랑
                elif val == 'C등급':
                    return 'background-color: #fed7aa; color: #c2410c'  # 주황
                else:
                    return 'background-color: #fee2e2; color: #991b1b'  # 빨강
            
            styled_quality_df = quality_detail_df.style.map(color_quality_grade, subset=['품질 등급'])
            st.dataframe(styled_quality_df, use_container_width=True, height=300)
            
            # 품질 개선 제안
            st.markdown("**💡 품질 개선 제안**")
            avg_defect_rate = quality_data['defect_rate'].mean()
            
            if avg_defect_rate > 2.0:
                st.error("🚨 평균 불량률이 2%를 초과하고 있습니다. 즉시 품질 관리 강화가 필요합니다.")
                st.info("🔧 긴급 제안사항: 공정 검토, 원자재 품질 확인, 작업자 교육 강화, 검사 기준 강화")
            elif avg_defect_rate > 1.0:
                st.warning("⚠️ 불량률이 1-2% 범위에 있습니다. 품질 관리 개선이 필요합니다.")
                st.info("🔧 제안사항: 공정 최적화, 품질 관리 프로세스 검토, 예방 정비 강화")
            elif avg_defect_rate > 0.5:
                st.info("ℹ️ 불량률이 0.5-1% 범위에 있습니다. 지속적인 모니터링이 필요합니다.")
                st.success("✅ 현재 품질 관리가 양호합니다. 지속적인 개선을 유지하세요.")
            else:
                st.success("✅ 불량률이 0.5% 미만으로 우수한 품질을 유지하고 있습니다.")
                st.info("🏆 목표: 이 수준을 유지하고 더욱 개선하기 위한 혁신적 접근을 고려하세요.")
        
        with report_tab3:
            st.markdown("### 🔧 설비 분석")
            
            # 설비 데이터 준비
            equipment_df = pd.DataFrame(equipment_data)
            
            # 설비 개요
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**📊 설비 개요**")
                st.metric(
                    "전체 설비 수", 
                    len(equipment_df)
                )
                st.metric(
                    "평균 효율", 
                    f"{equipment_df['efficiency'].mean():.1f}%"
                )
            
            with col2:
                st.markdown("**🔧 설비 상태**")
                normal_count = len(equipment_df[equipment_df['status'] == '정상'])
                warning_count = len(equipment_df[equipment_df['status'] == '주의'])
                error_count = len(equipment_df[equipment_df['status'] == '오류'])
                
                st.metric(
                    "정상 설비", 
                    f"{normal_count}개",
                    f"{normal_count/len(equipment_df)*100:.1f}%"
                )
                st.metric(
                    "주의/오류 설비", 
                    f"{warning_count + error_count}개"
                )
            
            with col3:
                st.markdown("**📈 효율성 분석**")
                st.metric(
                    "최고 효율", 
                    f"{equipment_df['efficiency'].max():.1f}%"
                )
                st.metric(
                    "최저 효율", 
                    f"{equipment_df['efficiency'].min():.1f}%"
                )
            
            # 설비 분석 차트
            st.markdown("**📈 설비 분석 차트**")
            col1, col2 = st.columns([1, 1])
            
            with col1:
                # 설비 상태 분포 파이 차트
                status_counts = equipment_df['status'].value_counts()
                colors = ['#10b981', '#f59e0b', '#ef4444']  # 정상, 주의, 오류
                
                fig_pie = go.Figure(data=[go.Pie(
                    labels=status_counts.index, 
                    values=status_counts.values,
                    hole=0.4,
                    marker_colors=colors[:len(status_counts)]
                )])
                fig_pie.update_layout(
                    title="설비 상태 분포",
                    height=400,
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    showlegend=True
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col2:
                # 설비 타입별 평균 효율 바 차트
                type_efficiency = equipment_df.groupby('type')['efficiency'].mean().sort_values(ascending=True)
                
                fig_bar = go.Figure(data=[go.Bar(
                    x=type_efficiency.values,
                    y=type_efficiency.index,
                    orientation='h',
                    marker_color='#3b82f6',
                    opacity=0.8
                )])
                fig_bar.update_layout(
                    title="설비 타입별 평균 효율",
                    xaxis_title="평균 효율 (%)",
                    yaxis_title="설비 타입",
                    height=400,
                    plot_bgcolor='white',
                    paper_bgcolor='white'
                )
                st.plotly_chart(fig_bar, use_container_width=True)
            
            # 설비 효율성 분석
            st.markdown("**📊 설비 효율성 분석**")
            col1, col2 = st.columns([1, 1])
            
            with col1:
                # 효율 분포 히스토그램
                fig_hist = go.Figure()
                fig_hist.add_trace(go.Histogram(
                    x=equipment_df['efficiency'],
                    nbinsx=10,
                    marker_color='#3b82f6',
                    opacity=0.7
                ))
                fig_hist.update_layout(
                    title="설비 효율 분포",
                    xaxis_title="효율 (%)",
                    yaxis_title="설비 수",
                    height=300,
                    plot_bgcolor='white',
                    paper_bgcolor='white'
                )
                st.plotly_chart(fig_hist, use_container_width=True)
            
            with col2:
                # 설비별 효율 순위
                efficiency_ranking = equipment_df[['name', 'efficiency', 'status']].sort_values('efficiency', ascending=False)
                efficiency_ranking['순위'] = range(1, len(efficiency_ranking) + 1)
                efficiency_ranking = efficiency_ranking[['순위', 'name', 'efficiency', 'status']].head(10)
                
                st.markdown("**🏆 효율성 상위 10개 설비**")
                st.dataframe(efficiency_ranking, use_container_width=True, height=300)
            
            # 설비 상세 성능 테이블
            st.markdown("**📋 설비 상세 성능**")
            
            # 마지막 정비일을 datetime으로 변환
            equipment_df['last_maintenance'] = pd.to_datetime(equipment_df['last_maintenance'])
            equipment_df['days_since_maintenance'] = (datetime.now() - equipment_df['last_maintenance']).dt.days
            
            # 성능 등급 추가
            equipment_df['성능 등급'] = equipment_df['efficiency'].apply(
                lambda x: 'A등급' if x >= 95 else 'B등급' if x >= 85 else 'C등급' if x >= 75 else 'D등급'
            )
            
            # 정비 필요성 평가
            equipment_df['정비 필요성'] = equipment_df['days_since_maintenance'].apply(
                lambda x: '긴급' if x > 30 else '주의' if x > 20 else '정상'
            )
            
            display_df = equipment_df[['name', 'type', 'status', 'efficiency', '성능 등급', 'days_since_maintenance', '정비 필요성']].copy()
            display_df = display_df.rename(columns={
                'name': '설비명',
                'type': '타입',
                'status': '상태',
                'efficiency': '효율(%)',
                'days_since_maintenance': '정비 후 경과일'
            })
            
            # 조건부 스타일링
            def color_performance_grade(val):
                if val == 'A등급':
                    return 'background-color: #d1fae5; color: #065f46'
                elif val == 'B등급':
                    return 'background-color: #fef3c7; color: #92400e'
                elif val == 'C등급':
                    return 'background-color: #fed7aa; color: #c2410c'
                else:
                    return 'background-color: #fee2e2; color: #991b1b'
            
            def color_maintenance_need(val):
                if val == '긴급':
                    return 'background-color: #fee2e2; color: #991b1b'
                elif val == '주의':
                    return 'background-color: #fef3c7; color: #92400e'
                else:
                    return 'background-color: #d1fae5; color: #065f46'
            
            styled_equipment_df = display_df.style.map(color_performance_grade, subset=['성능 등급']).map(color_maintenance_need, subset=['정비 필요성'])
            st.dataframe(styled_equipment_df, use_container_width=True, height=400)
            
            # 설비 관리 제안
            st.markdown("**💡 설비 관리 제안**")
            
            low_efficiency_count = len(equipment_df[equipment_df['efficiency'] < 80])
            urgent_maintenance_count = len(equipment_df[equipment_df['days_since_maintenance'] > 30])
            
            if low_efficiency_count > 0 or urgent_maintenance_count > 0:
                if urgent_maintenance_count > 0:
                    st.error(f"🚨 {urgent_maintenance_count}개 설비의 긴급 정비가 필요합니다.")
                if low_efficiency_count > 0:
                    st.warning(f"⚠️ {low_efficiency_count}개 설비의 효율이 80% 미만입니다.")
                st.info("🔧 제안사항: 정비 일정 조정, 설비 점검 강화, 효율 개선 프로젝트 검토")
            else:
                st.success("✅ 설비 관리가 양호한 상태입니다. 지속적인 모니터링을 유지하세요.")
        
        with report_tab4:
            st.markdown("### 🚨 알림 분석")
            
            # 알림 데이터 준비
            alert_df = pd.DataFrame(alerts)
            
            # 알림 개요
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**📊 알림 개요**")
                st.metric(
                    "전체 알림", 
                    len(alert_df)
                )
                if len(alert_df) > 0:
                    st.metric(
                        "일평균 알림", 
                        f"{len(alert_df) / 7:.1f}건"
                    )
            
            with col2:
                st.markdown("**🚨 심각도별 분포**")
                error_count = len(alert_df[alert_df['severity'] == 'error'])
                warning_count = len(alert_df[alert_df['severity'] == 'warning'])
                info_count = len(alert_df[alert_df['severity'] == 'info'])
                
                st.metric(
                    "긴급 알림", 
                    f"{error_count}건",
                    f"{error_count/len(alert_df)*100:.1f}%" if len(alert_df) > 0 else "0%"
                )
                st.metric(
                    "주의 알림", 
                    f"{warning_count}건"
                )
            
            with col3:
                st.markdown("**📈 알림 트렌드**")
                if len(alert_df) > 0:
                    st.metric(
                        "정보 알림", 
                        f"{info_count}건"
                    )
                    st.metric(
                        "알림 해결률", 
                        "85.2%"  # 더미 데이터
                    )
            
            # 알림 분석 차트
            st.markdown("**📈 알림 분석 차트**")
            col1, col2 = st.columns([1, 1])
            
            with col1:
                # 심각도별 알림 분포 파이 차트
                if len(alert_df) > 0:
                    severity_counts = alert_df['severity'].value_counts()
                    colors = ['#ef4444', '#f59e0b', '#3b82f6']  # error, warning, info
                    
                    fig_pie = go.Figure(data=[go.Pie(
                        labels=severity_counts.index, 
                        values=severity_counts.values,
                        hole=0.4,
                        marker_colors=colors[:len(severity_counts)]
                    )])
                    fig_pie.update_layout(
                        title="심각도별 알림 분포",
                        height=400,
                        plot_bgcolor='white',
                        paper_bgcolor='white',
                        showlegend=True
                    )
                    st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    st.info("📊 알림 데이터가 없습니다.")
            
            with col2:
                # 설비별 알림 건수 바 차트
                if len(alert_df) > 0:
                    equipment_counts = alert_df['equipment'].value_counts().head(8)
                    
                    # 설비별 알림 건수와 설비 상태 정보 결합
                    equipment_df = pd.DataFrame(equipment_data)
                    equipment_status_dict = dict(zip(equipment_df['name'], equipment_df['status']))
                    
                    # 설비별 알림 건수에 상태 정보 추가
                    equipment_data_for_chart = []
                    for equipment, count in equipment_counts.items():
                        status = equipment_status_dict.get(equipment, '알 수 없음')
                        equipment_data_for_chart.append({
                            'equipment': equipment,
                            'count': count,
                            'status': status
                        })
                    
                    # 상태별 색상 매핑
                    color_map = {
                        '정상': '#10b981',
                        '점검중': '#f59e0b',
                        '고장': '#ef4444',
                        '알 수 없음': '#6b7280'
                    }
                    
                    colors = [color_map.get(data['status'], '#6b7280') for data in equipment_data_for_chart]
                    
                    fig_bar = go.Figure(data=[go.Bar(
                        x=[data['count'] for data in equipment_data_for_chart],
                        y=[data['equipment'] for data in equipment_data_for_chart],
                        orientation='h',
                        marker_color=colors,
                        opacity=0.8,
                        text=[f"{data['count']}건 ({data['status']})" for data in equipment_data_for_chart],
                        textposition='auto'
                    )])
                    fig_bar.update_layout(
                        title="설비별 알림 발생 건수 (상위 8개)",
                        xaxis_title="알림 건수",
                        yaxis_title="설비명",
                        height=400,
                        plot_bgcolor='white',
                        paper_bgcolor='white'
                    )
                    # x축을 정수로 표시 (1, 2, 3, 4...)
                    fig_bar.update_xaxes(tickmode='linear', dtick=1, range=[0, max(equipment_counts.values) + 1])
                    st.plotly_chart(fig_bar, use_container_width=True)
                else:
                    st.info("📊 알림 데이터가 없습니다.")
            
            # 알림 상세 분석
            if len(alert_df) > 0:
                st.markdown("**📋 알림 상세 분석**")
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    # 알림 지표 상세
                    st.markdown("**📊 알림 지표 상세**")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.metric("긴급 알림", f"{error_count}건")
                        st.metric("주의 알림", f"{warning_count}건")
                    
                    with col2:
                        st.metric("정보 알림", f"{info_count}건")
                        st.metric("평균 응답시간", "2.3분")
                
                with col2:
                    # 알림 패턴 분석
                    st.markdown("**🔍 알림 패턴 분석**")
                    
                    if len(alert_df) > 0:
                        most_common_equipment = alert_df['equipment'].mode()[0] if len(alert_df['equipment'].mode()) > 0 else "없음"
                        most_common_severity = alert_df['severity'].mode()[0] if len(alert_df['severity'].mode()) > 0 else "없음"
                        
                        st.write(f"**🔧 가장 많은 알림 발생 설비:** {most_common_equipment}")
                        st.write(f"**⚠️ 가장 빈번한 알림 유형:** {most_common_severity}")
                        
                        # 알림 심각도 비율 분석
                        error_ratio = error_count / len(alert_df) * 100
                        if error_ratio > 30:
                            st.error(f"🚨 긴급 알림 비율이 {error_ratio:.1f}%로 매우 높습니다!")
                        elif error_ratio > 10:
                            st.warning(f"⚠️ 긴급 알림 비율이 {error_ratio:.1f}%로 높습니다.")
                        else:
                            st.success(f"✅ 긴급 알림 비율이 {error_ratio:.1f}%로 양호합니다.")
                
                # 알림 상세 데이터 테이블
                st.markdown("**📊 알림 상세 데이터**")
                
                # 알림 데이터 전처리
                alert_detail_df = alert_df.copy()
                if 'timestamp' in alert_detail_df.columns:
                    alert_detail_df['timestamp'] = pd.to_datetime(alert_detail_df['timestamp'])
                    alert_detail_df['발생시간'] = alert_detail_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M')
                else:
                    alert_detail_df['발생시간'] = 'N/A'
                
                # 심각도 한글화
                severity_map = {'error': '긴급', 'warning': '주의', 'info': '정보'}
                alert_detail_df['심각도'] = alert_detail_df['severity'].map(severity_map)
                
                # 상태 정보 추가 (더미 데이터)
                status_options = ['해결됨', '처리중', '미처리']
                alert_detail_df['상태'] = [status_options[i % len(status_options)] for i in range(len(alert_detail_df))]
                
                # 실제 알림 데이터의 컬럼에 맞게 수정
                available_columns = alert_detail_df.columns.tolist()
                
                # 필요한 컬럼들이 있는지 확인하고 없으면 기본값 설정
                if 'sensor_type' not in available_columns:
                    alert_detail_df['sensor_type'] = 'N/A'
                if 'value' not in available_columns:
                    alert_detail_df['value'] = 'N/A'
                
                display_alert_df = alert_detail_df[['equipment', 'sensor_type', '심각도', 'value', '발생시간', '상태']].copy()
                display_alert_df = display_alert_df.rename(columns={
                    'equipment': '설비명',
                    'sensor_type': '센서',
                    'value': '측정값'
                })
                
                # 조건부 스타일링
                def color_severity(val):
                    if val == '긴급':
                        return 'background-color: #fee2e2; color: #991b1b'
                    elif val == '주의':
                        return 'background-color: #fef3c7; color: #92400e'
                    else:
                        return 'background-color: #dbeafe; color: #1e40af'
                
                def color_status(val):
                    if val == '해결됨':
                        return 'background-color: #d1fae5; color: #065f46'
                    elif val == '처리중':
                        return 'background-color: #fef3c7; color: #92400e'
                    else:
                        return 'background-color: #fee2e2; color: #991b1b'
                
                styled_alert_df = display_alert_df.style.map(color_severity, subset=['심각도']).map(color_status, subset=['상태'])
                st.dataframe(styled_alert_df, use_container_width=True, height=300)
                
                # 알림 관리 제안
                st.markdown("**💡 알림 관리 제안**")
                
                if error_ratio > 30:
                    st.error("🚨 긴급 알림 비율이 30%를 초과하고 있습니다. 즉시 조치가 필요합니다.")
                    st.info("🔧 긴급 제안사항: 설비 점검 강화, 예방 정비 일정 조정, 알림 임계값 재검토")
                elif error_ratio > 10:
                    st.warning("⚠️ 긴급 알림 비율이 10%를 초과하고 있습니다. 주의가 필요합니다.")
                    st.info("🔧 제안사항: 알림 관리 프로세스 개선, 설비 상태 모니터링 강화")
                elif len(alert_df) > 0:
                    st.success("✅ 알림 상황이 양호합니다. 지속적인 모니터링을 유지하세요.")
                else:
                    st.success("✅ 알림이 없어 매우 양호한 상태입니다.")
            else:
                st.success("✅ 현재 알림이 없어 매우 양호한 상태입니다.")
                st.info("📊 알림 데이터가 생성되면 상세한 분석이 제공됩니다.")
        
        with report_tab5:
            st.markdown("### 💰 비용 분석")
            
            # 비용 개요
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown("**📊 비용 개요**")
                st.metric(
                    "총 운영 비용", 
                    "₩2,450,000",
                    "₩180,000"
                )
                st.metric(
                    "일평균 비용", 
                    "₩350,000"
                )
            
            with col2:
                st.markdown("**💰 비용 분류**")
                st.metric(
                    "인건비", 
                    "₩1,200,000",
                    "45%"
                )
                st.metric(
                    "설비 유지보수", 
                    "₩800,000",
                    "30%"
                )
            
            with col3:
                st.markdown("**📈 비용 효율성**")
                st.metric(
                    "생산성 대비 비용", 
                    "₩245/개"
                )
                st.metric(
                    "비용 절감률", 
                    "12.5%",
                    "2.3%"
                )
            
            # 비용 분석 차트
            st.markdown("**📈 비용 분석 차트**")
            col1, col2 = st.columns([1, 1])
            
            with col1:
                # 비용 분류 파이 차트
                cost_categories = ['인건비', '설비 유지보수', '원자재', '에너지', '기타']
                cost_values = [1200000, 800000, 300000, 100000, 50000]
                colors = ['#3b82f6', '#ef4444', '#10b981', '#f59e0b', '#8b5cf6']
                
                fig_pie = go.Figure(data=[go.Pie(
                    labels=cost_categories, 
                    values=cost_values,
                    hole=0.4,
                    marker_colors=colors
                )])
                fig_pie.update_layout(
                    title="비용 분류별 구성",
                    height=400,
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    showlegend=True
                )
                st.plotly_chart(fig_pie, use_container_width=True)
            
            with col2:
                # 일별 비용 트렌드
                days = ['월', '화', '수', '목', '금', '토', '일']
                daily_costs = [320000, 350000, 380000, 340000, 360000, 280000, 260000]
                
                fig_line = go.Figure()
                fig_line.add_trace(go.Scatter(
                    x=days,
                    y=daily_costs,
                    mode='lines+markers',
                    name='일별 비용',
                    line=dict(color='#3b82f6', width=3),
                    marker=dict(size=8)
                ))
                fig_line.update_layout(
                    title="일별 운영 비용 트렌드",
                    xaxis_title="요일",
                    yaxis_title="비용 (₩)",
                    height=400,
                    plot_bgcolor='white',
                    paper_bgcolor='white'
                )
                st.plotly_chart(fig_line, use_container_width=True)
            
            # 비용 상세 분석
            st.markdown("**📋 비용 상세 분석**")
            col1, col2 = st.columns([1, 1])
            
            with col1:
                # 비용 효율성 지표
                st.markdown("**📊 비용 효율성 지표**")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("생산성 대비 비용", "₩245/개")
                    st.metric("설비당 평균 비용", "₩153,125")
                
                with col2:
                    st.metric("품질 대비 비용", "₩2.45/품질점수")
                    st.metric("시간당 비용", "₩29,167")
            
            with col2:
                # 비용 절감 기회
                st.markdown("**💡 비용 절감 기회**")
                
                savings_opportunities = [
                    {"항목": "에너지 효율화", "절감 가능액": "₩50,000", "우선순위": "높음"},
                    {"항목": "예방 정비 최적화", "절감 가능액": "₩30,000", "우선순위": "중간"},
                    {"항목": "인력 배치 최적화", "절감 가능액": "₩40,000", "우선순위": "높음"}
                ]
                
                for opp in savings_opportunities:
                    priority_color = "🔴" if opp["우선순위"] == "높음" else "🟡" if opp["우선순위"] == "중간" else "🟢"
                    st.write(f"{priority_color} **{opp['항목']}**: {opp['절감 가능액']} ({opp['우선순위']})")
            
            # 비용 상세 데이터 테이블
            st.markdown("**📊 비용 상세 데이터**")
            
            cost_detail_data = [
                {"비용 항목": "인건비", "금액": "₩1,200,000", "비율": "45%", "전월 대비": "+5%", "상태": "정상"},
                {"비용 항목": "설비 유지보수", "금액": "₩800,000", "비율": "30%", "전월 대비": "-2%", "상태": "개선"},
                {"비용 항목": "원자재", "금액": "₩300,000", "비율": "11%", "전월 대비": "+1%", "상태": "정상"},
                {"비용 항목": "에너지", "금액": "₩100,000", "비율": "4%", "전월 대비": "-8%", "상태": "개선"},
                {"비용 항목": "기타", "금액": "₩50,000", "비율": "2%", "전월 대비": "0%", "상태": "정상"}
            ]
            
            cost_df = pd.DataFrame(cost_detail_data)
            
            # 조건부 스타일링
            def color_status(val):
                if val == "개선":
                    return 'background-color: #d1fae5; color: #065f46'
                elif val == "주의":
                    return 'background-color: #fef3c7; color: #92400e'
                else:
                    return 'background-color: #f3f4f6; color: #374151'
            
            styled_cost_df = cost_df.style.map(color_status, subset=['상태'])
            st.dataframe(styled_cost_df, use_container_width=True, height=300)
            
            # 비용 관리 제안
            st.markdown("**💡 비용 관리 제안**")
            
            total_cost = 2450000
            cost_efficiency = total_cost / quality_data['production_volume'].mean()
            
            if cost_efficiency > 300:
                st.error("🚨 생산성 대비 비용이 높습니다. 비용 최적화가 필요합니다.")
                st.info("🔧 긴급 제안사항: 에너지 효율화, 인력 배치 최적화, 공정 개선")
            elif cost_efficiency > 250:
                st.warning("⚠️ 비용 효율성 개선의 여지가 있습니다.")
                st.info("🔧 제안사항: 예방 정비 최적화, 원자재 사용량 최적화")
            else:
                st.success("✅ 비용 효율성이 양호합니다. 지속적인 모니터링을 유지하세요.")
        


    with tabs[5]:  # 설정
        st.markdown('<div class="main-header no-translate" translate="no">⚙️ 설정</div>', unsafe_allow_html=True)
        st.write("대시보드 환경설정 및 알림, 데이터, 테마 설정을 할 수 있습니다.")
        
        # 설정 탭
        settings_tab1, settings_tab2, settings_tab3, settings_tab4 = st.tabs(["일반 설정", "알림 설정", "데이터 설정", "사용자 설정"])
        
        with settings_tab1:
            st.markdown("### 🎨 일반 설정")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**대시보드 테마**")
                theme = st.selectbox("테마 선택", ["라이트", "다크", "자동"], index=0, key="theme_selector")
                
                st.markdown("**언어 설정**")
                language = st.selectbox("언어", ["한국어", "English", "日本語"], index=0, key="language_selector")
                
                st.markdown("**시간대 설정**")
                timezone = st.selectbox("시간대", ["Asia/Seoul (KST)", "UTC", "America/New_York"], index=0, key="timezone_selector")
            
            with col2:
                st.markdown("**표시 설정**")
                show_animations = st.checkbox("애니메이션 표시", value=True, key="show_animations")
                show_tooltips = st.checkbox("툴팁 표시", value=True, key="show_tooltips")
                compact_mode = st.checkbox("컴팩트 모드", value=False, key="compact_mode")
                
                st.markdown("**접근성 설정**")
                high_contrast = st.checkbox("고대비 모드", value=False, key="high_contrast")
                large_font = st.checkbox("큰 글씨 모드", value=False, key="large_font")
            
            # 일반 설정 저장 버튼을 중앙에 독립적으로 배치
            st.markdown("<br>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                if st.button("일반 설정 저장", key="save_general_settings", use_container_width=True):
                    st.success("일반 설정이 저장되었습니다.")
        
        with settings_tab2:
            st.markdown("### 🔔 알림 설정")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**알림 활성화**")
                alert_on = st.toggle("알림 수신(ON/OFF)", value=True, key="alert_toggle")
                
                st.markdown("**알림 유형별 설정**")
                error_alerts = st.checkbox("긴급 알림 (Error)", value=True, key="error_alerts")
                warning_alerts = st.checkbox("주의 알림 (Warning)", value=True, key="warning_alerts")
                info_alerts = st.checkbox("정보 알림 (Info)", value=False, key="info_alerts")
                
                st.markdown("**알림 방법**")
                browser_notifications = st.checkbox("브라우저 알림", value=True, key="browser_notifications")
                email_notifications = st.checkbox("이메일 알림", value=False, key="email_notifications")
                sms_notifications = st.checkbox("SMS 알림", value=False, key="sms_notifications")
            
            with col2:
                st.markdown("**알림 임계값**")
                error_threshold = st.slider("긴급 알림 임계값", 0, 100, 80, key="error_threshold")
                warning_threshold = st.slider("주의 알림 임계값", 0, 100, 60, key="warning_threshold")
                
                st.markdown("**알림 스케줄**")
                quiet_hours_start = st.time_input("방해 금지 시작", key="quiet_start")
                quiet_hours_end = st.time_input("방해 금지 종료", key="quiet_end")
                
                st.markdown("**알림 소리**")
                notification_sound = st.selectbox("알림음", ["기본", "부드러운", "경고음", "무음"], index=0, key="notification_sound")
            
            # 알림 설정 저장 버튼을 중앙에 독립적으로 배치
            st.markdown("<br>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                if st.button("알림 설정 저장", key="save_alert_settings", use_container_width=True):
                    st.success("알림 설정이 저장되었습니다.")
        
        with settings_tab3:
            st.markdown("### 📊 데이터 설정")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**데이터 소스**")
                data_source = st.radio("데이터 소스 선택", ["더미 데이터", "실제 API"], index=0, horizontal=True, key="data_source_radio")
                
                st.markdown("**자동 새로고침**")
                auto_refresh_enabled = st.checkbox("자동 새로고침 활성화", value=True, key="auto_refresh_enabled")
                refresh_interval = st.selectbox("새로고침 주기", ["15초", "30초", "1분", "3분", "5분", "10분", "수동"], index=1, key="refresh_interval_settings")
                
                st.markdown("**데이터 보존**")
                data_retention_days = st.slider("데이터 보존 기간 (일)", 1, 365, 30, key="data_retention")
                auto_cleanup = st.checkbox("자동 데이터 정리", value=True, key="auto_cleanup")
            
            with col2:
                st.markdown("**데이터 내보내기**")
                export_format_default = st.selectbox("기본 내보내기 형식", ["CSV", "Excel", "PDF"], index=0, key="export_format_default")
                include_charts = st.checkbox("차트 포함", value=True, key="include_charts")
                include_metadata = st.checkbox("메타데이터 포함", value=True, key="include_metadata")
                
                st.markdown("**데이터 백업**")
                auto_backup = st.checkbox("자동 백업", value=False, key="auto_backup")
                backup_frequency = st.selectbox("백업 주기", ["매일", "매주", "매월"], index=1, key="backup_frequency")
                
                if st.button("데이터 초기화", key="reset_data"):
                    st.warning("모든 데이터가 초기화됩니다. 계속하시겠습니까?")
                    if st.button("확인", key="confirm_reset"):
                        try:
                            response = requests.post("http://localhost:8000/clear_data", timeout=5)
                            if response.status_code == 200:
                                st.success("모든 데이터가 초기화되었습니다.")
                            else:
                                st.error("데이터 초기화 실패")
                        except Exception as e:
                            st.error(f"API 서버 연결 실패: {e}")
            
            # 데이터 설정 저장 버튼을 중앙에 독립적으로 배치
            st.markdown("<br>", unsafe_allow_html=True)
            col1, col2, col3 = st.columns([1, 1, 1])
            with col2:
                if st.button("데이터 설정 저장", key="save_data_settings", use_container_width=True):
                    st.success("데이터 설정이 저장되었습니다.")
        
        with settings_tab4:
            st.markdown("### 👤 사용자 관리")
            
            # 사용자 관리 탭
            user_tab1, user_tab2, user_tab3, user_tab4 = st.tabs(["사용자 목록", "새 사용자 등록", "알림 구독 관리", "설비별 할당 현황"])
            
            with user_tab1:
                st.markdown("**📋 등록된 사용자 목록**")
                
                # 사용자 목록 조회
                users = get_users_from_api(use_real_api)
                
                if users:
                    # 사용자 목록 표시
                    users_data = []
                    for user in users:
                        status_icon = "🟢" if user['is_active'] else "🔴"
                        users_data.append({
                            "ID": user['id'],
                            "이름": user['name'],
                            "전화번호": user['phone_number'],
                            "부서": user['department'] or "-",
                            "권한": user['role'],
                            "상태": f"{status_icon} {'활성' if user['is_active'] else '비활성'}",
                            "등록일": user['created_at'][:10] if user['created_at'] else "-"
                        })
                    
                    users_df = pd.DataFrame(users_data)
                    st.dataframe(users_df, use_container_width=True, height=300)
                    
                    # 사용자 상세 정보
                    if users:
                        st.markdown("**👤 사용자 상세 정보**")
                        selected_user_id = st.selectbox(
                            "사용자 선택",
                            options=[(u['id'], u['name']) for u in users],
                            format_func=lambda x: x[1],
                            key="user_detail_select"
                        )
                        
                        if selected_user_id:
                            selected_user = next((u for u in users if u['id'] == selected_user_id[0]), None)
                            if selected_user:
                                col1, col2 = st.columns(2)
                                
                                with col1:
                                    st.write(f"**이름:** {selected_user['name']}")
                                    st.write(f"**전화번호:** {selected_user['phone_number']}")
                                    st.write(f"**부서:** {selected_user['department'] or '-'}")
                                
                                with col2:
                                    st.write(f"**권한:** {selected_user['role']}")
                                    st.write(f"**상태:** {'활성' if selected_user['is_active'] else '비활성'}")
                                    st.write(f"**등록일:** {selected_user['created_at'][:10] if selected_user['created_at'] else '-'}")
                                
                                # 담당 설비 목록
                                user_equipment = get_equipment_users_by_user(selected_user['id'])
                                if user_equipment:
                                    st.markdown("**🏭 담당 설비**")
                                    equipment_data = []
                                    for eq in user_equipment:
                                        role_icon = "👑" if eq.get('is_primary', False) else "👤"
                                        equipment_data.append({
                                            "설비명": eq['equipment_name'],
                                            "설비타입": eq['equipment_type'],
                                            "역할": f"{role_icon} {eq['role']}",
                                            "주담당자": "예" if eq.get('is_primary', False) else "아니오"
                                        })
                                    
                                    equipment_df = pd.DataFrame(equipment_list)
                                    st.dataframe(equipment_df, use_container_width=True, height=150)
                                else:
                                    st.info("담당 설비가 없습니다.")
                else:
                    st.info("등록된 사용자가 없습니다.")
            
            with user_tab2:
                st.markdown("**➕ 새 사용자 등록**")
                
                with st.form("new_user_form"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        new_user_name = st.text_input("이름 *", key="new_user_name")
                        new_user_phone = st.text_input("전화번호 *", key="new_user_phone")
                        new_user_department = st.selectbox(
                            "부서",
                            ["생산관리팀", "품질관리팀", "설비관리팀", "기술팀", "IT팀", "기타"],
                            key="new_user_department"
                        )
                    
                    with col2:
                        new_user_role = st.selectbox(
                            "권한",
                            ["user", "manager", "admin"],
                            format_func=lambda x: {"user": "일반 사용자", "manager": "관리자", "admin": "시스템 관리자"}[x],
                            key="new_user_role"
                        )
                        
                        # 기본 알림 구독 설정
                        st.markdown("**🔔 기본 알림 설정**")
                        default_error_alerts = st.checkbox("긴급 알림 (Error)", value=True, key="default_error_alerts")
                        default_warning_alerts = st.checkbox("주의 알림 (Warning)", value=False, key="default_warning_alerts")
                        default_info_alerts = st.checkbox("정보 알림 (Info)", value=False, key="default_info_alerts")
                    
                    submitted = st.form_submit_button("사용자 등록")
                    
                    if submitted:
                        if new_user_name and new_user_phone:
                            # 사용자 등록 API 호출
                            try:
                                user_data = {
                                    "phone_number": new_user_phone,
                                    "name": new_user_name,
                                    "department": new_user_department,
                                    "role": new_user_role
                                }
                                
                                response = requests.post(f"{API_BASE_URL}/users", json=user_data, timeout=5)
                                
                                if response.status_code == 200:
                                    st.success(f"사용자 '{new_user_name}'이(가) 등록되었습니다.")
                                    st.rerun()
                                else:
                                    error_msg = response.json().get('detail', '사용자 등록에 실패했습니다.')
                                    st.error(f"등록 실패: {error_msg}")
                            except Exception as e:
                                st.error(f"API 호출 오류: {e}")
                        else:
                            st.error("이름과 전화번호는 필수 입력 항목입니다.")
                
                # 사용자 수정/삭제 기능 추가
                st.markdown("**✏️ 사용자 정보 수정**")
                
                if users:
                    user_to_edit = st.selectbox(
                        "수정할 사용자 선택",
                        options=[(u['id'], u['name']) for u in users],
                        format_func=lambda x: x[1],
                        key="edit_user_select"
                    )
                    
                    if user_to_edit:
                        selected_user = next((u for u in users if u['id'] == user_to_edit[0]), None)
                        if selected_user:
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                edit_name = st.text_input("이름", value=selected_user['name'], key="edit_name")
                                edit_phone = st.text_input("전화번호", value=selected_user['phone_number'], key="edit_phone")
                                edit_department = st.selectbox(
                                    "부서",
                                    ["생산관리팀", "품질관리팀", "설비관리팀", "기술팀", "IT팀", "기타"],
                                    index=["생산관리팀", "품질관리팀", "설비관리팀", "기술팀", "IT팀", "기타"].index(selected_user['department']) if selected_user['department'] in ["생산관리팀", "품질관리팀", "설비관리팀", "기술팀", "IT팀", "기타"] else 0,
                                    key="edit_department"
                                )
                            
                            with col2:
                                edit_role = st.selectbox(
                                    "권한",
                                    ["user", "manager", "admin"],
                                    format_func=lambda x: {"user": "일반 사용자", "manager": "관리자", "admin": "시스템 관리자"}[x],
                                    index=["user", "manager", "admin"].index(selected_user['role']),
                                    key="edit_role"
                                )
                                edit_active = st.checkbox("활성 상태", value=selected_user['is_active'], key="edit_active")
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                if st.button("정보 수정", key="update_user_btn"):
                                    try:
                                        update_data = {
                                            "name": edit_name,
                                            "department": edit_department,
                                            "role": edit_role,
                                            "is_active": edit_active
                                        }
                                        
                                        response = requests.put(f"{API_BASE_URL}/users/{selected_user['id']}", 
                                                              json=update_data, timeout=5)
                                        
                                        if response.status_code == 200:
                                            st.success("사용자 정보가 수정되었습니다.")
                                            st.rerun()
                                        else:
                                            error_msg = response.json().get('detail', '사용자 수정에 실패했습니다.')
                                            st.error(f"수정 실패: {error_msg}")
                                    except Exception as e:
                                        st.error(f"API 호출 오류: {e}")
                            
                            with col2:
                                if st.button("사용자 삭제", key="delete_user_btn", type="secondary"):
                                    if st.checkbox("정말 삭제하시겠습니까?", key="confirm_delete"):
                                        try:
                                            response = requests.delete(f"{API_BASE_URL}/users/{selected_user['id']}", timeout=5)
                                            
                                            if response.status_code == 200:
                                                st.success("사용자가 삭제되었습니다.")
                                                st.rerun()
                                            else:
                                                error_msg = response.json().get('detail', '사용자 삭제에 실패했습니다.')
                                                st.error(f"삭제 실패: {error_msg}")
                                        except Exception as e:
                                            st.error(f"API 호출 오류: {e}")
                else:
                    st.info("수정할 사용자가 없습니다.")
            
            with user_tab3:
                st.markdown("**🔔 알림 구독 관리**")
                
                if users:
                    # 사용자별 알림 구독 설정
                    subscription_user = st.selectbox(
                        "구독 설정할 사용자 선택",
                        options=[(u['id'], u['name']) for u in users],
                        format_func=lambda x: x[1],
                        key="subscription_user_select"
                    )
                    
                    if subscription_user:
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.markdown("**알림 구독 설정**")
                            sub_equipment = st.selectbox(
                                "설비 (전체: None)",
                                options=[None] + [eq['id'] for eq in equipment_list] if 'equipment_list' in locals() else [None],
                                format_func=lambda x: "전체 설비" if x is None else x,
                                key="sub_equipment"
                            )
                            
                            sub_sensor_type = st.selectbox(
                                "센서 타입 (전체: None)",
                                options=[None, "temperature", "pressure", "vibration", "power"],
                                format_func=lambda x: "전체 센서" if x is None else x,
                                key="sub_sensor_type"
                            )
                        
                        with col2:
                            sub_severity = st.selectbox(
                                "심각도",
                                ["error", "warning", "info"],
                                format_func=lambda x: {"error": "긴급", "warning": "주의", "info": "정보"}[x],
                                key="sub_severity"
                            )
                            
                            sub_active = st.checkbox("구독 활성화", value=True, key="sub_active")
                        
                        if st.button("구독 설정 추가", key="add_subscription_btn"):
                            try:
                                subscription_data = {
                                    "user_id": subscription_user[0],
                                    "equipment": sub_equipment,
                                    "sensor_type": sub_sensor_type,
                                    "severity": sub_severity,
                                    "is_active": sub_active
                                }
                                
                                response = requests.post(f"{API_BASE_URL}/users/{subscription_user[0]}/subscriptions", 
                                                       json=subscription_data, timeout=5)
                                
                                if response.status_code == 200:
                                    st.success("알림 구독이 설정되었습니다.")
                                    st.rerun()
                                else:
                                    error_msg = response.json().get('detail', '구독 설정에 실패했습니다.')
                                    st.error(f"구독 설정 실패: {error_msg}")
                            except Exception as e:
                                st.error(f"API 호출 오류: {e}")
                
                # 구독 설정 목록 조회
                st.markdown("**📋 현재 구독 설정 목록**")
                try:
                    response = requests.get(f"{API_BASE_URL}/users", timeout=5)
                    if response.status_code == 200:
                        all_users = response.json()['users']
                        for user in all_users:
                            try:
                                sub_response = requests.get(f"{API_BASE_URL}/users/{user['id']}/subscriptions", timeout=5)
                                if sub_response.status_code == 200:
                                    subscriptions = sub_response.json()['subscriptions']
                                    if subscriptions:
                                        st.write(f"**{user['name']}** ({user['phone_number']})")
                                        for sub in subscriptions:
                                            status_icon = "🟢" if sub['is_active'] else "🔴"
                                            st.write(f"  {status_icon} {sub['equipment'] or '전체'} | {sub['sensor_type'] or '전체'} | {sub['severity']}")
                            except:
                                pass
                except:
                    st.info("구독 설정 정보를 불러올 수 없습니다.")
            
            with user_tab4:
                st.markdown("**📊 설비별 사용자 할당 현황**")
                
                # 할당 요약 정보
                summary = get_equipment_users_summary_api(use_real_api)
                
                if summary and 'summary' in summary:
                    # 전체 통계
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("전체 설비", summary['equipment_count'])
                    
                    with col2:
                        st.metric("총 할당", summary['total_assignments'])
                    
                    with col3:
                        st.metric("주담당자", summary['total_primary_users'])
                    
                    with col4:
                        avg_assignments = summary['total_assignments'] / summary['equipment_count'] if summary['equipment_count'] > 0 else 0
                        st.metric("평균 할당", f"{avg_assignments:.1f}")
                    
                    # 설비별 상세 현황
                    st.markdown("**🏭 설비별 상세 현황**")
                    summary_data = []
                    for item in summary['summary']:
                        summary_data.append({
                            "설비명": item['equipment_name'],
                            "설비타입": item['equipment_type'],
                            "총 할당": item['user_count'],
                            "주담당자": item['primary_user_count'],
                            "일반 담당자": item['user_count'] - item['primary_user_count']
                        })
                    
                    if summary_data:
                        summary_df = pd.DataFrame(summary_data)
                        st.dataframe(summary_df, use_container_width=True, height=300)
                    else:
                        st.info("할당 현황 정보가 없습니다.")
                else:
                    st.info("할당 현황 정보를 불러올 수 없습니다.")
            
            # SMS 이력 조회 탭 추가
            st.markdown("**📱 SMS 전송 이력**")
            
            try:
                response = requests.get(f"{API_BASE_URL}/sms/history?limit=50", timeout=5)
                if response.status_code == 200:
                    sms_history = response.json()['history']
                    
                    if sms_history:
                        # SMS 이력 데이터프레임 생성
                        sms_data = []
                        for sms in sms_history:
                            status_icon = "✅" if sms['status'] == 'sent' else "❌"
                            sms_data.append({
                                "사용자": sms['user_name'],
                                "전화번호": sms['phone_number'],
                                "상태": f"{status_icon} {sms['status']}",
                                "전송시간": sms['sent_at'][:19] if sms['sent_at'] else "-",
                                "메시지": sms['message'][:50] + "..." if len(sms['message']) > 50 else sms['message']
                            })
                        
                        sms_df = pd.DataFrame(sms_data)
                        st.dataframe(sms_df, use_container_width=True, height=400)
                        
                        # SMS 통계
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("총 전송", len(sms_history))
                        with col2:
                            success_count = sum(1 for sms in sms_history if sms['status'] == 'sent')
                            st.metric("성공", success_count)
                        with col3:
                            failed_count = len(sms_history) - success_count
                            st.metric("실패", failed_count)
                    else:
                        st.info("SMS 전송 이력이 없습니다.")
                else:
                    st.info("SMS 이력을 불러올 수 없습니다.")
            except Exception as e:
                st.error(f"SMS 이력 조회 오류: {e}")
        
        # 시스템 정보
        st.markdown("### ℹ️ 시스템 정보")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**애플리케이션 정보**")
            st.write("**버전:** 1.0.0")
            st.write("**빌드 날짜:** 2024-01-15")
            st.write("**라이선스:** POSCO Internal")
        
        with col2:
            st.markdown("**시스템 상태**")
            st.write("**서버 상태:** 정상")
            st.write("**데이터베이스:** 연결됨")
            st.write("**API 서버:** 연결됨")
        
        with col3:
            st.markdown("**성능 정보**")
            st.write("**메모리 사용량:** 45%")
            st.write("**CPU 사용량:** 23%")
            st.write("**디스크 사용량:** 67%")
        
        # 관리자 기능
        st.markdown("### 🔧 관리자 기능")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("시스템 로그 확인", key="view_logs"):
                st.info("시스템 로그를 확인할 수 있습니다.")
        
        with col2:
            if st.button("사용자 관리", key="user_management"):
                st.info("사용자 계정을 관리할 수 있습니다.")
        
        with col3:
            if st.button("시스템 백업", key="system_backup"):
                st.success("시스템 백업이 시작되었습니다.")
        
        st.info("추가 관리자 기능(사용자 권한 관리, 시스템 모니터링, 로그 분석 등)은 추후 확장 예정입니다.")
    
    # 실시간 알림 처리를 위한 JavaScript 추가
    st.markdown("""
    <script>
        // 실시간 알림 처리
        function checkForNewAlerts() {
            // 5초마다 새로운 알림 확인
            setInterval(() => {
                fetch('/dashboard/data')
                    .then(response => response.json())
                    .then(data => {
                        const alerts = data.alerts || [];
                        const criticalAlerts = alerts.filter(alert => 
                            alert.severity === 'error' || 
                            alert.issue.includes('위험') || 
                            alert.issue.includes('오류')
                        );
                        
                        if (criticalAlerts.length > 0) {
                            // 위험 알림이 있으면 브라우저 알림 표시
                            if (Notification.permission === 'granted') {
                                new Notification('🚨 위험 알림 발생!', {
                                    body: `${criticalAlerts.length}개의 위험 상황이 감지되었습니다.`,
                                    icon: '/favicon.ico'
                                });
                            }
                            
                            // 페이지 새로고침 트리거
                            console.log('위험 알림 감지! 페이지 새로고침 필요');
                        }
                    })
                    .catch(error => {
                        console.log('알림 확인 중 오류:', error);
                    });
            }, 5000);
        }
        
        // 브라우저 알림 권한 요청
        if (Notification.permission === 'default') {
            Notification.requestPermission();
        }
        
        // 페이지 로드 시 알림 체크 시작
        document.addEventListener('DOMContentLoaded', function() {
            checkForNewAlerts();
        });
    </script>
    """, unsafe_allow_html=True)

# 모듈로 사용할 때만 실행
if __name__ == "__main__":
    main()