import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import numpy as np
import time
import requests

# 페이지 설정
st.set_page_config(
    page_title="POSCO Mobility IoT 대시보드",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 커스텀 CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f2937;
        margin-bottom: 1rem;
    }
    
    .kpi-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        text-align: center;
        border: 1px solid #e5e7eb;
    }
    
    .kpi-value {
        font-size: 2rem;
        font-weight: bold;
        color: #1f2937;
        margin-bottom: 0.5rem;
    }
    
    .kpi-label {
        font-size: 0.9rem;
        color: #6b7280;
    }
    
    .sidebar-section {
        background: #f9fafb;
        padding: 1rem;
        border-radius: 8px;
        margin-bottom: 1rem;
        border: 1px solid #e5e7eb;
    }
    
    .chart-container {
        background: white;
        padding: 1.5rem;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
        border: 1px solid #e5e7eb;
    }
    
    .chart-title {
        font-size: 1.2rem;
        font-weight: bold;
        color: #1f2937;
        margin-bottom: 1rem;
    }
    
    .equipment-card {
        background: white;
        padding: 1rem;
        border-radius: 8px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        margin-bottom: 0.5rem;
        border: 1px solid #e5e7eb;
    }
    
    .status-normal { color: #10b981; }
    .status-warning { color: #f59e0b; }
    .status-error { color: #ef4444; }
    
    .alert-table {
        background: white;
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid #e5e7eb;
    }
</style>
""", unsafe_allow_html=True)

# 선택된 멀티셀렉트/날짜 색상 파란색으로 변경 (강조 아님)
st.markdown('''
<style>
/* 멀티셀렉트 선택된 값(태그) 파란색 */
span[data-baseweb="tag"] {
    background-color: #2563eb !important;
    color: #fff !important;
    border-radius: 6px !important;
}
/* date_input 캘린더에서 선택된 날짜 파란색 (다양한 버전 대응) */
div[role="dialog"] [aria-selected="true"],
div[role="dialog"] [data-selected="true"],
.css-1d391kg[aria-selected="true"],
.css-1v5z18m[aria-selected="true"],
.css-1d391kg[data-selected="true"],
.css-1v5z18m[data-selected="true"] {
    background: #2563eb !important;
    color: #fff !important;
}
/* 대제목 위 여백 조정 /
.stElementContainer.element-container.st-emotion-cache-v3w3zg.eertqu00 {
    margin-top: 0.0rem !important;
    padding-top: 0.0rem !important;
}
/* 첫 번째 stElementContainer 여백 조정 */
div[data-testid="stVerticalBlock"] > div:first-child {
    margin-top: 0.0rem !important;
    padding-top: 0.0rem !important;
}
</style>
''', unsafe_allow_html=True)

# chart-container 스타일을 st.container()에 맞게 전역 적용
st.markdown('''
<style>
.st-card {
    background: #fff;
    border-radius: 8px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    border: 1px solid #e5e7eb;
    padding: 1.5rem 1.2rem 1.2rem 1.2rem;
    margin-bottom: 1.2rem;
}
.st-card-title {
    font-size: 1.2rem;
    font-weight: bold;
    color: #1f2937;
    margin-bottom: 1rem;
}
</style>
''', unsafe_allow_html=True)

# 샘플 데이터 생성 함수
@st.cache_data
def generate_sensor_data():
    """실시간 센서 데이터 생성"""
    times = pd.date_range(start=datetime.now() - timedelta(hours=2), end=datetime.now(), freq='5min')
    
    # 온도 데이터 (20-80도)
    temperature = 50 + 12 * np.sin(np.linspace(0, 4*np.pi, len(times))) + np.random.normal(0, 3, len(times))
    
    # 압력 데이터 (100-200 bar)
    pressure = 150 + 25 * np.cos(np.linspace(0, 3*np.pi, len(times))) + np.random.normal(0, 5, len(times))
    
    return pd.DataFrame({
        'time': times,
        'temperature': temperature,
        'pressure': pressure
    })

@st.cache_data
def generate_equipment_status():
    """설비 상태 데이터 생성"""
    equipment = [
        {'name': '프레스기 A', 'status': '정상', 'efficiency': 94},
        {'name': '프레스기 B', 'status': '주의', 'efficiency': 78},
        {'name': '용접기 1', 'status': '정상', 'efficiency': 89},
        {'name': '용접기 2', 'status': '오류', 'efficiency': 0}
    ]
    return equipment

def get_alerts_data():
    url = "http://localhost:8000/alerts"
    res = requests.get(url)
    if res.status_code == 200:
        return res.json()
    else:
        return []

@st.cache_data
def generate_alert_data():
    """이상 알림 데이터 생성 (더미 데이터)"""
    alerts = [
        {'time': '14:30', 'equipment': '프레스기 B', 'issue': '정상 복구', 'severity': 'info'},
        {'time': '13:20', 'equipment': '용접기 1', 'issue': '비상 정지', 'severity': 'error'},
        {'time': '13:11', 'equipment': '프레스기 B', 'issue': '온도 임계값 초과', 'severity': 'error'},
        {'time': '10:12', 'equipment': '프레스기 A', 'issue': '진동 수치 증가', 'severity': 'warning'}
    ]
    return alerts

def get_alerts_data():
    url = "http://localhost:8000/alerts"
    res = requests.get(url)
    if res.status_code == 200:
        return res.json()
    else:
        return []


@st.cache_data
def generate_quality_trend():
    """품질 추세 데이터 생성"""
    days = ['월', '화', '수', '목', '금', '토', '일']
    quality_rates = [98, 97, 95, 99, 98, 92, 94]
    
    return pd.DataFrame({
        'day': days,
        'quality_rate': quality_rates
    })

# 메인 대시보드
def main():
    # 사이드바 (필터, 날짜 선택)
    with st.sidebar:
        st.markdown('### 필터')
        st.markdown('공정 선택')
        process = st.selectbox("", ["전체 공정", "프레스 공정", "용접 공정", "조립 공정"], label_visibility="collapsed")
        st.markdown('설비 필터')
        equipment_filter = st.multiselect(
            "",
            ["프레스기 A", "프레스기 B", "용접기 1", "용접기 2"],
            default=["프레스기 A", "프레스기 B", "용접기 1", "용접기 2"],
            label_visibility="collapsed"
        )
        st.markdown('---')
        st.markdown('### 날짜 선택')
        st.markdown('일자 선택')
        selected_date = st.date_input("", datetime.now().date(), label_visibility="collapsed")
        st.markdown('기간 선택')
        date_range = st.date_input(
            "",
            value=(datetime.now().date() - timedelta(days=7), datetime.now().date()),
            label_visibility="collapsed"
        )
        st.markdown('---')
        # 데이터 소스 토글 추가
        st.markdown('### 데이터 소스')
        use_real_api = st.toggle("실제 API 연동", value=False, help="실제 API에서 데이터를 받아옵니다. 끄면 더미 데이터를 사용합니다.")
        st.markdown('---')
        # 자동 새로고침 관련 코드 완전 제거

    # 자동 새로고침 기능 완전 제거

    # 헤더 및 KPI 카드 영역 (여백 조정)
    st.markdown('<div class="main-header" style="margin-top: 0;">POSCO MOBILITY IoT 대시보드</div>', unsafe_allow_html=True)
    kpi1, kpi2, kpi3 = st.columns(3, gap="medium")
    with kpi1:
        st.markdown("""
        <div class="kpi-card">
            <div class="kpi-value">92%</div>
            <div class="kpi-label">전체 가동률</div>
        </div>
        """, unsafe_allow_html=True)
    with kpi2:
        st.markdown("""
        <div class="kpi-card">
            <div class="kpi-value">1.3%</div>
            <div class="kpi-label">불량률</div>
        </div>
        """, unsafe_allow_html=True)
    with kpi3:
        st.markdown("""
        <div class="kpi-card">
            <div class="kpi-value">5건</div>
            <div class="kpi-label">알림 수</div>
        </div>
        """, unsafe_allow_html=True)

    # KPI 카드 영역 이후 여백 추가
    st.markdown('<div style="height: 32px;"></div>', unsafe_allow_html=True)

    # 메인 콘텐츠 상단: 실시간 센서 데이터 & 설비 상태
    col1, col2 = st.columns([1.6, 1], gap="large")
    # 실시간 센서 데이터 차트
    with col1:
        st.markdown('### 실시간 센서 데이터')
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
            height=320,
            margin=dict(l=0, r=0, t=0, b=0),
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(title="온도 (°C)", side="left"),
            yaxis2=dict(title="압력 (bar)", overlaying="y", side="right"),
            xaxis=dict(title="시간")
        )
        st.plotly_chart(fig, use_container_width=True)
    # 설비 상태 2x2 그리드
    with col2:
        st.markdown('### 설비 상태')
        equipment_status = generate_equipment_status()
        eq_grid = st.columns(2, gap="small")
        for i, equipment in enumerate(equipment_status):
            col = eq_grid[i % 2]
            status_class = {
                '정상': 'status-normal',
                '주의': 'status-warning',
                '오류': 'status-error'
            }.get(equipment['status'], 'status-normal')
            status_dot = {
                '정상': '🟢',
                '주의': '🟠',
                '오류': '🔴'
            }.get(equipment['status'], '🟢')
            with col:
                st.markdown(f"""
                <div class="equipment-card" style="margin-bottom: 12px; min-height: 90px;">
                    <div style="font-weight: bold; margin-bottom: 0.3rem;">{equipment['name']}</div>
                    <div class="{status_class}" style="font-weight: bold; margin-bottom: 0.3rem;">{status_dot} {equipment['status']}</div>
                    <div style="color: #6b7280; font-size: 0.9rem;">효율: {equipment['efficiency']}%</div>
                </div>
                """, unsafe_allow_html=True)

    # 하단 영역: 이상 알림 & 품질 추세
    col1, col2 = st.columns([1.2, 1], gap="large")
    # 이상 알림 테이블
    with col1:
        st.markdown('### 이상 알림')
        # 토글에 따라 데이터 소스 선택
        if use_real_api:
            alerts = get_alerts_data()
        else:
            alerts = generate_alert_data()
        
        alert_df = pd.DataFrame(alerts)
        # 심각도 색상 스타일링
        def highlight_issue(row):
            color = {'info': 'color: #10b981;', 'warning': 'color: #f59e0b;', 'error': 'color: #ef4444;'}
            return [color.get(row['severity'], '') if col == 'issue' else '' for col in row.index]
        styled_alert = alert_df.style.apply(highlight_issue, axis=1)
        st.dataframe(styled_alert, use_container_width=True, hide_index=True)
    # 품질 추세
    with col2:
        st.markdown('### 품질 추세')
        quality_data = generate_quality_trend()
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
            height=300,
            margin=dict(l=0, r=0, t=0, b=0),
            yaxis=dict(title="품질률 (%)", range=[80, 100]),
            xaxis=dict(title="요일"),
            showlegend=False
        )
        st.plotly_chart(fig, use_container_width=True)



if __name__ == "__main__":
    main()