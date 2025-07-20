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
    /* 전체 배경 화이트 모드 */
    .main {
        background: #f8fafc;
        padding-top: 1rem;
    }
    
    /* 자연스러운 여백 조정 */
    .block-container {
        padding-top: 1rem;
        padding-bottom: 2rem;
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
    # 네비게이션 바
    st.markdown("""
    <div class="nav-container">
        <ul class="nav-tabs">
            <li class="nav-tab active">📊 대시보드</li>
            <li class="nav-tab">🏭 설비 관리</li>
            <li class="nav-tab">🚨 알림 관리</li>
            <li class="nav-tab">📈 리포트</li>
            <li class="nav-tab">⚙️ 설정</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    # 사이드바 (필터, 날짜 선택)
    with st.sidebar:
        st.markdown('<div class="no-translate" translate="no">### 🔧 필터 설정</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="no-translate" translate="no">**공정 선택**</div>', unsafe_allow_html=True)
        process = st.selectbox("", ["전체 공정", "프레스 공정", "용접 공정", "조립 공정", "검사 공정"], label_visibility="collapsed")
        
        st.markdown('<div class="no-translate" translate="no">**설비 필터**</div>', unsafe_allow_html=True)
        equipment_list = generate_equipment_status()
        
        # 설비 이름을 축약형으로 변환
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
        
        # 축약형 이름으로 필터 표시
        equipment_filter_short = st.multiselect(
            "",
            equipment_names_short,
            default=equipment_names_short,
            label_visibility="collapsed"
        )
        
        # 축약형을 전체 이름으로 변환
        equipment_filter = []
        for short_name in equipment_filter_short:
            for i, full_name in enumerate(equipment_names_full):
                if equipment_names_short[i] == short_name:
                    equipment_filter.append(full_name)
                    break
        
        st.markdown('---')
        st.markdown('<div class="no-translate" translate="no">### 📅 날짜 선택</div>', unsafe_allow_html=True)
        
        st.markdown('<div class="no-translate" translate="no">**일자 선택**</div>', unsafe_allow_html=True)
        selected_date = st.date_input("", datetime.now().date(), label_visibility="collapsed")
        
        st.markdown('<div class="no-translate" translate="no">**기간 선택**</div>', unsafe_allow_html=True)
        date_range = st.date_input(
            "",
            value=(datetime.now().date() - timedelta(days=7), datetime.now().date()),
            label_visibility="collapsed"
        )
        
        st.markdown('---')
        st.markdown('<div class="no-translate" translate="no">### ⚙️ 설정</div>', unsafe_allow_html=True)
        
        # 데이터 소스 토글
        use_real_api = st.toggle("실제 API 연동", value=False, help="실제 API에서 데이터를 받아옵니다.")
        
        # 자동 새로고침
        auto_refresh = st.toggle("자동 새로고침", value=True, help="30초마다 자동으로 데이터를 새로고침합니다.")

    # 자동 새로고침
    if auto_refresh:
        time.sleep(0.1)  # 짧은 지연으로 새로고침 효과

    # 헤더 (좌측 정렬)
    st.markdown('<div class="main-header no-translate" translate="no">🏭 POSCO MOBILITY IoT 대시보드</div>', unsafe_allow_html=True)
    
    # KPI 카드 섹션
    production_kpi = generate_production_kpi()
    
    kpi1, kpi2, kpi3, kpi4 = st.columns(4, gap="large")
    
    with kpi1:
        st.markdown(f"""
        <div class="kpi-card success no-translate" translate="no">
            <div class="kpi-label">전체 가동률</div>
            <div class="kpi-value">{production_kpi['availability']}%</div>
            <div class="kpi-change">
                <div class="status-indicator"></div>
                <span>어제 대비 +2.3%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with kpi2:
        alerts = generate_alert_data()
        active_alerts = len([a for a in alerts if a.get('status', '미처리') != '완료'])
        warning_class = "warning" if active_alerts > 5 else ""
        st.markdown(f"""
        <div class="kpi-card {warning_class} no-translate" translate="no">
            <div class="kpi-label">활성 알림</div>
            <div class="kpi-value">{active_alerts}</div>
            <div class="kpi-change warning">
                <div class="status-indicator warning"></div>
                <span>{len([a for a in alerts if a.get('status', '미처리') == '처리중'])}건 처리 중</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with kpi3:
        st.markdown(f"""
        <div class="kpi-card no-translate" translate="no">
            <div class="kpi-label">일 생산량</div>
            <div class="kpi-value">{production_kpi['daily_actual']:,}</div>
            <div class="kpi-change">
                <div class="status-indicator"></div>
                <span>목표 달성률 {production_kpi['daily_actual']/production_kpi['daily_target']*100:.1f}%</span>
            </div>
        </div>
        """, unsafe_allow_html=True)
    
    with kpi4:
        quality_data = generate_quality_trend()
        current_defect_rate = quality_data['defect_rate'].iloc[-1]
        danger_class = "danger" if current_defect_rate > 2.5 else ""
        st.markdown(f"""
        <div class="kpi-card {danger_class} no-translate" translate="no">
            <div class="kpi-label">불량률</div>
            <div class="kpi-value">{current_defect_rate}%</div>
            <div class="kpi-change {danger_class}">
                <div class="status-indicator {danger_class}"></div>
                <span>{'임계값 초과' if current_defect_rate > 2.5 else '정상 범위 내'}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

    # 메인 콘텐츠 영역
    col1, col2 = st.columns([2, 1], gap="medium")
    
    # 실시간 센서 데이터 차트
    with col1:
        st.markdown('<div class="chart-title no-translate" translate="no">📊 실시간 센서 데이터 <div class="real-time-badge"><div class="status-indicator"></div>LIVE</div></div>', unsafe_allow_html=True)
        
        # 필터
        col_filter1, col_filter2 = st.columns(2)
        with col_filter1:
            sensor_type = st.selectbox("센서 타입", ["온도", "압력", "진동", "전체"])
        with col_filter2:
            time_range = st.selectbox("시간 범위", ["최근 2시간", "최근 6시간", "최근 24시간"])
        
        sensor_data = generate_sensor_data()
        fig = go.Figure()
        
        if sensor_type in ["온도", "전체"]:
            fig.add_trace(go.Scatter(
                x=sensor_data['time'],
                y=sensor_data['temperature'],
                mode='lines',
                name='온도 (°C)',
                line=dict(color='#ef4444', width=3)
            ))
        
        if sensor_type in ["압력", "전체"]:
            fig.add_trace(go.Scatter(
                x=sensor_data['time'],
                y=sensor_data['pressure'],
                mode='lines',
                name='압력 (bar)',
                line=dict(color='#3b82f6', width=3),
                yaxis='y2' if sensor_type == "전체" else 'y'
            ))
        
        if sensor_type in ["진동", "전체"]:
            fig.add_trace(go.Scatter(
                x=sensor_data['time'],
                y=sensor_data['vibration'],
                mode='lines',
                name='진동 (mm/s)',
                line=dict(color='#10b981', width=3),
                yaxis='y3' if sensor_type == "전체" else 'y'
            ))
        
        fig.update_layout(
            height=300,
            margin=dict(l=0, r=0, t=0, b=0),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(title="온도 (°C)", side="left"),
            yaxis2=dict(title="압력 (bar)", overlaying="y", side="right") if sensor_type == "전체" else None,
            yaxis3=dict(title="진동 (mm/s)", overlaying="y", side="right", anchor="free", position=0.95) if sensor_type == "전체" else None,
            xaxis=dict(title="시간"),
            plot_bgcolor='white',
            paper_bgcolor='white',
            font=dict(color='#1e293b')
        )
        st.plotly_chart(fig, use_container_width=True)
    
    # 설비 상태 현황
    with col2:
        st.subheader("🏭 현재 상태")
        
        equipment_status = generate_equipment_status()
        filtered_equipment = [eq for eq in equipment_status if eq['name'] in equipment_filter]
        
        # 데이터가 없을 때 안내 메시지
        if not filtered_equipment:
            st.info("📋 표시할 설비 데이터가 없습니다.")
        else:
            # 테이블형 표시 (고정 높이, 스크롤)
            # 테이블 생성
            table_data = []
            for i, equipment in enumerate(filtered_equipment):
                status_emoji = {
                    '정상': '🟢',
                    '주의': '🟠', 
                    '오류': '🔴',
                    'normal': '🟢',
                    'warning': '🟠',
                    'error': '🔴'
                }.get(equipment.get('status', '정상'), '🟢')
                
                # 상태를 한글로 변환
                status_korean = {
                    '정상': '정상',
                    '주의': '주의', 
                    '오류': '오류',
                    'normal': '정상',
                    'warning': '주의',
                    'error': '오류'
                }.get(equipment.get('status', '정상'), '정상')
                
                table_data.append({
                    '설비명': equipment.get('name', '알 수 없는 설비'),
                    '상태': f"{status_emoji} {status_korean}",
                    '가동률': f"{equipment.get('efficiency', 0)}%",
                    '마지막 업데이트': datetime.now().strftime('%H:%M:%S')
                })
            
            if table_data:
                df = pd.DataFrame(table_data)
                st.dataframe(df, height=300, use_container_width=True)
        
        # 전체 설비 효율성
        if filtered_equipment:
            avg_efficiency = sum(eq.get('efficiency', 0) for eq in filtered_equipment) / len(filtered_equipment)
            st.metric("전체 설비 효율성", f"{avg_efficiency:.1f}%")

    # 하단 영역
    col1, col2 = st.columns([1.2, 1], gap="medium")
    
    # 이상 알림 테이블
    with col1:
        st.subheader("🚨 업무 알림")
        
        # 토글에 따라 데이터 소스 선택
        if use_real_api:
            alerts = get_alerts_data()
        else:
            alerts = generate_alert_data()
        
        # 알림만 필터링 (설비 정보 제외)
        filtered_alerts = []
        for alert in alerts:
            # 알림/경고/이슈만 포함 (설비 상태 정보 제외)
            severity = alert.get('severity', 'info')
            issue_text = alert.get('issue') or alert.get('message') or alert.get('sensor_type') or alert.get('alert_type', '알림')
            
            # 실제 알림/경고/이슈인지 확인
            if (severity in ['error', 'warning', 'info'] and 
                any(keyword in issue_text.lower() for keyword in ['오류', '경고', '알림', '이슈', '임계값', '불량', '정지', '점검'])):
                filtered_alerts.append(alert)
        
        # 데이터가 없을 때 안내 메시지
        if not filtered_alerts:
            st.info("🔔 표시할 알림 데이터가 없습니다.")
        else:
            # 테이블형 표시 (고정 높이, 스크롤)
            # 테이블 생성
            table_data = []
            for i, alert in enumerate(filtered_alerts):
                alert_id = alert.get('id', i)
                severity = alert.get('severity', 'info')
                status = alert.get('status', '미처리')
                
                if 'alert_status' not in st.session_state:
                    st.session_state.alert_status = {}
                
                current_status = st.session_state.alert_status.get(alert_id, status)
                
                severity_emoji = {
                    'error': '🔴',
                    'warning': '🟠',
                    'info': '🔵',
                    'success': '🟢'
                }.get(severity, '🔵')
                
                # 심각도를 한글로 변환
                severity_korean = {
                    'error': '오류',
                    'warning': '경고',
                    'info': '정보',
                    'success': '정상'
                }.get(severity, '정보')
                
                equipment_name = alert.get('equipment') or alert.get('sensor_name') or alert.get('device_name', '알 수 없는 설비')
                issue_text = alert.get('issue') or alert.get('message') or alert.get('sensor_type') or alert.get('alert_type', '알림')
                time_text = alert.get('time') or alert.get('timestamp') or alert.get('created_at', '12:00')
                
                table_data.append({
                    '설비': equipment_name,
                    '이슈': f"{severity_emoji} {issue_text}",
                    '시간': time_text,
                    '상태': current_status,
                    '심각도': severity_korean
                })
            
            if table_data:
                df = pd.DataFrame(table_data)
                st.dataframe(df, height=250, use_container_width=True)
        
        # 알림 다운로드 버튼
        st.markdown(download_alerts_csv(), unsafe_allow_html=True)
    
    # 품질/생산성 트렌드
    with col2:
        st.markdown('<div class="chart-title no-translate" translate="no">📈 품질/생산성 트렌드</div>', unsafe_allow_html=True)
        
        quality_data = generate_quality_trend()
        
        # 차트 타입 선택
        chart_type = st.selectbox("차트 타입", ["품질률", "생산량", "불량률", "전체"])
        
        if chart_type == "품질률":
            colors = ['#10b981' if rate >= 95 else '#f59e0b' if rate >= 90 else '#ef4444' for rate in quality_data['quality_rate']]
            fig = go.Figure(data=[
                go.Bar(
                    x=quality_data['day'],
                    y=quality_data['quality_rate'],
                    marker_color=colors,
                    text=[f'{rate}%' for rate in quality_data['quality_rate']],
                    textposition='inside',
                    textfont=dict(color='white', size=12)
                )
            ])
            fig.update_layout(
                height=250,
                margin=dict(l=0, r=0, t=0, b=0),
                yaxis=dict(title="품질률 (%)", range=[80, 100]),
                xaxis=dict(title="요일"),
                showlegend=False,
                plot_bgcolor='white',
                paper_bgcolor='white',
                font=dict(color='#1e293b')
            )
        elif chart_type == "생산량":
            fig = go.Figure(data=[
                go.Bar(
                    x=quality_data['day'],
                    y=quality_data['production_volume'],
                    marker_color='#3b82f6',
                    text=[f'{vol:,}' for vol in quality_data['production_volume']],
                    textposition='inside',
                    textfont=dict(color='white', size=12)
                )
            ])
            fig.update_layout(
                height=250,
                margin=dict(l=0, r=0, t=0, b=0),
                yaxis=dict(title="생산량 (개)"),
                xaxis=dict(title="요일"),
                showlegend=False,
                plot_bgcolor='white',
                paper_bgcolor='white',
                font=dict(color='#1e293b')
            )
        elif chart_type == "불량률":
            colors = ['#ef4444' if rate > 2.5 else '#f59e0b' if rate > 2.0 else '#10b981' for rate in quality_data['defect_rate']]
            fig = go.Figure(data=[
                go.Bar(
                    x=quality_data['day'],
                    y=quality_data['defect_rate'],
                    marker_color=colors,
                    text=[f'{rate}%' for rate in quality_data['defect_rate']],
                    textposition='inside',
                    textfont=dict(color='white', size=12)
                )
            ])
            fig.update_layout(
                height=250,
                margin=dict(l=0, r=0, t=0, b=0),
                yaxis=dict(title="불량률 (%)", range=[0, 5]),
                xaxis=dict(title="요일"),
                showlegend=False,
                plot_bgcolor='white',
                paper_bgcolor='white',
                font=dict(color='#1e293b')
            )
        else:  # 전체
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=quality_data['day'],
                y=quality_data['quality_rate'],
                mode='lines+markers',
                name='품질률 (%)',
                line=dict(color='#10b981', width=3),
                yaxis='y'
            ))
            fig.add_trace(go.Scatter(
                x=quality_data['day'],
                y=quality_data['production_volume']/15,  # 스케일 조정
                mode='lines+markers',
                name='생산량 (개/15)',
                line=dict(color='#3b82f6', width=3),
                yaxis='y2'
            ))
            fig.add_trace(go.Scatter(
                x=quality_data['day'],
                y=quality_data['defect_rate']*20,  # 스케일 조정
                mode='lines+markers',
                name='불량률 (x20)',
                line=dict(color='#ef4444', width=3),
                yaxis='y3'
            ))
            fig.update_layout(
                height=250,
                margin=dict(l=0, r=0, t=0, b=0),
                yaxis=dict(title="품질률 (%)", side="left"),
                yaxis2=dict(title="생산량 (개/15)", overlaying="y", side="right"),
                yaxis3=dict(title="불량률 (x20)", overlaying="y", side="right", anchor="free", position=0.95),
                xaxis=dict(title="요일"),
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                plot_bgcolor='white',
                paper_bgcolor='white',
                font=dict(color='#1e293b')
            )
        
        st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()