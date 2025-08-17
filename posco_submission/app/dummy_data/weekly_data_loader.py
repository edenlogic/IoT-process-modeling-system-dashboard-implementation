import json
import pandas as pd
import os
from datetime import datetime, timedelta

class WeeklyDataLoader:
    def __init__(self):
        self.data_dir = "dummy_data"
        self.start_date = datetime(2024, 7, 28)
        self.end_date = datetime(2024, 8, 4)
        
    def load_sensor_data(self, equipment=None, sensor_type=None, hours=None):
        """센서 데이터 로드"""
        try:
            df = pd.read_csv(f"{self.data_dir}/weekly_sensor_data.csv")
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # 주간 데이터이므로 기본적으로 전체 데이터 반환
            # hours가 168시간(1주일) 미만일 때만 필터링
            if hours and hours < 168:  # 1주일 = 168시간
                # 주간 데이터의 마지막 부분에서 최근 N시간 데이터 추출
                latest_time = df['timestamp'].max()
                cutoff_time = latest_time - timedelta(hours=hours)
                df = df[df['timestamp'] >= cutoff_time]
            
            # 설비 필터링
            if equipment and equipment != "전체":
                df = df[df['equipment'] == equipment]
            
            # 센서 타입 필터링
            if sensor_type and sensor_type != "전체":
                df = df[df['sensor_type'] == sensor_type]
            
            return df.to_dict('records')
        except FileNotFoundError:
            print("주간 센서 데이터 파일을 찾을 수 없습니다.")
            return []
    
    def load_equipment_status(self, target_date=None):
        """설비 상태 데이터 로드"""
        try:
            with open(f"{self.data_dir}/weekly_equipment_status.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if target_date:
                # 특정 날짜의 데이터만 필터링
                filtered_data = [item for item in data if item.get('date') == target_date]
                return filtered_data
            
            # 최신 데이터만 반환 (마지막 날짜)
            latest_date = max(item.get('date', '') for item in data)
            latest_data = [item for item in data if item.get('date') == latest_date]
            return latest_data
            
        except FileNotFoundError:
            print("주간 설비 상태 데이터 파일을 찾을 수 없습니다.")
            return []
    
    def load_alert_data(self, equipment=None, severity=None, status=None):
        """경고 데이터 로드"""
        try:
            with open(f"{self.data_dir}/weekly_alert_data.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # 설비 필터링
            if equipment and equipment != "전체":
                data = [item for item in data if item.get('equipment') == equipment]
            
            # 심각도 필터링
            if severity and severity != "전체":
                data = [item for item in data if item.get('severity') == severity]
            
            # 상태 필터링
            if status and status != "전체":
                data = [item for item in data if item.get('status') == status]
            
            return data
            
        except FileNotFoundError:
            print("주간 경고 데이터 파일을 찾을 수 없습니다.")
            return []
    
    def load_ai_prediction_data(self):
        """AI 설비이상 예측 데이터 로드"""
        try:
            with open(f"{self.data_dir}/weekly_ai_prediction_data.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except FileNotFoundError:
            print("주간 AI 예측 데이터 파일을 찾을 수 없습니다.")
            return []
    
    def load_hydraulic_prediction_data(self):
        """AI 유압 프레스 이상 탐지 데이터 로드"""
        try:
            with open(f"{self.data_dir}/weekly_hydraulic_prediction_data.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except FileNotFoundError:
            print("주간 유압 예측 데이터 파일을 찾을 수 없습니다.")
            return []
    
    def load_quality_trend(self):
        """품질 트렌드 데이터 로드"""
        try:
            df = pd.read_csv(f"{self.data_dir}/weekly_quality_trend.csv")
            return df.to_dict('records')
        except FileNotFoundError:
            print("주간 품질 트렌드 데이터 파일을 찾을 수 없습니다.")
            return []
    
    def load_production_kpi(self):
        """생산 KPI 데이터 로드"""
        try:
            with open(f"{self.data_dir}/weekly_production_kpi.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except FileNotFoundError:
            print("주간 생산 KPI 데이터 파일을 찾을 수 없습니다.")
            return []
    
    def load_users_data(self):
        """사용자 데이터 로드"""
        try:
            with open(f"{self.data_dir}/weekly_users_data.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except FileNotFoundError:
            print("주간 사용자 데이터 파일을 찾을 수 없습니다.")
            return []
    
    def load_equipment_users_data(self, equipment_id=None):
        """설비별 사용자 할당 데이터 로드"""
        try:
            with open(f"{self.data_dir}/weekly_equipment_users_data.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if equipment_id:
                data = [item for item in data if item.get('equipment_id') == equipment_id]
            
            return data
        except FileNotFoundError:
            print("주간 설비별 사용자 할당 데이터 파일을 찾을 수 없습니다.")
            return []
    
    def get_date_range(self):
        """데이터 범위 반환"""
        return {
            "start_date": self.start_date.strftime("%Y-%m-%d"),
            "end_date": self.end_date.strftime("%Y-%m-%d"),
            "total_days": (self.end_date - self.start_date).days + 1
        }
    
    def get_data_summary(self):
        """데이터 요약 정보 반환"""
        summary = {
            "date_range": self.get_date_range(),
            "sensor_records": len(self.load_sensor_data()),
            "equipment_status_records": len(self.load_equipment_status()),
            "alert_records": len(self.load_alert_data()),
            "ai_prediction_records": len(self.load_ai_prediction_data()),
            "hydraulic_prediction_records": len(self.load_hydraulic_prediction_data()),
            "quality_records": len(self.load_quality_trend()),
            "kpi_records": len(self.load_production_kpi()),
            "users_records": len(self.load_users_data()),
            "equipment_users_records": len(self.load_equipment_users_data())
        }
        return summary

# 사용 예시
if __name__ == "__main__":
    loader = WeeklyDataLoader()
    
    # 데이터 요약 출력
    summary = loader.get_data_summary()
    print("=== 주간 더미 데이터 요약 ===")
    for key, value in summary.items():
        print(f"{key}: {value}")
    
    # 샘플 데이터 출력
    print("\n=== 샘플 센서 데이터 (최근 6시간) ===")
    sensor_data = loader.load_sensor_data(hours=6)
    for i, record in enumerate(sensor_data[:5]):
        print(f"{i+1}. {record}")
    
    print("\n=== 샘플 설비 상태 데이터 ===")
    equipment_status = loader.load_equipment_status()
    for i, record in enumerate(equipment_status[:3]):
        print(f"{i+1}. {record}")
    
    print("\n=== 샘플 경고 데이터 ===")
    alert_data = loader.load_alert_data()
    for i, record in enumerate(alert_data[:3]):
        print(f"{i+1}. {record}") 