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
import urllib.parse

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
if 'action_history' not in st.session_state:
    st.session_state.action_history = []

def generate_alert_id(equipment: str, sensor_type: str, timestamp: str) -> str:
    """API와 일치하는 알림 ID 생성"""
    # timestamp에서 초 단위까지만 사용 (API와 일치)
    if 'T' in timestamp:
        timestamp_normalized = timestamp.split('.')[0]  # 밀리초 제거
        if len(timestamp_normalized) > 19:  # YYYY-MM-DDTHH:MM:SS
            timestamp_normalized = timestamp_normalized[:19]
    else:
        timestamp_normalized = timestamp
    
    # URL 인코딩
    return urllib.parse.quote(f"{equipment}_{sensor_type}_{timestamp_normalized}")

def get_sensor_data_from_api(use_real_api=True):
    """FastAPI에서 센서 데이터 가져오기"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/sensor_data?use_real_api={str(use_real_api).lower()}", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"센서 데이터 API 오류: {response.status_code}")
    except Exception as e:
        st.error(f"센서 데이터 API 연결 오류: {e}")
    return None

def get_equipment_status_from_api(use_real_api=True):
    """FastAPI에서 설비 상태 가져오기"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/equipment_status?use_real_api={str(use_real_api).lower()}", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"설비 상태 API 오류: {response.status_code}")
    except Exception as e:
        st.error(f"설비 상태 API 연결 오류: {e}")
    return []

def get_alerts_from_api(use_real_api=True):
    """FastAPI에서 알림 데이터 가져오기"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/alerts?use_real_api={str(use_real_api).lower()}", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"알림 데이터 API 오류: {response.status_code}")
    except Exception as e:
        st.error(f"알림 데이터 API 연결 오류: {e}")
    return []

def get_quality_trend_from_api(use_real_api=True):
    """FastAPI에서 품질 추세 데이터 가져오기"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/quality_trend?use_real_api={str(use_real_api).lower()}", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"품질 추세 API 오류: {response.status_code}")
    except Exception as e:
        st.error(f"품질 추세 API 연결 오류: {e}")
    return None

def get_action_history_from_api():
    """FastAPI에서 인터락/바이패스 조치 이력 가져오기"""
    try:
        response = requests.get(f"{API_BASE_URL}/action_history", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"조치 이력 API 오류: {response.status_code}")
    except Exception as e:
        st.error(f"조치 이력 API 연결 오류: {e}")
    return []

def get_action_stats_from_api():
    """FastAPI에서 조치 통계 가져오기"""
    try:
        response = requests.get(f"{API_BASE_URL}/action_stats", timeout=5)
        if response.status_code == 200:
            return response.json()
        else:
            st.error(f"조치 통계 API 오류: {response.status_code}")
    except Exception as e:
        st.error(f"조치 통계 API 연결 오류: {e}")
    return {}

