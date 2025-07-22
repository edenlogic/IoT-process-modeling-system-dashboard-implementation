from kafka import KafkaConsumer
import json
import logging
from datetime import datetime
import sqlite3
import threading
import time
import os

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('KafkaConsumer')

class DataConsumer:
    """Kafka에서 데이터를 받아 처리하는 Consumer"""
    
    def __init__(self, bootstrap_servers='localhost:9092', db_path='iot_streaming.db'):
        self.bootstrap_servers = bootstrap_servers
        self.db_path = db_path
        self.init_database()
        
    def init_database(self):
        """데이터베이스 초기화"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 센서 데이터 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sensor_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                equipment_id TEXT NOT NULL,
                sensor_type TEXT NOT NULL,
                value REAL NOT NULL,
                timestamp TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 알림 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                equipment_id TEXT NOT NULL,
                sensor_type TEXT NOT NULL,
                value REAL NOT NULL,
                threshold REAL NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        conn.close()
        logger.info("데이터베이스 초기화 완료")
    
    def consume_sensor_data(self):
        """센서 데이터 컨슈머"""
        consumer = KafkaConsumer(
            'sensor-data',
            bootstrap_servers=self.bootstrap_servers,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            group_id='sensor-data-group',
            auto_offset_reset='latest'
        )
        
        logger.info("센서 데이터 컨슈머 시작")
        
        conn = sqlite3.connect(self.db_path)
        
        try:
            for message in consumer:
                data = message.value
                equipment_id = data['equipment_id']
                timestamp = data['timestamp']
                
                # 각 센서 데이터를 개별 레코드로 저장
                for sensor_type, value in data['data'].items():
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO sensor_data (equipment_id, sensor_type, value, timestamp)
                        VALUES (?, ?, ?, ?)
                    ''', (equipment_id, sensor_type, value, timestamp))
                    
                    logger.info(f"센서 데이터 저장: {equipment_id} - {sensor_type}: {value}")
                
                conn.commit()
                
        except KeyboardInterrupt:
            logger.info("센서 데이터 컨슈머 중지")
        finally:
            consumer.close()
            conn.close()
    
    def consume_alerts(self):
        """알림 컨슈머"""
        consumer = KafkaConsumer(
            'alerts',
            bootstrap_servers=self.bootstrap_servers,
            value_deserializer=lambda m: json.loads(m.decode('utf-8')),
            group_id='alert-group',
            auto_offset_reset='latest'
        )
        
        logger.info("알림 컨슈머 시작")
        
        conn = sqlite3.connect(self.db_path)
        
        try:
            for message in consumer:
                alert = message.value
                
                # DB에 알림 저장
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO alerts (equipment_id, sensor_type, value, threshold, severity, message, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    alert['equipment_id'],
                    alert['sensor_type'],
                    alert['value'],
                    alert['threshold'],
                    alert['severity'],
                    alert['message'],
                    alert['timestamp']
                ))
                conn.commit()
                
                # 콘솔에 알림 표시
                severity_emoji = {
                    'error': '🔴',
                    'warning': '🟠',
                    'info': '🔵'
                }.get(alert['severity'], '⚪')
                
                logger.warning(f"{severity_emoji} 알림: {alert['message']}")
                
                # TODO: 여기에 카카오톡 알림 전송 로직 추가
                # send_kakao_alert(alert)
                
        except KeyboardInterrupt:
            logger.info("알림 컨슈머 중지")
        finally:
            consumer.close()
            conn.close()
    
    def start_all_consumers(self):
        """모든 컨슈머 동시 실행"""
        threads = []
        
        # 센서 데이터 컨슈머 스레드
        sensor_thread = threading.Thread(target=self.consume_sensor_data, daemon=True)
        sensor_thread.start()
        threads.append(sensor_thread)
        
        # 알림 컨슈머 스레드
        alert_thread = threading.Thread(target=self.consume_alerts, daemon=True)
        alert_thread.start()
        threads.append(alert_thread)
        
        try:
            for thread in threads:
                thread.join()
        except KeyboardInterrupt:
            logger.info("모든 컨슈머 중지")
    
    def get_recent_data(self, equipment_id=None, limit=10):
        """최근 데이터 조회"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if equipment_id:
            cursor.execute('''
                SELECT * FROM sensor_data 
                WHERE equipment_id = ?
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (equipment_id, limit))
        else:
            cursor.execute('''
                SELECT * FROM sensor_data 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (limit,))
        
        data = cursor.fetchall()
        conn.close()
        
        return data
    
    def get_recent_alerts(self, limit=10):
        """최근 알림 조회"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM alerts 
            ORDER BY timestamp DESC 
            LIMIT ?
        ''', (limit,))
        
        alerts = cursor.fetchall()
        conn.close()
        
        return alerts


# 데이터 모니터링 도구
class DataMonitor:
    """실시간 데이터 모니터링"""
    
    def __init__(self, db_path='iot_streaming.db'):
        self.db_path = db_path
    
    def print_stats(self):
        """데이터 통계 출력"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 전체 데이터 수
        cursor.execute("SELECT COUNT(*) FROM sensor_data")
        total_data = cursor.fetchone()[0]
        
        # 전체 알림 수
        cursor.execute("SELECT COUNT(*) FROM alerts")
        total_alerts = cursor.fetchone()[0]
        
        # 설비별 데이터 수
        cursor.execute("""
            SELECT equipment_id, COUNT(*) as count 
            FROM sensor_data 
            GROUP BY equipment_id
        """)
        equipment_stats = cursor.fetchall()
        
        # 심각도별 알림 수
        cursor.execute("""
            SELECT severity, COUNT(*) as count 
            FROM alerts 
            GROUP BY severity
        """)
        alert_stats = cursor.fetchall()
        
        conn.close()
        
        print("\n" + "="*50)
        print("📊 IoT 스트리밍 데이터 통계")
        print("="*50)
        print(f"전체 센서 데이터: {total_data}개")
        print(f"전체 알림: {total_alerts}개")
        
        print("\n설비별 데이터:")
        for equipment, count in equipment_stats:
            print(f"  - {equipment}: {count}개")
        
        print("\n알림 심각도별:")
        for severity, count in alert_stats:
            emoji = {'error': '🔴', 'warning': '🟠', 'info': '🔵'}.get(severity, '⚪')
            print(f"  {emoji} {severity}: {count}개")
        
    def monitor_live(self, interval=5):
        """실시간 모니터링"""
        import os
        
        try:
            while True:
                os.system('cls' if os.name == 'nt' else 'clear')
                self.print_stats()
                
                # 최근 알림 표시
                consumer = DataConsumer(db_path=self.db_path)
                recent_alerts = consumer.get_recent_alerts(5)
                
                if recent_alerts:
                    print("\n🚨 최근 알림:")
                    for alert in recent_alerts:
                        print(f"  [{alert[7]}] {alert[1]}: {alert[6]}")
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n모니터링 종료")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == 'monitor':
        # 모니터링 모드
        monitor = DataMonitor()
        monitor.monitor_live()
    else:
        # 컨슈머 실행
        consumer = DataConsumer()
        consumer.start_all_consumers()