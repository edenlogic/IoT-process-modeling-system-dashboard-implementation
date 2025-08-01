import streamlit as st
import pandas as pd
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

# Plotly 경고 무시
warnings.filterwarnings("ignore", category=FutureWarning, module="_plotly_utils")

# FastAPI 서버
# FastAPI 서버 URL
API_BASE_URL = "http://localhost:8000"

# 실시간 데이터 갱신을 위한 전역 변수
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
if 'background_thread_started' not in st.session_state:
    st.session_state.background_thread_started = False
if 'update_thread_started' not in st.session_state:
    st.session_state.update_thread_started = False
if 'api_toggle_previous' not in st.session_state:
    st.session_state.api_toggle_previous = False

def get_sensor_data_from_api(use_real_api=True):
    """FastAPI에서 센서 데이터 가져오기"""
    if not use_real_api:
        return None
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/sensor_data", timeout=5)
        if response.status_code == 200:
            data = response.json()
            # API 데이터에 equipment 컬럼이 없는 경우 기본값 추가
            if isinstance(data, list):
                for item in data:
                    if 'equipment' not in item:
                        item['equipment'] = '알 수 없는 설비'
            return data
    except Exception as e:
        pass
    return None

def get_equipment_status_from_api(use_real_api=True):
    """FastAPI에서 설비 상태 데이터 가져오기"""
    if not use_real_api:
        return []
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/equipment_status", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data
    except Exception as e:
        pass
    return []

def get_alerts_from_api(use_real_api=True):
    """FastAPI에서 알림 데이터 가져오기"""
    if not use_real_api:
        return []
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/alerts", timeout=5)
        if response.status_code == 200:
            data = response.json()
            return data
    except Exception as e:
        pass
    return []

