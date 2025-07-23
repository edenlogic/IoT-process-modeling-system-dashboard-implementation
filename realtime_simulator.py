import pandas as pd
import numpy as np
import requests
import json
import time
import logging
from datetime import datetime, timedelta
import threading
from typing import Dict, List, Optional, Tuple
import random
from collections import deque
from abc import ABC, abstractmethod
import os

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# API 엔드포인트
API_BASE_URL = "http://localhost:8000"
SENSOR_API = f"{API_BASE_URL}/sensors"
ALERT_API = f"{API_BASE_URL}/alerts"
EQUIPMENT_STATUS_API = f"{API_BASE_URL}/equipment"
QUALITY_TREND_API = f"{API_BASE_URL}/api/quality_trend"
PRODUCTION_KPI_API = f"{API_BASE_URL}/api/production_kpi"

class BaseCSVSimulator(ABC):
    """CSV 기반 시뮬레이터 베이스 클래스"""
    
    def __init__(self, csv_path: str, topic_name: str):
        self.csv_path = csv_path
        self.topic_name = topic_name
        self.df = None
        self.patterns = {}
        self.running = False
        self.logger = logging.getLogger(f'{self.__class__.__name__}')
        
    def load_data(self):
        """CSV 데이터 로드 (더미 분기 제거)"""
        if not os.path.exists(self.csv_path):
            self.logger.error(f"CSV 파일 없음: {self.csv_path}, 시뮬레이터를 실행할 수 없습니다.")
            self.df = None
            self.patterns = {}
            return
        try:
            self.df = pd.read_csv(self.csv_path)
            self.logger.info(f"CSV 데이터 로드 완료: {len(self.df)} 행")
            self.learn_patterns()
        except Exception as e:
            self.logger.error(f"CSV 로드 실패: {e}")
            self.df = None
            self.patterns = {}
    
    @abstractmethod
    def learn_patterns(self):
        """데이터 패턴 학습"""
        pass
    
    @abstractmethod
    def generate_data(self) -> Dict:
        """가상 데이터 생성"""
        pass
    
    def send_to_api(self, data: Dict):
        """센서 데이터를 FastAPI 서버로 전송"""
        try:
            # 모든 numpy 타입을 Python 네이티브 타입으로 변환
            def convert_to_native(obj):
                if isinstance(obj, np.integer):
                    return int(obj)
                elif isinstance(obj, np.floating):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, np.bool_):  # numpy bool 타입 처리
                    return bool(obj)
                elif isinstance(obj, bool):  # Python native bool은 그대로
                    return obj
                elif isinstance(obj, dict):
                    return {key: convert_to_native(value) for key, value in obj.items()}
                elif isinstance(obj, list):
                    return [convert_to_native(item) for item in obj]
                return obj
            
            # 데이터 변환
            data = convert_to_native(data)
            
            response = requests.post(SENSOR_API, json=data, timeout=5)
            
            if response.status_code == 200:
                self.logger.info(f"[센서] {data.get('equipment')} {data.get('sensor_type')}={data.get('value')}")
            else:
                self.logger.warning(f"[센서] 데이터 전송 실패: {response.status_code}")
        except Exception as e:
            self.logger.error(f"[센서] 데이터 API 오류: {e}")

    def send_alert(self, data: dict):
        """알림 데이터를 FastAPI 서버로 전송"""
        try:
            response = requests.post(ALERT_API, json=data, timeout=5)
            if response.status_code == 200:
                self.logger.info(f"[알림] {data.get('equipment')} {data.get('sensor_type')} {data.get('severity')} {data.get('message')}")
            else:
                self.logger.warning(f"[알림] 데이터 전송 실패: {response.status_code}")
        except Exception as e:
            self.logger.error(f"[알림] 데이터 API 오류: {e}")

    def update_equipment_status(self, equipment_id: str, status: str, efficiency: float):
        """설비 상태를 FastAPI 서버로 전송"""
        url = f"{EQUIPMENT_STATUS_API}/{equipment_id}/status"
        try:
            response = requests.put(url, params={"status": status, "efficiency": efficiency}, timeout=5)
            if response.status_code == 200:
                self.logger.info(f"[설비상태] {equipment_id} 상태={status}, 효율={efficiency:.2f}%")
            else:
                self.logger.warning(f"[설비상태] 데이터 전송 실패: {equipment_id} ({response.status_code})")
        except Exception as e:
            self.logger.error(f"[설비상태] 데이터 API 오류: {e}")

    def send_quality_trend(self, trend_data: dict):
        try:
            response = requests.post(QUALITY_TREND_API, json=trend_data, timeout=5)
            if response.status_code == 200:
                self.logger.info("[트렌드] 품질/생산 트렌드 데이터 전송 성공")
            else:
                self.logger.warning(f"[트렌드] 데이터 전송 실패: {response.status_code}")
        except Exception as e:
            self.logger.error(f"[트렌드] 데이터 API 오류: {e}")

    def send_production_kpi(self, kpi_data: dict):
        try:
            response = requests.post(PRODUCTION_KPI_API, json=kpi_data, timeout=5)
            if response.status_code == 200:
                self.logger.info("[KPI] 생산성 KPI 데이터 전송 성공")
            else:
                self.logger.warning(f"[KPI] 데이터 전송 실패: {response.status_code}")
        except Exception as e:
            self.logger.error(f"[KPI] 데이터 API 오류: {e}")
    
    def run(self, interval: float = 1.0, test_mode: bool = True, test_scenario: int = 1):
        """시뮬레이터 실행 (알림/설비상태/트렌드/KPI 자동 전송 추가, 센서 여러 개 처리)"""
        self.running = True
        self.logger.info(f"{self.topic_name} 시뮬레이터 시작")
        self.start_time = time.time()  # generate_data에서 사용하기 위해 저장
        self.test_mode = test_mode
        self.test_scenario = test_scenario
        max_duration = 120 if test_mode else float('inf')  # 테스트모드: 2분
        normal_count = 0
        fault_count = 0
        while self.running and (time.time() - self.start_time) < max_duration:
            try:
                elapsed = time.time() - self.start_time
                if test_mode and int(elapsed) % 10 == 0 and int(elapsed) > 0:
                    self.logger.info(f"[테스트 {elapsed:.0f}초] 정상: {normal_count}, 이상: {fault_count}")
                datas = self.generate_data()
                if datas is None:
                    continue
                # 센서 데이터가 dict 하나면 리스트로 변환
                if isinstance(datas, dict):
                    datas = [datas]
                for data in datas:
                    # 카운트 업데이트
                    if self.topic_name == 'manufacturing':
                        if (data.get('predictions', {}).get('energy_anomaly') or 
                            data.get('predictions', {}).get('vibration_spike')):
                            fault_count += 1
                        else:
                            normal_count += 1
                    else:
                        if data.get('fault_status', {}).get('is_normal', 1) == 0:
                            fault_count += 1
                        else:
                            normal_count += 1
                    # 센서 데이터 전송
                    self.send_to_api(data)
                    # 센서 임계값 초과 시 알림/설비상태 전송
                    equipment = data.get('equipment', 'press_001')
                    sensor_type = data.get('sensor_type', None)
                    value = data.get('value', None)
                    thresholds = {"temperature": 65.0, "pressure": 1.1, "vibration": 3.0}
                    if sensor_type in thresholds and value is not None and value > thresholds[sensor_type]:
                        severity = "warning" if value < thresholds[sensor_type] * 1.1 else "error"
                        alert = {
                            "equipment": equipment,
                            "sensor_type": sensor_type,
                            "value": value,
                            "threshold": thresholds[sensor_type],
                            "severity": severity,
                            "timestamp": data.get('timestamp', None) or datetime.now().isoformat(),
                            "message": f"{equipment} {sensor_type} 임계치 초과: {value} (임계값: {thresholds[sensor_type]})"
                        }
                        self.send_alert(alert)
                        status = "주의" if severity == "warning" else "오류"
                        efficiency = 80.0 if severity == "warning" else 60.0
                        self.update_equipment_status(equipment, status, efficiency)
                # 트렌드/KPI는 대시보드에서 GET으로 가져오므로 제거
                time.sleep(interval)
            except KeyboardInterrupt:
                self.stop()
            except Exception as e:
                self.logger.error(f"시뮬레이션 오류: {e}")
        if test_mode:
            self.logger.info(f"테스트 완료! 총 {elapsed:.0f}초 실행")
            self.logger.info(f"최종 결과 - 정상: {normal_count}, 이상: {fault_count}")
    
    def stop(self):
        """시뮬레이터 중지"""
        self.running = False
        self.logger.info(f"{self.topic_name} 시뮬레이터 중지")


