import requests
import random
import time
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

API_BASE_URL = "http://localhost:8000"
SENSOR_API = f"{API_BASE_URL}/sensors"
ALERT_API = f"{API_BASE_URL}/alerts"
EQUIPMENT_STATUS_API = f"{API_BASE_URL}/equipment"
QUALITY_TREND_API = f"{API_BASE_URL}/api/quality_trend"
PRODUCTION_KPI_API = f"{API_BASE_URL}/api/production_kpi"

EQUIPMENTS = [
    {"id": "press_001", "name": "프레스기 #001"},
    {"id": "press_002", "name": "프레스기 #002"},
    {"id": "weld_001", "name": "용접기 #001"},
    {"id": "weld_002", "name": "용접기 #002"},
    {"id": "assemble_001", "name": "조립기 #001"},
    {"id": "inspect_001", "name": "검사기 #001"}
]
SENSOR_TYPES = ["temperature", "pressure", "vibration"]

class DummySimulator:
    def __init__(self, interval=2.0):
        self.interval = interval
        self.logger = logging.getLogger('DummySimulator')
        self.day_count = 0
        self.daily_stats = []

    def send_sensor(self, data):
        try:
            res = requests.post(SENSOR_API, json=data, timeout=5)
            if res.status_code == 200:
                self.logger.info(f"센서 데이터 전송 성공: {data['equipment']} {data['sensor_type']}={data['value']}")
            else:
                self.logger.warning(f"센서 데이터 전송 실패: {res.status_code}")
        except Exception as e:
            self.logger.error(f"센서 데이터 API 오류: {e}")

    def send_alert(self, data):
        try:
            res = requests.post(ALERT_API, json=data, timeout=5)
            if res.status_code == 200:
                self.logger.info(f"알림 전송 성공: {data['equipment']} {data['sensor_type']} {data['severity']}")
            else:
                self.logger.warning(f"알림 전송 실패: {res.status_code}")
        except Exception as e:
            self.logger.error(f"알림 API 오류: {e}")

    def update_equipment_status(self, equipment_id, status, efficiency):
        url = f"{EQUIPMENT_STATUS_API}/{equipment_id}/status"
        try:
            res = requests.put(url, params={"status": status, "efficiency": efficiency}, timeout=5)
            if res.status_code == 200:
                self.logger.info(f"설비 상태 업데이트 성공: {equipment_id} → {status}, 효율: {efficiency:.2f}%")
            else:
                self.logger.warning(f"설비 상태 업데이트 실패: {equipment_id} ({res.status_code})")
        except Exception as e:
            self.logger.error(f"설비 상태 API 오류: {e}")

    def send_quality_trend(self, trend_data):
        try:
            res = requests.post(QUALITY_TREND_API, json=trend_data, timeout=5)
            if res.status_code == 200:
                self.logger.info("품질/생산 트렌드 데이터 전송 성공")
            else:
                self.logger.warning(f"품질/생산 트렌드 전송 실패: {res.status_code}")
        except Exception as e:
            self.logger.error(f"품질/생산 트렌드 API 오류: {e}")

    def send_production_kpi(self, kpi_data):
        try:
            res = requests.post(PRODUCTION_KPI_API, json=kpi_data, timeout=5)
            if res.status_code == 200:
                self.logger.info("KPI 데이터 전송 성공")
            else:
                self.logger.warning(f"KPI 전송 실패: {res.status_code}")
        except Exception as e:
            self.logger.error(f"KPI API 오류: {e}")

    def run(self, duration=60):
        start_time = time.time()
        self.logger.info("🚀 더미 시뮬레이터 시작!")
        daily_production = 0
        daily_defect = 0
        while time.time() - start_time < duration:
            timestamp = datetime.now().isoformat()
            for eq in EQUIPMENTS:
                for sensor_type in SENSOR_TYPES:
                    value = {
                        "temperature": round(random.uniform(20, 80), 2),
                        "pressure": round(random.uniform(0.8, 1.2), 3),
                        "vibration": round(random.uniform(0.1, 5.0), 2)
                    }[sensor_type]
                    data = {
                        "equipment": eq["id"],
                        "sensor_type": sensor_type,
                        "value": value,
                        "timestamp": timestamp
                    }
                    self.send_sensor(data)
                    daily_production += 1
                    # 임계값 초과 시 알림/설비상태도 전송
                    threshold = {"temperature": 65.0, "pressure": 1.1, "vibration": 3.0}[sensor_type]
                    if value > threshold:
                        alert = {
                            "equipment": eq["id"],
                            "sensor_type": sensor_type,
                            "value": value,
                            "threshold": threshold,
                            "severity": "warning" if value < threshold * 1.1 else "error",
                            "timestamp": timestamp,
                            "message": f"{eq['id']} {sensor_type} 임계치 초과: {value} (임계값: {threshold})"
                        }
                        self.send_alert(alert)
                        daily_defect += 1
                        status = "주의" if alert["severity"] == "warning" else "오류"
                        efficiency = round(random.uniform(60, 90), 2)
                        self.update_equipment_status(eq["id"], status, efficiency)
                    else:
                        self.update_equipment_status(eq["id"], "정상", 98.0)
            # 일정 주기마다 트렌드/KPI 전송
            if int(time.time() - start_time) % 30 == 0:
                defect_rate = round((daily_defect / daily_production) * 100, 1) if daily_production else 0.0
                trend = {
                    'day': ['월', '화', '수', '목', '금', '토', '일'],
                    'quality_rate': [98.1, 97.8, 95.5, 99.1, 98.2, 92.3, 94.7],
                    'production_volume': [1200, 1350, 1180, 1420, 1247, 980, 650],
                    'defect_rate': [2.1, 1.8, 2.5, 1.9, 2.8, 3.1, 2.2]
                }
                self.send_quality_trend(trend)
                kpi = {
                    'daily_target': 1300,
                    'daily_actual': daily_production,
                    'weekly_target': 9100,
                    'weekly_actual': daily_production * 7,
                    'monthly_target': 39000,
                    'monthly_actual': daily_production * 30,
                    'oee': round(random.uniform(85, 95), 1),
                    'availability': round(random.uniform(90, 99), 1),
                    'performance': round(random.uniform(90, 99), 1),
                    'quality': round(100 - defect_rate, 1)
                }
                self.send_production_kpi(kpi)
            time.sleep(self.interval)
        self.logger.info("✅ 더미 시뮬레이터 종료")

if __name__ == "__main__":
    simulator = DummySimulator(interval=2.0)
    simulator.run(duration=120)