def update_alert_status(alert_id: str, status: str, action_type: str = None):
    """알림 상태 업데이트 (인터락/바이패스 포함)"""
    try:
        params = {
            "status": status,
            "assigned_to": f"dashboard_{st.session_state.get('user_id', 'unknown')}"
        }
        if action_type:
            params["action_type"] = action_type
            
        response = requests.put(
            f"{API_BASE_URL}/alerts/{alert_id}/status",
            params=params,
            timeout=5
        )
        
        if response.status_code == 200:
            st.success(f"✅ {action_type or '상태'} 처리 완료!")
            return True
        else:
            st.error(f"❌ 처리 실패: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        st.error(f"❌ API 오류: {e}")
        return False

# 페이지 설정
st.set_page_config(
    page_title="POSCO MOBILITY IoT 대시보드",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 화이트 모드 CSS 적용 (기존 CSS 유지)
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
    
    /* 조치 버튼 스타일 */
    .action-button {
        padding: 0.5rem 1rem;
        border-radius: 8px;
        font-weight: 600;
        border: none;
        cursor: pointer;
        transition: all 0.3s ease;
    }
    
    .action-button.interlock {
        background: #ef4444;
        color: white;
    }
    
    .action-button.interlock:hover {
        background: #dc2626;
    }
    
    .action-button.bypass {
        background: #f59e0b;
        color: white;
    }
    
    .action-button.bypass:hover {
        background: #f97316;
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
    
    /* 구분선 최적화 */
    hr {
        margin: 1rem 0;
        border: none;
        height: 1px;
        background: #e2e8f0;
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
    
    /* 사이드바 필터 선택 강조(색상만 유지, 배경/밑줄 등은 건드리지 않음) */
    .stSidebar .stMultiSelect [data-baseweb="tag"] {
        background: var(--posco-blue) !important;
        color: #fff !important;
    }
    .stSidebar .stSelectbox [data-baseweb="select"] .css-1n7v3ny-option[aria-selected="true"] {
        background: var(--posco-blue) !important;
        color: #fff !important;
    }
    
    /* 카드 행간 여백을 CSS로 강제 최소화 */
    .block-container .stHorizontalBlock { margin-bottom: 0.01rem !important; }
    .stColumn { margin-bottom: 0.01rem !important; }
    
    /* 사이드바 구분선(hr) 원래대로 */
    .stSidebar hr {
        border: none;
        border-top: 1px solid #e2e8f0 !important;
        margin: 1rem 0 0.5rem 0;
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
                popup.style.cssText = `
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    padding: 16px 24px;
                    border-radius: 8px;
                    color: white;
                    font-weight: 600;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                    z-index: 9999;
                    animation: slideIn 0.3s ease-out;
                    max-width: 350px;
                `;
                popup.style.background = type === 'error' ? 'linear-gradient(135deg, #ef4444, #dc2626)' : 
                                        type === 'warning' ? 'linear-gradient(135deg, #f59e0b, #f97316)' :
                                        'linear-gradient(135deg, #10b981, #059669)';
                popup.innerHTML = message;
                document.body.appendChild(popup);
                
                setTimeout(() => {
                    popup.style.animation = 'slideOut 0.3s ease-in';
                    setTimeout(() => {
                        if (popup && popup.parentNode) {
                            popup.parentNode.removeChild(popup);
                        }
                    }, 300);
                }, 5000);
            } catch (error) {
                console.log('알림 표시 중 오류:', error);
            }
        }
        
        // CSS 애니메이션 추가
        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
            @keyframes slideOut {
                from { transform: translateX(0); opacity: 1; }
                to { transform: translateX(100%); opacity: 0; }
            }
        `;
        document.head.appendChild(style);
        
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
</script>
""", unsafe_allow_html=True)

# 세션 상태 초기화
if 'alerts' not in st.session_state:
    st.session_state.alerts = []
if 'equipment_details' not in st.session_state:
    st.session_state.equipment_details = {}
if 'user_id' not in st.session_state:
    st.session_state.user_id = f"user_{int(time.time())}"

# 데이터 생성 함수들 (기존 함수 유지)
def generate_sensor_data():
    """실시간 센서 데이터 생성"""
    times = pd.date_range(start=datetime.now() - timedelta(hours=2), end=datetime.now(), freq='5min')
    
    temperature = 50 + 12 * np.sin(np.linspace(0, 4*np.pi, len(times))) + np.random.normal(0, 3, len(times))
    pressure = 150 + 25 * np.cos(np.linspace(0, 3*np.pi, len(times))) + np.random.normal(0, 5, len(times))
    vibration = 0.5 + 0.3 * np.sin(np.linspace(0, 2*np.pi, len(times))) + np.random.normal(0, 0.1, len(times))
    
    return pd.DataFrame({
        'time': times,
        'temperature': temperature,
        'pressure': pressure,
        'vibration': vibration
    })

def generate_equipment_status():
    """설비 상태 데이터 생성"""
    equipment = [
        {'id': 'press_001', 'name': '프레스기 #001', 'status': '정상', 'efficiency': 98.2, 'type': '프레스', 'last_maintenance': '2024-01-15'},
        {'id': 'press_002', 'name': '프레스기 #002', 'status': '주의', 'efficiency': 78.5, 'type': '프레스', 'last_maintenance': '2024-01-10'},
        {'id': 'press_003', 'name': '프레스기 #003', 'status': '정상', 'efficiency': 92.1, 'type': '프레스', 'last_maintenance': '2024-01-13'},
        {'id': 'press_004', 'name': '프레스기 #004', 'status': '정상', 'efficiency': 95.8, 'type': '프레스', 'last_maintenance': '2024-01-11'},
        {'id': 'weld_001', 'name': '용접기 #001', 'status': '정상', 'efficiency': 89.3, 'type': '용접', 'last_maintenance': '2024-01-12'},
        {'id': 'weld_002', 'name': '용접기 #002', 'status': '오류', 'efficiency': 0, 'type': '용접', 'last_maintenance': '2024-01-08'},
        {'id': 'weld_003', 'name': '용접기 #003', 'status': '주의', 'efficiency': 82.4, 'type': '용접', 'last_maintenance': '2024-01-09'},
        {'id': 'weld_004', 'name': '용접기 #004', 'status': '정상', 'efficiency': 91.7, 'type': '용접', 'last_maintenance': '2024-01-14'},
        {'id': 'assemble_001', 'name': '조립기 #001', 'status': '정상', 'efficiency': 96.1, 'type': '조립', 'last_maintenance': '2024-01-14'},
        {'id': 'assemble_002', 'name': '조립기 #002', 'status': '정상', 'efficiency': 94.3, 'type': '조립', 'last_maintenance': '2024-01-12'},
        {'id': 'assemble_003', 'name': '조립기 #003', 'status': '주의', 'efficiency': 85.6, 'type': '조립', 'last_maintenance': '2024-01-10'},
        {'id': 'inspect_001', 'name': '검사기 #001', 'status': '오류', 'efficiency': 0, 'type': '검사', 'last_maintenance': '2024-01-05'},
        {'id': 'inspect_002', 'name': '검사기 #002', 'status': '정상', 'efficiency': 97.2, 'type': '검사', 'last_maintenance': '2024-01-13'},
        {'id': 'inspect_003', 'name': '검사기 #003', 'status': '정상', 'efficiency': 93.8, 'type': '검사', 'last_maintenance': '2024-01-11'},
        {'id': 'pack_001', 'name': '포장기 #001', 'status': '정상', 'efficiency': 88.9, 'type': '포장', 'last_maintenance': '2024-01-15'},
        {'id': 'pack_002', 'name': '포장기 #002', 'status': '주의', 'efficiency': 76.2, 'type': '포장', 'last_maintenance': '2024-01-07'}
    ]
    return equipment

def get_alerts_data(use_real_api=True):
    """실제 API에서 알림 데이터 가져오기 (개선된 버전)"""
    try:
        url = f"{API_BASE_URL}/alerts"
        res = requests.get(url, timeout=5)
        if res.status_code == 200:
            api_alerts = res.json()
            formatted_alerts = []
            
            for alert in api_alerts:
                # 데이터 추출 (fallback 처리)
                equipment_name = alert.get('equipment', '알 수 없는 설비')
                sensor_type = alert.get('sensor_type', 'unknown')
                timestamp = alert.get('timestamp', datetime.now().isoformat())
                
                # API와 일치하는 ID 생성
                alert_id = generate_alert_id(equipment_name, sensor_type, timestamp)
                
                # 시간 포맷팅
                time_text = timestamp.split('T')[1][:5] if 'T' in timestamp else '00:00'
                
                # 알림 포맷팅
                formatted_alert = {
                    'id': alert_id,
                    'time': time_text,
                    'equipment': equipment_name,
                    'sensor_type': sensor_type,
                    'value': alert.get('value', 0),
                    'threshold': alert.get('threshold', 0),
                    'issue': alert.get('message', f"{sensor_type} 알림"),
                    'severity': alert.get('severity', 'info'),
                    'status': alert.get('status', '미처리'),
                    'details': f"값: {alert.get('value', 0)}, 임계값: {alert.get('threshold', 0)}",
                    'timestamp': timestamp
                }
                formatted_alerts.append(formatted_alert)
                
            return formatted_alerts
    except Exception as e:
        st.error(f"API 연결 오류: {e}")
    return []

def generate_alert_data():
    """이상 알림 데이터 생성 (더미 데이터)"""
    alerts = [
        {'id': '1', 'time': '14:30', 'equipment': '용접기 #002', 'sensor_type': 'temperature', 'value': 87, 'threshold': 85, 'issue': '온도 임계값 초과', 'severity': 'error', 'status': '미처리', 'details': '현재 온도: 87°C (임계값: 85°C)', 'timestamp': datetime.now().isoformat()},
        {'id': '2', 'time': '13:20', 'equipment': '프레스기 #001', 'sensor_type': 'vibration', 'value': 3.5, 'threshold': 3.0, 'issue': '진동 증가', 'severity': 'warning', 'status': '처리중', 'details': '진동레벨: 높음, 정비 검토 필요', 'timestamp': datetime.now().isoformat()},
        {'id': '3', 'time': '12:15', 'equipment': '검사기 #001', 'sensor_type': 'pressure', 'value': 0, 'threshold': 0.5, 'issue': '비상 정지', 'severity': 'error', 'status': '미처리', 'details': '센서 오류로 인한 비상 정지', 'timestamp': datetime.now().isoformat()},
        {'id': '4', 'time': '11:30', 'equipment': '조립기 #001', 'sensor_type': 'status', 'value': 1, 'threshold': 0, 'issue': '정기점검 완료', 'severity': 'info', 'status': '완료', 'details': '정기점검 완료, 정상 가동 재개', 'timestamp': datetime.now().isoformat()},
    ]
    return alerts

def generate_quality_trend():
    """품질 추세 데이터 생성"""
    days = ['월', '화', '수', '목', '금', '토', '일']
    quality_rates = [98.1, 97.8, 95.5, 99.1, 98.2, 92.3, 94.7]
    production_volume = [1200, 1350, 1180, 1420, 1247, 980, 650]
    defect_rates = [2.1, 1.8, 2.5, 1.9, 2.8, 3.1, 2.2]
    
    return pd.DataFrame({
        'day': days,
        'quality_rate': quality_rates,
        'production_volume': production_volume,
        'defect_rate': defect_rates
    })

def generate_production_kpi():
    """생산성 KPI 데이터 생성"""
    return {
        'daily_target': 1300,
        'daily_actual': 1247,
        'weekly_target': 9100,
        'weekly_actual': 8727,
        'monthly_target': 39000,
        'monthly_actual': 35420,
        'oee': 87.3,
        'availability': 94.2,
        'performance': 92.8,
        'quality': 97.6
    }

def update_sensor_data_container(use_real_api=False):
    """센서 데이터 컨테이너 업데이트"""
    if st.session_state.sensor_container is None:
        st.session_state.sensor_container = st.empty()
    
    with st.session_state.sensor_container.container():
        st.markdown('<div class="chart-title no-translate" translate="no" style="font-size:1rem; margin-bottom:0.2rem;">실시간 센서</div>', unsafe_allow_html=True)
        
        sensor_data = get_sensor_data_from_api(use_real_api)
        if sensor_data and use_real_api:
            fig = go.Figure()
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
            fig.update_layout(
                height=200,
                margin=dict(l=8, r=8, t=8, b=8),
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=9)),
                yaxis=dict(title={'text':"온도", 'font':{'size':9}}, side="left"),
                yaxis2=dict(title="압력", overlaying="y", side="right"),
                xaxis=dict(title={'text':"시간", 'font':{'size':9}}),
                plot_bgcolor='white',
                paper_bgcolor='white',
                font=dict(color='#1e293b', size=9)
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        else:
            sensor_data = generate_sensor_data()
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=sensor_data['time'],
                y=sensor_data['temperature'],
                mode='lines',
                name='온도',
                line=dict(color='#ef4444', width=2)
            ))
            fig.add_trace(go.Scatter(
                x=sensor_data['time'],
                y=sensor_data['pressure'],
                mode='lines',
                name='압력',
                line=dict(color='#3b82f6', width=2),
                yaxis='y2'
            ))
            fig.update_layout(
                height=200,
                margin=dict(l=8, r=8, t=8, b=8),
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1, font=dict(size=9)),
                yaxis=dict(title={'text':"온도", 'font':{'size':9}}, side="left"),
                yaxis2=dict(title="압력", overlaying="y", side="right"),
                xaxis=dict(title={'text':"시간", 'font':{'size':9}}),
                plot_bgcolor='white',
                paper_bgcolor='white',
                font=dict(color='#1e293b', size=9)
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})

def update_alert_container(use_real_api=False):
    """알림 컨테이너 업데이트"""
    if st.session_state.alert_container is None:
        st.session_state.alert_container = st.empty()
    
    with st.session_state.alert_container.container():
        st.markdown('<div class="chart-title no-translate" translate="no" style="font-size:1rem; margin-bottom:0.2rem;">업무 알림</div>', unsafe_allow_html=True)
        
        alerts = get_alerts_data(use_real_api) if use_real_api else generate_alert_data()
        filtered_alerts = [a for a in alerts if a['severity'] in ['error','warning','info']][:6]
        table_data = []
        for a in filtered_alerts:
            emoji = {'error':'🔴','warning':'🟠','info':'🔵'}.get(a['severity'],'🔵')
            status_emoji = {'미처리':'❌','처리중':'⏳','완료':'✅','인터락':'🔒','바이패스':'⏭️'}.get(a['status'],'❓')
            table_data.append({
                '설비': a['equipment'],
                '이슈': f"{emoji} {a['issue']}",
                '상태': f"{status_emoji} {a['status']}",
                '시간': a['time']
            })
        df = pd.DataFrame(table_data)
        st.dataframe(df, height=200, use_container_width=True)

def update_equipment_container(use_real_api=False):
    """설비 상태 컨테이너 업데이트"""
    if st.session_state.equipment_container is None:
        st.session_state.equipment_container = st.empty()
    
    with st.session_state.equipment_container.container():
        st.markdown('<div class="chart-title no-translate" translate="no" style="font-size:1rem; margin-bottom:0.2rem;">설비 상태</div>', unsafe_allow_html=True)
        
        equipment_status = get_equipment_status_from_api(use_real_api) if use_real_api else generate_equipment_status()[:6]
        table_data = []
        for eq in equipment_status:
            status_emoji = {'정상':'🟢','주의':'🟠','오류':'🔴','정지':'🔒'}.get(eq['status'],'🟢')
            table_data.append({
                '설비': eq['name'],
                '상태': f"{status_emoji} {eq['status']}",
                '가동률': f"{eq['efficiency']}%"
            })
        df = pd.DataFrame(table_data)
        st.dataframe(df, height=200, use_container_width=True)

# 메인 대시보드
def main():
    # session_state 초기화
    if 'sensor_container' not in st.session_state:
        st.session_state.sensor_container = None
    if 'alert_container' not in st.session_state:
        st.session_state.alert_container = None
    if 'equipment_container' not in st.session_state:
        st.session_state.equipment_container = None
    if 'update_thread_started' not in st.session_state:
        st.session_state.update_thread_started = False
    
    # 자동 새로고침 설정 (5초마다로 변경)
    if 'last_update' not in st.session_state:
        st.session_state.last_update = time.time()
    
    # 5초마다 자동 새로고침 (페이지 전체가 아닌 데이터만)
    if time.time() - st.session_state.last_update > 5:
        st.session_state.last_update = time.time()
        # 알림 탭에서만 새로고침
        if 'current_tab' in st.session_state and st.session_state.current_tab == 2:
            st.rerun()

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
        </style>
        ''',
        unsafe_allow_html=True
    )

    # 탭 설정 (조치 이력 탭 추가)
    tab_titles = ["대시보드", "설비 관리", "알림 관리", "조치 이력", "리포트", "설정"]
    tabs = st.tabs(tab_titles)
    
    # 현재 탭 저장
    for i, tab in enumerate(tabs):
        if tab:
            st.session_state.current_tab = i

    # 사이드바
    with st.sidebar:
        st.markdown('<div style="font-size:18px; font-weight:bold; margin-bottom:0.5rem; margin-top:0.5rem;">필터 설정</div>', unsafe_allow_html=True)
        st.markdown('<div style="font-size:13px; color:#64748b; margin-bottom:0.2rem; margin-top:0.7rem;">공정 선택</div>', unsafe_allow_html=True)
        process = st.selectbox("", ["전체 공정", "프레스 공정", "용접 공정", "조립 공정", "검사 공정"], label_visibility="collapsed")
        
        st.markdown('<div style="font-size:13px; color:#64748b; margin-bottom:0.2rem; margin-top:0.7rem;">설비 필터</div>', unsafe_allow_html=True)
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
        
        equipment_filter_short = st.multiselect(
            "",
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
        st.markdown('<div style="font-size:13px; color:#64748b; margin-bottom:0.2rem; margin-top:0.7rem;">일자 선택</div>', unsafe_allow_html=True)
        selected_date = st.date_input("", datetime.now().date(), label_visibility="collapsed")
        st.markdown('<div style="font-size:13px; color:#64748b; margin-bottom:0.2rem; margin-top:0.7rem;">기간 선택</div>', unsafe_allow_html=True)
        date_range = st.date_input(
            "",
            value=(datetime.now().date() - timedelta(days=7), datetime.now().date()),
            label_visibility="collapsed"
        )
        
        st.markdown('<hr style="margin:1.5rem 0 1rem 0; border: none; border-top: 1.5px solid #e2e8f0;" />', unsafe_allow_html=True)
        
        # API 연동 설정
        use_real_api = st.toggle("실제 API 연동", value=False, help="실제 API에서 데이터를 받아옵니다.", key="api_toggle")
        use_ai_model = st.toggle("AI 모델 연동", value=False, help="AI 예측/진단 기능을 활성화합니다.", key="ai_toggle")
        
        # 자동 새로고침 설정
        auto_refresh = st.toggle("자동 새로고침", value=True, help="5초마다 데이터를 자동으로 새로고침합니다.")
        
        # 데이터 초기화 버튼
        if st.button("🗑️ 데이터 초기화", help="기존 센서 데이터와 알림을 모두 삭제합니다."):
            try:
                response = requests.post(f"{API_BASE_URL}/clear_data", timeout=5)
                if response.status_code == 200:
                    st.success("데이터베이스가 초기화되었습니다!")
                    st.rerun()
                else:
                    st.error("데이터 초기화 실패")
            except Exception as e:
                st.error(f"API 서버 연결 실패: {e}")
    
    with tabs[0]:  # 대시보드
        st.markdown('<div class="main-header no-translate" translate="no" style="margin-bottom:0.5rem; font-size:1.5rem;">🏭 POSCO MOBILITY IoT 대시보드</div>', unsafe_allow_html=True)
        
        # KPI 카드
        row1 = st.columns(3, gap="small")
        row2 = st.columns(3, gap="small")
        production_kpi = generate_production_kpi()
        quality_data = generate_quality_trend()
        alerts = get_alerts_data(use_real_api) if use_real_api else generate_alert_data()
        active_alerts = len([a for a in alerts if a.get('status', '미처리') not in ['완료', '인터락', '바이패스']])
        current_defect_rate = quality_data['defect_rate'].iloc[-1]
        
        # 1행: 가동률, 불량률, 생산량
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
                <div class="kpi-label" style="font-size:0.9rem;">불량률</div>
                <div class="kpi-value" style="font-size:1.3rem;">{current_defect_rate}%</div>
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
        with row2[1]:
            st.markdown(f"""
            <div class="kpi-card no-translate" translate="no" style="padding:0.5rem 0.4rem; min-height:70px; height:80px;">
                <div class="kpi-label" style="font-size:0.9rem; margin-bottom:0.08rem;">AI 에너지 예측</div>
                <div class="kpi-value" style="font-size:1.1rem; margin-bottom:0.08rem;">1,230 kWh</div>
                <div class="kpi-change warning" style="font-size:0.8rem; margin:0.08rem 0 0 0;">평균 대비 +5%</div>
            </div>
            """, unsafe_allow_html=True)
        with row2[2]:
            st.markdown(f"""
            <div class="kpi-card danger no-translate" translate="no" style="padding:0.5rem 0.4rem; min-height:70px; height:80px;">
                <div class="kpi-label" style="font-size:0.9rem; margin-bottom:0.08rem;">AI 설비 이상</div>
                <div class="kpi-value" style="font-size:1.1rem; margin-bottom:0.08rem;">프레스기 #003</div>
                <div class="kpi-change danger" style="font-size:0.8rem; margin:0.08rem 0 0 0;">진동 이상 감지</div>
            </div>
            """, unsafe_allow_html=True)
        
        # 차트 영역
        row_top = st.columns(3, gap="small")
        row_bottom = st.columns(3, gap="small")
        
        # 상단 1행
        with row_top[0]:
            if st.session_state.equipment_container is None:
                st.session_state.equipment_container = st.empty()
            update_equipment_container(use_real_api)
        
        with row_top[1]:
            if st.session_state.sensor_container is None:
                st.session_state.sensor_container = st.empty()
            update_sensor_data_container(use_real_api)
        
        with row_top[2]:
            st.markdown('<div class="chart-title no-translate" translate="no" style="font-size:1rem; margin-bottom:0.2rem;">품질/생산 트렌드</div>', unsafe_allow_html=True)
            qd = quality_data
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=qd['day'],
                y=qd['quality_rate'],
                name='품질률',
                marker_color=['#10b981' if r>=95 else '#f59e0b' if r>=90 else '#ef4444' for r in qd['quality_rate']],
                text=[f'{r}%' for r in qd['quality_rate']],
                textposition='inside',
                textfont=dict(color='white', size=9)
            ))
            fig.update_layout(
                height=200,
                margin=dict(l=8, r=8, t=8, b=8),
                yaxis=dict(title={'text':"품질률(%)", 'font':{'size':9}}, range=[80,100]),
                xaxis=dict(title={'text':"요일", 'font':{'size':9}}),
                showlegend=False,
                plot_bgcolor='white',
                paper_bgcolor='white',
                font=dict(color='#1e293b', size=9)
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        
        # 하단 2행
        with row_bottom[0]:
            if st.session_state.alert_container is None:
                st.session_state.alert_container = st.empty()
            update_alert_container(use_real_api)
        
        with row_bottom[1]:
            st.markdown('<div class="chart-title no-translate" translate="no" style="font-size:1rem; margin-bottom:0.4rem;">AI 에너지 소비 예측</div>', unsafe_allow_html=True)
            sensor_data = generate_sensor_data()
            st.line_chart(sensor_data['temperature'] + 10 * np.random.rand(len(sensor_data)), height=200)
        
        with row_bottom[2]:
            st.markdown('<div class="chart-title no-translate" translate="no" style="font-size:1rem; margin-bottom:0.4rem;">AI 설비 이상 감지</div>', unsafe_allow_html=True)
            sensor_data = generate_sensor_data()
            st.line_chart(sensor_data['vibration'] + 0.2 * (np.arange(len(sensor_data)) > len(sensor_data) * 0.7), height=200)

    with tabs[1]:  # 설비 관리
        st.markdown('<div class="main-header no-translate" translate="no">🏭 설비 관리</div>', unsafe_allow_html=True)
        st.write("공장 내 주요 설비의 상태, 효율, 정비 이력 등을 한눈에 관리할 수 있습니다.")
        
        equipment_list = get_equipment_status_from_api(use_real_api) if use_real_api else generate_equipment_status()
        df = pd.DataFrame(equipment_list)
        
        # 필터
        col1, col2 = st.columns(2)
        with col1:
            type_filter = st.selectbox("설비 타입", ["전체"] + sorted(df['type'].unique()))
        with col2:
            status_filter = st.selectbox("상태", ["전체", "정상", "주의", "오류", "정지"])
        
        filtered = df[((df['type'] == type_filter) | (type_filter == "전체")) & ((df['status'] == status_filter) | (status_filter == "전체"))]
        
        # 상태 컬러/아이콘 강조
        def status_icon(status):
            return {'정상': '🟢', '주의': '🟠', '오류': '🔴', '정지': '🔒'}.get(status, '⚪') + ' ' + status
        filtered['상태'] = filtered['status'].apply(status_icon)
        
        st.dataframe(filtered[['name', '상태', 'efficiency', 'type', 'last_maintenance']], use_container_width=True, height=350)
        
        # 상세정보 패널
        if len(filtered) > 0:
            selected = st.selectbox("설비 선택", filtered.index, format_func=lambda i: filtered.loc[i, 'name'])
            with st.expander(f"상세 정보: {filtered.loc[selected, 'name']}", expanded=True):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**설비 ID:** {filtered.loc[selected, 'id']}")
                    st.write(f"**상태:** {filtered.loc[selected, 'status']}")
                    st.write(f"**가동률:** {filtered.loc[selected, 'efficiency']}%")
                with col2:
                    st.write(f"**마지막 정비:** {filtered.loc[selected, 'last_maintenance']}")
                    st.write(f"**설비 타입:** {filtered.loc[selected, 'type']}")
                    
                st.write("**실시간 센서 데이터**")
                sensor_data = generate_sensor_data()
                st.line_chart(sensor_data[['temperature', 'pressure', 'vibration']])

    with tabs[2]:  # 알림 관리
        st.markdown('<div class="main-header no-translate" translate="no">🚨 알림 관리</div>', unsafe_allow_html=True)
        st.write("실시간 알림(이상/경보/정보 등)을 확인하고, 처리 상태를 관리할 수 있습니다.")
        
        # 새로고침 버튼 추가
        col1, col2 = st.columns([10, 1])
        with col2:
            if st.button("🔄 새로고침"):
                st.rerun()
        
        alerts = get_alerts_data(use_real_api) if use_real_api else generate_alert_data()
        adf = pd.DataFrame(alerts)
        
        if len(adf) > 0:
            # 필터
            col1, col2, col3 = st.columns(3)
            with col1:
                eq_filter = st.selectbox("설비별", ["전체"] + sorted(adf['equipment'].unique()))
            with col2:
                sev_filter = st.selectbox("심각도", ["전체", "error", "warning", "info"])
            with col3:
                status_filter = st.selectbox("처리상태", ["전체", "미처리", "처리중", "완료", "인터락", "바이패스"])
            
            filtered = adf[
                ((adf['equipment'] == eq_filter) | (eq_filter == "전체")) & 
                ((adf['severity'] == sev_filter) | (sev_filter == "전체")) & 
                ((adf['status'] == status_filter) | (status_filter == "전체"))
            ]
            
            # 심각도 컬러/아이콘 강조
            def sev_icon(sev):
                return {'error': '🔴', 'warning': '🟠', 'info': '🔵'}.get(sev, '⚪') + ' ' + sev
            
            def status_badge(status):
                return {'미처리': '❌', '처리중': '⏳', '완료': '✅', '인터락': '🔒', '바이패스': '⏭️'}.get(status, '❓') + ' ' + status
            
            filtered['심각도'] = filtered['severity'].apply(sev_icon)
            filtered['처리상태'] = filtered['status'].apply(status_badge)
            
            # 테이블 표시
            display_cols = ['equipment', 'sensor_type', 'value', 'threshold', 'issue', 'time', '심각도', '처리상태']
            st.dataframe(filtered[display_cols], use_container_width=True, height=350)
            
            # 상세정보 및 조치 패널
            if len(filtered) > 0:
                selected_idx = st.selectbox(
                    "알림 선택", 
                    filtered.index, 
                    format_func=lambda i: f"{filtered.loc[i, 'equipment']} - {filtered.loc[i, 'issue']} ({filtered.loc[i, 'time']})"
                )
                
                selected_alert = filtered.loc[selected_idx]
                
                with st.expander(f"상세 내용: {selected_alert['equipment']} - {selected_alert['issue']}", expanded=True):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**시간:** {selected_alert['time']}")
                        st.write(f"**심각도:** {selected_alert['severity']}")
                        st.write(f"**상태:** {selected_alert['status']}")
                        st.write(f"**센서:** {selected_alert.get('sensor_type', 'N/A')}")
                    
                    with col2:
                        st.write(f"**측정값:** {selected_alert.get('value', 'N/A')}")
                        st.write(f"**임계값:** {selected_alert.get('threshold', 'N/A')}")
                        st.write(f"**상세 설명:** {selected_alert['details']}")
                    
                    # 조치 버튼 (미처리 또는 처리중인 경우만)
                    if selected_alert['status'] in ['미처리', '처리중']:
                        st.write("---")
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            if st.button("🚨 인터락 (즉시정지)", type="primary", key=f"interlock_{selected_idx}"):
                                if update_alert_status(selected_alert['id'], "인터락", "interlock"):
                                    st.success("✅ 인터락 실행됨 - 설비가 즉시 정지되었습니다!")
                                    time.sleep(1)
                                    st.rerun()
                        
                        with col2:
                            if st.button("⏭️ 바이패스 (일시무시)", key=f"bypass_{selected_idx}"):
                                if update_alert_status(selected_alert['id'], "바이패스", "bypass"):
                                    st.warning("⏭️ 바이패스 적용됨 - 30분간 알림이 무시됩니다.")
                                    time.sleep(1)
                                    st.rerun()
                        
                        with col3:
                            if st.button("✅ 처리 완료", key=f"complete_{selected_idx}"):
                                if update_alert_status(selected_alert['id'], "완료"):
                                    st.success("✅ 알림이 처리 완료되었습니다.")
                                    time.sleep(1)
                                    st.rerun()
                    else:
                        st.info(f"이 알림은 이미 '{selected_alert['status']}' 상태입니다.")
        else:
            st.info("현재 알림이 없습니다.")

    with tabs[3]:  # 조치 이력
        st.markdown('<div class="main-header no-translate" translate="no">📋 조치 이력</div>', unsafe_allow_html=True)
        st.write("인터락 및 바이패스 조치 이력을 확인할 수 있습니다.")
        
        # 조치 통계 표시
        action_stats = get_action_stats_from_api()
        if action_stats:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("총 조치 수", f"{action_stats.get('total_actions', 0)}건")
            with col2:
                st.metric("인터락 조치", f"{action_stats.get('interlock_count', 0)}건", 
                         delta="설비 정지", delta_color="normal")
            with col3:
                st.metric("바이패스 조치", f"{action_stats.get('bypass_count', 0)}건",
                         delta="일시 무시", delta_color="normal")
        
        # 조치 이력 테이블
        st.subheader("최근 조치 이력")
        action_history = get_action_history_from_api()
        
        if action_history:
            # 데이터프레임 생성
            history_data = []
            for action in action_history:
                history_data.append({
                    '시간': action.get('action_time', '').split('T')[1][:8] if 'T' in action.get('action_time', '') else '',
                    '설비': action.get('equipment', ''),
                    '센서': action.get('sensor_type', ''),
                    '조치': '🔒 인터락' if action.get('action_type') == 'interlock' else '⏭️ 바이패스',
                    '담당자': action.get('assigned_to', ''),
                    '측정값': f"{action.get('value', 0):.2f}",
                    '임계값': f"{action.get('threshold', 0):.2f}",
                    '심각도': {'error': '🔴 Error', 'warning': '🟠 Warning', 'info': '🔵 Info'}.get(action.get('severity', ''), ''),
                })
            
            history_df = pd.DataFrame(history_data)
            st.dataframe(history_df, use_container_width=True, height=400)
            
            # 설비별 통계
            if 'equipment_stats' in action_stats and action_stats['equipment_stats']:
                st.subheader("설비별 조치 통계")
                eq_stats_data = []
                for eq, stats in action_stats['equipment_stats'].items():
                    eq_stats_data.append({
                        '설비': eq,
                        '인터락': stats.get('interlock', 0),
                        '바이패스': stats.get('bypass', 0),
                        '총 조치': stats.get('interlock', 0) + stats.get('bypass', 0)
                    })
                
                eq_stats_df = pd.DataFrame(eq_stats_data)
                eq_stats_df = eq_stats_df.sort_values('총 조치', ascending=False)
                
                # 막대 그래프
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    name='인터락',
                    x=eq_stats_df['설비'],
                    y=eq_stats_df['인터락'],
                    marker_color='#ef4444'
                ))
                fig.add_trace(go.Bar(
                    name='바이패스',
                    x=eq_stats_df['설비'],
                    y=eq_stats_df['바이패스'],
                    marker_color='#f59e0b'
                ))
                
                fig.update_layout(
                    barmode='stack',
                    title='설비별 조치 현황',
                    height=300,
                    margin=dict(l=0, r=0, t=30, b=0),
                    plot_bgcolor='white',
                    paper_bgcolor='white'
                )
                
                st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("조치 이력이 없습니다.")

    with tabs[4]:  # 리포트
        st.markdown('<div class="main-header no-translate" translate="no">📈 리포트</div>', unsafe_allow_html=True)
        st.write("기간별 주요 KPI, 생산량, 불량률, 알림 통계 등 리포트 요약을 제공합니다.")
        
        # 기간 선택
        col1, col2 = st.columns(2)
        with col1:
            report_range = st.selectbox("리포트 기간", ["최근 7일", "최근 30일", "올해", "전체"])
        with col2:
            if st.button("📊 리포트 생성"):
                st.info("리포트 생성 중...")
        
        # KPI 요약
        st.subheader("주요 KPI 요약")
        kpi_data = generate_production_kpi()
        
        kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4, gap="small")
        with kpi_col1:
            st.metric("OEE(설비종합효율)", f"{kpi_data['oee']}%", delta="+2.3%")
        with kpi_col2:
            st.metric("가동률", f"{kpi_data['availability']}%", delta="+1.2%")
        with kpi_col3:
            st.metric("품질률", f"{kpi_data['quality']}%", delta="-0.5%")
        with kpi_col4:
            st.metric("불량률", f"{100-kpi_data['quality']:.1f}%", delta="+0.5%", delta_color="inverse")
        
        # 생산량/불량률 추이
        st.subheader("생산량/불량률 추이")
        quality_data = generate_quality_trend()
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=quality_data['day'],
            y=quality_data['production_volume'],
            name='생산량',
            mode='lines+markers',
            line=dict(color='#3b82f6', width=3),
            yaxis='y'
        ))
        fig.add_trace(go.Scatter(
            x=quality_data['day'],
            y=quality_data['defect_rate'],
            name='불량률(%)',
            mode='lines+markers',
            line=dict(color='#ef4444', width=3),
            yaxis='y2'
        ))
        
        fig.update_layout(
            title='주간 생산 현황',
            height=400,
            yaxis=dict(title='생산량', side='left'),
            yaxis2=dict(title='불량률(%)', overlaying='y', side='right'),
            hovermode='x unified',
            plot_bgcolor='white',
            paper_bgcolor='white'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # 알림 통계
        st.subheader("알림 통계")
        alerts = get_alerts_data(use_real_api) if use_real_api else generate_alert_data()
        if alerts:
            alert_df = pd.DataFrame(alerts)
            
            col1, col2 = st.columns(2)
            
            with col1:
                # 심각도별 통계
                severity_counts = alert_df['severity'].value_counts()
                fig = go.Figure(data=[go.Pie(
                    labels=['🔴 Error', '🟠 Warning', '🔵 Info'],
                    values=[
                        severity_counts.get('error', 0),
                        severity_counts.get('warning', 0),
                        severity_counts.get('info', 0)
                    ],
                    hole=.3,
                    marker_colors=['#ef4444', '#f59e0b', '#3b82f6']
                )])
                fig.update_layout(
                    title='심각도별 알림 분포',
                    height=300,
                    margin=dict(l=0, r=0, t=30, b=0)
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                # 설비별 알림 수
                equipment_counts = alert_df['equipment'].value_counts().head(5)
                fig = go.Figure(data=[go.Bar(
                    x=equipment_counts.values,
                    y=equipment_counts.index,
                    orientation='h',
                    marker_color='#3b82f6'
                )])
                fig.update_layout(
                    title='설비별 알림 수 (Top 5)',
                    height=300,
                    margin=dict(l=0, r=0, t=30, b=0),
                    xaxis_title='알림 수',
                    plot_bgcolor='white',
                    paper_bgcolor='white'
                )
                st.plotly_chart(fig, use_container_width=True)
        
        # 다운로드 버튼
        st.write("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.download_button(
                "📥 리포트 다운로드 (CSV)",
                data=quality_data.to_csv(index=False),
                file_name=f"report_{datetime.now().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )
        with col2:
            st.button("📄 PDF 리포트 생성", disabled=True)
        with col3:
            st.button("📊 상세 분석 보기", disabled=True)

    with tabs[5]:  # 설정
        st.markdown('<div class="main-header no-translate" translate="no">⚙️ 설정</div>', unsafe_allow_html=True)
        st.write("대시보드 환경설정 및 알림, 데이터, 테마 설정을 할 수 있습니다.")
        
        # 알림 설정
        st.subheader("🔔 알림 설정")
        col1, col2 = st.columns(2)
        with col1:
            alert_on = st.toggle("알림 수신(ON/OFF)", value=True)
            alert_sound = st.toggle("알림음 사용", value=False)
        with col2:
            alert_level = st.select_slider(
                "알림 수준",
                options=["모든 알림", "Warning 이상", "Error만"],
                value="Warning 이상"
            )
        
        # 자동 새로고침 설정
        st.subheader("🔄 자동 새로고침")
        refresh_interval = st.selectbox(
            "새로고침 주기",
            ["5초", "10초", "30초", "1분", "5분", "수동"],
            index=0
        )
        
        # 데이터 소스 설정
        st.subheader("📊 데이터 소스")
        data_source = st.radio(
            "데이터 소스 선택",
            ["더미 데이터", "실제 API", "CSV 파일"],
            index=1 if use_real_api else 0,
            horizontal=True
        )
        
        if data_source == "CSV 파일":
            uploaded_file = st.file_uploader("CSV 파일 업로드", type=['csv'])
            if uploaded_file:
                st.success("파일 업로드 완료!")
        
        # 테마 설정
        st.subheader("🎨 테마 설정")
        theme = st.selectbox("테마", ["라이트", "다크", "자동"], index=0)
        primary_color = st.color_picker("주 색상", "#05507D")
        
        # 사용자 설정
        st.subheader("👤 사용자 설정")
        user_name = st.text_input("사용자 이름", value="운영자")
        user_role = st.selectbox("권한", ["관리자", "운영자", "뷰어"])
        
        # 저장 버튼
        st.write("---")
        if st.button("💾 설정 저장", type="primary"):
            st.success("✅ 설정이 저장되었습니다!")
            # 실제로는 여기서 설정을 저장하는 로직 구현
            
        # 고급 설정
        with st.expander("🔧 고급 설정"):
            st.write("**API 설정**")
            api_url = st.text_input("API URL", value=API_BASE_URL)
            api_timeout = st.number_input("API 타임아웃(초)", value=5, min_value=1, max_value=60)
            
            st.write("**알림 필터링**")
            min_alert_interval = st.number_input(
                "동일 알림 최소 간격(분)",
                value=5,
                min_value=1,
                max_value=60,
                help="동일한 알림이 반복될 때 최소 대기 시간"
            )
            
            st.write("**성능 설정**")
            max_chart_points = st.number_input(
                "차트 최대 데이터 포인트",
                value=100,
                min_value=50,
                max_value=1000,
                step=50
            )

if __name__ == "__main__":
    main()