class HydraulicSimulator(BaseCSVSimulator):
    """유압 시스템 시뮬레이터"""
    
    def __init__(self, csv_path: str):
        super().__init__(csv_path, "hydraulic")
        self.sensor_types = ['PS', 'TS', 'FS', 'VS', 'EPS', 'CE', 'CP', 'SE']
        self.fault_components = ['Cooler', 'Valve', 'Pump', 'Accumulator']
        
    def learn_patterns(self):
        """유압 데이터 패턴 학습 - 부품 값 기반 정상/고장 판단"""
        
        if self.df is None:
            self.logger.warning("CSV 없이 더미 패턴으로 동작합니다.")
            # 더미 패턴/랜덤값 등으로 self.patterns 초기화
            self.patterns = {f"dummy_sensor_{i}": {"normal_mean": 1.0, "normal_std": 0.1, "normal_min": 0.5, "normal_max": 1.5, "abnormal_samples": [2.0]} for i in range(3)}
            return

        # 각 부품의 정상값 정의 (높은 값이 정상)
        COMPONENT_NORMAL_VALUES = {
            'Cooler': 3.0,      # 3 = 정상, 20/100 = 고장
            'Valve': 100.0,     # 100 = 정상, 73/80/90 = 고장  
            'Pump': 2.0,        # 2 = 정상, 0/1 = 고장
            'Accumulator': 130.0  # 130 = 정상, 90/100/115 = 고장
        }
        
        self.component_normal_values = COMPONENT_NORMAL_VALUES
        
        # 각 부품의 정상 임계값 (이 값 이상이면 정상)
        NORMAL_THRESHOLDS = {
            'Cooler': 2.5,      # 2.5 이상이면 정상
            'Valve': 95.0,      # 95 이상이면 정상
            'Pump': 1.5,        # 1.5 이상이면 정상
            'Accumulator': 125.0  # 125 이상이면 정상
        }
        
        # 실제 정상/비정상 데이터 분리 (부품 값 기반)
        # 모든 부품이 정상인 경우를 정상 데이터로 간주
        normal_mask = pd.Series(True, index=self.df.index)
        
        for component, threshold in NORMAL_THRESHOLDS.items():
            if component in self.df.columns:
                normal_mask &= (self.df[component] >= threshold)
        
        normal_data = self.df[normal_mask]
        abnormal_data = self.df[~normal_mask]
        
        self.logger.info(f"부품 값 기반 데이터 분포 - 정상: {len(normal_data)}, 비정상: {len(abnormal_data)}")
        
        # 센서별 패턴 학습
        sensor_cols = []
        for col in self.df.columns:
            for sensor_prefix in self.sensor_types:
                if col.startswith(sensor_prefix) and any(stat in col for stat in ['_mean', '_std', '_min', '_max']):
                    sensor_cols.append(col)
                    break
        
        self.logger.info(f"찾은 센서 컬럼 수: {len(sensor_cols)}")
        
        # 센서 패턴 학습
        for col in sensor_cols:
            if len(normal_data) > 0:
                # 정상 데이터가 있으면 사용
                normal_values = normal_data[col]
                abnormal_values = abnormal_data[col] if len(abnormal_data) > 0 else pd.Series()
            else:
                # 정상 데이터가 없으면 상위 25%를 정상으로 간주
                threshold = self.df[col].quantile(0.75)
                normal_values = self.df[self.df[col] >= threshold][col]
                abnormal_values = self.df[self.df[col] < threshold][col]
            
            # 빈 데이터 처리
            if len(normal_values) == 0:
                normal_values = self.df[col]
            
            self.patterns[col] = {
                'normal_mean': normal_values.mean(),
                'normal_std': normal_values.std() if normal_values.std() > 0 else 0.1,
                'normal_min': normal_values.min(),
                'normal_max': normal_values.max(),
                'abnormal_samples': abnormal_values.values if len(abnormal_values) > 0 else []
            }
        
        # 고장 유형별 패턴 학습
        self.fault_patterns = {}
        
        for component in self.fault_components:
            if component in self.df.columns:
                normal_value = COMPONENT_NORMAL_VALUES.get(component, self.df[component].max())
                threshold = NORMAL_THRESHOLDS.get(component, normal_value * 0.9)
                
                # 고장 데이터 추출 (임계값 미만)
                fault_data = self.df[self.df[component] < threshold]
                
                if len(fault_data) > 0:
                    fault_values = fault_data[component].unique()
                    self.fault_patterns[component] = {
                        'probability': len(fault_data) / len(self.df),
                        'normal_value': normal_value,
                        'threshold': threshold,
                        'fault_values': sorted(fault_values),  # 정렬하여 저장
                        'value_range': (fault_data[component].min(), fault_data[component].max()),
                        'severity_levels': {
                            'mild': [v for v in fault_values if v >= threshold * 0.7],
                            'moderate': [v for v in fault_values if threshold * 0.4 <= v < threshold * 0.7],
                            'severe': [v for v in fault_values if v < threshold * 0.4]
                        }
                    }
                    
                    self.logger.info(f"{component} 고장 패턴: 정상={normal_value}, "
                                   f"임계값={threshold}, 고장값={len(fault_values)}개")
        
        self.logger.info(f"패턴 학습 완료: {len(self.patterns)} 센서 패턴, {len(self.fault_patterns)} 고장 패턴")
        
        # 패턴이 비어있으면 경고
        if len(self.patterns) == 0:
            self.logger.warning("⚠️ 센서 패턴이 비어있습니다! CSV 파일 구조를 확인하세요.")
    
    def generate_data(self) -> list:
        """유압 시스템 데이터 생성"""
        timestamp = datetime.now()
        
        if self.df is None or not self.patterns:
            # 더미/랜덤 데이터 생성: 센서별로 하나씩 반환
            dummy_equipment = "press_001"
            dummy_types = ["temperature", "pressure", "vibration"]
            dummy_values = [round(random.uniform(20, 80), 2), round(random.uniform(0.8, 1.2), 3), round(random.uniform(0.1, 5.0), 2)]
            # 센서별로 하나씩 dict 생성
            datas = []
            for sensor_type, value in zip(dummy_types, dummy_values):
                data = {
                    "equipment": dummy_equipment,
                    "sensor_type": sensor_type,
                    "value": value,
                    "timestamp": timestamp.isoformat()
                }
                datas.append(data)
            return datas

        # 테스트 모드 시나리오 1: 시간대별 명확한 구분
        if hasattr(self, 'test_mode') and self.test_mode and self.test_scenario == 1:
            elapsed = time.time() - self.start_time
            
            # 시간대별 시나리오 적용
            if elapsed < 10:
                # 0-10초: 정상 작동
                is_fault = False
                fault_component = None
                fault_value = None
                self.logger.info(f"[{elapsed:.1f}초] 시나리오: 정상 작동")
            elif 10 <= elapsed < 20:
                # 10-20초: 경미한 이상 (Cooler)
                is_fault = True
                fault_component = 'Cooler'
                if fault_component in self.fault_patterns:
                    # Cooler의 정상값과 고장값 범위 사용
                    normal_val = self.component_normal_values.get(fault_component, 3)
                    fault_value = normal_val * 0.7  # 정상값의 70% (경미한 이상)
                else:
                    fault_value = 2.0
                self.logger.info(f"[{elapsed:.1f}초] 시나리오: Cooler 경미한 이상")
            elif 20 <= elapsed < 30:
                # 20-30초: 정상 복구
                is_fault = False
                fault_component = None
                fault_value = None
                self.logger.info(f"[{elapsed:.1f}초] 시나리오: 정상 복구")
            elif 30 <= elapsed < 40:
                # 30-40초: 심각한 고장 (Pump)
                is_fault = True
                fault_component = 'Pump'
                if fault_component in self.fault_patterns:
                    fault_value = self.fault_patterns[fault_component]['value_range'][0]  # 최소값 (심각)
                else:
                    fault_value = 0.0
                self.logger.info(f"[{elapsed:.1f}초] 시나리오: Pump 심각한 고장")
            elif 40 <= elapsed < 50:
                # 40-50초: 복합 고장 (Pump + Valve)
                is_fault = True
                fault_component = random.choice(['Pump', 'Valve'])
                if fault_component in self.fault_patterns:
                    fault_value = random.uniform(
                        self.fault_patterns[fault_component]['value_range'][0],
                        self.fault_patterns[fault_component]['value_range'][1]
                    )
                else:
                    fault_value = random.uniform(0, 1)
                self.logger.info(f"[{elapsed:.1f}초] 시나리오: {fault_component} 복합 고장")
            elif 50 <= elapsed < 60:
                # 50-60초: 점진적 회복
                is_fault = random.random() < 0.3  # 30% 확률로 가끔 이상
                if is_fault:
                    fault_component = random.choice(list(self.fault_patterns.keys())) if self.fault_patterns else 'Cooler'
                    if fault_component in self.fault_patterns:
                        normal_val = self.component_normal_values.get(fault_component, 100)
                        fault_value = normal_val * 0.85  # 정상값의 85% (경미)
                    else:
                        fault_value = 2.5
                else:
                    fault_component = None
                    fault_value = None
                self.logger.info(f"[{elapsed:.1f}초] 시나리오: 점진적 회복")
            elif 60 <= elapsed < 90:
                # 60-90초: 간헐적 스파이크 (5초마다)
                if int(elapsed) % 5 == 0:
                    is_fault = True
                    fault_component = random.choice(list(self.fault_patterns.keys())) if self.fault_patterns else 'Valve'
                    if fault_component in self.fault_patterns:
                        fault_value = random.uniform(
                            self.fault_patterns[fault_component]['value_range'][0],
                            self.fault_patterns[fault_component]['value_range'][1]
                        )
                    else:
                        fault_value = random.uniform(1, 2)
                    self.logger.info(f"[{elapsed:.1f}초] 시나리오: 간헐적 스파이크 - {fault_component}")
                else:
                    is_fault = False
                    fault_component = None
                    fault_value = None
            else:
                # 90-120초: 완전 정상화
                is_fault = False
                fault_component = None
                fault_value = None
                self.logger.info(f"[{elapsed:.1f}초] 시나리오: 완전 정상화")
                
        else:
            # 일반 모드: 기존 로직
            is_fault = random.random() < 0.1
            fault_component = None
            fault_value = None
            
            if is_fault and self.fault_patterns:
                fault_component = random.choice(list(self.fault_patterns.keys()))
                pattern = self.fault_patterns[fault_component]
                
                if len(pattern['fault_values']) > 0:
                    fault_value = random.choice(pattern['fault_values'])
                else:
                    fault_value = random.uniform(pattern['value_range'][0], pattern['value_range'][1])
        
        # 센서 데이터 생성
        sensor_data = {}
        
        for sensor_name, pattern in self.patterns.items():
            if is_fault and len(pattern.get('abnormal_samples', [])) > 0:
                # 고장 시: 이상 패턴에서 샘플링
                if random.random() < 0.3:  # 30% 확률로 이상값
                    value = random.choice(pattern['abnormal_samples'])
                else:
                    # 정상 범위에서 벗어난 값
                    value = pattern['normal_mean'] + random.gauss(0, pattern['normal_std'] * 2)
            else:
                # 정상 시: 정상 분포에서 샘플링
                value = random.gauss(pattern['normal_mean'], pattern['normal_std'])
                value = np.clip(value, pattern['normal_min'], pattern['normal_max'])
            
            sensor_data[sensor_name] = float(value)
        
        # 전체 데이터 구성
        data = {
            'timestamp': timestamp.isoformat(),
            'sensors': sensor_data,
            'fault_status': {
                'is_normal': 0 if is_fault else 1,
                'fault_component': fault_component,
                'fault_value': fault_value,
                'component_normal_value': self.component_normal_values.get(fault_component) if fault_component else None
            },
            'topic': 'hydraulic'
        }
        
        # 고장 발생 시 로그
        if is_fault and fault_component:
            normal_val = self.component_normal_values.get(fault_component, "알 수 없음")
            self.logger.warning(f"⚠️ 유압 시스템 이상 감지: {fault_component} (정상: {normal_val}, 현재: {fault_value:.1f})")
        
        return [data]


