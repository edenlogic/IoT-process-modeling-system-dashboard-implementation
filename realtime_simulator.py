import requests
import json
import time
import random
import numpy as np
from datetime import datetime, timedelta
import threading
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import pandas as pd

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('IoTSimulator')

# API 엔드포인트
API_BASE_URL = "http://localhost:8000"

class EquipmentStatus(Enum):
    """설비 상태 열거형"""
    NORMAL = "정상"
    WARNING = "주의"
    ERROR = "오류"

class SensorType(Enum):
    """센서 타입 열거형"""
    TEMPERATURE = "temperature"
    PRESSURE = "pressure"
    VIBRATION = "vibration"
    HUMIDITY = "humidity"
    POWER = "power"
    SPEED = "speed"

@dataclass
class SensorConfig:
    """센서 설정 클래스"""
    sensor_type: SensorType
    min_value: float
    max_value: float
    normal_range: Tuple[float, float]
    warning_threshold: float
    error_threshold: float
    noise_level: float = 0.1
    trend_factor: float = 0.0  # 트렌드 영향도

@dataclass
class Equipment:
    """설비 정보 클래스"""
    id: str
    name: str
    type: str
    sensors: List[SensorConfig]
    status: EquipmentStatus = EquipmentStatus.NORMAL
    efficiency: float = 95.0
    failure_probability: float = 0.001  # 고장 확률
    efficiency_updated: datetime = None  # 효율성 업데이트 시간
    
    def __post_init__(self):
        """초기화 후 처리"""
        if self.efficiency_updated is None:
            self.efficiency_updated = datetime.now()

class Scenario(Enum):
    """시뮬레이션 시나리오"""
    NORMAL = "normal"  # 정상 운영
    GRADUAL_DEGRADATION = "gradual_degradation"  # 점진적 성능 저하
    SUDDEN_FAILURE = "sudden_failure"  # 급작스런 고장
    PERIODIC_MAINTENANCE = "periodic_maintenance"  # 정기 점검
    OVERLOAD = "overload"  # 과부하
    SENSOR_MALFUNCTION = "sensor_malfunction"  # 센서 오작동
    CYBER_ATTACK = "cyber_attack"  # 사이버 공격 (이상 패턴)

