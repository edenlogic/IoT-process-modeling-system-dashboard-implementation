import pandas as pd
import json
import time
from datetime import datetime
from kafka import KafkaProducer
import logging
import threading
from typing import Dict, List

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('DualCSVProducer')

class DualCSVStreamer:
    """두 개의 서로 다른 CSV를 Kafka로 스트리밍"""
    
    def __init__(self, bootstrap_servers='localhost:9092'):
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            key_serializer=lambda v: v.encode('utf-8') if v else None
        )
        
        self.data_cache = {}
        self.current_index = {}
        
    def load_csv_data(self, file_path: str, dataset_name: str):
        """CSV 파일 로드"""
        try:
            df = pd.read_csv(file_path)
            self.data_cache[dataset_name] = df
            self.current_index[dataset_name] = 0
            logger.info(f"CSV 로드 완료: {dataset_name} ({len(df)}개 레코드, {len(df.columns)}개 컬럼)")
            return df
        except Exception as e:
            logger.error(f"CSV 로드 실패: {e}")
            return None
    
    def prepare_hydraulic_data(self, row: pd.Series, equipment_id: str) -> Dict:
        """유압 시스템 데이터 준비"""
        sensor_data = {
            "equipment_id": equipment_id,
            "equipment_type": "hydraulic_system",
            "timestamp": datetime.now().isoformat(),
            "cycle_id": int(row['cycle_id']),
            "sensors": {
                # 압력 센서들 (PS1-PS6)
                "pressure": {
                    f"PS{i}": {
                        "mean": float(row[f'PS{i}_mean']),
                        "max": float(row[f'PS{i}_max']),
                        "min": float(row[f'PS{i}_min'])
                    } for i in range(1, 7)
                },
                # 온도 센서들 (TS1-TS4)
                "temperature": {
                    f"TS{i}": {
                        "mean": float(row[f'TS{i}_mean']),
                        "max": float(row[f'TS{i}_max']),
                        "min": float(row[f'TS{i}_min'])
                    } for i in range(1, 5)
                },
                # 유량 센서들 (FS1-FS2)
                "flow": {
                    f"FS{i}": {
                        "mean": float(row[f'FS{i}_mean']),
                        "max": float(row[f'FS{i}_max']),
                        "min": float(row[f'FS{i}_min'])
                    } for i in range(1, 3)
                },
                # 진동 센서 (VS1)
                "vibration": {
                    "VS1": {
                        "mean": float(row['VS1_mean']),
                        "max": float(row['VS1_max']),
                        "min": float(row['VS1_min'])
                    }
                },
                # 전기 센서들
                "electrical": {
                    "efficiency": float(row['CE_mean']),
                    "power": float(row['CP_mean']),
                    "speed": float(row['SE_mean'])
                }
            },
            "system_status": {
                "cooler": int(row['Cooler']),
                "valve": int(row['Valve']),
                "pump": int(row['Pump']),
                "accumulator": int(row['Accumulator']),
                "stable_flag": int(row['Stable_flag']),
                "is_normal": int(row['is_normal']),
                "fault_type": int(row.get('fault_type', 0))
            }
        }
        return sensor_data
    
    def prepare_manufacturing_data(self, row: pd.Series, equipment_id: str) -> Dict:
        """제조 공정 데이터 준비"""
        sensor_data = {
            "equipment_id": equipment_id,
            "equipment_type": "manufacturing_line",
            "timestamp": datetime.now().isoformat(),
            "original_timestamp": str(row['Timestamp']),
            "sensors": {
                "temperature": float(row['Temperature (°C)']),
                "machine_speed": int(row['Machine Speed (RPM)']),
                "vibration": float(row['Vibration Level (mm/s)']),
                "energy_consumption": float(row['Energy Consumption (kWh)'])
            },
            "quality": {
                "production_quality_score": float(row['Production Quality Score']),
                "optimal_conditions": bool(row['Optimal Conditions'])
            }
        }
        return sensor_data
    
    def check_hydraulic_alerts(self, data: Dict) -> List[Dict]:
        """유압 시스템 알림 체크"""
        alerts = []
        
        # 압력 센서 체크 (PS1-PS6)
        for sensor, values in data['sensors']['pressure'].items():
            if values['max'] > 200:  # 압력 임계값
                alerts.append({
                    "equipment_id": data['equipment_id'],
                    "sensor_type": f"pressure_{sensor}",
                    "value": values['max'],
                    "threshold": 200,
                    "severity": "error" if values['max'] > 250 else "warning",
                    "message": f"{sensor} 압력 초과: {values['max']:.2f} bar",
                    "timestamp": data['timestamp']
                })
        
        # 온도 센서 체크 (TS1-TS4)
        for sensor, values in data['sensors']['temperature'].items():
            if values['max'] > 70:  # 온도 임계값
                alerts.append({
                    "equipment_id": data['equipment_id'],
                    "sensor_type": f"temperature_{sensor}",
                    "value": values['max'],
                    "threshold": 70,
                    "severity": "error" if values['max'] > 85 else "warning",
                    "message": f"{sensor} 온도 초과: {values['max']:.2f}°C",
                    "timestamp": data['timestamp']
                })
        
        # 시스템 상태 체크
        if data['system_status']['is_normal'] == 0:
            fault_type = data['system_status']['fault_type']
            fault_names = {
                1: "Cooler 고장",
                2: "Valve 고장", 
                3: "Pump 누출",
                4: "Accumulator 고장"
            }
            alerts.append({
                "equipment_id": data['equipment_id'],
                "sensor_type": "system_fault",
                "value": fault_type,
                "threshold": 0,
                "severity": "error",
                "message": f"시스템 이상: {fault_names.get(fault_type, '알 수 없는 고장')}",
                "timestamp": data['timestamp']
            })
        
        return alerts
    
    def check_manufacturing_alerts(self, data: Dict) -> List[Dict]:
        """제조 공정 알림 체크"""
        alerts = []
        sensors = data['sensors']
        
        # 온도 체크
        if sensors['temperature'] > 80:
            alerts.append({
                "equipment_id": data['equipment_id'],
                "sensor_type": "temperature",
                "value": sensors['temperature'],
                "threshold": 80,
                "severity": "error" if sensors['temperature'] > 90 else "warning",
                "message": f"온도 초과: {sensors['temperature']:.2f}°C",
                "timestamp": data['timestamp']
            })
        
        # 진동 레벨 체크
        if sensors['vibration'] > 2.0:
            alerts.append({
                "equipment_id": data['equipment_id'],
                "sensor_type": "vibration",
                "value": sensors['vibration'],
                "threshold": 2.0,
                "severity": "error" if sensors['vibration'] > 3.0 else "warning",
                "message": f"진동 초과: {sensors['vibration']:.2f} mm/s",
                "timestamp": data['timestamp']
            })
        
        # 품질 점수 체크
        if data['quality']['production_quality_score'] < 70:
            alerts.append({
                "equipment_id": data['equipment_id'],
                "sensor_type": "quality",
                "value": data['quality']['production_quality_score'],
                "threshold": 70,
                "severity": "warning",
                "message": f"품질 저하: {data['quality']['production_quality_score']:.1f}점",
                "timestamp": data['timestamp']
            })
        
        # 최적 조건 이탈
        if not data['quality']['optimal_conditions']:
            alerts.append({
                "equipment_id": data['equipment_id'],
                "sensor_type": "optimal_conditions",
                "value": 0,
                "threshold": 1,
                "severity": "info",
                "message": "최적 운영 조건 이탈",
                "timestamp": data['timestamp']
            })
        
        return alerts
    
    def stream_hydraulic_data(self):
        """유압 시스템 데이터 스트리밍"""
        df = self.data_cache.get('hydraulic')
        if df is None:
            return
        
        equipment_id = "hydraulic_system_001"
        
        while True:
            current_idx = self.current_index['hydraulic']
            
            if current_idx >= len(df):
                self.current_index['hydraulic'] = 0
                logger.info("유압 데이터 끝 도달, 처음부터 다시 시작")
                continue
            
            row = df.iloc[current_idx]
            
            # 데이터 준비
            sensor_data = self.prepare_hydraulic_data(row, equipment_id)
            
            # Kafka로 전송
            self.producer.send(
                'sensor-data',
                key=equipment_id,
                value=sensor_data
            )
            
            logger.info(f"유압 데이터 전송: Cycle {sensor_data['cycle_id']}")
            
            # 알림 체크
            alerts = self.check_hydraulic_alerts(sensor_data)
            for alert in alerts:
                self.producer.send('alerts', key=equipment_id, value=alert)
                logger.warning(f"🚨 유압 알림: {alert['message']}")
            
            self.current_index['hydraulic'] += 1
            time.sleep(2)  # 2초마다
    
    def stream_manufacturing_data(self):
        """제조 공정 데이터 스트리밍"""
        df = self.data_cache.get('manufacturing')
        if df is None:
            return
        
        equipment_id = "manufacturing_line_001"
        
        while True:
            current_idx = self.current_index['manufacturing']
            
            if current_idx >= len(df):
                self.current_index['manufacturing'] = 0
                logger.info("제조 데이터 끝 도달, 처음부터 다시 시작")
                continue
            
            row = df.iloc[current_idx]
            
            # 데이터 준비
            sensor_data = self.prepare_manufacturing_data(row, equipment_id)
            
            # Kafka로 전송
            self.producer.send(
                'sensor-data',
                key=equipment_id,
                value=sensor_data
            )
            
            logger.info(f"제조 데이터 전송: {sensor_data['original_timestamp']}")
            
            # 알림 체크
            alerts = self.check_manufacturing_alerts(sensor_data)
            for alert in alerts:
                self.producer.send('alerts', key=equipment_id, value=alert)
                logger.warning(f"🚨 제조 알림: {alert['message']}")
            
            self.current_index['manufacturing'] += 1
            time.sleep(1)  # 1초마다
    
    def start_all_streams(self):
        """모든 스트림 동시 시작"""
        # CSV 로드
        self.load_csv_data('hydraulic_processed_data.csv', 'hydraulic')
        self.load_csv_data('Manufacturing_dataset.csv', 'manufacturing')
        
        # 스레드 생성
        threads = []
        
        # 유압 시스템 스레드
        hydraulic_thread = threading.Thread(target=self.stream_hydraulic_data, daemon=True)
        hydraulic_thread.start()
        threads.append(hydraulic_thread)
        
        # 제조 공정 스레드
        manufacturing_thread = threading.Thread(target=self.stream_manufacturing_data, daemon=True)
        manufacturing_thread.start()
        threads.append(manufacturing_thread)
        
        try:
            for thread in threads:
                thread.join()
        except KeyboardInterrupt:
            logger.info("스트리밍 중지")
            self.producer.close()


if __name__ == "__main__":
    logger.info("🚀 듀얼 CSV Kafka Producer 시작")
    logger.info("=" * 60)
    logger.info("유압 시스템: hydraulic_processed_data.csv (2초 간격)")
    logger.info("제조 라인: Manufacturing_dataset.csv (1초 간격)")
    logger.info("=" * 60)
    
    streamer = DualCSVStreamer()
    streamer.start_all_streams()