class ManufacturingSimulator(BaseCSVSimulator):
    """제조 공정 시뮬레이터 - 1분 간격 실시간 데이터"""
    
    def __init__(self, csv_path: str):
        super().__init__(csv_path, "manufacturing")
        self.time_window = deque(maxlen=60)  # 60분 슬라이딩 윈도우 (딥러닝 입력용)
        self.energy_history = deque(maxlen=90)  # 과거 90분 에너지 데이터
        # correlations를 항상 기본값으로 초기화
        self.correlations = {
            'temp_speed': 0.0,
            'speed_vibration': 0.0,
            'temp_energy': 0.0,
            'vibration_energy': 0.0
        }
        
    def learn_patterns(self):
        """제조 데이터 패턴 학습 - 1분 단위 실시간 데이터"""
        if self.df is None:
            self.logger.warning("CSV 없이 더미 패턴으로 동작합니다.")
            self.patterns = {f"dummy_sensor_{i}": {"normal_mean": 1.0, "normal_std": 0.1, "normal_min": 0.5, "normal_max": 1.5, "abnormal_samples": [2.0]} for i in range(3)}
            # correlations도 더미로 초기화
            self.correlations = {
                'temp_speed': 0.0,
                'speed_vibration': 0.0,
                'temp_energy': 0.0,
                'vibration_energy': 0.0
            }
            return

        # 시간 정보 추출
        self.df['Timestamp'] = pd.to_datetime(self.df['Timestamp'])
        self.df['minute'] = self.df['Timestamp'].dt.minute
        self.df['hour'] = self.df['Timestamp'].dt.hour
        
        # 1. 분 단위 패턴 학습 (더 세밀한 패턴)
        self.minute_patterns = {}
        features = ['Temperature (°C)', 'Machine Speed (RPM)', 'Production Quality Score', 
                   'Vibration Level (mm/s)', 'Energy Consumption (kWh)']
        
        # 10분 단위로 그룹화 (0-9분, 10-19분, ...)
        for minute_group in range(6):  # 0~5 (각 10분 구간)
            start_min = minute_group * 10
            end_min = start_min + 10
            group_data = self.df[(self.df['minute'] >= start_min) & (self.df['minute'] < end_min)]
            
            if len(group_data) > 0:
                self.minute_patterns[minute_group] = {}
                for feature in features:
                    self.minute_patterns[minute_group][feature] = {
                        'mean': group_data[feature].mean(),
                        'std': group_data[feature].std(),
                        'min': group_data[feature].min(),
                        'max': group_data[feature].max()
                    }
        
        # 2. 센서 간 상관관계 학습
        self.correlations = {
            'temp_speed': np.corrcoef(self.df['Temperature (°C)'], 
                                     self.df['Machine Speed (RPM)'])[0, 1],
            'speed_vibration': np.corrcoef(self.df['Machine Speed (RPM)'], 
                                          self.df['Vibration Level (mm/s)'])[0, 1],
            'temp_energy': np.corrcoef(self.df['Temperature (°C)'], 
                                      self.df['Energy Consumption (kWh)'])[0, 1],
            'vibration_energy': np.corrcoef(self.df['Vibration Level (mm/s)'], 
                                           self.df['Energy Consumption (kWh)'])[0, 1]
        }
        
        # 3. 에너지 소비 패턴 학습 (이동평균 적용)
        self.df['Energy_MA10'] = self.df['Energy Consumption (kWh)'].rolling(window=10, center=True).mean()
        self.df['Energy_MA10'].fillna(self.df['Energy Consumption (kWh)'], inplace=True)
        
        # 4. 최적 조건 패턴
        optimal_data = self.df[self.df['Optimal Conditions'] == 1]
        
        self.optimal_patterns = {
            'temp_range': (optimal_data['Temperature (°C)'].quantile(0.1), 
                          optimal_data['Temperature (°C)'].quantile(0.9)),
            'speed_range': (optimal_data['Machine Speed (RPM)'].quantile(0.1),
                           optimal_data['Machine Speed (RPM)'].quantile(0.9)),
            'vibration_threshold': optimal_data['Vibration Level (mm/s)'].quantile(0.95),
            'energy_efficient': optimal_data['Energy Consumption (kWh)'].median()
        }
        
        # 5. 노이즈 특성 학습
        self.noise_patterns = {
            'energy_noise_std': (self.df['Energy Consumption (kWh)'] - self.df['Energy_MA10']).std(),
            'vibration_spike_prob': len(self.df[self.df['Vibration Level (mm/s)'] > 
                                       self.df['Vibration Level (mm/s)'].quantile(0.99)]) / len(self.df)
        }
        
        self.logger.info("제조 패턴 학습 완료 (1분 단위 실시간)")
        self.logger.info(f"상관관계: 온도-속도={self.correlations['temp_speed']:.2f}, "
                        f"속도-진동={self.correlations['speed_vibration']:.2f}")
    
    def generate_correlated_values(self, base_temp: float) -> Dict[str, float]:
        """상관관계를 고려한 센서값 생성"""
        if self.df is None:
            # 더미/랜덤 데이터 생성
            values = {'Temperature (°C)': base_temp}
            values['Machine Speed (RPM)'] = int(np.clip(
                random.gauss(3000 + (base_temp - 75) * 20 * self.correlations['temp_speed'], 50),
                1450, 1550  # 실제 데이터 범위
            ))
            values['Vibration Level (mm/s)'] = np.clip(
                random.gauss(0.05 + (values['Machine Speed (RPM)'] - 1500) * 0.0001 * abs(self.correlations['speed_vibration']), 0.01),
                0.03, 0.1
            )
            values['Production Quality Score'] = random.uniform(8.5, 9.0)
            values['Energy Consumption (kWh)'] = np.clip(
                1.5 + (base_temp - 75) * 0.01 * abs(self.correlations['temp_energy']) + (values['Machine Speed (RPM)'] - 1500) * 0.001 + values['Vibration Level (mm/s)'] * 10 * abs(self.correlations['vibration_energy']),
                0.5, 3.0
            )
            return values

        # 온도 기반으로 다른 센서값 생성
        values = {'Temperature (°C)': base_temp}
        
        # 속도: 온도와 상관관계 적용
        speed_base = 3000 + (base_temp - 75) * 20 * self.correlations['temp_speed']
        values['Machine Speed (RPM)'] = int(np.clip(
            random.gauss(speed_base, 50),
            1450, 1550  # 실제 데이터 범위
        ))
        
        # 진동: 속도와 상관관계 적용
        vibration_base = 0.05 + (values['Machine Speed (RPM)'] - 1500) * 0.0001 * abs(self.correlations['speed_vibration'])
        values['Vibration Level (mm/s)'] = np.clip(
            random.gauss(vibration_base, 0.01),
            0.03, 0.1
        )
        
        # 품질 점수: 최적 조건 근처일수록 높음
        if self.optimal_patterns['temp_range'][0] <= base_temp <= self.optimal_patterns['temp_range'][1]:
            quality_base = random.uniform(8.5, 9.0)
        else:
            quality_base = random.uniform(7.5, 8.5)
        values['Production Quality Score'] = quality_base
        
        # 에너지: 온도, 속도, 진동과 상관관계 적용
        energy_base = 1.5
        energy_base += (base_temp - 75) * 0.01 * abs(self.correlations['temp_energy'])
        energy_base += (values['Machine Speed (RPM)'] - 1500) * 0.001
        energy_base += values['Vibration Level (mm/s)'] * 10 * abs(self.correlations['vibration_energy'])
        
        # 노이즈 추가
        if random.random() < 0.1:  # 10% 확률로 노이즈
            energy_base += random.gauss(0, self.noise_patterns['energy_noise_std'])
        
        values['Energy Consumption (kWh)'] = np.clip(energy_base, 0.5, 3.0)
        
        return values
    
    def predict_energy_30min(self) -> List[float]:
        """과거 60분 데이터로 미래 30분 에너지 예측 (간단한 시뮬레이션)"""
        if self.df is None or len(self.energy_history) < 60:
            # 데이터 부족 시 현재 값 반복
            return [self.energy_history[-1] if self.energy_history else 1.5] * 30
        
        # 최근 60분 데이터
        recent_60 = list(self.energy_history)[-60:]
        
        # 간단한 예측: 추세 + 주기성 + 노이즈
        trend = (recent_60[-1] - recent_60[0]) / 60  # 선형 추세
        mean_energy = np.mean(recent_60)
        
        predictions = []
        for i in range(30):
            # 기본값 = 평균 + 추세
            pred = mean_energy + trend * (60 + i)
            
            # 주기성 추가 (10분 주기)
            pred += 0.1 * np.sin(2 * np.pi * i / 10)
            
            # 노이즈
            pred += random.gauss(0, 0.05)
            
            predictions.append(np.clip(pred, 0.5, 3.0))
        
        return predictions
    
    def generate_data(self) -> list:
        """제조 공정 데이터 생성 - 1분 간격"""
        timestamp = datetime.now()
        current_minute = timestamp.minute
        minute_group = current_minute // 10  # 0~5
        if self.df is None or not hasattr(self, 'minute_patterns') or minute_group not in getattr(self, 'minute_patterns', {}):
            # 더미/랜덤 데이터 생성: 센서별로 하나씩 반환
            dummy_equipment = "press_001"
            dummy_types = ["temperature", "pressure", "vibration"]
            dummy_values = [round(random.uniform(20, 80), 2), round(random.uniform(0.8, 1.2), 3), round(random.uniform(0.1, 5.0), 2)]
            datas = []
            for sensor_type, value in zip(dummy_types, dummy_values):
                data = {
                    "equipment": dummy_equipment,
                    "sensor_type": sensor_type,
                    "value": value,
                    "timestamp": timestamp.isoformat()
                }
                datas.append(data)
            return datas
        # 현재 시간대 패턴 가져오기
        pattern = self.minute_patterns[minute_group]
        
        # 기본 온도 생성
        temp_pattern = pattern['Temperature (°C)']
        base_temp = random.gauss(temp_pattern['mean'], temp_pattern['std'] * 0.5)
        base_temp = np.clip(base_temp, temp_pattern['min'], temp_pattern['max'])
        
        # 상관관계 기반 센서값 생성
        current_data = self.generate_correlated_values(base_temp)
        
        # 최적 조건 판단
        is_optimal = (
            self.optimal_patterns['temp_range'][0] <= current_data['Temperature (°C)'] <= self.optimal_patterns['temp_range'][1] and
            current_data['Vibration Level (mm/s)'] < self.optimal_patterns['vibration_threshold'] and
            current_data['Energy Consumption (kWh)'] < self.optimal_patterns['energy_efficient'] * 1.2
        )
        
        # 에너지 히스토리 업데이트
        self.energy_history.append(current_data['Energy Consumption (kWh)'])
        
        # 30분 후 에너지 예측
        energy_predictions = self.predict_energy_30min()
        
        # 시계열 윈도우 업데이트 (딥러닝 입력용)
        self.time_window.append({
            'temperature': current_data['Temperature (°C)'],
            'speed': current_data['Machine Speed (RPM)'],
            'vibration': current_data['Vibration Level (mm/s)'],
            'energy': current_data['Energy Consumption (kWh)']
        })
        
        # 이상 감지 (이동평균 기반)
        energy_anomaly = False
        if len(self.energy_history) >= 10:
            recent_ma = np.mean(list(self.energy_history)[-10:])
            if abs(current_data['Energy Consumption (kWh)'] - recent_ma) > 0.5:
                energy_anomaly = True
        
        # 진동 스파이크 감지
        vibration_spike = current_data['Vibration Level (mm/s)'] > 0.08
        
        # 전체 데이터 구성
        data = {
            'timestamp': timestamp.isoformat(),
            'sensors': current_data,
            'predictions': {
                'energy_next_30min': energy_predictions,
                'energy_next_hour_avg': np.mean(energy_predictions),
                'optimal_conditions': 1 if is_optimal else 0,
                'energy_anomaly': energy_anomaly,
                'vibration_spike': vibration_spike
            },
            'time_window': list(self.time_window) if len(self.time_window) == 60 else None,  # 딥러닝 입력용
            'topic': 'manufacturing'
        }
        
        # 이상 상황 로그
        if energy_anomaly:
            self.logger.warning(f"⚡ 에너지 소비 이상 감지: {current_data['Energy Consumption (kWh)']:.2f} kWh (이동평균 대비)")
        if vibration_spike:
            self.logger.warning(f"📊 진동 스파이크 감지: {current_data['Vibration Level (mm/s)']:.3f} mm/s")
        
        return [data]


