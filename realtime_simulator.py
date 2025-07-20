# simulator.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

app = FastAPI(
    title="시계열 데이터 시뮬레이터 (SW1)",
    description="AI 모델 테스트를 위한 가상 공정 데이터 생성기. 다양한 시나리오 주입이 가능합니다.",
    version="1.0.0"
)

# --- 시나리오 정의 ---
# 시나리오는 데이터에 특정 패턴을 '주입'하는 함수입니다.

def apply_gradual_drift(data: pd.DataFrame, column: str, total_drift: float):
    """데이터에 점진적인 값 변화(드리프트)를 적용합니다."""
    drift_trend = np.linspace(0, total_drift, len(data))
    data[column] += drift_trend
    return data

def apply_sudden_spike(data: pd.DataFrame, column: str, spike_value: float, position_ratio: float = 0.75):
    """데이터 중간에 갑작스러운 스파이크(이상치)를 주입합니다."""
    spike_index = int(len(data) * position_ratio)
    data.loc[data.index[spike_index], column] += spike_value
    return data

def apply_sensor_failure(data: pd.DataFrame, column: str, position_ratio: float = 0.5):
    """특정 시점부터 센서가 고장나 0의 값만 반환하는 상황을 시뮬레이션합니다."""
    failure_index = int(len(data) * position_ratio)
    data.loc[data.index[failure_index]:, column] = 0
    return data


# --- 시뮬레이터 핵심 로직 ---

def generate_process_data(duration_hours: int, scenario: Optional[str] = None) -> pd.DataFrame:
    """
    주어진 시간과 시나리오에 따라 공정 데이터를 생성합니다.
    이것이 시뮬레이터의 심장부입니다.
    """
    # 1. 시간 축 생성
    end_time = datetime.now()
    start_time = end_time - timedelta(hours=duration_hours)
    timestamps = pd.date_range(start=start_time, end=end_time, freq='1min')
    df = pd.DataFrame(index=timestamps)

    # 2. 기본 정상 데이터 생성 (sin/cos 함수 + 노이즈로 현실성 부여)
    base_cycle = np.linspace(0, 4 * np.pi, len(df))
    df['temperature'] = 70 + 10 * np.sin(base_cycle) + np.random.normal(0, 0.5, len(df))
    df['pressure'] = 150 + 20 * np.cos(base_cycle) + np.random.normal(0, 1, len(df))
    df['vibration'] = 0.5 + 0.1 * np.sin(base_cycle * 2) + np.random.normal(0, 0.02, len(df))
    df['energy_kwh'] = 1.5 + 0.5 * (df['temperature']/80) + 0.3 * (df['pressure']/170) + np.random.normal(0, 0.1, len(df))

    # 3. 요청된 시나리오 주입
    if scenario == "gradual_drift":
        df = apply_gradual_drift(df, 'temperature', total_drift=15)
    elif scenario == "sudden_spike":
        df = apply_sudden_spike(df, 'pressure', spike_value=50)
    elif scenario == "sensor_failure":
        df = apply_sensor_failure(df, 'vibration')

    df.reset_index(inplace=True)
    df = df.rename(columns={'index': 'timestamp'})
    return df

# --- API 엔드포인트 정의 ---
# 외부 시스템이 시뮬레이터를 조종하는 '리모컨' 역할을 합니다.

class SensorData(BaseModel):
    timestamp: datetime
    temperature: float
    pressure: float
    vibration: float
    energy_kwh: float

@app.get("/simulation/run", response_model=List[SensorData])
def run_simulation(duration_hours: int = 1, scenario: Optional[str] = None):
    """
    시뮬레이션을 실행하고 생성된 시계열 데이터를 반환합니다.
    - duration_hours: 생성할 데이터의 기간 (시간 단위)
    - scenario: 주입할 시나리오 (gradual_drift, sudden_spike, sensor_failure)
    """
    scenarios = ["gradual_drift", "sudden_spike", "sensor_failure", None]
    if scenario not in scenarios:
        raise HTTPException(status_code=400, detail=f"사용 불가능한 시나리오입니다. 선택 가능: {scenarios}")

    df = generate_process_data(duration_hours=duration_hours, scenario=scenario)
    return df.to_dict(orient='records')

@app.get("/simulation/scenarios")
def get_available_scenarios():
    """사용 가능한 시나리오 목록을 반환합니다."""
    return {
        "scenarios": {
            "normal": "정상 작동 데이터",
            "gradual_drift": "온도가 서서히 증가하는 시나리오",
            "sudden_spike": "압력이 갑자기 치솟는 시나리오",
            "sensor_failure": "진동 센서가 고장나는 시나리오"
        }
    }

if __name__ == "__main__":
    import uvicorn
    # uvicorn.run(앱객체, host="0.0.0.0"은 외부접속허용, port=포트번호)
    uvicorn.run(app, host="0.0.0.0", port=8001)