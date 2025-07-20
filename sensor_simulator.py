import requests
import time
import random
import json
from datetime import datetime, timedelta
import threading
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class IoTSensorSimulator:
    def __init__(self, api_url="http://localhost:8000", interval=30):
        self.api_url = api_url
        self.interval = interval  # 전송 간격 추가
        self.running = False
        self.equipment_list = [
            {"id": "press_001", "name": "프레스기 #001", "type": "프레스", "sensors": ["temperature", "pressure", "vibration"]},
            {"id": "press_002", "name": "프레스기 #002", "type": "프레스", "sensors": ["temperature", "pressure", "vibration"]},
            {"id": "weld_001", "name": "용접기 #001", "type": "용접", "sensors": ["temperature", "current", "voltage"]},
            {"id": "weld_002", "name": "용접기 #002", "type": "용접", "sensors": ["temperature", "current", "voltage"]},
            {"id": "assemble_001", "name": "조립기 #001", "type": "조립", "sensors": ["speed", "torque", "position"]},
            {"id": "inspect_001", "name": "검사기 #001", "type": "검사", "sensors": ["accuracy", "speed", "quality"]}
        ]
        
        # 센서별 정상 범위
        self.sensor_ranges = {
            "temperature": {"min": 20, "max": 80, "unit": "°C"},
            "pressure": {"min": 100, "max": 200, "unit": "bar"},
            "vibration": {"min": 0.1, "max": 2.0, "unit": "mm/s"},
            "current": {"min": 100, "max": 500, "unit": "A"},
            "voltage": {"min": 20, "max": 50, "unit": "V"},
            "speed": {"min": 10, "max": 100, "unit": "rpm"},
            "torque": {"min": 50, "max": 200, "unit": "Nm"},
            "position": {"min": 0, "max": 100, "unit": "mm"},
            "accuracy": {"min": 95, "max": 100, "unit": "%"},
            "quality": {"min": 90, "max": 100, "unit": "%"}
        }
        
        # 알림 임계값
        self.alert_thresholds = {
            "temperature": {"warning": 70, "critical": 85},
            "pressure": {"warning": 180, "critical": 190},
            "vibration": {"warning": 1.5, "critical": 2.0},
            "current": {"warning": 450, "critical": 480},
            "voltage": {"warning": 45, "critical": 48},
            "speed": {"warning": 90, "critical": 95},
            "torque": {"warning": 180, "critical": 190},
            "position": {"warning": 90, "critical": 95},
            "accuracy": {"warning": 97, "critical": 95},
            "quality": {"warning": 95, "critical": 92}
        }

    def generate_sensor_value(self, sensor_type, base_value=None):
        """센서 값 생성 (정상 범위 내에서 약간의 변동)"""
        range_info = self.sensor_ranges[sensor_type]
        
        if base_value is None:
            base_value = (range_info["min"] + range_info["max"]) / 2
        
        # 정상적인 변동 (5% 이내)
        variation = random.uniform(-0.05, 0.05)
        new_value = base_value * (1 + variation)
        
        # 범위 내로 제한
        new_value = max(range_info["min"], min(range_info["max"], new_value))
        
        return round(new_value, 2)

    def generate_anomaly(self, sensor_type, base_value):
        """이상 상황 생성 (10% 확률)"""
        if random.random() < 0.1:  # 10% 확률로 이상 발생
            range_info = self.sensor_ranges[sensor_type]
            threshold = self.alert_thresholds[sensor_type]
            
            # 경고 수준 이상값 생성
            if random.random() < 0.7:  # 70% 확률로 경고 수준
                anomaly_factor = random.uniform(1.1, 1.3)
            else:  # 30% 확률로 임계값 초과
                anomaly_factor = random.uniform(1.3, 1.5)
            
            return base_value * anomaly_factor
        
        return base_value

    def send_sensor_data(self, equipment_id, sensor_type, value):
        """센서 데이터를 API 서버로 전송"""
        try:
            data = {
                "equipment": equipment_id,
                "sensor_type": sensor_type,
                "value": value,
                "timestamp": datetime.now().isoformat()
            }
            
            response = requests.post(f"{self.api_url}/sensors", json=data, timeout=5)
            if response.status_code == 200:
                logger.debug(f"센서 데이터 전송 성공: {equipment_id} - {sensor_type}: {value}")
            else:
                logger.warning(f"센서 데이터 전송 실패: {response.status_code}")
                
        except requests.exceptions.RequestException as e:
            logger.error(f"센서 데이터 전송 오류: {e}")

    def check_and_send_alert(self, equipment_id, sensor_type, value):
        """임계값 체크 및 알림 전송"""
        if sensor_type in self.alert_thresholds:
            threshold = self.alert_thresholds[sensor_type]
            range_info = self.sensor_ranges[sensor_type]
            
            severity = None
            if value > threshold["critical"]:
                severity = "error"
            elif value > threshold["warning"]:
                severity = "warning"
            
            if severity:
                alert_data = {
                    "equipment": equipment_id,
                    "sensor_type": sensor_type,
                    "value": value,
                    "threshold": threshold["warning"] if severity == "warning" else threshold["critical"],
                    "severity": severity,
                    "timestamp": datetime.now().isoformat(),
                    "message": f"{sensor_type} 임계값 초과: {value}{range_info['unit']}"
                }
                
                try:
                    response = requests.post(f"{self.api_url}/alerts", json=alert_data, timeout=5)
                    if response.status_code == 200:
                        logger.info(f"알림 전송 성공: {equipment_id} - {severity}")
                    else:
                        logger.warning(f"알림 전송 실패: {response.status_code}")
                        
                except requests.exceptions.RequestException as e:
                    logger.error(f"알림 전송 오류: {e}")

    def simulate_equipment(self, equipment):
        """개별 설비 시뮬레이션"""
        equipment_id = equipment["id"]
        base_values = {}
        
        while self.running:
            try:
                # 설비의 모든 센서 데이터를 한 번에 수집
                sensor_data_batch = []
                
                for sensor_type in equipment["sensors"]:
                    # 기본값 초기화
                    if sensor_type not in base_values:
                        base_values[sensor_type] = self.generate_sensor_value(sensor_type)
                    
                    # 센서 값 생성
                    value = self.generate_sensor_value(sensor_type, base_values[sensor_type])
                    
                    # 이상 상황 생성
                    value = self.generate_anomaly(sensor_type, value)
                    
                    # 배치에 추가
                    sensor_data_batch.append({
                        'equipment_id': equipment_id,
                        'sensor_type': sensor_type,
                        'value': value
                    })
                    
                    # 기본값 업데이트
                    base_values[sensor_type] = value
                
                # 배치로 한 번에 전송
                for sensor_data in sensor_data_batch:
                    self.send_sensor_data(sensor_data['equipment_id'], sensor_data['sensor_type'], sensor_data['value'])
                    # 알림 체크
                    self.check_and_send_alert(sensor_data['equipment_id'], sensor_data['sensor_type'], sensor_data['value'])
                
                # 설정된 간격만큼 대기
                time.sleep(self.interval)  # 사용자가 설정한 간격 사용
                
            except Exception as e:
                logger.error(f"설비 시뮬레이션 오류 ({equipment_id}): {e}")
                time.sleep(10)

    def start(self):
        """시뮬레이터 시작"""
        self.running = True
        logger.info("IoT 센서 시뮬레이터 시작")
        
        # 각 설비별로 별도 스레드 생성
        threads = []
        for equipment in self.equipment_list:
            thread = threading.Thread(
                target=self.simulate_equipment, 
                args=(equipment,),
                daemon=True
            )
            thread.start()
            threads.append(thread)
            logger.info(f"설비 시뮬레이션 시작: {equipment['name']}")
        
        return threads

    def stop(self):
        """시뮬레이터 중지"""
        self.running = False
        logger.info("IoT 센서 시뮬레이터 중지")