class IoTDataSimulator:
    """IoT 데이터 시뮬레이터 메인 클래스"""
    
    def __init__(self):
        self.equipment_list = self._initialize_equipment()
        self.running = False
        self.threads = []
        self.scenario = Scenario.NORMAL
        self.time_acceleration = 1.0  # 시간 가속 배율
        self.data_buffer = []  # 데이터 버퍼
        self.alert_buffer = []  # 알림 버퍼
        self.data_lock = threading.Lock()  # 스레드 동기화용
        self.alert_lock = threading.Lock()  # 알림 버퍼 동기화용
        
    def _initialize_equipment(self) -> List[Equipment]:
        """설비 및 센서 초기화"""
        equipment_configs = [
            # 프레스기
            Equipment(
                id="press_001",
                name="프레스기 #001",
                type="프레스",
                sensors=[
                    SensorConfig(
                        sensor_type=SensorType.TEMPERATURE,
                        min_value=20, max_value=100,
                        normal_range=(40, 60),
                        warning_threshold=65,  # 낮춤
                        error_threshold=75,    # 낮춤
                        noise_level=3.0
                    ),
                    SensorConfig(
                        sensor_type=SensorType.PRESSURE,
                        min_value=0, max_value=300,
                        normal_range=(120, 180),
                        warning_threshold=200,  # 낮춤
                        error_threshold=220,    # 낮춤
                        noise_level=8.0
                    ),
                    SensorConfig(
                        sensor_type=SensorType.VIBRATION,
                        min_value=0, max_value=5,
                        normal_range=(0.2, 0.8),
                        warning_threshold=1.2,  # 낮춤
                        error_threshold=1.5,    # 낮춤
                        noise_level=0.15
                    )
                ]
            ),
            Equipment(
                id="press_002",
                name="프레스기 #002",
                type="프레스",
                sensors=[
                    SensorConfig(
                        sensor_type=SensorType.TEMPERATURE,
                        min_value=20, max_value=100,
                        normal_range=(40, 60),
                        warning_threshold=75,
                        error_threshold=85,
                        noise_level=2.0
                    ),
                    SensorConfig(
                        sensor_type=SensorType.PRESSURE,
                        min_value=0, max_value=300,
                        normal_range=(120, 180),
                        warning_threshold=220,
                        error_threshold=250,
                        noise_level=5.0
                    )
                ]
            ),
            # 용접기
            Equipment(
                id="weld_001",
                name="용접기 #001",
                type="용접",
                sensors=[
                    SensorConfig(
                        sensor_type=SensorType.TEMPERATURE,
                        min_value=100, max_value=500,
                        normal_range=(200, 300),
                        warning_threshold=350,
                        error_threshold=400,
                        noise_level=10.0
                    ),
                    SensorConfig(
                        sensor_type=SensorType.POWER,
                        min_value=0, max_value=100,
                        normal_range=(40, 70),
                        warning_threshold=85,
                        error_threshold=95,
                        noise_level=3.0
                    )
                ]
            ),
            Equipment(
                id="weld_002",
                name="용접기 #002",
                type="용접",
                sensors=[
                    SensorConfig(
                        sensor_type=SensorType.TEMPERATURE,
                        min_value=100, max_value=500,
                        normal_range=(200, 300),
                        warning_threshold=350,
                        error_threshold=400,
                        noise_level=10.0
                    ),
                    SensorConfig(
                        sensor_type=SensorType.POWER,
                        min_value=0, max_value=100,
                        normal_range=(40, 70),
                        warning_threshold=85,
                        error_threshold=95,
                        noise_level=3.0
                    )
                ]
            ),
            # 조립기
            Equipment(
                id="assemble_001",
                name="조립기 #001",
                type="조립",
                sensors=[
                    SensorConfig(
                        sensor_type=SensorType.SPEED,
                        min_value=0, max_value=200,
                        normal_range=(80, 120),
                        warning_threshold=150,
                        error_threshold=180,
                        noise_level=5.0
                    ),
                    SensorConfig(
                        sensor_type=SensorType.VIBRATION,
                        min_value=0, max_value=3,
                        normal_range=(0.1, 0.5),
                        warning_threshold=1.0,
                        error_threshold=1.5,
                        noise_level=0.05
                    )
                ]
            ),
            # 검사기
            Equipment(
                id="inspect_001",
                name="검사기 #001",
                type="검사",
                sensors=[
                    SensorConfig(
                        sensor_type=SensorType.POWER,
                        min_value=0, max_value=50,
                        normal_range=(10, 30),
                        warning_threshold=40,
                        error_threshold=45,
                        noise_level=2.0
                    )
                ]
            )
        ]
        
        return equipment_configs
    
    def generate_sensor_value(self, equipment: Equipment, sensor: SensorConfig, 
                            timestamp: datetime) -> float:
        """센서 값 생성 (시나리오 기반)"""
        
        # 기본값: 정상 범위 중간값
        base_value = (sensor.normal_range[0] + sensor.normal_range[1]) / 2
        
        # 시간에 따른 주기적 변동 (일일 패턴)
        hour = timestamp.hour
        daily_pattern = np.sin(2 * np.pi * hour / 24) * 5
        
        # 노이즈 추가
        noise = np.random.normal(0, sensor.noise_level)
        
        # 시나리오별 값 조정
        if self.scenario == Scenario.NORMAL:
            # 정상: 기본 패턴 + 노이즈 + 가끔 스파이크
            value = base_value + daily_pattern + noise
            # 10% 확률로 작은 스파이크 추가
            if random.random() < 0.1:
                spike = random.uniform(5, 15) * random.choice([1, -1])
                value += spike
                
        elif self.scenario == Scenario.GRADUAL_DEGRADATION:
            # 점진적 성능 저하: 시간에 따라 값이 증가
            days_elapsed = (datetime.now() - equipment.efficiency_updated).total_seconds() / 86400  # 일 단위
            degradation = days_elapsed * 5  # 하루에 5씩 증가 (테스트용으로 빠르게)
            value = base_value + daily_pattern + noise + degradation
            
        elif self.scenario == Scenario.SUDDEN_FAILURE:
            # 급작스런 고장: 자주 이상값 발생
            if random.random() < 0.3:  # 30% 확률로 이상값
                value = sensor.error_threshold + random.uniform(0, 20)
            else:
                value = base_value + daily_pattern + noise
                
        elif self.scenario == Scenario.OVERLOAD:
            # 과부하: 모든 값이 높은 범위에서 변동
            overload_factor = 1.5  # 1.3 → 1.5로 증가
            value = base_value * overload_factor + daily_pattern + noise
            # 추가로 20% 확률로 임계값 초과
            if random.random() < 0.2:
                value = sensor.warning_threshold + random.uniform(0, 10)
            
        elif self.scenario == Scenario.SENSOR_MALFUNCTION:
            # 센서 오작동: 비정상적인 패턴
            if random.random() < 0.2:  # 20% 확률로 오작동
                # 이상한 값들: 0, 최대값, 랜덤
                malfunction_type = random.choice(['zero', 'max', 'random'])
                if malfunction_type == 'zero':
                    value = 0
                elif malfunction_type == 'max':
                    value = sensor.max_value
                else:
                    value = random.uniform(sensor.min_value, sensor.max_value)
            else:
                value = base_value + daily_pattern + noise
                
        elif self.scenario == Scenario.CYBER_ATTACK:
            # 사이버 공격: 규칙적인 이상 패턴
            attack_pattern = np.sin(10 * np.pi * timestamp.second / 60) * 20
            value = base_value + attack_pattern + noise
            
        else:
            value = base_value + daily_pattern + noise
        
        # 값 범위 제한
        value = np.clip(value, sensor.min_value, sensor.max_value)
        
        return float(value)
    
    def check_and_create_alert(self, equipment: Equipment, sensor: SensorConfig, 
                              value: float, timestamp: datetime):
        """임계값 체크 및 알림 생성"""
        severity = None
        message = None
        
        if value >= sensor.error_threshold:
            severity = "error"
            message = f"{sensor.sensor_type.value} 임계값 초과: {value:.2f} (임계값: {sensor.error_threshold})"
            equipment.status = EquipmentStatus.ERROR
            
        elif value >= sensor.warning_threshold:
            severity = "warning"
            message = f"{sensor.sensor_type.value} 경고 수준: {value:.2f} (경고값: {sensor.warning_threshold})"
            if equipment.status != EquipmentStatus.ERROR:
                equipment.status = EquipmentStatus.WARNING
                
        else:
            # 모든 센서가 정상이면 설비 상태도 정상으로
            all_normal = True
            for s in equipment.sensors:
                last_value = getattr(equipment, f'last_{s.sensor_type.value}', 0)
                if last_value >= s.warning_threshold:
                    all_normal = False
                    break
            if all_normal:
                equipment.status = EquipmentStatus.NORMAL
        
        # 알림 생성
        if severity:
            alert_data = {
                "equipment": equipment.id,
                "sensor_type": sensor.sensor_type.value,
                "value": value,
                "threshold": sensor.error_threshold if severity == "error" else sensor.warning_threshold,
                "severity": severity,
                "timestamp": timestamp.isoformat(),
                "message": message
            }
            
            with self.alert_lock:
                self.alert_buffer.append(alert_data)
            
            logger.info(f"🚨 알림 생성: {equipment.name} - {message}")
    
    def send_sensor_data(self):
        """버퍼의 센서 데이터를 API로 전송"""
        with self.data_lock:
            if not self.data_buffer:
                return
            
            # 버퍼 복사 후 비우기
            data_to_send = self.data_buffer.copy()
            self.data_buffer.clear()
            
        try:
            for data in data_to_send:
                response = requests.post(
                    f"{API_BASE_URL}/sensors",
                    json=data,
                    timeout=5
                )
                if response.status_code != 200:
                    logger.error(f"센서 데이터 전송 실패: {response.status_code}")
            
            logger.info(f"센서 데이터 {len(data_to_send)}건 전송 완료")
            
        except Exception as e:
            logger.error(f"센서 데이터 전송 오류: {e}")
    
    def send_alerts(self):
        """버퍼의 알림을 API로 전송"""
        with self.alert_lock:
            if not self.alert_buffer:
                return
            
            # 버퍼 복사 후 비우기
            alerts_to_send = self.alert_buffer.copy()
            self.alert_buffer.clear()
            
        try:
            for alert in alerts_to_send:
                response = requests.post(
                    f"{API_BASE_URL}/alerts",
                    json=alert,
                    timeout=5
                )
                if response.status_code != 200:
                    logger.error(f"알림 전송 실패: {response.status_code}")
            
            logger.info(f"알림 {len(alerts_to_send)}건 전송 완료")
            
        except Exception as e:
            logger.error(f"알림 전송 오류: {e}")
    
    def update_equipment_status(self, equipment: Equipment):
        """설비 상태 업데이트"""
        try:
            # 효율성 계산 (상태에 따라)
            if equipment.status == EquipmentStatus.ERROR:
                equipment.efficiency = 0
            elif equipment.status == EquipmentStatus.WARNING:
                equipment.efficiency = random.uniform(60, 80)
            else:
                equipment.efficiency = random.uniform(85, 98)
            
            response = requests.put(
                f"{API_BASE_URL}/equipment/{equipment.id}/status",
                params={
                    "status": equipment.status.value,
                    "efficiency": equipment.efficiency
                },
                timeout=5
            )
            
            if response.status_code != 200:
                logger.error(f"설비 상태 업데이트 실패: {response.status_code}")
                
        except Exception as e:
            logger.error(f"설비 상태 업데이트 오류: {e}")
    
    def simulate_equipment(self, equipment: Equipment):
        """개별 설비 시뮬레이션"""
        logger.info(f"{equipment.name} 시뮬레이션 시작")
        
        while self.running:
            timestamp = datetime.now()
            
            # 각 센서별 데이터 생성
            for sensor in equipment.sensors:
                value = self.generate_sensor_value(equipment, sensor, timestamp)
                
                # 센서 데이터 버퍼에 추가 (스레드 안전)
                sensor_data = {
                    "equipment": equipment.id,
                    "sensor_type": sensor.sensor_type.value,
                    "value": value,
                    "timestamp": timestamp.isoformat()
                }
                
                with self.data_lock:
                    self.data_buffer.append(sensor_data)
                
                # 임계값 체크 및 알림 생성
                self.check_and_create_alert(equipment, sensor, value, timestamp)
                
                # 마지막 값 저장 (상태 확인용)
                setattr(equipment, f'last_{sensor.sensor_type.value}', value)
                
                # 로그에 값 출력 (디버깅용)
                logger.debug(f"{equipment.name} - {sensor.sensor_type.value}: {value:.2f}")
            
            # 설비 상태 업데이트
            self.update_equipment_status(equipment)
            
            # 버퍼가 일정 크기 이상이면 전송
            if len(self.data_buffer) >= 10:
                self.send_sensor_data()
            
            if len(self.alert_buffer) >= 3:  # 알림은 3개 이상이면 전송
                self.send_alerts()
            
            # 대기 (시간 가속 적용)
            time.sleep(5 / self.time_acceleration)  # 5초마다 데이터 생성
        
        logger.info(f"{equipment.name} 시뮬레이션 종료")
    
    def start(self, scenario: Scenario = Scenario.NORMAL, time_acceleration: float = 1.0):
        """시뮬레이션 시작"""
        self.scenario = scenario
        self.time_acceleration = time_acceleration
        self.running = True
        
        logger.info(f"시뮬레이션 시작 - 시나리오: {scenario.value}, 시간 가속: {time_acceleration}x")
        
        # 각 설비별 스레드 생성
        for equipment in self.equipment_list:
            thread = threading.Thread(
                target=self.simulate_equipment,
                args=(equipment,),
                daemon=True
            )
            thread.start()
            self.threads.append(thread)
        
        # 메인 루프
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()
    
    def stop(self):
        """시뮬레이션 중지"""
        logger.info("시뮬레이션 중지 중...")
        self.running = False
        
        # 남은 데이터 전송
        self.send_sensor_data()
        self.send_alerts()
        
        # 스레드 종료 대기
        for thread in self.threads:
            thread.join()
        
        logger.info("시뮬레이션 완전 중지")
    
    def run_batch_scenario(self, scenario_sequence: List[Tuple[Scenario, int]]):
        """배치 시나리오 실행"""
        for scenario, duration in scenario_sequence:
            logger.info(f"시나리오 '{scenario.value}' {duration}초 동안 실행")
            self.scenario = scenario
            time.sleep(duration)
        
        self.stop()