class DualCSVSimulator:
    """듀얼 시뮬레이터 관리자"""
    
    def __init__(self, hydraulic_csv: str, manufacturing_csv: str):
        self.hydraulic_sim = HydraulicSimulator(hydraulic_csv)
        self.manufacturing_sim = ManufacturingSimulator(manufacturing_csv)
        self.threads = []
        
    def load_all(self):
        """모든 데이터 로드"""
        self.hydraulic_sim.load_data()
        self.manufacturing_sim.load_data()
        
    def start(self, hydraulic_interval: float = 1.0, manufacturing_interval: float = 5.0, 
              test_mode: bool = True, test_scenario: int = 1):
        """두 시뮬레이터 동시 실행"""
        # 유압 시뮬레이터 스레드
        hydraulic_thread = threading.Thread(
            target=self.hydraulic_sim.run,
            args=(hydraulic_interval, test_mode, test_scenario),
            daemon=True
        )
        
        # 제조 시뮬레이터 스레드
        manufacturing_thread = threading.Thread(
            target=self.manufacturing_sim.run,
            args=(manufacturing_interval, test_mode, test_scenario),
            daemon=True
        )
        
        self.threads = [hydraulic_thread, manufacturing_thread]
        
        # 스레드 시작
        for thread in self.threads:
            thread.start()
        
        print("🚀 듀얼 CSV 시뮬레이터 시작!")
        if test_mode:
            print(f"🧪 테스트 모드: 시나리오 {test_scenario} (2분간 실행)")
            print("📋 시나리오 1: 시간대별 명확한 구분")
            print("  - 0-10초: 정상")
            print("  - 10-20초: 경미한 이상")
            print("  - 20-30초: 정상 복구")
            print("  - 30-40초: 심각한 고장")
            print("  - 40-50초: 복합 고장")
            print("  - 50-60초: 점진적 회복")
            print("  - 60-90초: 간헐적 스파이크")
            print("  - 90-120초: 완전 정상화")
        print("📊 유압 시스템: 부품 고장 조기 감지")
        print("⚡ 제조 공정: 에너지 소비 예측")
        print("-" * 50)
        
        try:
            # 메인 스레드 유지
            for thread in self.threads:
                thread.join()
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        """모든 시뮬레이터 중지"""
        print("\n시뮬레이터 중지 중...")
        self.hydraulic_sim.stop()
        self.manufacturing_sim.stop()
        
        for thread in self.threads:
            thread.join()
        
        print("모든 시뮬레이터 중지 완료")