def main():
    """메인 실행 함수"""
    print("🏭 POSCO MOBILITY IoT 센서 시뮬레이터")
    print("=" * 50)
    
    # API 서버 URL 확인
    api_url = input("API 서버 URL (기본: http://localhost:8000): ").strip()
    if not api_url:
        api_url = "http://localhost:8000"
    
    # 전송 간격 설정
    try:
        interval = input("전송 간격 (초, 기본: 30): ").strip()
        if not interval:
            interval = 30
        else:
            interval = int(interval)
    except ValueError:
        interval = 30
        print("잘못된 입력입니다. 기본값 30초를 사용합니다.")
    
    # 시뮬레이터 생성
    simulator = IoTSensorSimulator(api_url, interval)
    
    try:
        # 시뮬레이터 시작
        threads = simulator.start()
        
        print(f"시뮬레이터가 시작되었습니다!")
        print(f" API 서버: {api_url}")
        print(f" 시뮬레이션 설비: {len(simulator.equipment_list)}개")
        print(f" 전송 간격: {interval}초")
        print(" 실시간 센서 데이터 생성 중...")
        print(" 중지하려면 Ctrl+C를 누르세요.")
        
        # 메인 스레드 대기
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n\n 시뮬레이터를 중지합니다...")
        simulator.stop()
        print(" 시뮬레이터가 중지되었습니다.")

if __name__ == "__main__":
    main() 