class DataGenerator:
    """과거 데이터 생성기 (테스트용)"""
    
    @staticmethod
    def generate_historical_data(equipment_id: str, sensor_type: str, 
                               start_date: datetime, end_date: datetime,
                               interval_minutes: int = 5) -> pd.DataFrame:
        """과거 데이터 생성"""
        timestamps = pd.date_range(start=start_date, end=end_date, 
                                 freq=f'{interval_minutes}min')
        
        # 기본 패턴 생성
        base_pattern = 50 + 10 * np.sin(2 * np.pi * np.arange(len(timestamps)) / (24 * 60 / interval_minutes))
        
        # 노이즈 추가
        noise = np.random.normal(0, 2, len(timestamps))
        
        # 이상값 추가 (5% 확률)
        anomalies = np.random.random(len(timestamps)) < 0.05
        values = base_pattern + noise
        values[anomalies] = values[anomalies] * 1.5
        
        df = pd.DataFrame({
            'timestamp': timestamps,
            'equipment': equipment_id,
            'sensor_type': sensor_type,
            'value': values
        })
        
        return df
    
    @staticmethod
    def inject_historical_data(df: pd.DataFrame):
        """과거 데이터를 API에 주입"""
        for _, row in df.iterrows():
            data = {
                "equipment": row['equipment'],
                "sensor_type": row['sensor_type'],
                "value": row['value'],
                "timestamp": row['timestamp'].isoformat()
            }
            
            try:
                response = requests.post(
                    f"{API_BASE_URL}/sensors",
                    json=data,
                    timeout=5
                )
                if response.status_code != 200:
                    logger.error(f"데이터 주입 실패: {response.status_code}")
            except Exception as e:
                logger.error(f"데이터 주입 오류: {e}")
        
        logger.info(f"과거 데이터 {len(df)}건 주입 완료")

