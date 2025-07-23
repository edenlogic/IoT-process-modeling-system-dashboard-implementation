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

# FastAPI 서버 URL
API_BASE_URL = "http://localhost:8000"

def get_sensor_data_from_api(use_real_api=True):
    """FastAPI에서 센서 데이터 가져오기"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/sensor_data?use_real_api={str(use_real_api).lower()}", timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"센서 데이터 API 연결 오류: {e}")
    return None

def get_equipment_status_from_api(use_real_api=True):
    """FastAPI에서 설비 상태 가져오기"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/equipment_status?use_real_api={str(use_real_api).lower()}", timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"설비 상태 API 연결 오류: {e}")
    return []

def get_alerts_from_api(use_real_api=True):
    """FastAPI에서 알림 데이터 가져오기"""
    try:
        response = requests.get(f"{API_BASE_URL}/api/alerts?use_real_api={str(use_real_api).lower()}", timeout=5)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        st.error(f"알림 데이터 API 연결 오류: {e}")
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
</script>
""", unsafe_allow_html=True)

# 세션 상태 초기화
if 'alerts' not in st.session_state:
    st.session_state.alerts = []
if 'equipment_details' not in st.session_state:
    st.session_state.equipment_details = {}

# 데이터 생성 함수들
@st.cache_data(ttl=60)  # 1분마다 캐시 갱신
def generate_sensor_data():
    """실시간 센서 데이터 생성"""
    times = pd.date_range(start=datetime.now() - timedelta(hours=2), end=datetime.now(), freq='5min')
    
    # 온도 데이터 (20-80도)
    temperature = 50 + 12 * np.sin(np.linspace(0, 4*np.pi, len(times))) + np.random.normal(0, 3, len(times))
    
    # 압력 데이터 (100-200 bar)
    pressure = 150 + 25 * np.cos(np.linspace(0, 3*np.pi, len(times))) + np.random.normal(0, 5, len(times))
    
    # 진동 데이터 추가
    vibration = 0.5 + 0.3 * np.sin(np.linspace(0, 2*np.pi, len(times))) + np.random.normal(0, 0.1, len(times))
    
    return pd.DataFrame({
        'time': times,
        'temperature': temperature,
        'pressure': pressure,
        'vibration': vibration
    })

@st.cache_data(ttl=60)
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

def get_alerts_data():
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

@st.cache_data(ttl=60)
def generate_alert_data():
    """이상 알림 데이터 생성 (더미 데이터)"""
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
        {'id': 16, 'time': '04:00', 'equipment': '포장기 #002', 'issue': '시스템 오류', 'severity': 'error', 'status': '미처리', 'details': 'PLC 통신 오류로 인한 시스템 정지'}
    ]
    return alerts

@st.cache_data(ttl=60)
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

@st.cache_data(ttl=60)
def generate_production_kpi():
    """생산성 KPI 데이터 생성"""
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
        'quality': 97.6
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

    tab_titles = ["대시보드", "설비 관리", "알림 관리", "리포트", "설정"]
    tabs = st.tabs(tab_titles)

    # ----------- 사이드바(필터, AI 연동, 새로고침) 복원 -----------
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
        # 연동 토글 항상 하단에
        use_real_api = st.toggle("실제 API 연동", value=False, help="실제 API에서 데이터를 받아옵니다.")
        use_ai_model = st.toggle("AI 모델 연동", value=False, help="AI 예측/진단 기능을 활성화합니다.")

    with tabs[0]:  # 대시보드
        st.markdown('<div class="main-header no-translate" translate="no" style="margin-bottom:0.5rem; font-size:1.5rem;">🏭 POSCO MOBILITY IoT 대시보드</div>', unsafe_allow_html=True)
        # KPI+AI 카드 2행 3열 (총 6개)
        row1 = st.columns(3, gap="small")
        row2 = st.columns(3, gap="small")
        production_kpi = generate_production_kpi()
        quality_data = generate_quality_trend()
        alerts = get_alerts_from_api(use_real_api) if use_real_api else generate_alert_data()
        active_alerts = len([a for a in alerts if a.get('status', '미처리') != '완료'])
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
        # 6개 정보 3,3으로 2행 배치 (상단: 설비 상태, 실시간 센서, 품질/생산 트렌드 / 하단: 업무 알림, AI 에너지 예측, AI 설비 이상 감지)
        row_top = st.columns(3, gap="small")
        row_bottom = st.columns(3, gap="small")
        # 상단 1행
        # 1. 설비 상태
        with row_top[0]:
            st.markdown('<div class="chart-title no-translate" translate="no" style="font-size:1rem; margin-bottom:0.2rem;">설비 상태</div>', unsafe_allow_html=True)
            equipment_status = get_equipment_status_from_api(use_real_api) if use_real_api else generate_equipment_status()[:6]
            table_data = []
            for eq in equipment_status:
                status_emoji = {'정상':'🟢','주의':'🟠','오류':'🔴'}.get(eq['status'],'🟢')
                table_data.append({
                    '설비': eq['name'],
                    '상태': f"{status_emoji} {eq['status']}",
                    '가동률': f"{eq['efficiency']}%"
                })
            df = pd.DataFrame(table_data)
            st.dataframe(df, height=200, use_container_width=True)
        # 2. 실시간 센서
        with row_top[1]:
            st.markdown('<div class="chart-title no-translate" translate="no" style="font-size:1rem; margin-bottom:0.2rem;">실시간 센서</div>', unsafe_allow_html=True)
            # FastAPI에서 센서 데이터 가져오기
            sensor_data = get_sensor_data_from_api(use_real_api)
            if sensor_data and use_real_api:
                # 실제 API 데이터로 그래프 그리기
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
                # 더미 데이터 사용
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
        # 3. 품질/생산 트렌드
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
        # 4. 업무 알림
        with row_bottom[0]:
            st.markdown('<div class="chart-title no-translate" translate="no" style="font-size:1rem; margin-bottom:0.2rem;">업무 알림</div>', unsafe_allow_html=True)
            filtered_alerts = [a for a in alerts if a['severity'] in ['error','warning','info']][:6]
            table_data = []
            for a in filtered_alerts:
                emoji = {'error':'🔴','warning':'🟠','info':'🔵'}.get(a['severity'],'🔵')
                table_data.append({
                    '설비': a['equipment'],
                    '이슈': f"{emoji} {a['issue']}",
                    '시간': a['time']
                })
            df = pd.DataFrame(table_data)
            st.dataframe(df, height=200, use_container_width=True)
        # 5. AI 에너지 예측 (카드 없이 제목+그래프만, 그래프 height 확대)
        with row_bottom[1]:
            st.markdown('<div class="chart-title no-translate" translate="no" style="font-size:1rem; margin-bottom:0.4rem;">AI 에너지 소비 예측</div>', unsafe_allow_html=True)
            sensor_data = generate_sensor_data()
            st.line_chart(sensor_data['temperature'] + 10 * np.random.rand(len(sensor_data)), height=200)
        # 6. AI 설비 이상 감지 (카드 없이 제목+그래프만, 그래프 height 확대)
        with row_bottom[2]:
            st.markdown('<div class="chart-title no-translate" translate="no" style="font-size:1rem; margin-bottom:0.4rem;">AI 설비 이상 감지</div>', unsafe_allow_html=True)
            sensor_data = generate_sensor_data()
            st.line_chart(sensor_data['vibration'] + 0.2 * (np.arange(len(sensor_data)) > len(sensor_data) * 0.7), height=200)

    with tabs[1]:  # 설비 관리
        st.markdown('<div class="main-header no-translate" translate="no">🏭 설비 관리</div>', unsafe_allow_html=True)
        st.write("공장 내 주요 설비의 상태, 효율, 정비 이력 등을 한눈에 관리할 수 있습니다.")
        equipment_list = generate_equipment_status()
        df = pd.DataFrame(equipment_list)
        # 필터
        col1, col2 = st.columns(2)
        with col1:
            type_filter = st.selectbox("설비 타입", ["전체"] + sorted(df['type'].unique()))
        with col2:
            status_filter = st.selectbox("상태", ["전체", "정상", "주의", "오류"])
        filtered = df[((df['type'] == type_filter) | (type_filter == "전체")) & ((df['status'] == status_filter) | (status_filter == "전체"))]
        # 상태 컬러/아이콘 강조
        def status_icon(status):
            return {'정상': '🟢', '주의': '🟠', '오류': '🔴'}.get(status, '⚪') + ' ' + status
        filtered['상태'] = filtered['status'].apply(status_icon)
        st.dataframe(filtered[['name', '상태', 'efficiency', 'type', 'last_maintenance']], use_container_width=True, height=350)
        # 상세정보 패널
        selected = st.selectbox("설비 선택", filtered.index, format_func=lambda i: filtered.loc[i, 'name'])
        with st.expander(f"상세 정보: {filtered.loc[selected, 'name']}", expanded=True):
            st.write(f"**설비 ID:** {filtered.loc[selected, 'id']}")
            st.write(f"**상태:** {filtered.loc[selected, 'status']}")
            st.write(f"**가동률:** {filtered.loc[selected, 'efficiency']}%")
            st.write(f"**마지막 정비:** {filtered.loc[selected, 'last_maintenance']}")
            st.write(f"**설비 타입:** {filtered.loc[selected, 'type']}")
            st.write("**실시간 센서 데이터**")
            sensor_data = generate_sensor_data()
            st.line_chart(sensor_data[['temperature', 'pressure', 'vibration']])
            st.write("**최근 알림/이상 이력**")
            alert_df = pd.DataFrame([a for a in generate_alert_data() if a['equipment']==filtered.loc[selected, 'name']])
            if not alert_df.empty:
                st.dataframe(alert_df[['time','issue','severity','status','details']], use_container_width=True, height=120)
            else:
                st.info("최근 알림/이상 이력이 없습니다.")
            st.write("**정비 기록 (샘플)**")
            st.dataframe(pd.DataFrame([
                {"정비일": filtered.loc[selected, 'last_maintenance'], "내용": "정기점검", "담당자": "홍길동"}
            ]), use_container_width=True, height=60)
            st.button("정비 완료(확장)", disabled=True, key="eq_maint_btn")
            st.button("코멘트/이력 추가(확장)", disabled=True, key="eq_comment_btn")
            st.info("정비/코멘트/이력 등은 추후 확장 예정입니다.")

    with tabs[2]:  # 알림 관리
        st.markdown('<div class="main-header no-translate" translate="no">🚨 알림 관리</div>', unsafe_allow_html=True)
        st.write("실시간 알림(이상/경보/정보 등)을 확인하고, 처리 상태를 관리할 수 있습니다.")
        alerts = generate_alert_data()
        adf = pd.DataFrame(alerts)
        # 필터
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            eq_filter = st.selectbox("설비별", ["전체"] + sorted(adf['equipment'].unique()))
        with col2:
            sev_filter = st.selectbox("심각도", ["전체", "error", "warning", "info"])
        with col3:
            status_filter = st.selectbox("처리상태", ["전체", "미처리", "처리중", "완료"])
        with col4:
            # 기간 필터(샘플, 실제 구현시 날짜 파싱 필요)
            st.date_input("기간(시작)", key="alert_date_start")
            st.date_input("기간(종료)", key="alert_date_end")
        filtered = adf[((adf['equipment'] == eq_filter) | (eq_filter == "전체")) & ((adf['severity'] == sev_filter) | (sev_filter == "전체")) & ((adf['status'] == status_filter) | (status_filter == "전체"))]
        # 심각도 컬러/아이콘 강조
        def sev_icon(sev):
            return {'error': '🔴', 'warning': '🟠', 'info': '🔵'}.get(sev, '⚪') + ' ' + sev
        filtered['심각도'] = filtered['severity'].apply(sev_icon)
        st.dataframe(filtered[['equipment', 'issue', 'time', '심각도', 'status', 'details']], use_container_width=True, height=350)
        # 상세정보 패널
        selected = st.selectbox("알림 선택", filtered.index, format_func=lambda i: f"{filtered.loc[i, 'equipment']} - {filtered.loc[i, 'issue']}")
        with st.expander(f"상세 내용: {filtered.loc[selected, 'equipment']} - {filtered.loc[selected, 'issue']}", expanded=True):
            st.write(f"**시간:** {filtered.loc[selected, 'time']}")
            st.write(f"**심각도:** {filtered.loc[selected, 'severity']}")
            st.write(f"**상태:** {filtered.loc[selected, 'status']}")
            st.write(f"**상세 설명:** {filtered.loc[selected, 'details']}")
            new_status = st.selectbox("처리 상태", ["미처리", "처리중", "완료"], index=["미처리", "처리중", "완료"].index(filtered.loc[selected, 'status']), key=f"alert_status_{selected}")
            st.button("상태 변경(확장)", disabled=True, key=f"alert_status_btn_{selected}")
            st.info("담당자/정비/첨부 등은 추후 확장 예정입니다.")
        # 다운로드 버튼
        st.download_button("알림 이력 다운로드 (CSV)", adf.to_csv(index=False), file_name="alerts.csv", mime="text/csv", key="alert_csv_btn")
        st.button("엑셀 다운로드(확장)", disabled=True, key="alert_excel_btn")

    with tabs[3]:  # 리포트
        st.markdown('<div class="main-header no-translate" translate="no">📈 리포트</div>', unsafe_allow_html=True)
        st.write("기간별 주요 KPI, 생산량, 불량률, 알림 통계 등 리포트 요약을 제공합니다.")
        # 샘플 기간 선택
        col1, col2 = st.columns(2)
        with col1:
            report_range = st.selectbox("리포트 기간", ["최근 7일", "최근 30일", "올해", "전체"])
        with col2:
            st.button("구현 준비 중", disabled=True, key="report_ready_btn")
        # 샘플 KPI/생산량/불량률/알림 통계 차트
        st.subheader("주요 KPI 요약")
        kpi_data = generate_production_kpi()
        kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4, gap="small")
        with kpi_col1:
            st.metric("OEE(설비종합효율)", f"{kpi_data['oee']}%")
        with kpi_col2:
            st.metric("가동률", f"{kpi_data['availability']}%")
        with kpi_col3:
            st.metric("품질률", f"{kpi_data['quality']}%")
        with kpi_col4:
            st.metric("불량률", f"{100-kpi_data['quality']:.1f}%")
        st.subheader("생산량/불량률 추이")
        quality_data = generate_quality_trend()
        st.line_chart(quality_data.set_index('day')[['production_volume', 'defect_rate']])
        st.subheader("알림 통계 (샘플)")
        alert_df = pd.DataFrame(generate_alert_data())
        st.bar_chart(alert_df['severity'].value_counts())
        st.info("리포트 다운로드(PDF/엑셀), 상세 분석 등은 추후 확장 예정입니다.")

    with tabs[4]:  # 설정
        st.markdown('<div class="main-header no-translate" translate="no">⚙️ 설정</div>', unsafe_allow_html=True)
        st.write("대시보드 환경설정 및 알림, 데이터, 테마 설정을 할 수 있습니다.")
        st.subheader("알림 설정")
        alert_on = st.toggle("알림 수신(ON/OFF)", value=True)
        st.subheader("자동 새로고침 주기")
        refresh_interval = st.selectbox("새로고침 주기", ["30초", "1분", "5분", "수동"], index=0)
        st.subheader("데이터 소스 선택")
        data_source = st.radio("데이터 소스", ["더미 데이터", "실제 API"], index=0, horizontal=True)
        st.subheader("대시보드 테마 설정")
        theme = st.selectbox("테마", ["라이트", "다크"], index=0)
        st.button("구현 준비 중", disabled=True, key="settings_ready_btn")
        st.info("사용자별/권한별 설정, 알림 수신 방법(카톡/이메일), 관리자 로그 등은 추후 확장 예정입니다.")

if __name__ == "__main__":
    main()