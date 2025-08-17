import json
import csv
import random
import pandas as pd
from datetime import datetime, timedelta
import numpy as np

class WeeklyDataGenerator:
    def __init__(self):
        self.start_date = datetime(2024, 7, 28)
        self.end_date = datetime(2024, 8, 4)
        self.equipment_list = [
            "압연기_1호기", "압연기_2호기", "압연기_3호기", "압연기_4호기", "압연기_5호기",
            "압연기_6호기", "압연기_7호기", "압연기_8호기", "압연기_9호기", "압연기_10호기",
            "압연기_11호기", "압연기_12호기", "압연기_13호기", "압연기_14호기", "압연기_15호기",
            "압연기_16호기", "압연기_17호기", "압연기_18호기", "압연기_19호기", "압연기_20호기",
            "압연기_21호기", "압연기_22호기", "압연기_23호기", "압연기_24호기", "압연기_25호기",
            "압연기_26호기", "압연기_27호기", "압연기_28호기", "압연기_29호기", "압연기_30호기",
            "압연기_31호기", "압연기_32호기", "압연기_33호기", "압연기_34호기", "압연기_35호기",
            "압연기_36호기", "압연기_37호기", "압연기_38호기", "압연기_39호기", "압연기_40호기",
            "압연기_41호기", "압연기_42호기", "압연기_43호기", "압연기_44호기", "압연기_45호기",
            "압연기_46호기", "압연기_47호기", "압연기_48호기", "압연기_49호기", "압연기_50호기"
        ]
        
        self.sensor_types = ["온도", "압력", "진동", "전류", "전압", "유량", "속도", "위치"]
        self.severity_levels = ["낮음", "보통", "높음", "긴급"]
        self.status_levels = ["정상", "주의", "경고", "위험"]
        
    def generate_date_range(self):
        """7월 28일부터 8월 4일까지의 날짜 범위 생성"""
        dates = []
        current_date = self.start_date
        while current_date <= self.end_date:
            dates.append(current_date)
            current_date += timedelta(days=1)
        return dates
    
    def generate_sensor_data(self):
        """센서 데이터 생성 - 시간별로 많은 데이터"""
        sensor_data = []
        dates = self.generate_date_range()
        
        for date in dates:
            # 하루에 24시간, 시간당 4-6개의 데이터 생성 (낮 시간대에 더 많게)
            for hour in range(24):
                # 낮 시간대(6-18시)에는 더 많은 데이터 생성
                if 6 <= hour <= 18:
                    num_records = random.randint(8, 12)
                else:
                    num_records = random.randint(2, 4)
                
                for _ in range(num_records):
                    minute = random.randint(0, 59)
                    second = random.randint(0, 59)
                    timestamp = date.replace(hour=hour, minute=minute, second=second)
                    
                    equipment = random.choice(self.equipment_list)
                    sensor_type = random.choice(self.sensor_types)
                    
                    # 센서 타입별 적절한 값 범위 설정
                    if sensor_type == "온도":
                        value = random.uniform(20, 80)
                    elif sensor_type == "압력":
                        value = random.uniform(50, 200)
                    elif sensor_type == "진동":
                        value = random.uniform(0.1, 5.0)
                    elif sensor_type == "전류":
                        value = random.uniform(10, 100)
                    elif sensor_type == "전압":
                        value = random.uniform(200, 400)
                    elif sensor_type == "유량":
                        value = random.uniform(10, 50)
                    elif sensor_type == "속도":
                        value = random.uniform(100, 500)
                    else:  # 위치
                        value = random.uniform(0, 100)
                    
                    sensor_data.append({
                        "equipment": equipment,
                        "sensor_type": sensor_type,
                        "value": round(value, 2),
                        "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S")
                    })
        
        return sensor_data
    
    def generate_equipment_status(self):
        """설비 상태 데이터 생성 - 하루에 모든 설비의 데이터 하나씩"""
        equipment_status = []
        dates = self.generate_date_range()
        
        for date in dates:
            for equipment in self.equipment_list:
                status = random.choice(self.status_levels)
                efficiency = random.uniform(70, 98)
                equipment_type = "압연기"
                last_maintenance = (date - timedelta(days=random.randint(1, 30))).strftime("%Y-%m-%d")
                
                equipment_status.append({
                    "id": equipment,
                    "name": equipment,
                    "status": status,
                    "efficiency": round(efficiency, 1),
                    "type": equipment_type,
                    "last_maintenance": last_maintenance,
                    "date": date.strftime("%Y-%m-%d")
                })
        
        return equipment_status
    
    def generate_alert_data(self):
        """경고 데이터 생성 - 하루에 5-8개씩"""
        alert_data = []
        dates = self.generate_date_range()
        
        for date in dates:
            num_alerts = random.randint(5, 8)
            
            for _ in range(num_alerts):
                hour = random.randint(0, 23)
                minute = random.randint(0, 59)
                timestamp = date.replace(hour=hour, minute=minute)
                
                equipment = random.choice(self.equipment_list)
                sensor_type = random.choice(self.sensor_types)
                severity = random.choice(self.severity_levels)
                
                # 심각도별 메시지 생성
                if severity == "긴급":
                    message = f"{equipment} {sensor_type} 긴급 이상 감지"
                    value = random.uniform(80, 100)
                    threshold = random.uniform(70, 85)
                elif severity == "높음":
                    message = f"{equipment} {sensor_type} 높은 수준 이상 감지"
                    value = random.uniform(70, 85)
                    threshold = random.uniform(60, 75)
                elif severity == "보통":
                    message = f"{equipment} {sensor_type} 주의 수준 이상 감지"
                    value = random.uniform(60, 75)
                    threshold = random.uniform(50, 65)
                else:  # 낮음
                    message = f"{equipment} {sensor_type} 경미한 이상 감지"
                    value = random.uniform(50, 65)
                    threshold = random.uniform(40, 55)
                
                alert_data.append({
                    "equipment": equipment,
                    "sensor_type": sensor_type,
                    "value": round(value, 2),
                    "threshold": round(threshold, 2),
                    "severity": severity,
                    "timestamp": timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                    "message": message,
                    "status": "미처리"
                })
        
        return alert_data
    
    def generate_ai_prediction_data(self):
        """AI 설비이상 예측 데이터 생성 - 하루에 1개씩"""
        ai_prediction_data = []
        dates = self.generate_date_range()
        
        for date in dates:
            equipment = random.choice(self.equipment_list)
            prediction_date = (date + timedelta(days=random.randint(1, 7))).strftime("%Y-%m-%d")
            probability = random.uniform(0.1, 0.9)
            
            if probability > 0.7:
                status = "높음"
            elif probability > 0.4:
                status = "보통"
            else:
                status = "낮음"
            
            ai_prediction_data.append({
                "equipment": equipment,
                "prediction_date": prediction_date,
                "probability": round(probability, 3),
                "status": status,
                "timestamp": date.strftime("%Y-%m-%d %H:%M:%S")
            })
        
        return ai_prediction_data
    
    def generate_hydraulic_prediction_data(self):
        """AI 유압 프레스 이상 탐지 데이터 생성 - 하루에 1개씩"""
        hydraulic_data = []
        dates = self.generate_date_range()
        
        for date in dates:
            equipment = random.choice(self.equipment_list)
            prediction_date = (date + timedelta(days=random.randint(1, 5))).strftime("%Y-%m-%d")
            probability = random.uniform(0.05, 0.85)
            
            if probability > 0.6:
                status = "높음"
            elif probability > 0.3:
                status = "보통"
            else:
                status = "낮음"
            
            hydraulic_data.append({
                "equipment": equipment,
                "prediction_date": prediction_date,
                "probability": round(probability, 3),
                "status": status,
                "timestamp": date.strftime("%Y-%m-%d %H:%M:%S")
            })
        
        return hydraulic_data
    
    def generate_quality_trend(self):
        """품질 트렌드 데이터 생성"""
        quality_data = []
        dates = self.generate_date_range()
        
        for date in dates:
            quality_score = random.uniform(85, 98)
            defect_rate = random.uniform(0.5, 3.0)
            
            quality_data.append({
                "date": date.strftime("%Y-%m-%d"),
                "quality_score": round(quality_score, 1),
                "defect_rate": round(defect_rate, 2)
            })
        
        return quality_data
    
    def generate_production_kpi(self):
        """생산 KPI 데이터 생성"""
        kpi_data = []
        dates = self.generate_date_range()
        
        for date in dates:
            production_volume = random.randint(800, 1200)
            efficiency = random.uniform(85, 95)
            downtime = random.uniform(2, 8)
            
            kpi_data.append({
                "date": date.strftime("%Y-%m-%d"),
                "production_volume": production_volume,
                "efficiency": round(efficiency, 1),
                "downtime": round(downtime, 1)
            })
        
        return kpi_data
    
    def generate_users_data(self):
        """사용자 데이터 생성"""
        users = [
            {"id": 1, "name": "김철수", "phone_number": "010-1234-5678", "department": "생산팀", "role": "담당자"},
            {"id": 2, "name": "이영희", "phone_number": "010-2345-6789", "department": "품질팀", "role": "관리자"},
            {"id": 3, "name": "박민수", "phone_number": "010-3456-7890", "department": "설비팀", "role": "감시자"},
            {"id": 4, "name": "정수진", "phone_number": "010-4567-8901", "department": "생산팀", "role": "담당자"},
            {"id": 5, "name": "최동욱", "phone_number": "010-5678-9012", "department": "품질팀", "role": "관리자"}
        ]
        return users
    
    def generate_equipment_users_data(self):
        """설비별 사용자 할당 데이터 생성"""
        equipment_users = []
        users = self.generate_users_data()
        
        for equipment in self.equipment_list:
            # 각 설비당 1-3명의 사용자 할당
            num_users = random.randint(1, 3)
            assigned_users = random.sample(users, num_users)
            
            for i, user in enumerate(assigned_users):
                is_primary = (i == 0)  # 첫 번째 사용자를 주 담당자로 설정
                role = random.choice(["담당자", "관리자", "감시자"])
                
                equipment_users.append({
                    "equipment_id": equipment,
                    "user_id": user["id"],
                    "user_name": user["name"],
                    "role": role,
                    "is_primary": is_primary
                })
        
        return equipment_users
    
    def save_all_data(self):
        """모든 데이터를 파일로 저장"""
        print("1주일치 더미 데이터 생성 시작...")
        
        # 센서 데이터 생성 및 저장
        print("센서 데이터 생성 중...")
        sensor_data = self.generate_sensor_data()
        df_sensor = pd.DataFrame(sensor_data)
        df_sensor.to_csv("dummy_data/weekly_sensor_data.csv", index=False, encoding='utf-8-sig')
        print(f"센서 데이터 저장 완료: {len(sensor_data)}개 레코드")
        
        # 설비 상태 데이터 생성 및 저장
        print("설비 상태 데이터 생성 중...")
        equipment_status = self.generate_equipment_status()
        with open("dummy_data/weekly_equipment_status.json", "w", encoding="utf-8") as f:
            json.dump(equipment_status, f, ensure_ascii=False, indent=2)
        print(f"설비 상태 데이터 저장 완료: {len(equipment_status)}개 레코드")
        
        # 경고 데이터 생성 및 저장
        print("경고 데이터 생성 중...")
        alert_data = self.generate_alert_data()
        with open("dummy_data/weekly_alert_data.json", "w", encoding="utf-8") as f:
            json.dump(alert_data, f, ensure_ascii=False, indent=2)
        print(f"경고 데이터 저장 완료: {len(alert_data)}개 레코드")
        
        # AI 예측 데이터 생성 및 저장
        print("AI 예측 데이터 생성 중...")
        ai_prediction_data = self.generate_ai_prediction_data()
        with open("dummy_data/weekly_ai_prediction_data.json", "w", encoding="utf-8") as f:
            json.dump(ai_prediction_data, f, ensure_ascii=False, indent=2)
        print(f"AI 예측 데이터 저장 완료: {len(ai_prediction_data)}개 레코드")
        
        # 유압 예측 데이터 생성 및 저장
        print("유압 예측 데이터 생성 중...")
        hydraulic_data = self.generate_hydraulic_prediction_data()
        with open("dummy_data/weekly_hydraulic_prediction_data.json", "w", encoding="utf-8") as f:
            json.dump(hydraulic_data, f, ensure_ascii=False, indent=2)
        print(f"유압 예측 데이터 저장 완료: {len(hydraulic_data)}개 레코드")
        
        # 품질 트렌드 데이터 생성 및 저장
        print("품질 트렌드 데이터 생성 중...")
        quality_data = self.generate_quality_trend()
        df_quality = pd.DataFrame(quality_data)
        df_quality.to_csv("dummy_data/weekly_quality_trend.csv", index=False, encoding='utf-8-sig')
        print(f"품질 트렌드 데이터 저장 완료: {len(quality_data)}개 레코드")
        
        # 생산 KPI 데이터 생성 및 저장
        print("생산 KPI 데이터 생성 중...")
        kpi_data = self.generate_production_kpi()
        with open("dummy_data/weekly_production_kpi.json", "w", encoding="utf-8") as f:
            json.dump(kpi_data, f, ensure_ascii=False, indent=2)
        print(f"생산 KPI 데이터 저장 완료: {len(kpi_data)}개 레코드")
        
        # 사용자 데이터 생성 및 저장
        print("사용자 데이터 생성 중...")
        users_data = self.generate_users_data()
        with open("dummy_data/weekly_users_data.json", "w", encoding="utf-8") as f:
            json.dump(users_data, f, ensure_ascii=False, indent=2)
        print(f"사용자 데이터 저장 완료: {len(users_data)}개 레코드")
        
        # 설비별 사용자 할당 데이터 생성 및 저장
        print("설비별 사용자 할당 데이터 생성 중...")
        equipment_users_data = self.generate_equipment_users_data()
        with open("dummy_data/weekly_equipment_users_data.json", "w", encoding="utf-8") as f:
            json.dump(equipment_users_data, f, ensure_ascii=False, indent=2)
        print(f"설비별 사용자 할당 데이터 저장 완료: {len(equipment_users_data)}개 레코드")
        
        print("\n=== 1주일치 더미 데이터 생성 완료 ===")
        print(f"생성 기간: {self.start_date.strftime('%Y-%m-%d')} ~ {self.end_date.strftime('%Y-%m-%d')}")
        print("생성된 파일들:")
        print("- weekly_sensor_data.csv (센서 데이터)")
        print("- weekly_equipment_status.json (설비 상태)")
        print("- weekly_alert_data.json (경고 데이터)")
        print("- weekly_ai_prediction_data.json (AI 설비이상 예측)")
        print("- weekly_hydraulic_prediction_data.json (AI 유압 프레스 이상 탐지)")
        print("- weekly_quality_trend.csv (품질 트렌드)")
        print("- weekly_production_kpi.json (생산 KPI)")
        print("- weekly_users_data.json (사용자 데이터)")
        print("- weekly_equipment_users_data.json (설비별 사용자 할당)")

if __name__ == "__main__":
    generator = WeeklyDataGenerator()
    generator.save_all_data() 