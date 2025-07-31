import requests
import time
import logging
from datetime import datetime
from typing import Optional, Tuple
import random
from dataclasses import dataclass

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# API 엔드포인트
API_BASE_URL = "http://localhost:8000"
SENSOR_API = f"{API_BASE_URL}/sensors"
ALERT_API = f"{API_BASE_URL}/alerts"
EQUIPMENT_STATUS_API = f"{API_BASE_URL}/equipment"

@dataclass
class Equipment:
    """설비 정보"""
    id: str
    name: str
    type: str
    
@dataclass
class SensorThreshold:
    """센서별 임계값 정보"""
    normal_range: Tuple[float, float]  # 정상 범위
    warning_threshold: float           # 주의 임계값 (H)
    error_threshold: float             # 경고 임계값 (HH)
    unit: str                          # 단위

class MultiEquipmentSimulator:
    """다중 설비 시뮬레이터"""
    
    def __init__(self):
        # 설비 정의
        self.equipments = [
            # 프레스기
            Equipment("press_001", "프레스기 #1", "프레스"),
            Equipment("press_002", "프레스기 #2", "프레스"),
            Equipment("press_003", "프레스기 #3", "프레스"),
            Equipment("press_004", "프레스기 #4", "프레스"),
            # 용접기
            Equipment("weld_001", "용접기 #1", "용접"),
            Equipment("weld_002", "용접기 #2", "용접"),
            Equipment("weld_003", "용접기 #3", "용접"),
            Equipment("weld_004", "용접기 #4", "용접"),
            # 조립기
            Equipment("assemble_001", "조립기 #1", "조립"),
            Equipment("assemble_002", "조립기 #2", "조립"),
            Equipment("assemble_003", "조립기 #3", "조립"),
            # 검사기
            Equipment("inspect_001", "검사기 #1", "검사"),
            Equipment("inspect_002", "검사기 #2", "검사"),
            Equipment("inspect_003", "검사기 #3", "검사"),
            # 포장기
            Equipment("pack_001", "포장기 #1", "포장"),
            Equipment("pack_002", "포장기 #2", "포장"),
        ]
        
        # DB에 실제로 존재하는 설비 ID만 필터링
        try:
            
            # API 서버가 준비될 때까지 최대 10초 대기
            for attempt in range(10):
                try:
                    resp = requests.get("http://localhost:8000/api/equipment_status", timeout=3)
                    if resp.status_code == 200:
                        equipment_list = resp.json()
                        db_ids = set([item['id'] for item in equipment_list])
                        logger.info(f"🔍 API 응답: {len(equipment_list)}개 설비 발견")
                        if len(db_ids) > 0:  # 설비가 실제로 있으면
                            self.equipments = [eq for eq in self.equipments if eq.id in db_ids]
                            logger.info(f"✅ DB에서 {len(self.equipments)}개 설비 로드 완료")
                            # 설비 목록 출력
                            for eq in self.equipments:
                                logger.info(f"  - {eq.id}: {eq.name}")
                            break
                        else:
                            logger.warning(f"⚠️ DB에 설비가 없음 (시도 {attempt+1}/10), 1초 대기...")
                            time.sleep(1)
                    else:
                        logger.warning(f"⚠️ API 실패: {resp.status_code} (시도 {attempt+1}/10), 1초 대기...")
                        time.sleep(1)
                except Exception as e:
                    logger.warning(f"⚠️ API 연결 실패 (시도 {attempt+1}/10): {e}, 1초 대기...")
                    time.sleep(1)
            else:
                logger.warning("⚠️ API 서버 연결 실패, 전체 설비 사용")
        except Exception as e:
            logger.warning(f"⚠️ 설비 리스트 API 예외: {e}, 전체 설비 사용")
        
        # 설비가 없으면 시뮬레이터 종료
        if len(self.equipments) == 0:
            logger.error("❌ 설비가 없어서 시뮬레이터를 종료합니다.")
            raise Exception("설비가 없습니다. API 서버를 확인해주세요.")
        
        # 알림 카운터 초기화
        self.alert_count = {'error': 0, 'warning': 0}
        
        # 센서 타입별 임계값 정의 (설비 타입별로 다르게 설정)
        self.sensor_thresholds = {
            "프레스": {
                "temperature": SensorThreshold(
                    normal_range=(45, 65),
                    warning_threshold=70,    # H: 70도 이상
                    error_threshold=80,      # HH: 80도 이상
                    unit="°C"
                ),
                "pressure": SensorThreshold(
                    normal_range=(0.8, 1.0),
                    warning_threshold=1.2,   # H: 1.2 이상
                    error_threshold=1.5,     # HH: 1.5 이상
                    unit="MPa"
                ),
                "vibration": SensorThreshold(
                    normal_range=(1.5, 2.5),
                    warning_threshold=3.0,   # H: 3.0 이상
                    error_threshold=4.0,     # HH: 4.0 이상
                    unit="mm/s"
                )
            },
            "용접": {
                "temperature": SensorThreshold(
                    normal_range=(60, 85),
                    warning_threshold=90,    # H: 90도 이상
                    error_threshold=100,     # HH: 100도 이상
                    unit="°C"
                ),
                "pressure": SensorThreshold(
                    normal_range=(1.0, 1.3),
                    warning_threshold=1.5,   # H: 1.5 이상
                    error_threshold=1.8,     # HH: 1.8 이상
                    unit="MPa"
                ),
                "vibration": SensorThreshold(
                    normal_range=(2.0, 3.0),
                    warning_threshold=3.5,   # H: 3.5 이상
                    error_threshold=4.5,     # HH: 4.5 이상
                    unit="mm/s"
                )
            },
            "조립": {
                "temperature": SensorThreshold(
                    normal_range=(20, 35),
                    warning_threshold=40,    # H: 40도 이상
                    error_threshold=45,      # HH: 45도 이상
                    unit="°C"
                ),
                "pressure": SensorThreshold(
                    normal_range=(0.5, 0.8),
                    warning_threshold=1.0,   # H: 1.0 이상
                    error_threshold=1.2,     # HH: 1.2 이상
                    unit="MPa"
                ),
                "vibration": SensorThreshold(
                    normal_range=(1.0, 2.0),
                    warning_threshold=2.5,   # H: 2.5 이상
                    error_threshold=3.0,     # HH: 3.0 이상
                    unit="mm/s"
                )
            },
            "검사": {
                "temperature": SensorThreshold(
                    normal_range=(22, 28),
                    warning_threshold=32,    # H: 32도 이상
                    error_threshold=35,      # HH: 35도 이상
                    unit="°C"
                ),
                "pressure": SensorThreshold(
                    normal_range=(0.3, 0.5),
                    warning_threshold=0.7,   # H: 0.7 이상
                    error_threshold=0.9,     # HH: 0.9 이상
                    unit="MPa"
                ),
                "vibration": SensorThreshold(
                    normal_range=(0.5, 1.5),
                    warning_threshold=2.0,   # H: 2.0 이상
                    error_threshold=2.5,     # HH: 2.5 이상
                    unit="mm/s"
                )
            },
            "포장": {
                "temperature": SensorThreshold(
                    normal_range=(18, 25),
                    warning_threshold=30,    # H: 30도 이상
                    error_threshold=35,      # HH: 35도 이상
                    unit="°C"
                ),
                "pressure": SensorThreshold(
                    normal_range=(0.2, 0.4),
                    warning_threshold=0.6,   # H: 0.6 이상
                    error_threshold=0.8,     # HH: 0.8 이상
                    unit="MPa"
                ),
                "vibration": SensorThreshold(
                    normal_range=(0.8, 1.8),
                    warning_threshold=2.3,   # H: 2.3 이상
                    error_threshold=3.0,     # HH: 3.0 이상
                    unit="mm/s"
                )
            }
        }
        
        # 알림 카운터 초기화
        self.alert_count = {"error": 0, "warning": 0}
        self.running = False
        

    
    def generate_sensor_value(self, equipment: Equipment, sensor_type: str, 
                            force_severity: Optional[str] = None) -> float:
        """센서값 생성"""
        threshold = self.sensor_thresholds[equipment.type][sensor_type]
        
        if force_severity == "error":
            # HH 범위의 값 생성 - 임계값보다 확실히 높게
            base = threshold.error_threshold
            value = base * random.uniform(1.05, 1.2)  # 5~20% 높게
            
        elif force_severity == "warning":
            # H 범위의 값 생성 (warning과 error 사이)
            min_val = threshold.warning_threshold
            max_val = threshold.error_threshold
            value = random.uniform(min_val * 1.02, max_val * 0.98)  # 여유를 둠
            
        else:
            # 정상 범위의 값 생성 (약간의 변동성 추가)
            min_val, max_val = threshold.normal_range
            mean = (min_val + max_val) / 2
            std = (max_val - min_val) / 6
            
            # 가끔 정상 범위를 살짝 벗어나는 값도 생성 (더 현실적)
            if random.random() < 0.05:  # 5% 확률로
                value = random.gauss(mean, std * 1.5)
            else:
                value = random.gauss(mean, std)
            
            value = max(min_val * 0.9, min(max_val * 1.1, value))
        
        return round(value, 2)
    
    def send_sensor_data(self, equipment: Equipment, sensor_type: str, value: float):
        """센서 데이터 전송"""
        data = {
            "equipment": equipment.id,
            "sensor_type": sensor_type,
            "value": value,
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            response = requests.post(SENSOR_API, json=data, timeout=5)
            if response.status_code == 200:
                logger.info(f"[센서] {equipment.id} {sensor_type}={value}")
        except Exception as e:
            logger.error(f"[센서] 데이터 전송 오류: {e}")
    
    def send_system_alert(self, equipment: Equipment, efficiency: float):
        """시스템 알림 전송 (가동률 0% 등)"""
        alert_data = {
            "equipment": equipment.id,
            "sensor_type": "system",
            "value": efficiency,
            "threshold": 5.0,
            "severity": "error",
            "timestamp": datetime.now().isoformat(),
            "message": f"{equipment.name} 가동률 {efficiency:.1f}% - 시스템 이상 감지"
        }
        
        try:
            response = requests.post(ALERT_API, json=alert_data, timeout=5)
            if response.status_code == 200:
                logger.info(f"🚨 [SYSTEM] {equipment.name} 가동률 {efficiency:.1f}% - 시스템 알림 발생")
                self.alert_count["error"] += 1
        except Exception as e:
            logger.error(f"[시스템알림] 전송 오류: {e}")
    
    def send_alert(self, equipment: Equipment, sensor_type: str, 
                   value: float, severity: str):
        """알람 전송"""
        threshold = self.sensor_thresholds[equipment.type][sensor_type]
        
        if severity == "error":
            threshold_value = threshold.error_threshold
            severity_code = "HH"
        else:
            threshold_value = threshold.warning_threshold
            severity_code = "H"
        
        alert_data = {
            "equipment": equipment.id,
            "sensor_type": sensor_type,
            "value": value,
            "threshold": threshold_value,
            "severity": severity,
            "timestamp": datetime.now().isoformat(),
            "message": f"{equipment.name} {sensor_type} {severity_code} "
                      f"임계치 초과: {value}{threshold.unit} "
                      f"(임계값: {threshold_value}{threshold.unit})"
        }
        
        try:
            response = requests.post(ALERT_API, json=alert_data, timeout=5)
            if response.status_code == 200:
                logger.info(f"🚨 [{severity.upper()}] {equipment.name} "
                           f"{sensor_type} = {value}{threshold.unit}")
                self.alert_count[severity] += 1
        except Exception as e:
            logger.error(f"[알람] 전송 오류: {e}")
    
    def update_equipment_status(self, equipment_id: str, status: str, efficiency: float):
        """설비 상태 업데이트"""
        url = f"{EQUIPMENT_STATUS_API}/{equipment_id}/status"
        try:
            # API 서버에서 status와 efficiency를 쿼리 파라미터로 받음
            response = requests.put(url, params={"status": status, "efficiency": efficiency}, timeout=5)
            if response.status_code == 200:
                logger.info(f"[설비상태] {equipment_id} 상태={status}, 효율={efficiency:.1f}% - API 성공")
            else:
                logger.error(f"[설비상태] 업데이트 실패: {response.status_code} - {response.text}")
        except Exception as e:
            logger.error(f"[설비상태] 업데이트 오류: {e}")
    
    def run(self, duration_seconds: int = 120, interval: float = 2.0):
        """시뮬레이터 실행"""
        self.running = True
        self.start_time = time.time()
        
        logger.info("="*50)
        logger.info("🚀 다중 설비 시뮬레이터 시작!")
        logger.info(f"⏱️ 실행 시간: {duration_seconds}초")
        logger.info("="*50)
        
        # 알림 카운터 초기화
        alert_counter = 0
        # 20초마다 알림 생성 (총 6개: 20초, 40초, 60초, 80초, 100초, 120초)
        alert_times = [20, 40, 60, 80, 100, 120]
        next_alert_idx = 0
        last_alert_check = 0
        alerted_equipment = set()  # 이미 알림이 생성된 장비 추적
        
        while self.running:
            current_time = time.time()
            elapsed = current_time - self.start_time
            
            if elapsed >= duration_seconds:
                break
            
            # 고정된 시간에 알림 생성 (총 6개) - 우선순위로 처리
            if (next_alert_idx < len(alert_times) and 
                elapsed >= alert_times[next_alert_idx] and
                elapsed - last_alert_check >= 0.5):  # 최소 0.5초 간격으로 완화
                
                # 아직 알림이 생성되지 않은 장비들 중에서 선택
                available_equipment = [eq for eq in self.equipments if eq.id not in alerted_equipment]
                
                # 모든 장비에 알림이 생성되었다면 초기화
                if not available_equipment:
                    alerted_equipment.clear()
                    available_equipment = self.equipments
                
                # 랜덤 설비와 센서 선택
                equipment = random.choice(available_equipment)
                sensor_type = random.choice(["temperature", "pressure", "vibration"])
                severity = random.choice(["warning", "error"])
                
                # 알림 발생
                value = self.generate_sensor_value(equipment, sensor_type, severity)
                self.send_alert(equipment, sensor_type, value, severity)
                
                # 알림 발생 시 설비 상태 업데이트
                if severity == "error":
                    status = "오류"
                else:
                    status = "주의"
                efficiency = round(random.uniform(75.0, 98.0), 1)
                self.update_equipment_status(equipment.id, status, efficiency)
                
                # 알림 생성된 장비 기록
                alerted_equipment.add(equipment.id)
                
                alert_counter += 1
                next_alert_idx += 1
                last_alert_check = elapsed
                logger.info(f"🚨 [알림 #{alert_counter}] {equipment.name} {sensor_type} {severity.upper()} - {value:.1f}")
                
                # 알림 생성 후 즉시 다음 루프로
                continue
            
            # 센서 데이터 생성은 알림 생성 후에 처리 (더 많은 빈도로)
            # 매 루프마다 모든 설비에서 센서 데이터 생성 (확률 제거)
            for equipment in self.equipments:
                # 설비 상태 업데이트 (랜덤 간격)
                if random.random() < 0.3:  # 30% 확률로 설비 상태 업데이트
                    efficiency = round(random.uniform(75.0, 98.0), 1)
                    status = "정상"
                    self.update_equipment_status(equipment.id, status, efficiency)
                    logger.info(f"[설비상태] {equipment.name}: {efficiency:.1f}% ({status})")
                
                # 센서 데이터 생성 및 전송 (매번 전송)
                sensor_type = random.choice(["temperature", "pressure", "vibration"])
                value = self.generate_sensor_value(equipment, sensor_type)
                self.send_sensor_data(equipment, sensor_type, value)
            
            time.sleep(interval)
        
        # 최종 결과
        final_elapsed = time.time() - self.start_time
        logger.info("="*50)
        logger.info("✅ 시뮬레이션 완료!")
        logger.info(f"📊 최종 결과: 경고(HH) {self.alert_count['error']}개, "
                   f"주의(H) {self.alert_count['warning']}개")
        logger.info(f"⏱️ 총 실행 시간: {final_elapsed:.1f}초")
        logger.info("="*50)
    
    def stop(self):
        """시뮬레이터 중지"""
        self.running = False
        logger.info("시뮬레이터 중지 요청")


# 메인 실행
if __name__ == "__main__":
    simulator = MultiEquipmentSimulator()
    
    try:
        # 2분간 실행, 0.02초마다 데이터 생성 (매우 빠른 속도로 더 많은 데이터 생성)
        simulator.run(duration_seconds=120, interval=0.02)
        
    except KeyboardInterrupt:
        logger.info("\n사용자에 의해 중지됨")
        simulator.stop()
    except Exception as e:
        logger.error(f"오류 발생: {e}")
        simulator.stop()