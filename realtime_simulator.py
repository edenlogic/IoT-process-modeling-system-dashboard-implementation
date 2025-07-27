import numpy as np
import requests
import json
import time
import logging
from datetime import datetime, timedelta
import threading
from typing import Dict, List, Optional, Tuple
import random
from dataclasses import dataclass
from collections import defaultdict

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
        
        # 알람 관리
        self.planned_alerts = []  # 발생시킬 알람 계획
        self.sent_alerts = set()  # 이미 발송한 알람
        self.alert_count = {"error": 0, "warning": 0}
        self.running = False
        
    def plan_alerts(self, duration_seconds: int = 120):
        """2분(120초) 동안 발생할 알람 계획 수립"""
        self.planned_alerts = []
        
        # 가능한 모든 조합 (16개 설비 × 3개 센서 = 48개)
        all_combinations = []
        for equipment in self.equipments:
            for sensor_type in ["temperature", "pressure", "vibration"]:
                all_combinations.append((equipment, sensor_type))
        
        # 랜덤하게 섞기
        random.shuffle(all_combinations)
        
        # 기본 시간에 랜덤 변동 추가 (±5초)
        error_base_times = [30, 70]  # 경고 알람 기본 시간
        warning_base_times = [35, 65, 95]  # 주의 알람 기본 시간
        
        error_times = [base + random.uniform(-5, 5) for base in error_base_times]
        warning_times = [base + random.uniform(-5, 5) for base in warning_base_times]
        
        # 시간이 유효한 범위 내에 있는지 확인
        error_times = [max(5, min(duration_seconds-5, t)) for t in error_times]
        warning_times = [max(5, min(duration_seconds-5, t)) for t in warning_times]
        
        # 경고(error) 알람 2개 계획
        for i in range(2):
            equipment, sensor_type = all_combinations[i]
            self.planned_alerts.append({
                "time": error_times[i],
                "equipment": equipment,
                "sensor_type": sensor_type,
                "severity": "error"
            })
        
        # 주의(warning) 알람 3개 계획
        for i in range(2, 5):
            equipment, sensor_type = all_combinations[i]
            self.planned_alerts.append({
                "time": warning_times[i-2],
                "equipment": equipment,
                "sensor_type": sensor_type,
                "severity": "warning"
            })
        
        # 시간순으로 정렬
        self.planned_alerts.sort(key=lambda x: x["time"])
        
        logger.info("📋 알람 계획 수립 완료:")
        for idx, alert in enumerate(self.planned_alerts):
            severity_label = "경고(HH)" if alert['severity'] == 'error' else "주의(H)"
            logger.info(f"  {idx+1}. {alert['time']:.1f}초: {alert['equipment'].name} "
                       f"{alert['sensor_type']} - {severity_label}")
    
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
                
                # 설비 상태 업데이트
                if severity == "error":
                    self.update_equipment_status(equipment.id, "오류", 60.0)
                else:
                    self.update_equipment_status(equipment.id, "주의", 80.0)
        except Exception as e:
            logger.error(f"[알람] 전송 오류: {e}")
    
    def update_equipment_status(self, equipment_id: str, status: str, efficiency: float):
        """설비 상태 업데이트"""
        url = f"{EQUIPMENT_STATUS_API}/{equipment_id}/status"
        try:
            response = requests.put(url, params={"status": status, "efficiency": efficiency}, timeout=5)
            if response.status_code == 200:
                logger.info(f"[설비상태] {equipment_id} 상태={status}, 효율={efficiency:.1f}%")
        except Exception as e:
            logger.error(f"[설비상태] 업데이트 오류: {e}")
    
    def run(self, duration_seconds: int = 120, interval: float = 2.0):
        """시뮬레이터 실행"""
        self.running = True
        self.start_time = time.time()
        
        # 알람 계획 수립
        self.plan_alerts(duration_seconds)
        
        logger.info("="*50)
        logger.info("🚀 다중 설비 시뮬레이터 시작!")
        logger.info(f"⏱️ 실행 시간: {duration_seconds}초")
        logger.info(f"🎯 목표: 경고(HH) 2개, 주의(H) 3개")
        logger.info("="*50)
        
        # 다음 알람 인덱스
        next_alert_idx = 0
        
        while self.running:
            current_time = time.time()
            elapsed = current_time - self.start_time
            
            if elapsed >= duration_seconds:
                break
            
            # 계획된 알람 확인
            force_alerts = []
            while (next_alert_idx < len(self.planned_alerts) and 
                   self.planned_alerts[next_alert_idx]["time"] <= elapsed):
                force_alerts.append(self.planned_alerts[next_alert_idx])
                # 알람 활성화 로그 (INFO 레벨로 유지)
                alert = self.planned_alerts[next_alert_idx]
                severity_label = "경고(HH)" if alert['severity'] == 'error' else "주의(H)"
                logger.info(f"⏰ [{elapsed:.1f}초] {alert['equipment'].name} "
                           f"{alert['sensor_type']} {severity_label} 알람 예정")
                next_alert_idx += 1
            
            # 모든 설비의 센서 데이터 생성
            for equipment in self.equipments:
                for sensor_type in ["temperature", "pressure", "vibration"]:
                    # 강제 알람 확인
                    force_severity = None
                    for force_alert in force_alerts:
                        if (force_alert["equipment"].id == equipment.id and 
                            force_alert["sensor_type"] == sensor_type):
                            force_severity = force_alert["severity"]
                            break
                    
                    # 센서값 생성
                    value = self.generate_sensor_value(equipment, sensor_type, force_severity)
                    
                    # 센서 데이터 전송
                    self.send_sensor_data(equipment, sensor_type, value)
                    
                    # 알람 체크
                    if force_severity:
                        self.send_alert(equipment, sensor_type, value, force_severity)
                    else:
                        # 자연 발생 알람 체크 (낮은 확률)
                        threshold = self.sensor_thresholds[equipment.type][sensor_type]
                        if value >= threshold.error_threshold and random.random() < 0.1:
                            self.send_alert(equipment, sensor_type, value, "error")
                        elif value >= threshold.warning_threshold and random.random() < 0.05:
                            self.send_alert(equipment, sensor_type, value, "warning")
            
            # 진행 상황 출력 (20초마다)
            if int(elapsed) % 20 == 0 and int(elapsed) > 0:
                remaining = duration_seconds - elapsed
                logger.info(f"[진행 {elapsed:.0f}초] 경고: {self.alert_count['error']}개, "
                           f"주의: {self.alert_count['warning']}개 (남은시간: {remaining:.0f}초)")
            
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
        # 2분간 실행, 2초마다 데이터 생성
        simulator.run(duration_seconds=120, interval=2.0)
        
    except KeyboardInterrupt:
        logger.info("\n사용자에 의해 중지됨")
        simulator.stop()
    except Exception as e:
        logger.error(f"오류 발생: {e}")
        simulator.stop()