# 사용 예제
if __name__ == "__main__":
    # 시뮬레이터 생성
    simulator = IoTDataSimulator()
    
    # 테스트용: 알림이 많이 생성되는 시나리오 조합
    print("🚀 IoT 데이터 시뮬레이터 시작!")
    print("📊 다양한 시나리오로 데이터와 알림을 생성합니다...")
    print("-" * 50)
    
    # 옵션 1: 빠른 테스트 (알림 많이 생성)
    scenario_sequence = [
        (Scenario.NORMAL, 30),           # 정상 운영 30초 (가끔 스파이크)
        (Scenario.OVERLOAD, 20),         # 과부하 20초 (알림 다수 발생)
        (Scenario.SUDDEN_FAILURE, 15),   # 급작스런 고장 15초 (알림 폭발)
        (Scenario.SENSOR_MALFUNCTION, 10), # 센서 오작동 10초
        (Scenario.GRADUAL_DEGRADATION, 30), # 점진적 악화 30초
        (Scenario.CYBER_ATTACK, 15),     # 사이버 공격 패턴 15초
        (Scenario.NORMAL, 30),           # 정상 복구 30초
    ]
    
    # 배치 시나리오를 별도 스레드에서 실행
    threading.Thread(
        target=simulator.run_batch_scenario,
        args=(scenario_sequence,),
        daemon=True
    ).start()
    
    # 동시에 정상 시뮬레이션도 실행 (시간 가속 3배)
    simulator.start(scenario=Scenario.NORMAL, time_acceleration=3.0)
    
    # 옵션 2: 특정 시나리오만 실행 (주석 해제하여 사용)
    # simulator.start(scenario=Scenario.SUDDEN_FAILURE, time_acceleration=5.0)
    
    # 옵션 3: 과거 데이터 대량 생성 (주석 해제하여 사용)
    # print("\n📈 과거 데이터 생성 중...")
    # generator = DataGenerator()
    # for equipment_id in ["press_001", "weld_001", "assemble_001"]:
    #     for sensor_type in ["temperature", "pressure", "vibration"]:
    #         historical_data = generator.generate_historical_data(
    #             equipment_id=equipment_id,
    #             sensor_type=sensor_type,
    #             start_date=datetime.now() - timedelta(hours=2),
    #             end_date=datetime.now(),
    #             interval_minutes=5
    #         )
    #         generator.inject_historical_data(historical_data)
    #         print(f"✅ {equipment_id}/{sensor_type} 데이터 주입 완료")