# 사용 예제
if __name__ == "__main__":
    # CSV 파일 경로 설정
    HYDRAULIC_CSV = "C:/posco/data/hydraulic_processed_data.csv"
    MANUFACTURING_CSV = "C:/posco/data/Manufacturing_dataset.csv"
    
    # 듀얼 시뮬레이터 생성
    simulator = DualCSVSimulator(HYDRAULIC_CSV, MANUFACTURING_CSV)
    
    try:
        # 데이터 로드
        simulator.load_all()
        
        # 시뮬레이터 시작 - 테스트 모드, 시나리오 1
        # 유압: 0.5초마다 (빠른 테스트), 제조: 2초마다
        simulator.start(
            hydraulic_interval=0.5,      # 더 빠른 주기로 테스트
            manufacturing_interval=2.0,   # 더 빠른 주기로 테스트
            test_mode=True,              # 테스트 모드 활성화
            test_scenario=1              # 시나리오 1: 시간대별 명확한 구분
        )
        
    except Exception as e:
        print(f"오류 발생: {e}")
        
    # 개별 실행 옵션 (필요시 주석 해제)
    # # 유압 시뮬레이터만 실행
    # hydraulic_sim = HydraulicSimulator(HYDRAULIC_CSV)
    # hydraulic_sim.load_data()
    # hydraulic_sim.run(interval=1.0)
    
    # # 제조 시뮬레이터만 실행
    # manufacturing_sim = ManufacturingSimulator(MANUFACTURING_CSV)
    # manufacturing_sim.load_data()
    # manufacturing_sim.run(interval=5.0)