def get_quality_trend_from_api(use_real_api=True):
    """FastAPI에서 품질 추세 데이터 가져오기"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/quality_trend?use_real_api={str(use_real_api).lower()}", timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"품질 추세 API 연결 오류: {e}")
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
        if probability < 0.3:  # 30% 미만
            return {'color': '#10B981', 'bg': '#ECFDF5', 'icon': '🟢'}
        elif probability < 0.6:  # 30% 이상 60% 미만
            return {'color': '#F59E0B', 'bg': '#FFFBEB', 'icon': '🟠'}
        else:  # 60% 이상
            return {'color': '#EF4444', 'bg': '#FEF2F2', 'icon': '🔴'}

def get_ai_prediction_results(use_real_api=True):
    """AI 예측 결과 JSON 파일들을 읽어오기"""
    predictions = {}
    
        # API 연동이 OFF인 경우 더미 데이터 반환
    if not use_real_api:
        # 설비 이상 예측 더미 데이터 (77.1% 정상 - 주의 상태)
        predictions['abnormal_detection'] = {
            'status': 'success',
            'prediction': {
                'predicted_class': 'normal',
                'predicted_class_description': '정상',
                'confidence': 0.85,
                'probabilities': {
                    'normal': 0.771,
                    'bearing_fault': 0.089,
                    'roll_misalignment': 0.067,
                    'motor_overload': 0.045,
                    'lubricant_shortage': 0.028
                },
                'max_status': 'normal'
            },
            'timestamp': datetime.now().isoformat()
        }
        
        # 유압 이상 탐지 더미 데이터 (90% 정상)
        predictions['hydraulic_detection'] = {
            'status': 'success',
            'prediction': {
                'prediction': 0,  # 0: 정상, 1: 이상
                'probabilities': {
                    'normal': 0.90,
                    'abnormal': 0.10
                },
                'confidence': 0.90
            },
            'timestamp': datetime.now().isoformat()
        }
        
        return predictions
    
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

def background_data_fetcher():
    """백그라운드에서 데이터를 가져오는 함수"""

    
    # 전역 변수로 데이터 상태 관리
    global last_data_state
    last_data_state = {
        'has_sensor_data': False,
        'alert_count': 0,
        'sensor_count': 0,
        'last_check': time.time()
    }
    
    while True:
        try:
            # API 서버에서 데이터 가져오기
            response = requests.get('http://localhost:8000/dashboard/data', timeout=5)
            if response.status_code == 200:
                data = response.json()
                
                # 위험 알림 확인 (ERROR와 WARNING)
                alerts = data.get('alerts', [])
                error_warning_alerts = [a for a in alerts if a.get('severity') in ['error', 'warning']]
                
                # 센서 데이터 확인
                sensor_data = data.get('sensor_data', {})
                has_sensor_data = any(len(sensor_data.get(key, [])) > 0 for key in ['temperature', 'pressure', 'vibration'])
                
                # 데이터 개수 계산
                current_sensor_count = sum(len(sensor_data.get(key, [])) for key in ['temperature', 'pressure', 'vibration'])
                current_alert_count = len(error_warning_alerts)
                
                # 데이터 상태 변경 감지
                data_changed = (
                    has_sensor_data != last_data_state['has_sensor_data'] or
                    current_alert_count != last_data_state['alert_count'] or
                    current_sensor_count != last_data_state['sensor_count']
                )
                
                if data_changed:
                    print(f"🔄 데이터 변경 감지! 센서: {has_sensor_data} ({current_sensor_count}), 알림: {current_alert_count}")
                    
                    # 전역 변수 업데이트
                    last_data_state.update({
                        'has_sensor_data': has_sensor_data,
                        'alert_count': current_alert_count,
                        'sensor_count': current_sensor_count,
                        'last_check': time.time(),
                        'needs_refresh': True
                    })
                else:
                    pass
            else:
                print(f"API 응답 오류: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            print("API 서버 연결 실패 - 서버가 실행 중인지 확인하세요")
        except Exception as e:
            print(f"백그라운드 데이터 가져오기 오류: {e}")
        
        time.sleep(1)  # 1초마다 체크

def start_background_thread():
    """백그라운드 스레드 시작"""
    if not hasattr(st.session_state, 'background_thread_started') or not st.session_state.background_thread_started:
        st.session_state.background_thread_started = True
        # thread = threading.Thread(target=background_data_fetcher, daemon=True)
        # thread.start()
        print("[DEBUG] 백그라운드 스레드 비활성화됨")

# 실시간 업데이트 함수들 제거 (불필요)

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
    
    /* 버튼 간격 최적화 */
    .stButton > button {
        margin-bottom: 0.3rem;
        padding: 0.4rem 0.8rem;
        font-size: 0.85rem;
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
    """설비 상태 데이터 생성"""
    # 데이터 제거 상태 확인
    if hasattr(st, 'session_state') and st.session_state.get('data_cleared', False):
        return []  # 데이터 제거 시 빈 리스트 반환
    
    equipment = [
        {'id': 'press_001', 'name': '프레스기 #001', 'status': '정상', 'efficiency': 98.2, 'type': '프레스기', 'last_maintenance': '2024-01-15'},
        {'id': 'press_002', 'name': '프레스기 #002', 'status': '주의', 'efficiency': 78.5, 'type': '프레스기', 'last_maintenance': '2024-01-10'},
        {'id': 'press_003', 'name': '프레스기 #003', 'status': '정상', 'efficiency': 92.1, 'type': '프레스기', 'last_maintenance': '2024-01-13'},
        {'id': 'press_004', 'name': '프레스기 #004', 'status': '정상', 'efficiency': 95.8, 'type': '프레스기', 'last_maintenance': '2024-01-11'},
        {'id': 'weld_001', 'name': '용접기 #001', 'status': '정상', 'efficiency': 89.3, 'type': '용접기', 'last_maintenance': '2024-01-12'},
        {'id': 'weld_002', 'name': '용접기 #002', 'status': '오류', 'efficiency': 0, 'type': '용접기', 'last_maintenance': '2024-01-08'},
        {'id': 'weld_003', 'name': '용접기 #003', 'status': '주의', 'efficiency': 82.4, 'type': '용접기', 'last_maintenance': '2024-01-09'},
        {'id': 'weld_004', 'name': '용접기 #004', 'status': '정상', 'efficiency': 91.7, 'type': '용접기', 'last_maintenance': '2024-01-14'},
        {'id': 'assemble_001', 'name': '조립기 #001', 'status': '정상', 'efficiency': 96.1, 'type': '조립기', 'last_maintenance': '2024-01-14'},
        {'id': 'assemble_002', 'name': '조립기 #002', 'status': '정상', 'efficiency': 94.3, 'type': '조립기', 'last_maintenance': '2024-01-12'},
        {'id': 'assemble_003', 'name': '조립기 #003', 'status': '주의', 'efficiency': 85.6, 'type': '조립기', 'last_maintenance': '2024-01-10'},
        {'id': 'inspect_001', 'name': '검사기 #001', 'status': '오류', 'efficiency': 0, 'type': '검사기', 'last_maintenance': '2024-01-05'},
        {'id': 'inspect_002', 'name': '검사기 #002', 'status': '정상', 'efficiency': 97.2, 'type': '검사기', 'last_maintenance': '2024-01-13'},
        {'id': 'inspect_003', 'name': '검사기 #003', 'status': '정상', 'efficiency': 93.8, 'type': '검사기', 'last_maintenance': '2024-01-11'},
        {'id': 'pack_001', 'name': '포장기 #001', 'status': '정상', 'efficiency': 88.9, 'type': '포장기', 'last_maintenance': '2024-01-15'},
        {'id': 'pack_002', 'name': '포장기 #002', 'status': '주의', 'efficiency': 76.2, 'type': '포장기', 'last_maintenance': '2024-01-07'}
    ]
    return equipment

def get_alerts_from_api(use_real_api=True):
    """실제 API에서 알림 데이터 가져오기"""
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
    """이상 알림 데이터 생성 (더미 데이터) - 최소 4개 이상의 error/warning 알림 보장"""
    # 데이터 제거 상태 확인
    if hasattr(st, 'session_state') and st.session_state.get('data_cleared', False):
        return []  # 데이터 제거 시 빈 리스트 반환
    
    alerts = [
        {'id': 1, 'time': '14:30', 'equipment': '용접기 #002', 'issue': '온도 임계값 초과', 'severity': 'error', 'status': '미처리', 'details': '현재 온도: 87°C (임계값: 85°C)'},
        {'id': 2, 'time': '13:20', 'equipment': '프레스기 #001', 'issue': '진동 증가', 'severity': 'warning', 'status': '처리중', 'details': '진동레벨: 높음, 정비 검토 필요'},
        {'id': 3, 'time': '12:15', 'equipment': '검사기 #001', 'issue': '비상 정지', 'severity': 'error', 'status': '미처리', 'details': '센서 오류로 인한 비상 정지'},
        {'id': 4, 'time': '11:30', 'equipment': '조립기 #001', 'issue': '정기점검 완료', 'severity': 'info', 'status': '완료', 'details': '정기점검 완료, 정상 가동 재개'},
        {'id': 5, 'time': '10:45', 'equipment': '프레스기 #002', 'issue': '압력 불안정', 'severity': 'warning', 'status': '처리중', 'details': '압력 변동 폭 증가'},
        {'id': 6, 'time': '09:20', 'equipment': '용접기 #001', 'issue': '품질 검사 불량', 'severity': 'error', 'status': '미처리', 'details': '불량률: 3.2% (기준: 2.5%)'},
        {'id': 7, 'time': '08:45', 'equipment': '용접기 #003', 'issue': '가스 압력 부족', 'severity': 'warning', 'status': '처리중', 'details': '가스 압력: 0.3MPa (기준: 0.5MPa)'},
        {'id': 8, 'time': '08:15', 'equipment': '프레스기 #003', 'issue': '금형 교체 완료', 'severity': 'info', 'status': '완료', 'details': '금형 교체 작업 완료, 정상 가동 재개'},
        {'id': 9, 'time': '07:30', 'equipment': '조립기 #002', 'issue': '부품 공급 지연', 'severity': 'warning', 'status': '미처리', 'details': '부품 재고 부족으로 인한 가동 중단'},
        {'id': 10, 'time': '07:00', 'equipment': '검사기 #002', 'issue': '센서 교정 완료', 'severity': 'info', 'status': '완료', 'details': '센서 교정 작업 완료, 정상 검사 재개'},
        {'id': 11, 'time': '06:45', 'equipment': '포장기 #001', 'issue': '포장재 부족', 'severity': 'warning', 'status': '처리중', 'details': '포장재 재고 부족, 추가 공급 대기'},
        {'id': 12, 'time': '06:20', 'equipment': '프레스기 #004', 'issue': '유압 오일 온도 높음', 'severity': 'warning', 'status': '미처리', 'details': '유압 오일 온도: 75°C (기준: 65°C)'},
        {'id': 13, 'time': '05:30', 'equipment': '용접기 #004', 'issue': '전극 마모', 'severity': 'warning', 'status': '처리중', 'details': '전극 마모율: 85%, 교체 예정'},
        {'id': 14, 'time': '05:00', 'equipment': '조립기 #003', 'issue': '컨베이어 벨트 이탈', 'severity': 'error', 'status': '미처리', 'details': '컨베이어 벨트 이탈로 인한 가동 중단'},
        {'id': 15, 'time': '04:30', 'equipment': '검사기 #003', 'issue': '카메라 렌즈 오염', 'severity': 'warning', 'status': '처리중', 'details': '카메라 렌즈 오염으로 인한 검사 정확도 저하'},
        {'id': 16, 'time': '04:00', 'equipment': '포장기 #002', 'issue': '시스템 오류', 'severity': 'error', 'status': '미처리', 'details': 'PLC 통신 오류로 인한 시스템 정지'},
        {'id': 17, 'time': '03:45', 'equipment': '용접기 #005', 'issue': '전극 수명 경고', 'severity': 'warning', 'status': '미처리', 'details': '전극 사용 시간: 95% (교체 필요)'},
        {'id': 18, 'time': '03:30', 'equipment': '프레스기 #005', 'issue': '유압 시스템 누수', 'severity': 'error', 'status': '미처리', 'details': '유압 오일 누수 감지, 긴급 정비 필요'},
        {'id': 19, 'time': '03:15', 'equipment': '검사기 #004', 'issue': '검사 정확도 저하', 'severity': 'warning', 'status': '처리중', 'details': '검사 정확도: 92% (기준: 95%)'},
        {'id': 20, 'time': '03:00', 'equipment': '조립기 #004', 'issue': '부품 불량 감지', 'severity': 'error', 'status': '미처리', 'details': '부품 불량률: 4.1% (기준: 2.0%)'},
        {'id': 21, 'time': '02:45', 'equipment': '포장기 #003', 'issue': '포장 품질 저하', 'severity': 'warning', 'status': '처리중', 'details': '포장 품질 점수: 85점 (기준: 90점)'},
        {'id': 22, 'time': '02:30', 'equipment': '용접기 #006', 'issue': '용접 강도 부족', 'severity': 'error', 'status': '미처리', 'details': '용접 강도: 78% (기준: 85%)'},
        {'id': 23, 'time': '02:15', 'equipment': '프레스기 #006', 'issue': '압력 변동 폭 증가', 'severity': 'warning', 'status': '처리중', 'details': '압력 변동: ±8% (기준: ±5%)'},
        {'id': 24, 'time': '02:00', 'equipment': '검사기 #005', 'issue': '센서 교정 필요', 'severity': 'warning', 'status': '미처리', 'details': '센서 교정 주기 초과: 15일'}
    ]
    return alerts

def generate_quality_trend():
    """품질 추세 데이터 생성 (불량률 1% 미만, 품질률 99.9% 이상 예시)"""
    days = ['월', '화', '수', '목', '금', '토', '일']
    quality_rates = [99.98, 99.97, 99.99, 99.96, 99.98, 99.95, 99.97]
    production_volume = [1200, 1350, 1180, 1420, 1247, 980, 650]
    defect_rates = [0.02, 0.03, 0.01, 0.04, 0.02, 0.05, 0.03]  # 1% 미만
    # PPM 계산 (불량률 * 1,000,000)
    ppm_values = [rate * 10000 for rate in defect_rates]  # 0.02% = 200 PPM
    return pd.DataFrame({
        'day': days,
        'quality_rate': quality_rates,
        'production_volume': production_volume,
        'defect_rate': defect_rates,
        'PPM': ppm_values
    })

def generate_production_kpi():
    """생산성 KPI 데이터 생성 (불량률 1% 미만, 품질률 99.9% 이상 예시)"""
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
        'quality': 99.98  # 품질률 99.98% (불량률 0.02%)
    }

def download_alerts_csv():
    """알림 데이터를 CSV로 다운로드"""
    alerts = generate_alert_data()
    df = pd.DataFrame(alerts)
    
    # CSV 생성
    csv = df.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="alerts_{datetime.now().strftime("%Y%m%d")}.csv">📥 알림 데이터 다운로드</a>'
    return href



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

        # 센서 데이터 가져오기
        if use_real_api:
            sensor_data = get_sensor_data_from_api(use_real_api)
            if sensor_data is not None and (
                (isinstance(sensor_data, dict) and sensor_data) or
                (isinstance(sensor_data, pd.DataFrame) and not sensor_data.empty)
            ):
                st.session_state.data_cleared = False
                print("[DEBUG] 센서 데이터 제거 플래그 해제됨")
            else:
                sensor_data = generate_sensor_data()
        else:
            sensor_data = generate_sensor_data()

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
                    # 모든 센서 데이터 표시 (첫 번째 설비 기준)
                    if 'equipment' in sensor_data.columns:
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
        
        alerts = get_alerts_from_api(use_real_api) if use_real_api else generate_alert_data()  # API OFF일 때 더미 데이터
        
        # API 데이터를 가져왔으면 데이터 제거 플래그 해제
        if use_real_api and alerts:
            st.session_state.data_cleared = False
            print("[DEBUG] 알림 데이터 제거 플래그 해제됨")
        
        # ERROR와 WARNING 발생한 경우만 필터링
        error_warning_alerts = [a for a in alerts if a['severity'] in ['error', 'warning']]
        
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
        
        if data_cleared and not use_real_api:
            # 데이터가 제거된 경우 빈 테이블 표시
            empty_df = pd.DataFrame(columns=['설비', '상태', '가동률'])
            empty_df.index = range(1, 1)  # 빈 인덱스
            st.dataframe(empty_df, height=250, use_container_width=True)
            st.info("설비 상태 데이터가 없습니다.")
            return
        
        equipment_status = get_equipment_status_from_api(use_real_api) if use_real_api else generate_equipment_status()  # API OFF일 때 더미 데이터
        
        # API 데이터를 가져왔으면 데이터 제거 플래그 해제
        if use_real_api and equipment_status:
            st.session_state.data_cleared = False
            print("[DEBUG] 설비 상태 데이터 제거 플래그 해제됨")
        table_data = []
        for eq in equipment_status:
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

def start_data_update_thread(use_real_api=False):
    """백그라운드에서 데이터를 주기적으로 업데이트하는 스레드"""
    def update_loop():
        while True:
            try:
                # 3초마다 데이터 업데이트
                time.sleep(3)
                
                # 스레드 안전한 방식으로 업데이트 플래그 설정
                if 'last_update' not in st.session_state:
                    st.session_state.last_update = time.time()
                else:
                    st.session_state.last_update = time.time()
                
            except Exception as e:
                print(f"데이터 업데이트 오류: {e}")
                time.sleep(1)
    
    # 백그라운드 스레드 시작
    update_thread = threading.Thread(target=update_loop, daemon=True)
    update_thread.start()
    return update_thread

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
            if efficiency >= 90:
                color = "#10b981"
            elif efficiency >= 70:
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
    
    # 백그라운드 스레드 비활성화 (st_autorefresh 사용)
    print("[DEBUG] 백그라운드 스레드 비활성화됨")
    
    # st_autorefresh를 사용한 자동 새로고침 (API 토글이 ON일 때만)
    auto_refresh = st.session_state.get('auto_refresh', True)
    if auto_refresh and st.session_state.get('api_toggle', False):
        try:
            # 선택된 간격에 따라 자동 새로고침
            refresh_interval = st.session_state.get('refresh_interval_selector', '30초')
            if refresh_interval == '15초':
                interval_ms = 15000
            elif refresh_interval == '30초':
                interval_ms = 30000
            elif refresh_interval == '1분':
                interval_ms = 60000
            elif refresh_interval == '3분':
                interval_ms = 180000
            elif refresh_interval == '5분':
                interval_ms = 300000
            elif refresh_interval == '10분':
                interval_ms = 600000
            else:
                interval_ms = 30000  # 기본값
            
            st_autorefresh(interval=interval_ms, key="auto_refresh")
            print(f"🔄 st_autorefresh 활성화됨 ({refresh_interval} 간격)")
        except Exception as e:
            print(f"⚠️ st_autorefresh 오류: {e}")

    st.markdown(
        '''
        <style>
        .stButton > button {
            background: none !important;
            border: none !important;
            color: #222 !important;
            font-size: 1.08rem !important;
            padding: 0.6rem 1.3rem 0.3rem 1.3rem !important;
            margin: 0 !important;
            cursor: pointer !important;
            outline: none !important;
            border-radius: 0 !important;
            border-bottom: 3px solid transparent !important;
            box-shadow: none !important;
            font-weight: 500 !important;
            transition: color 0.18s, border-bottom 0.18s, background 0.18s;
        }
        .stButton > button.selected {
            color: #2563eb !important;
            border-bottom: 3px solid #2563eb !important;
            font-weight: 700 !important;
            background: #f5faff !important;
        }
        .stButton > button:hover {
            background: #f0f6ff !important;
            color: #1d4ed8 !important;
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
        st.markdown('<div style="font-size:13px; color:#64748b; margin-bottom:0.1rem; margin-top:0.3rem;">공정 선택</div>', unsafe_allow_html=True)
        process = st.selectbox("공정 선택", ["전체 공정", "프레스 공정", "용접 공정", "조립 공정", "검사 공정"], label_visibility="collapsed")
        st.markdown('<div style="font-size:13px; color:#64748b; margin-bottom:0.1rem; margin-top:0.3rem;">설비 필터</div>', unsafe_allow_html=True)
        
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
        </style>
        """, unsafe_allow_html=True)
        
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
        
        # 고정 높이 컨테이너 내에서 multiselect
        equipment_filter_short = st.multiselect(
            "설비 필터",
            equipment_names_short,
            default=equipment_names_short,
            label_visibility="collapsed"
        )
        
        equipment_filter = []
        for short_name in equipment_filter_short:
            for i, full_name in enumerate(equipment_names_full):
                if equipment_names_short[i] == short_name:
                    equipment_filter.append(full_name)
                    break
        st.markdown('<hr style="margin:1.5rem 0 1rem 0; border: none; border-top: 1.5px solid #e2e8f0;" />', unsafe_allow_html=True)
        st.markdown('<div style="font-size:18px; font-weight:bold; margin-bottom:0.5rem; margin-top:0.5rem;">날짜 선택</div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:13px; color:#64748b; margin-bottom:0.1rem; margin-top:0.3rem;">일자 선택</div>', unsafe_allow_html=True)
        selected_date = st.date_input("일자 선택", datetime.now().date(), label_visibility="collapsed")
        st.markdown('<div style="font-size:13px; color:#64748b; margin-bottom:0.1rem; margin-top:0.3rem;">기간 선택</div>', unsafe_allow_html=True)
        date_range = st.date_input(
            "기간 선택",
            value=(datetime.now().date() - timedelta(days=7), datetime.now().date()),
            label_visibility="collapsed"
        )
        st.markdown('<hr style="margin:1.5rem 0 1rem 0; border: none; border-top: 1.5px solid #e2e8f0;" />', unsafe_allow_html=True)
        # 연동 토글 항상 하단에
        use_real_api = st.toggle("API 연동", value=st.session_state.get('api_toggle', False), help="실제 API에서 데이터를 받아옵니다.", key="api_toggle")
        
        # API 토글 상태 변경 감지 및 초기화 (토글 정의 후에 실행)
        if use_real_api != st.session_state.api_toggle_previous:
            # API 토글이 변경되었을 때 컨테이너 초기화
            st.session_state.sensor_container = None
            st.session_state.alert_container = None
            st.session_state.equipment_container = None
            st.session_state.api_toggle_previous = use_real_api
            
            # API 토글이 ON으로 변경되었을 때 데이터베이스 초기화
            if use_real_api:
                print(f"[DEBUG] API 토글 변경 감지: OFF -> ON")
                try:
                    response = requests.post("http://localhost:8000/clear_data", timeout=5)
                    if response.status_code == 200:
                        print("[DEBUG] 데이터베이스 초기화 성공")
                        st.success("API 연동 시작: 데이터베이스가 초기화되었습니다! 시뮬레이터 데이터가 곧 반영됩니다.")
                        # 데이터 제거 플래그 설정
                        st.session_state.data_cleared = True
                    else:
                        print(f"[DEBUG] 데이터베이스 초기화 실패: {response.status_code}")
                        st.warning("API 연동 시작: 데이터 초기화 실패")
                except Exception as e:
                    print(f"[DEBUG] API 서버 연결 실패: {e}")
                    st.warning(f"API 연동 시작: 서버 연결 실패 - {e}")
        
        # 자동 새로고침 설정
        st.markdown('<hr style="margin:1.5rem 0 1rem 0; border: none; border-top: 1.5px solid #e2e8f0;" />', unsafe_allow_html=True)
        st.markdown('<div style="font-size:18px; font-weight:bold; margin-bottom:0.5rem;">🔄 자동 새로고침</div>', unsafe_allow_html=True)
        
        # 새로고침 간격 선택
        refresh_interval = st.selectbox(
            "새로고침 간격",
            ["15초", "30초", "1분", "3분", "5분", "10분", "수동"],
            index=["15초", "30초", "1분", "3분", "5분", "10분", "수동"].index(st.session_state.get('refresh_interval', "30초")),
            key="refresh_interval_selector"
        )
        
        # 자동 새로고침 활성화/비활성화
        auto_refresh = st.checkbox("자동 새로고침 활성화", value=st.session_state.get('auto_refresh', True), key="auto_refresh_checkbox")
        
        # 새로고침 상태 표시
        if auto_refresh and refresh_interval != "수동":
            st.info(f"🔄 {refresh_interval}마다 자동 새로고침")
        elif refresh_interval == "수동":
            st.info("🔄 수동 새로고침 모드")
        
        # 데이터 제거 버튼
        if st.button("🗑️ 데이터 제거", help="기존 센서 데이터와 알림을 모두 삭제합니다."):
            try:
                response = requests.post("http://localhost:8000/clear_data", timeout=5)
                if response.status_code == 200:
                    # 컨테이너 초기화
                    st.session_state.sensor_container = None
                    st.session_state.alert_container = None
                    st.session_state.equipment_container = None
                    # 데이터 초기화 플래그 설정
                    st.session_state.data_cleared = True
                    # 알림 데이터 초기화
                    st.session_state.critical_alerts = []
                    st.session_state.last_alert_count = 0
                    # 마지막 업데이트 시간 초기화
                    st.session_state.last_update = time.time()
                    st.session_state.last_refresh = datetime.now()
                    st.session_state.last_quick_update = time.time()
                    # 데이터 개수 초기화
                    st.session_state.previous_sensor_count = 0
                    st.session_state.previous_alert_count = 0
                    st.success("데이터베이스가 초기화되었습니다!")
                    st.rerun()
                else:
                    st.error("데이터 초기화 실패")
            except Exception as e:
                st.error(f"API 서버 연결 실패: {e}")
    
    with tabs[0]:  # 대시보드
        st.markdown('<div class="main-header no-translate" translate="no" style="margin-bottom:0.5rem; font-size:1.5rem;">🏭 POSCO MOBILITY IoT 대시보드</div>', unsafe_allow_html=True)
        
        # 위험 알림 팝업 표시
        if st.session_state.critical_alerts:
            st.error(f"🚨 **경고 알림 발생!** {len(st.session_state.critical_alerts)}개의 경고 상황이 감지되었습니다.")
            for alert in st.session_state.critical_alerts[:3]:  # 최대 3개만 표시
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
            print("[DEBUG] 데이터 제거 플래그 해제됨")
        
        # API 토글 상태에 따라 데이터 가져오기
        if use_real_api:
            try:
                production_kpi = generate_production_kpi()  # KPI는 더미 데이터 사용
                quality_data = generate_quality_trend()    # 품질 데이터는 더미 데이터 사용
                # 데이터 제거 상태에 따라 알림 데이터 결정
                if data_cleared:
                    alerts = []  # 빈 알림 리스트
                else:
                    alerts = get_alerts_from_api(use_real_api)
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
        
        active_alerts = len([a for a in alerts if a.get('status', '미처리') != '완료'])
        # PPM 계산
        last_defect_rate = quality_data['defect_rate'].iloc[-1]
        last_production_volume = quality_data['production_volume'].iloc[-1]
        ppm = round((last_defect_rate / 100) * last_production_volume / last_production_volume * 1_000_000, 2)
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
            
            # PPM 샘플 데이터 생성
            if ppm_period == "최근 7일":
                days = ['월', '화', '수', '목', '금', '토', '일']
                ppm_values = [450, 380, 520, 290, 410, 350, 480]
            elif ppm_period == "최근 30일":
                days = [f"{i+1}일" for i in range(30)]
                ppm_values = [400 + np.random.randint(-100, 150) for _ in range(30)]
            else:  # 최근 90일
                days = [f"{i+1}일" for i in range(90)]
                ppm_values = [400 + np.random.randint(-100, 150) for _ in range(90)]
            
            # PPM 색상 설정 (높을수록 빨간색)
            colors = []
            for ppm in ppm_values:
                if ppm <= 300:
                    colors.append('#10b981')  # 녹색
                elif ppm <= 500:
                    colors.append('#f59e0b')  # 주황색
                else:
                    colors.append('#ef4444')  # 빨간색
            
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
        
        col1, col2 = st.columns(2)
        
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
            
            # 최근 예측 이력 (가상 데이터)
            st.markdown("**최근 예측 이력:**")
            prediction_history = [
                {"시간": "14:30", "상태": "정상", "확률": 87.2, "결과": "✅"},
                {"시간": "14:25", "상태": "정상", "확률": 91.5, "결과": "✅"},
                {"시간": "14:20", "상태": "베어링 고장", "확률": 23.1, "결과": "✅"},
                {"시간": "14:15", "상태": "정상", "확률": 89.7, "결과": "✅"},
                {"시간": "14:10", "상태": "정상", "확률": 92.3, "결과": "✅"}
            ]
            
            for pred in prediction_history:
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
                
                st.markdown(f"""
                <div style="background: {bg_color}; border-radius: 8px; padding: 0.8rem; margin-bottom: 0.5rem;">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
                        <div style="display: flex; align-items: center; gap: 0.8rem;">
                            <div style="font-weight: 600; color: {status_color}; min-width: 50px;">{pred['시간']}</div>
                            <div style="font-weight: 600; color: #1e293b;">{pred['상태']}</div>
                        </div>
                        <div style="font-size: 1.1rem;">{pred['결과']}</div>
                    </div>
                    <div style="background: #e5e7eb; border-radius: 10px; height: 8px; overflow: hidden;">
                        <div style="background: {status_color}; height: 100%; width: {pred['확률']}%; 
                                    border-radius: 10px; transition: width 0.3s ease;"></div>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-top: 0.3rem;">
                        <span style="font-size: 0.8rem; color: #6b7280;">0%</span>
                        <span style="font-size: 0.8rem; font-weight: 600; color: {status_color};">{pred['확률']}%</span>
                        <span style="font-size: 0.8rem; color: #6b7280;">100%</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        
        with col2:
            st.markdown("#### ⚡ 유압 이상 탐지 모델")
            
            # 모델 성능 지표
            col2_1, col2_2 = st.columns(2)
            with col2_1:
                st.metric("정확도", "91.8%", "-0.2%")
                st.metric("재현율", "89.5%", "0.1%")
            with col2_2:
                st.metric("정밀도", "93.2%", "-0.3%")
                st.metric("F1-Score", "91.3%", "-0.1%")
            
            # 최근 예측 이력 (가상 데이터)
            st.markdown("**최근 예측 이력:**")
            hydraulic_history = [
                {"시간": "14:30", "상태": "정상", "신뢰도": 94.1, "결과": "✅"},
                {"시간": "14:25", "상태": "정상", "신뢰도": 96.2, "결과": "✅"},
                {"시간": "14:20", "상태": "정상", "신뢰도": 92.8, "결과": "✅"},
                {"시간": "14:15", "상태": "정상", "신뢰도": 95.3, "결과": "✅"},
                {"시간": "14:10", "상태": "정상", "신뢰도": 93.7, "결과": "✅"}
            ]
            
            for pred in hydraulic_history:
                if pred["상태"] == "정상":
                    status_color = "#10B981"
                    bg_color = "#ECFDF5"
                else:  # 이상
                    status_color = "#EF4444"
                    bg_color = "#FEF2F2"
                
                st.markdown(f"""
                <div style="background: {bg_color}; border-radius: 8px; padding: 0.8rem; margin-bottom: 0.5rem;">
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
                        <div style="display: flex; align-items: center; gap: 0.8rem;">
                            <div style="font-weight: 600; color: {status_color}; min-width: 50px;">{pred['시간']}</div>
                            <div style="font-weight: 600; color: #1e293b;">{pred['상태']}</div>
                        </div>
                        <div style="font-size: 1.1rem;">{pred['결과']}</div>
                    </div>
                    <div style="background: #e5e7eb; border-radius: 10px; height: 8px; overflow: hidden;">
                        <div style="background: {status_color}; height: 100%; width: {pred['신뢰도']}%; 
                                    border-radius: 10px; transition: width 0.3s ease;"></div>
                    </div>
                    <div style="display: flex; justify-content: space-between; margin-top: 0.3rem;">
                        <span style="font-size: 0.8rem; color: #6b7280;">0%</span>
                        <span style="font-size: 0.8rem; font-weight: 600; color: {status_color};">{pred['신뢰도']}%</span>
                        <span style="font-size: 0.8rem; color: #6b7280;">100%</span>
                    </div>
                </div>
                """, unsafe_allow_html=True)
        
        # AI 설정 및 관리
        st.markdown("### ⚙️ AI 모델 설정 및 관리")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 🔔 알림 설정")
            
            # 알림 임계값 설정
            st.markdown("**설비 이상 예측 알림 임계값:**")
            col1_1, col1_2 = st.columns(2)
            with col1_1:
                bearing_threshold = st.slider("베어링 고장", 0.0, 1.0, 0.6, 0.1, key="bearing_thresh")
                motor_threshold = st.slider("모터 과부하", 0.0, 1.0, 0.7, 0.1, key="motor_thresh")
            with col1_2:
                roll_threshold = st.slider("롤 정렬 불량", 0.0, 1.0, 0.6, 0.1, key="roll_thresh")
                lubricant_threshold = st.slider("윤활유 부족", 0.0, 1.0, 0.7, 0.1, key="lubricant_thresh")
            
            # 유압 시스템 알림 설정
            st.markdown("**유압 시스템 알림 설정:**")
            hydraulic_threshold = st.slider("이상 감지 임계값", 0.0, 1.0, 0.8, 0.05, key="hydraulic_thresh")
            
            # 알림 방법 설정
            st.markdown("**알림 방법:**")
            email_alerts = st.checkbox("이메일 알림", value=True)
            sms_alerts = st.checkbox("SMS 알림", value=False)
            dashboard_alerts = st.checkbox("대시보드 알림", value=True)
            
            if st.button("설정 저장", key="save_ai_settings"):
                st.success("AI 모델 설정이 저장되었습니다.")
        
        with col2:
            st.markdown("#### 📊 모델 관리")
            
            # 모델 재학습 설정
            st.markdown("**자동 재학습 설정:**")
            col2_1, col2_2 = st.columns(2)
            with col2_1:
                st.markdown("**설비 모델:**")
                st.write("• 재학습 주기: 매일")
                st.write("• 마지막 재학습: 2024-01-15")
                st.write("• 다음 재학습: 2024-01-16")
            with col2_2:
                st.markdown("**유압 모델:**")
                st.write("• 재학습 주기: 주 1회")
                st.write("• 마지막 재학습: 2024-01-12")
                st.write("• 다음 재학습: 2024-01-19")
            
            # 수동 모델 관리
            st.markdown("**수동 모델 관리:**")
            col2_3, col2_4 = st.columns(2)
            with col2_3:
                if st.button("설비 모델 재학습", key="retrain_equipment"):
                    st.info("설비 이상 예측 모델 재학습이 시작되었습니다. (예상 소요시간: 30분)")
            with col2_4:
                if st.button("유압 모델 재학습", key="retrain_hydraulic"):
                    st.info("유압 이상 탐지 모델 재학습이 시작되었습니다. (예상 소요시간: 15분)")
            
            # 모델 백업 및 복원
            st.markdown("**모델 백업:**")
            if st.button("현재 모델 백업", key="backup_models"):
                st.success("모델 백업이 완료되었습니다.")
        
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
        st.write("공장 내 주요 설비의 상태, 효율, 정비 이력 등을 한눈에 관리할 수 있습니다.")
        
        # API 토글 상태에 따라 데이터 가져오기
        if use_real_api:
            try:
                equipment_list = get_equipment_status_from_api(use_real_api)
                sensor_data = get_sensor_data_from_api(use_real_api)
                alerts = get_alerts_from_api(use_real_api)
            except Exception as e:
                st.error(f"API 데이터 가져오기 오류: {e}")
                equipment_list = generate_equipment_status()
                sensor_data = generate_sensor_data()
                alerts = generate_alert_data()
        else:
            equipment_list = generate_equipment_status()
            sensor_data = generate_sensor_data()
            alerts = generate_alert_data()
        
        df = pd.DataFrame(equipment_list)
        
        # 빈 데이터프레임 처리
        if df.empty:
            st.info("설비 데이터가 없습니다.")
            st.button("정비 완료(확장)", disabled=True, key="eq_maint_btn_empty")
            st.button("코멘트/이력 추가(확장)", disabled=True, key="eq_comment_btn_empty")
            return
        
        # 상단 KPI 카드
        st.markdown("### 📊 설비 현황 요약")
        col1, col2, col3, col4 = st.columns(4, gap="small")
        
        total_equipment = len(df)
        normal_count = len(df[df['status'] == '정상'])
        warning_count = len(df[df['status'] == '주의'])
        error_count = len(df[df['status'] == '오류'])
        avg_efficiency = df['efficiency'].mean()
        
        with col1:
            st.markdown(f"""
            <div class="kpi-card success no-translate" translate="no" style="padding:0.5rem 0.4rem; min-height:70px; height:80px;">
                <div class="kpi-label" style="font-size:0.9rem;">전체 설비</div>
                <div class="kpi-value" style="font-size:1.3rem;">{total_equipment}대</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.markdown(f"""
            <div class="kpi-card success no-translate" translate="no" style="padding:0.5rem 0.4rem; min-height:70px; height:80px;">
                <div class="kpi-label" style="font-size:0.9rem;">정상 설비</div>
                <div class="kpi-value" style="font-size:1.3rem;">{normal_count}대</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col3:
            st.markdown(f"""
            <div class="kpi-card warning no-translate" translate="no" style="padding:0.5rem 0.4rem; min-height:70px; height:80px;">
                <div class="kpi-label" style="font-size:0.9rem;">주의 설비</div>
                <div class="kpi-value" style="font-size:1.3rem;">{warning_count}대</div>
            </div>
            """, unsafe_allow_html=True)
        
        with col4:
            st.markdown(f"""
            <div class="kpi-card danger no-translate" translate="no" style="padding:0.5rem 0.4rem; min-height:70px; height:80px;">
                <div class="kpi-label" style="font-size:0.9rem;">평균 효율</div>
                <div class="kpi-value" style="font-size:1.3rem;">{avg_efficiency:.1f}%</div>
            </div>
            """, unsafe_allow_html=True)
        
        # 필터 및 검색
        st.markdown("### 🔍 설비 검색 및 필터")
        col1, col2, col3 = st.columns(3)
        with col1:
            type_filter = st.selectbox("설비 타입", ["전체"] + sorted(df['type'].unique()))
        with col2:
            status_filter = st.selectbox("상태", ["전체", "정상", "주의", "오류"])
        with col3:
            search_term = st.text_input("설비명 검색", placeholder="설비명을 입력하세요...")
        
        # 필터링 적용
        filtered = df.copy()
        if type_filter != "전체":
            filtered = filtered[filtered['type'] == type_filter]
        if status_filter != "전체":
            filtered = filtered[filtered['status'] == status_filter]
        if search_term:
            filtered = filtered[filtered['name'].str.contains(search_term, case=False, na=False)]
        
        # 상태 컬러/아이콘 강조
        def status_icon(status):
            return {'정상': '🟢', '주의': '🟠', '오류': '🔴'}.get(status, '⚪') + ' ' + status
        
        filtered['상태'] = filtered['status'].apply(status_icon)
        
        # 설비 목록 표시
        st.markdown("### 📋 설비 목록")
        st.dataframe(filtered[['name', '상태', 'efficiency', 'type', 'last_maintenance']], 
                    use_container_width=True, height=350)
        
        # 상세정보 패널
        if not filtered.empty:
            st.markdown("### 🔧 설비 상세 정보")
            selected = st.selectbox("설비 선택", filtered.index, format_func=lambda i: filtered.loc[i, 'name'])
            
            # 상세 정보 탭
            detail_tab1, detail_tab2, detail_tab3, detail_tab4 = st.tabs(["기본 정보", "실시간 모니터링", "알림 이력", "정비 이력"])
            
            with detail_tab1:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**설비 기본 정보**")
                    st.write(f"**설비 ID:** {filtered.loc[selected, 'id']}")
                    st.write(f"**설비명:** {filtered.loc[selected, 'name']}")
                    st.write(f"**설비 타입:** {filtered.loc[selected, 'type']}")
                    st.write(f"**현재 상태:** {filtered.loc[selected, 'status']}")
                
                with col2:
                    st.markdown("**운영 정보**")
                    st.write(f"**가동률:** {filtered.loc[selected, 'efficiency']}%")
                    st.write(f"**마지막 정비:** {filtered.loc[selected, 'last_maintenance']}")
                    
                    # 상태별 색상 표시
                    status = filtered.loc[selected, 'status']
                    if status == '정상':
                        st.success("✅ 설비가 정상적으로 운영되고 있습니다.")
                    elif status == '주의':
                        st.warning("⚠️ 설비에 주의가 필요합니다. 점검이 권장됩니다.")
                    else:
                        st.error("🚨 설비에 오류가 발생했습니다. 즉시 조치가 필요합니다.")
            
            with detail_tab2:
                st.markdown("**실시간 센서 데이터**")
                
                # 해당 설비의 센서 데이터 필터링
                equipment_name = filtered.loc[selected, 'name']
                
                # 센서 데이터가 DataFrame이고 equipment 컬럼이 있는 경우에만 필터링
                if isinstance(sensor_data, pd.DataFrame) and 'equipment' in sensor_data.columns:
                    equipment_sensor_data = sensor_data[sensor_data['equipment'] == equipment_name]
                    
                    if not equipment_sensor_data.empty:
                        # 센서 데이터 차트
                        fig = go.Figure()
                        
                        # 시간 인덱스 생성
                        time_range = list(range(len(equipment_sensor_data)))
                        
                        # 온도 데이터
                        if 'temperature' in equipment_sensor_data.columns:
                            fig.add_trace(go.Scatter(
                                x=time_range,
                                y=equipment_sensor_data['temperature'],
                                name='온도 (°C)',
                                line=dict(color='#ef4444', width=2)
                            ))
                        
                        # 압력 데이터
                        if 'pressure' in equipment_sensor_data.columns:
                            fig.add_trace(go.Scatter(
                                x=time_range,
                                y=equipment_sensor_data['pressure'],
                                name='압력 (bar)',
                                line=dict(color='#3b82f6', width=2)
                            ))
                        
                        # 진동 데이터
                        if 'vibration' in equipment_sensor_data.columns:
                            fig.add_trace(go.Scatter(
                                x=time_range,
                                y=equipment_sensor_data['vibration'],
                                name='진동 (mm/s)',
                                line=dict(color='#10b981', width=2)
                            ))
                        
                        fig.update_layout(
                            title=f"{equipment_name} 실시간 센서 데이터",
                            xaxis_title="시간",
                            yaxis_title="센서 값",
                            height=300,
                            plot_bgcolor='white',
                            paper_bgcolor='white',
                            margin=dict(l=8, r=8, t=8, b=8),
                            font=dict(color='#1e293b', size=11)
                        )
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # 현재 센서 값 표시
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            if 'temperature' in equipment_sensor_data.columns:
                                current_temp = equipment_sensor_data['temperature'].iloc[-1]
                                st.metric("현재 온도", f"{current_temp:.1f}°C")
                        with col2:
                            if 'pressure' in equipment_sensor_data.columns:
                                current_pressure = equipment_sensor_data['pressure'].iloc[-1]
                                st.metric("현재 압력", f"{current_pressure:.1f} bar")
                        with col3:
                            if 'vibration' in equipment_sensor_data.columns:
                                current_vibration = equipment_sensor_data['vibration'].iloc[-1]
                                st.metric("현재 진동", f"{current_vibration:.2f} mm/s")
                    else:
                        st.info("해당 설비의 센서 데이터가 없습니다.")
                else:
                    # 센서 데이터가 없거나 equipment 컬럼이 없는 경우 더미 데이터 표시
                    st.info("센서 데이터를 불러올 수 없습니다. 더미 데이터를 표시합니다.")
                    
                    # 더미 센서 데이터 생성
                    times = pd.date_range(start=datetime.now() - timedelta(hours=2), end=datetime.now(), freq='5min')
                    dummy_temp = 50 + 12 * np.sin(np.linspace(0, 4*np.pi, len(times))) + np.random.normal(0, 3, len(times))
                    dummy_pressure = 150 + 25 * np.cos(np.linspace(0, 3*np.pi, len(times))) + np.random.normal(0, 5, len(times))
                    dummy_vibration = 0.5 + 0.3 * np.sin(np.linspace(0, 2*np.pi, len(times))) + np.random.normal(0, 0.1, len(times))
                    
                    fig = go.Figure()
                    fig.add_trace(go.Scatter(x=list(range(len(times))), y=dummy_temp, name='온도 (°C)', line=dict(color='#ef4444', width=2)))
                    fig.add_trace(go.Scatter(x=list(range(len(times))), y=dummy_pressure, name='압력 (bar)', line=dict(color='#3b82f6', width=2)))
                    fig.add_trace(go.Scatter(x=list(range(len(times))), y=dummy_vibration, name='진동 (mm/s)', line=dict(color='#10b981', width=2)))
                    
                    fig.update_layout(
                        title=f"{equipment_name} 실시간 센서 데이터 (더미)",
                        xaxis_title="시간",
                        yaxis_title="센서 값",
                        height=300,
                        plot_bgcolor='white',
                        paper_bgcolor='white',
                        margin=dict(l=8, r=8, t=8, b=8),
                        font=dict(color='#1e293b', size=11)
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # 현재 센서 값 표시
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("현재 온도", f"{dummy_temp[-1]:.1f}°C")
                    with col2:
                        st.metric("현재 압력", f"{dummy_pressure[-1]:.1f} bar")
                    with col3:
                        st.metric("현재 진동", f"{dummy_vibration[-1]:.2f} mm/s")
            
            with detail_tab3:
                st.markdown("**최근 알림/이상 이력**")
                
                # 해당 설비의 알림 필터링
                equipment_alerts = [a for a in alerts if a.get('equipment') == equipment_name]
                
                if equipment_alerts:
                    alert_df = pd.DataFrame(equipment_alerts)
                    
                    # 심각도별 색상 적용
                    def sev_icon(sev):
                        return {'error': '🔴', 'warning': '🟠', 'info': '🔵'}.get(sev, '⚪') + ' ' + sev
                    
                    alert_df['심각도'] = alert_df['severity'].apply(sev_icon)
                    
                    # 필요한 컬럼들만 표시
                    display_columns = ['time', 'issue', '심각도', 'status'] if 'status' in alert_df.columns else ['time', 'issue', '심각도']
                    st.dataframe(alert_df[display_columns], use_container_width=True, height=200)
                    
                    # 알림 통계
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**심각도별 알림 통계**")
                        severity_counts = alert_df['severity'].value_counts()
                        st.bar_chart(severity_counts)
                    
                    with col2:
                        st.markdown("**최근 알림 트렌드**")
                        # 시간별 알림 개수 (가상 데이터)
                        hours = list(range(24))
                        alert_counts = [np.random.randint(0, 5) for _ in hours]
                        trend_df = pd.DataFrame({'시간': hours, '알림 수': alert_counts})
                        st.line_chart(trend_df.set_index('시간'))
                else:
                    st.success("✅ 최근 알림/이상 이력이 없습니다.")
            
            with detail_tab4:
                st.markdown("**정비 이력 및 관리**")
                
                # 정비 이력 (가상 데이터)
                maintenance_history = [
                    {"정비일": filtered.loc[selected, 'last_maintenance'], "정비유형": "정기점검", "담당자": "홍길동", "상태": "완료"},
                    {"정비일": "2024-01-10", "정비유형": "부품교체", "담당자": "김철수", "상태": "완료"},
                    {"정비일": "2024-01-05", "정비유형": "긴급수리", "담당자": "박영희", "상태": "완료"},
                    {"정비일": "2023-12-28", "정비유형": "정기점검", "담당자": "홍길동", "상태": "완료"}
                ]
                
                maintenance_df = pd.DataFrame(maintenance_history)
                st.dataframe(maintenance_df, use_container_width=True, height=200)
                
                # 정비 관리 기능
                st.markdown("**정비 관리**")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**정비 완료 등록**")
                    maintenance_type = st.selectbox("정비 유형", ["정기점검", "부품교체", "긴급수리", "기타"], key="maintenance_type")
                    maintenance_worker = st.text_input("담당자", key="maintenance_worker")
                    
                    if st.button("정비 완료 등록", key="maintenance_complete"):
                        st.success("정비 완료가 등록되었습니다.")
                
                with col2:
                    st.markdown("**다음 정비 예정**")
                    next_maintenance = st.date_input("다음 정비일", key="next_maintenance")
                    maintenance_note = st.text_area("정비 메모", key="maintenance_note")
                    
                    if st.button("정비 예정 등록", key="maintenance_schedule"):
                        st.success("정비 예정이 등록되었습니다.")
        
        # 설비 관리 기능
        st.markdown("### ⚙️ 설비 관리 기능")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**설비 상태 변경**")
            if not filtered.empty:
                status_change_equipment = st.selectbox("설비 선택", filtered.index, format_func=lambda i: filtered.loc[i, 'name'], key="status_change")
                new_status = st.selectbox("새 상태", ["정상", "주의", "오류"], key="new_status")
                
                if st.button("상태 변경", key="change_status"):
                    st.success(f"설비 상태가 '{new_status}'로 변경되었습니다.")
        
        with col2:
            st.markdown("**설비 효율 설정**")
            if not filtered.empty:
                efficiency_equipment = st.selectbox("설비 선택", filtered.index, format_func=lambda i: filtered.loc[i, 'name'], key="efficiency_change")
                new_efficiency = st.slider("새 효율 (%)", 0, 100, int(filtered.loc[efficiency_equipment, 'efficiency']), key="new_efficiency")
                
                if st.button("효율 변경", key="change_efficiency"):
                    st.success(f"설비 효율이 {new_efficiency}%로 변경되었습니다.")
        
        with col3:
            st.markdown("**설비 정보 관리**")
            if not filtered.empty:
                info_equipment = st.selectbox("설비 선택", filtered.index, format_func=lambda i: filtered.loc[i, 'name'], key="info_change")
                new_name = st.text_input("새 설비명", value=filtered.loc[info_equipment, 'name'], key="new_name")
                equipment_types = ["프레스기", "용접기", "조립기", "검사기", "포장기"]
                current_type = filtered.loc[info_equipment, 'type']
                try:
                    type_index = equipment_types.index(current_type)
                except ValueError:
                    type_index = 0  # 기본값
                new_type = st.selectbox("새 설비 타입", equipment_types, index=type_index, key="new_type")
                
                if st.button("정보 변경", key="change_info"):
                    st.success("설비 정보가 변경되었습니다.")

    with tabs[2]:  # 알림 관리
        st.markdown('<div class="main-header no-translate" translate="no">🚨 알림 관리</div>', unsafe_allow_html=True)
        st.write("실시간 알림(이상/경보/정보 등)을 확인하고, 처리 상태를 관리할 수 있습니다.")
        
        # API 토글 상태에 따라 데이터 가져오기
        if use_real_api:
            try:
                alerts = get_alerts_from_api(use_real_api)
            except Exception as e:
                st.error(f"API 데이터 가져오기 오류: {e}")
                alerts = generate_alert_data()
        else:
            alerts = generate_alert_data()
        
        adf = pd.DataFrame(alerts)
        
        # 빈 데이터프레임 처리
        if adf.empty:
            st.info("알림 데이터가 없습니다.")
            st.button("상태 변경(확장)", disabled=True, key="alert_status_btn_empty")
            st.download_button("알림 이력 다운로드 (CSV)", "", file_name="alerts.csv", mime="text/csv", key="alert_csv_btn_empty", disabled=True)
            st.button("엑셀 다운로드(확장)", disabled=True, key="alert_excel_btn_empty")
            return
        
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
        
        # 필터링 적용
        filtered = adf.copy()
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
        available_columns = ['equipment', 'issue', 'time', '심각도', 'status']
        if 'details' in filtered.columns:
            available_columns.append('details')
        
        st.dataframe(filtered[available_columns], use_container_width=True, height=350)
        
        # 상세정보 패널
        if not filtered.empty:
            st.markdown("### 🔧 알림 상세 정보")
            selected = st.selectbox("알림 선택", filtered.index, format_func=lambda i: f"{filtered.loc[i, 'equipment']} - {filtered.loc[i, 'issue']}")
            
            # 상세 정보 탭
            alert_detail_tab1, alert_detail_tab2, alert_detail_tab3 = st.tabs(["기본 정보", "처리 이력", "관련 데이터"])
            
            with alert_detail_tab1:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**알림 기본 정보**")
                    st.write(f"**설비:** {filtered.loc[selected, 'equipment']}")
                    st.write(f"**알림 내용:** {filtered.loc[selected, 'issue']}")
                    st.write(f"**발생 시간:** {filtered.loc[selected, 'time']}")
                    st.write(f"**심각도:** {filtered.loc[selected, 'severity']}")
                
                with col2:
                    st.markdown("**처리 정보**")
                    st.write(f"**현재 상태:** {filtered.loc[selected, 'status']}")
                    
                    # 심각도별 색상 표시
                    severity = filtered.loc[selected, 'severity']
                    if severity == 'error':
                        st.error("🚨 긴급 조치가 필요한 알림입니다.")
                    elif severity == 'warning':
                        st.warning("⚠️ 주의가 필요한 알림입니다.")
                    else:
                        st.info("ℹ️ 정보성 알림입니다.")
                    
            # details 컬럼이 있는 경우에만 표시
            if 'details' in filtered.columns:
                st.write(f"**상세 설명:** {filtered.loc[selected, 'details']}")
            else:
                st.write(f"**상세 설명:** 상세 정보 없음")
            
            with alert_detail_tab2:
                st.markdown("**처리 상태 관리**")
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**상태 변경**")
                    current_status = filtered.loc[selected, 'status']
                    new_status = st.selectbox("처리 상태", ["미처리", "처리중", "완료"], 
                                            index=["미처리", "처리중", "완료"].index(current_status), 
                                            key=f"alert_status_{selected}")
                    
                    if st.button("상태 변경", key=f"alert_status_btn_{selected}"):
                        st.success(f"알림 상태가 '{new_status}'로 변경되었습니다.")
                
                with col2:
                    st.markdown("**처리 메모**")
                    processing_note = st.text_area("처리 내용", key=f"processing_note_{selected}")
                    assigned_to = st.text_input("담당자", key=f"assigned_to_{selected}")
                    
                    if st.button("메모 저장", key=f"save_note_{selected}"):
                        st.success("처리 메모가 저장되었습니다.")
                
                # 처리 이력 (가상 데이터)
                st.markdown("**처리 이력**")
                processing_history = [
                    {"시간": filtered.loc[selected, 'time'], "상태": "발생", "담당자": "-", "메모": "알림 발생"},
                    {"시간": "2024-01-15 14:30", "상태": "처리중", "담당자": "홍길동", "메모": "점검 시작"},
                    {"시간": "2024-01-15 15:15", "상태": "완료", "담당자": "홍길동", "메모": "문제 해결 완료"}
                ]
                
                history_df = pd.DataFrame(processing_history)
                st.dataframe(history_df, use_container_width=True, height=150)
            
            with alert_detail_tab3:
                st.markdown("**관련 데이터 분석**")
                
                # 해당 설비의 관련 데이터
                equipment_name = filtered.loc[selected, 'equipment']
                
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**설비 상태**")
                    # 설비 상태 데이터 가져오기
                    if use_real_api:
                        try:
                            equipment_data = get_equipment_status_from_api(use_real_api)
                            equipment_df = pd.DataFrame(equipment_data)
                            equipment_info = equipment_df[equipment_df['name'] == equipment_name]
                            if not equipment_info.empty:
                                st.write(f"**현재 상태:** {equipment_info.iloc[0]['status']}")
                                st.write(f"**가동률:** {equipment_info.iloc[0]['efficiency']}%")
                                st.write(f"**마지막 정비:** {equipment_info.iloc[0]['last_maintenance']}")
                            else:
                                st.info("설비 정보를 찾을 수 없습니다.")
                        except:
                            st.info("설비 정보를 가져올 수 없습니다.")
                    else:
                        st.info("API 연동 시 설비 정보를 확인할 수 있습니다.")
                
                with col2:
                    st.markdown("**유사 알림 패턴**")
                    # 같은 설비의 유사 알림 찾기
                    similar_alerts = filtered[filtered['equipment'] == equipment_name]
                    if len(similar_alerts) > 1:
                        st.write(f"**같은 설비 알림:** {len(similar_alerts)}건")
                        st.write(f"**최근 발생:** {similar_alerts['time'].iloc[-1]}")
                    else:
                        st.write("**같은 설비 알림:** 없음")
        
        # 알림 관리 기능
        st.markdown("### ⚙️ 알림 관리 기능")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**일괄 처리**")
            if not filtered.empty:
                bulk_status = st.selectbox("일괄 상태 변경", ["미처리", "처리중", "완료"], key="bulk_status")
                if st.button("선택된 알림 일괄 처리", key="bulk_process"):
                    st.success(f"선택된 {len(filtered)}건의 알림이 '{bulk_status}'로 변경되었습니다.")
        
        with col2:
            st.markdown("**알림 설정**")
            auto_acknowledge = st.checkbox("자동 확인", value=False, key="auto_ack")
            notification_sound = st.checkbox("알림음", value=True, key="notification_sound_checkbox")
            email_notification = st.checkbox("이메일 알림", value=False, key="email_notification")
            
            if st.button("설정 저장", key="save_alert_settings_alerts"):
                st.success("알림 설정이 저장되었습니다.")
        
        with col3:
            st.markdown("**데이터 내보내기**")
            export_format = st.selectbox("내보내기 형식", ["CSV", "Excel", "PDF"], key="export_format")
            if st.button("데이터 내보내기", key="export_data"):
                st.success(f"{export_format} 형식으로 데이터 내보내기가 시작되었습니다.")
        
        # 알림 통계 및 분석
        st.markdown("### 📈 알림 통계 및 분석")
        
        col1, col2 = st.columns(2)
        
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
        
        with col2:
            st.markdown("**설비별 알림 발생 현황**")
            equipment_counts = adf['equipment'].value_counts().head(10)
            
            fig = go.Figure(data=[go.Bar(x=equipment_counts.values, y=equipment_counts.index, orientation='h')])
            fig.update_layout(
                title="설비별 알림 발생 건수 (상위 10개)",
                height=300,
                plot_bgcolor='white',
                paper_bgcolor='white',
                xaxis_title="알림 건수",
                yaxis_title="설비명"
            )
            st.plotly_chart(fig, use_container_width=True)
        
        # 시간대별 알림 분석
        st.markdown("**시간대별 알림 발생 패턴**")
        
        # 시간대별 알림 개수 (가상 데이터)
        hours = list(range(24))
        alert_counts = [np.random.randint(0, 8) for _ in hours]
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
        st.plotly_chart(fig, use_container_width=True)
        
        # 다운로드 버튼
        st.markdown("### 💾 데이터 내보내기")
        col1, col2 = st.columns(2)
        
        with col1:
            st.download_button("알림 이력 다운로드 (CSV)", adf.to_csv(index=False), 
                             file_name="alerts.csv", mime="text/csv", key="alert_csv_btn")
        
        with col2:
            st.button("엑셀 다운로드(확장)", disabled=True, key="alert_excel_btn")

    with tabs[3]:  # 리포트
        st.markdown('<div class="main-header no-translate" translate="no">📈 리포트</div>', unsafe_allow_html=True)
        st.write("기간별 주요 KPI, 생산량, 불량률, PPM, 알림 통계 등 리포트 상세를 제공합니다.")
        
        # API 토글 상태에 따라 데이터 가져오기
        if use_real_api:
            try:
                production_kpi = generate_production_kpi()  # KPI는 더미 데이터 사용
                quality_data = generate_quality_trend()    # 품질 데이터는 더미 데이터 사용
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
        
        # 기간 선택
        st.markdown("### 📅 리포트 기간 설정")
        col1, col2, col3 = st.columns(3)
        with col1:
            report_range = st.selectbox("리포트 기간", ["최근 7일", "최근 30일", "올해", "전체"])
        with col2:
            report_type = st.selectbox("리포트 유형", ["종합 리포트", "생산성 리포트", "품질 리포트", "설비 리포트", "알림 리포트"])
        with col3:
            if st.button("📊 리포트 생성", key="generate_report"):
                st.success("리포트가 생성되었습니다!")
        
        # KPI 요약
        st.markdown("### 📊 주요 KPI 요약")
        kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4, gap="small")
        
        with kpi_col1:
            st.markdown(f"""
            <div class="kpi-card success no-translate" translate="no" style="padding:0.5rem 0.4rem; min-height:70px; height:80px;">
                <div class="kpi-label" style="font-size:0.9rem;">OEE(설비종합효율)</div>
                <div class="kpi-value" style="font-size:1.3rem;">{production_kpi['oee']:.2f}%</div>
            </div>
            """, unsafe_allow_html=True)
        
        with kpi_col2:
            st.markdown(f"""
            <div class="kpi-card success no-translate" translate="no" style="padding:0.5rem 0.4rem; min-height:70px; height:80px;">
                <div class="kpi-label" style="font-size:0.9rem;">가동률</div>
                <div class="kpi-value" style="font-size:1.3rem;">{production_kpi['availability']:.2f}%</div>
            </div>
            """, unsafe_allow_html=True)
        
        with kpi_col3:
            st.markdown(f"""
            <div class="kpi-card success no-translate" translate="no" style="padding:0.5rem 0.4rem; min-height:70px; height:80px;">
                <div class="kpi-label" style="font-size:0.9rem;">품질률</div>
                <div class="kpi-value" style="font-size:1.3rem;">{production_kpi['quality']:.2f}%</div>
            </div>
            """, unsafe_allow_html=True)
        
        with kpi_col4:
            st.markdown(f"""
            <div class="kpi-card warning no-translate" translate="no" style="padding:0.5rem 0.4rem; min-height:70px; height:80px;">
                <div class="kpi-label" style="font-size:0.9rem;">불량률</div>
                <div class="kpi-value" style="font-size:1.3rem;">{100-production_kpi['quality']:.2f}%</div>
            </div>
            """, unsafe_allow_html=True)
        
        # 상세 분석 탭
        report_tab1, report_tab2, report_tab3, report_tab4 = st.tabs(["생산성 분석", "품질 분석", "설비 분석", "알림 분석"])
        
        with report_tab1:
            st.markdown("### 🏭 생산성 분석")
            
            # 생산량 트렌드
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**일별 생산량 트렌드**")
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=quality_data['day'],
                    y=quality_data['production_volume'],
                    name='생산량',
                    marker_color='#3b82f6'
                ))
                fig.update_layout(
                    title="일별 생산량",
                    xaxis_title="요일",
                    yaxis_title="생산량",
                    height=300,
                    plot_bgcolor='white',
                    paper_bgcolor='white'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.markdown("**생산성 지표**")
                st.metric("일평균 생산량", f"{quality_data['production_volume'].mean():.0f}개")
                st.metric("최대 생산량", f"{quality_data['production_volume'].max():.0f}개")
                st.metric("최소 생산량", f"{quality_data['production_volume'].min():.0f}개")
                st.metric("생산량 변동계수", f"{quality_data['production_volume'].std() / quality_data['production_volume'].mean():.2f}")
            
            # 생산성 상세 테이블 (PPM은 더미 데이터 사용)
            st.markdown("**생산성 상세 데이터**")
            dummy_quality_data = generate_quality_trend()
            detail_df = dummy_quality_data[['day', 'production_volume', 'defect_rate', 'PPM', 'quality_rate']].rename(columns={
                'day': '요일', 'production_volume': '생산량', 'defect_rate': '불량률(%)', 'PPM': 'PPM', 'quality_rate': '품질률(%)'
            })
            st.dataframe(detail_df, use_container_width=True, height=250, hide_index=True)
        
        with report_tab2:
            st.markdown("### 🎯 품질 분석")
            
        # PPM/불량률 이중축 그래프 (항상 더미 데이터 사용)
        st.markdown("**PPM/불량률 추이**")
        dummy_quality_data = generate_quality_trend()
        fig = go.Figure()
        fig.add_trace(go.Bar(x=dummy_quality_data['day'], y=dummy_quality_data['PPM'], name='PPM', marker_color='#3b82f6'))
        fig.add_trace(go.Scatter(x=dummy_quality_data['day'], y=dummy_quality_data['defect_rate'], name='불량률(%)', yaxis='y2', mode='lines+markers', line=dict(color='#ef4444', width=2)))
        fig.update_layout(
            yaxis=dict(title='PPM', side='left'),
            yaxis2=dict(title='불량률(%)', overlaying='y', side='right'),
            xaxis=dict(title='요일'),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            height=300,
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(l=8, r=8, t=8, b=8),
            font=dict(color='#1e293b', size=11)
        )
        st.plotly_chart(fig, use_container_width=True)
        
        # 품질 지표 (항상 더미 데이터 사용)
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("평균 PPM", f"{dummy_quality_data['PPM'].mean():.1f}")
        with col2:
            st.metric("평균 불량률", f"{dummy_quality_data['defect_rate'].mean():.2f}%")
        with col3:
            st.metric("최고 품질률", f"{dummy_quality_data['quality_rate'].max():.2f}%")
        with col4:
            st.metric("품질 개선률", f"{(dummy_quality_data['quality_rate'].iloc[-1] - dummy_quality_data['quality_rate'].iloc[0]):.2f}%")
        
        # 품질 개선 제안 (항상 더미 데이터 사용)
        st.markdown("**품질 개선 제안**")
        if dummy_quality_data['defect_rate'].mean() > 2.0:
            st.warning("⚠️ 평균 불량률이 2%를 초과하고 있습니다. 품질 관리 강화가 필요합니다.")
        elif dummy_quality_data['defect_rate'].mean() > 1.0:
            st.info("ℹ️ 불량률이 1-2% 범위에 있습니다. 지속적인 모니터링이 필요합니다.")
        else:
            st.success("✅ 불량률이 1% 미만으로 양호한 상태입니다.")
        
        with report_tab3:
            st.markdown("### 🔧 설비 분석")
            
            # 설비 상태 분석
            equipment_df = pd.DataFrame(equipment_data)
            
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**설비 상태 분포**")
            status_counts = equipment_df['status'].value_counts()
            
            fig = go.Figure(data=[go.Pie(labels=status_counts.index, values=status_counts.values)])
            fig.update_layout(
                title="설비 상태 분포",
                height=300,
                plot_bgcolor='white',
                paper_bgcolor='white'
            )
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.markdown("**설비 타입별 평균 효율**")
            type_efficiency = equipment_df.groupby('type')['efficiency'].mean()
            
            fig = go.Figure(data=[go.Bar(x=type_efficiency.index, y=type_efficiency.values)])
            fig.update_layout(
                title="설비 타입별 평균 효율",
                xaxis_title="설비 타입",
                yaxis_title="평균 효율 (%)",
                height=300,
                plot_bgcolor='white',
                paper_bgcolor='white'
            )
            st.plotly_chart(fig, use_container_width=True)
            
            # 설비 성능 지표
            st.markdown("**설비 성능 지표**")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("전체 설비 수", len(equipment_df))
            with col2:
                st.metric("평균 효율", f"{equipment_df['efficiency'].mean():.1f}%")
            with col3:
                st.metric("정상 설비", len(equipment_df[equipment_df['status'] == '정상']))
            with col4:
                st.metric("주의/오류 설비", len(equipment_df[equipment_df['status'] != '정상']))
            
            # 설비별 상세 성능
            st.markdown("**설비별 상세 성능**")
            st.dataframe(equipment_df[['name', 'type', 'status', 'efficiency', 'last_maintenance']], 
                        use_container_width=True, height=200)
        
        with report_tab4:
            st.markdown("### 🚨 알림 분석")
            
            # 알림 통계
            alert_df = pd.DataFrame(alerts)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**알림 심각도별 통계**")
                severity_counts = alert_df['severity'].value_counts()
                
                fig = go.Figure(data=[go.Bar(x=severity_counts.index, y=severity_counts.values)])
                fig.update_layout(
                    title="심각도별 알림 분포",
                    xaxis_title="심각도",
                    yaxis_title="알림 건수",
                    height=300,
                    plot_bgcolor='white',
                    paper_bgcolor='white'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.markdown("**설비별 알림 건수**")
                equipment_counts = alert_df['equipment'].value_counts().head(10)
                
                fig = go.Figure(data=[go.Bar(x=equipment_counts.values, y=equipment_counts.index, orientation='h')])
                fig.update_layout(
                    title="설비별 알림 발생 건수 (상위 10개)",
                    xaxis_title="알림 건수",
                    yaxis_title="설비명",
                    height=300,
                    plot_bgcolor='white',
                    paper_bgcolor='white'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            # 알림 지표
            st.markdown("**알림 지표**")
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("전체 알림", len(alert_df))
            with col2:
                st.metric("긴급 알림", len(alert_df[alert_df['severity'] == 'error']))
            with col3:
                st.metric("주의 알림", len(alert_df[alert_df['severity'] == 'warning']))
            with col4:
                st.metric("정보 알림", len(alert_df[alert_df['severity'] == 'info']))
            
            # 알림 패턴 분석
            st.markdown("**알림 패턴 분석**")
            if len(alert_df) > 0:
                most_common_equipment = alert_df['equipment'].mode()[0] if len(alert_df['equipment'].mode()) > 0 else "없음"
                most_common_severity = alert_df['severity'].mode()[0] if len(alert_df['severity'].mode()) > 0 else "없음"
                
                st.write(f"**가장 많은 알림 발생 설비:** {most_common_equipment}")
                st.write(f"**가장 빈번한 알림 유형:** {most_common_severity}")
                
                if len(alert_df[alert_df['severity'] == 'error']) > len(alert_df) * 0.3:
                    st.error("🚨 긴급 알림 비율이 30%를 초과하고 있습니다. 즉시 조치가 필요합니다.")
                elif len(alert_df[alert_df['severity'] == 'error']) > len(alert_df) * 0.1:
                    st.warning("⚠️ 긴급 알림 비율이 10%를 초과하고 있습니다. 주의가 필요합니다.")
                else:
                    st.success("✅ 알림 상황이 양호합니다.")
            else:
                st.success("✅ 알림이 없습니다.")
        
        # 리포트 다운로드 및 공유
        st.markdown("### 💾 리포트 다운로드 및 공유")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            export_format = st.selectbox("내보내기 형식", ["PDF", "Excel", "CSV"], key="report_export_format")
            if st.button("📄 리포트 다운로드", key="download_report"):
                st.success(f"{export_format} 형식으로 리포트가 다운로드되었습니다.")
        
        with col2:
            email_address = st.text_input("이메일 주소", placeholder="example@posco.com", key="report_email")
            if st.button("📧 이메일 전송", key="email_report"):
                if email_address:
                    st.success(f"리포트가 {email_address}로 전송되었습니다.")
                else:
                    st.error("이메일 주소를 입력해주세요.")
        
        with col3:
            schedule_report = st.checkbox("정기 리포트 예약", key="schedule_report")
            if schedule_report:
                schedule_frequency = st.selectbox("전송 주기", ["매일", "매주", "매월"], key="report_frequency")
                if st.button("📅 예약 설정", key="set_schedule"):
                    st.success(f"{schedule_frequency} 정기 리포트가 예약되었습니다.")
        
        # 리포트 히스토리
        st.markdown("### 📚 리포트 히스토리")
        report_history = [
            {"날짜": "2024-01-15", "리포트명": "일일 생산성 리포트", "생성자": "시스템", "상태": "완료"},
            {"날짜": "2024-01-14", "리포트명": "주간 품질 리포트", "생성자": "관리자", "상태": "완료"},
            {"날짜": "2024-01-13", "리포트명": "설비 상태 리포트", "생성자": "시스템", "상태": "완료"},
            {"날짜": "2024-01-12", "리포트명": "월간 종합 리포트", "생성자": "관리자", "상태": "완료"}
        ]
        
        history_df = pd.DataFrame(report_history)
        st.dataframe(history_df, use_container_width=True, height=150)

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
            
            if st.button("일반 설정 저장", key="save_general_settings"):
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
            
            if st.button("알림 설정 저장", key="save_alert_settings"):
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
                        st.success("데이터가 초기화되었습니다.")
            
            if st.button("데이터 설정 저장", key="save_data_settings"):
                st.success("데이터 설정이 저장되었습니다.")
        
        with settings_tab4:
            st.markdown("### 👤 사용자 설정")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("**사용자 정보**")
                username = st.text_input("사용자명", value="관리자", key="username")
                email = st.text_input("이메일", value="admin@posco.com", key="email")
                department = st.selectbox("부서", ["생산관리팀", "품질관리팀", "설비관리팀", "기술팀"], index=0, key="department")
                role = st.selectbox("권한", ["관리자", "운영자", "감시자"], index=0, key="role")
            
            with col2:
                st.markdown("**보안 설정**")
                change_password = st.button("비밀번호 변경", key="change_password")
                two_factor_auth = st.checkbox("2단계 인증", value=False, key="two_factor_auth")
                session_timeout = st.selectbox("세션 타임아웃", ["30분", "1시간", "4시간", "8시간"], index=1, key="session_timeout")
                
                st.markdown("**개인화 설정**")
                default_dashboard = st.selectbox("기본 대시보드", ["메인 대시보드", "설비 관리", "알림 관리", "리포트"], index=0, key="default_dashboard")
                favorite_equipment = st.multiselect("관심 설비", ["프레스기 #1", "용접기 #2", "조립기 #3", "검사기 #4"], key="favorite_equipment")
            
            if st.button("사용자 설정 저장", key="save_user_settings"):
                st.success("사용자 설정이 저장되었습니다.")
        
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

if __name__ == "__main__":
    main()