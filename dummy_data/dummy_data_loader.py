import pandas as pd
import json
from datetime import datetime, timedelta
import os

class DummyDataLoader:
    def __init__(self, use_weekly_data=True):
        # 주간 데이터 사용 여부 저장
        self.use_weekly_data = use_weekly_data
        
        # dummy_data 폴더 내의 파일 경로 (현재 디렉토리 기준)
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # 주간 데이터 사용 여부에 따라 파일 경로 설정
        if use_weekly_data:
            self.data_files = {
                'sensor_data': os.path.join(current_dir, 'weekly_sensor_data.csv'),
                'equipment_status': os.path.join(current_dir, 'weekly_equipment_status.json'),
                'alert_data': os.path.join(current_dir, 'weekly_alert_data.json'),
                'quality_trend': os.path.join(current_dir, 'weekly_quality_trend.csv'),
                'production_kpi': os.path.join(current_dir, 'weekly_production_kpi.json'),
                'ai_prediction_data': os.path.join(current_dir, 'weekly_ai_prediction_data.json'),
                'hydraulic_prediction_data': os.path.join(current_dir, 'weekly_hydraulic_prediction_data.json'),
                'users_data': os.path.join(current_dir, 'weekly_users_data.json'),
                'equipment_users_data': os.path.join(current_dir, 'weekly_equipment_users_data.json')
            }
        else:
            self.data_files = {
                'sensor_data': os.path.join(current_dir, 'dummy_sensor_data.csv'),
                'equipment_status': os.path.join(current_dir, 'dummy_equipment_status.json'),
                'alert_data': os.path.join(current_dir, 'dummy_alert_data.json'),
                'quality_trend': os.path.join(current_dir, 'dummy_quality_trend.csv'),
                'production_kpi': os.path.join(current_dir, 'dummy_production_kpi.json'),
                'ai_prediction_data': os.path.join(current_dir, 'dummy_ai_prediction_data.json'),
                'users_data': os.path.join(current_dir, 'dummy_users_data.json'),
                'equipment_users_data': os.path.join(current_dir, 'dummy_equipment_users_data.json')
            }
        
        # 데이터 캐시
        self._cached_data = {}
    
    def _load_csv_data(self, filename):
        """CSV 파일 로드"""
        if os.path.exists(filename):
            return pd.read_csv(filename)
        return pd.DataFrame()
    
    def _load_json_data(self, filename):
        """JSON 파일 로드"""
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    
    def _get_cached_data(self, data_type):
        """캐시된 데이터 반환"""
        if data_type not in self._cached_data:
            if data_type in ['sensor_data', 'quality_trend']:
                self._cached_data[data_type] = self._load_csv_data(self.data_files[data_type])
            else:
                self._cached_data[data_type] = self._load_json_data(self.data_files[data_type])
        return self._cached_data[data_type]
    
    def get_sensor_data(self, hours=None):
        """센서 데이터 반환"""
        sensor_data = self._get_cached_data('sensor_data')
        
        if sensor_data.empty:
            return pd.DataFrame()
        
        # 주간 데이터인 경우 시간 필터링 로직 수정
        if self.use_weekly_data:
            # 주간 데이터에서는 timestamp 컬럼 사용
            if 'timestamp' in sensor_data.columns:
                sensor_data['time'] = pd.to_datetime(sensor_data['timestamp'])
            else:
                sensor_data['time'] = pd.to_datetime(sensor_data['time'])
            
            # 시간 필터링 (hours가 지정된 경우)
            if hours:
                # 주간 데이터의 마지막 시간에서 N시간 전으로 필터링
                latest_time = sensor_data['time'].max()
                cutoff_time = latest_time - timedelta(hours=hours)
                sensor_data = sensor_data[sensor_data['time'] >= cutoff_time]
        else:
            # 기존 로직 (실시간 데이터)
            if hours:
                cutoff_time = datetime.now() - timedelta(hours=hours)
                sensor_data['time'] = pd.to_datetime(sensor_data['time'])
                sensor_data = sensor_data[sensor_data['time'] >= cutoff_time]
        
        return sensor_data
    
    def get_equipment_status(self, target_date=None):
        """설비 상태 데이터 반환 (알림 데이터 반영)"""
        # 매번 캐시를 클리어하여 최신 데이터 반영
        if 'equipment_status' in self._cached_data:
            del self._cached_data['equipment_status']
        if 'alert_data' in self._cached_data:
            del self._cached_data['alert_data']
            
        equipment_status = self._get_cached_data('equipment_status')
        alerts = self._get_cached_data('alert_data')
        
        # 주간 데이터인 경우 날짜 필터링 로직 수정
        if self.use_weekly_data:
            # 주간 데이터에서도 알림과 연동하여 상태 업데이트
            if target_date:
                # 특정 날짜의 설비 상태만 반환
                filtered_status = [eq for eq in equipment_status if eq.get('date') == target_date]
            else:
                # 최신 날짜의 설비 상태 반환
                if equipment_status:
                    latest_date = max(eq.get('date', '') for eq in equipment_status)
                    filtered_status = [eq for eq in equipment_status if eq.get('date') == latest_date]
                else:
                    return equipment_status
            
            # 알림 데이터에서 해당 날짜의 설비별 상태 매핑
            if alerts:
                status_map = {}
                for alert in alerts:
                    alert_date = alert.get('timestamp', '')[:10] if 'timestamp' in alert else alert.get('time', '')[:10]
                    if alert_date != (target_date or latest_date):
                        continue
                    
                    eq = alert['equipment']
                    sev = alert['severity']
                    
                    # 심각도에 따른 상태 매핑 (한국어 심각도)
                    if sev == '긴급':
                        status_map[eq] = '위험'
                    elif sev == '높음':
                        if status_map.get(eq) != '위험':
                            status_map[eq] = '주의'
                    elif sev == '보통':
                        if status_map.get(eq) not in ['위험', '주의']:
                            status_map[eq] = '경고'
                    elif sev == '낮음':
                        if status_map.get(eq) not in ['위험', '주의', '경고']:
                            status_map[eq] = '정상'
                
                # 설비 상태에 알림 기반 상태 반영
                for equip in filtered_status:
                    equip_name = equip['name']
                    if equip_name in status_map:
                        equip['status'] = status_map[equip_name]
                    else:
                        # 해당 날짜에 알림이 없으면 정상 상태로 설정
                        equip['status'] = '정상'
            
            return filtered_status
        else:
            # 기존 로직 (실시간 데이터)
            # target_date가 None이면 가장 최근 날짜 사용
            if target_date is None and alerts:
                dates = [alert['time'][:10] for alert in alerts]
                target_date = max(dates)
            
            # 알림 데이터에서 해당 날짜의 설비별 상태 매핑
            if target_date and alerts:
                status_map = {}
                for alert in alerts:
                    if alert['time'][:10] != target_date:
                        continue
                    eq = alert['equipment']
                    sev = alert['severity']
                    if sev == 'error':
                        status_map[eq] = '위험'
                    elif sev == 'warning' and status_map.get(eq) != '위험':
                        status_map[eq] = '주의'
                
                # 설비 상태에 알림 기반 상태 반영
                for equip in equipment_status:
                    equip_name = equip['name']
                    if equip_name in status_map:
                        equip['status'] = status_map[equip_name]
                    else:
                        # 해당 날짜에 알림이 없으면 정상 상태로 설정
                        equip['status'] = '정상'
        
        return equipment_status
    
    def get_alert_data(self, target_date=None):
        """알림 데이터 반환 (날짜별 필터링 지원)"""
        alerts = self._get_cached_data('alert_data')
        
        # 주간 데이터인 경우 timestamp를 time으로 변환하여 호환성 확보
        if self.use_weekly_data and alerts:
            for alert in alerts:
                if 'timestamp' in alert and 'time' not in alert:
                    alert['time'] = alert['timestamp']
        
        if target_date and alerts:
            # 특정 날짜의 알림만 필터링
            if self.use_weekly_data:
                # 주간 데이터에서는 timestamp 컬럼 사용
                filtered_alerts = [alert for alert in alerts if alert['timestamp'][:10] == target_date]
            else:
                # 기존 로직 (실시간 데이터)
                filtered_alerts = [alert for alert in alerts if alert['time'][:10] == target_date]
            return filtered_alerts
        
        return alerts
    
    def get_quality_trend(self):
        """품질 추세 데이터 반환"""
        quality_data = self._get_cached_data('quality_trend')
        if quality_data.empty:
            return pd.DataFrame()
        
        # 주간 데이터인 경우 대시보드 호환 형태로 변환
        if self.use_weekly_data:
            # 품질 데이터를 딕셔너리 형태로 변환
            if not quality_data.empty:
                latest_quality = quality_data.iloc[-1] if len(quality_data) > 0 else None
                if latest_quality is not None:
                    return {
                        'quality_score': latest_quality.get('quality_score', 0),
                        'defect_rate': latest_quality.get('defect_rate', 0),
                        'date': latest_quality.get('date', '')
                    }
        
        return quality_data
    
    def get_production_kpi(self):
        """생산성 KPI 데이터 반환"""
        kpi_data = self._get_cached_data('production_kpi')
        
        # 주간 데이터인 경우 대시보드 호환 형태로 변환
        if self.use_weekly_data and isinstance(kpi_data, list):
            # 가장 최근 KPI 데이터를 사용하여 대시보드 형식으로 변환
            if kpi_data:
                latest_kpi = max(kpi_data, key=lambda x: x.get('date', ''))
                production_volume = latest_kpi.get('production_volume', 0)
                efficiency = latest_kpi.get('efficiency', 0)
                downtime = latest_kpi.get('downtime', 0)
                availability = round(100 - downtime, 1)
                
                return {
                    'daily_target': 1300,
                    'daily_actual': production_volume,
                    'weekly_target': 9100,
                    'weekly_actual': production_volume * 7,  # 일일 생산량 * 7
                    'monthly_target': 39000,
                    'monthly_actual': production_volume * 30,  # 일일 생산량 * 30
                    'oee': efficiency,  # Overall Equipment Effectiveness
                    'availability': availability,
                    'performance': efficiency,
                    'quality': 99.98,  # 품질률 99.98% (불량률 0.02%)
                    'production_volume': production_volume,
                    'efficiency': efficiency,
                    'downtime': downtime,
                    'date': latest_kpi.get('date', '')
                }
            else:
                return {
                    'daily_target': 1300,
                    'daily_actual': 0,
                    'weekly_target': 9100,
                    'weekly_actual': 0,
                    'monthly_target': 39000,
                    'monthly_actual': 0,
                    'oee': 0,
                    'availability': 0,
                    'performance': 0,
                    'quality': 99.98,
                    'production_volume': 0,
                    'efficiency': 0,
                    'downtime': 0,
                    'date': ''
                }
        
        return kpi_data
    
    def get_ai_prediction_data(self):
        """AI 예측 데이터 반환 (대시보드 호환 형태로 변환)"""
        ai_data = self._get_cached_data('ai_prediction_data')
        
        if not ai_data:
            return {}
        
        # 주간 데이터인 경우 리스트 형태로 반환
        if self.use_weekly_data and isinstance(ai_data, list):
            # 주간 데이터는 리스트 형태이므로 대시보드 호환 형태로 변환
            result = {}
            
            # 가장 최근 AI 예측 데이터를 abnormal_detection으로 사용
            if ai_data:
                latest_abnormal = max(ai_data, key=lambda x: x.get('timestamp', ''))
                result['abnormal_detection'] = {
                    'equipment': latest_abnormal.get('equipment', ''),
                    'prediction': {
                        'probability': latest_abnormal.get('probability', 0),
                        'status': latest_abnormal.get('status', ''),
                        'date': latest_abnormal.get('prediction_date', '')
                    },
                    'timestamp': latest_abnormal.get('timestamp', '')
                }
            
            # 유압 예측 데이터도 추가
            hydraulic_data = self._get_cached_data('hydraulic_prediction_data')
            if hydraulic_data and isinstance(hydraulic_data, list):
                latest_hydraulic = max(hydraulic_data, key=lambda x: x.get('timestamp', ''))
                result['hydraulic_detection'] = {
                    'equipment': latest_hydraulic.get('equipment', ''),
                    'prediction': {
                        'probability': latest_hydraulic.get('probability', 0),
                        'status': latest_hydraulic.get('status', ''),
                        'date': latest_hydraulic.get('prediction_date', '')
                    },
                    'timestamp': latest_hydraulic.get('timestamp', '')
                }
            
            return result
        
        # 기존 로직 (실시간 데이터)
        # 대시보드에서 기대하는 형태로 변환
        # abnormal_detection과 hydraulic_detection 키로 통합
        result = {}
        
        # 모든 설비의 이상 탐지 데이터를 하나로 통합
        abnormal_predictions = []
        hydraulic_predictions = []
        
        for key, value in ai_data.items():
            if key.endswith('_abnormal'):
                abnormal_predictions.append(value)
            elif key.endswith('_hydraulic'):
                hydraulic_predictions.append(value)
        
        # 이상 탐지 데이터 통합 (가장 최근 데이터 또는 평균 사용)
        if abnormal_predictions:
            # 가장 높은 신뢰도를 가진 예측을 선택
            best_abnormal = max(abnormal_predictions, key=lambda x: x.get('prediction', {}).get('confidence', 0))
            result['abnormal_detection'] = best_abnormal
        
        # 유압 이상 탐지 데이터 통합
        if hydraulic_predictions:
            # 가장 높은 신뢰도를 가진 예측을 선택
            best_hydraulic = max(hydraulic_predictions, key=lambda x: x.get('prediction', {}).get('confidence', 0))
            result['hydraulic_detection'] = best_hydraulic
        
        return result
    
    def get_users_data(self):
        """사용자 데이터 반환"""
        return self._get_cached_data('users_data')
    
    def get_equipment_users_data(self):
        """설비별 사용자 데이터 반환"""
        return self._get_cached_data('equipment_users_data')
    
    def get_hydraulic_prediction_data(self):
        """유압 예측 데이터 반환"""
        return self._get_cached_data('hydraulic_prediction_data')
    
    def get_filtered_sensor_data(self, equipment=None, sensor_type=None, hours=6):
        """필터링된 센서 데이터 반환"""
        sensor_data = self.get_sensor_data(hours)
        
        if sensor_data.empty:
            return pd.DataFrame()
        
        # 설비 필터링
        if equipment and equipment != "전체":
            sensor_data = sensor_data[sensor_data['equipment'] == equipment]
        
        # 센서 타입 필터링
        if sensor_type and sensor_type != "전체":
            sensor_data = sensor_data[sensor_data['sensor_type'] == sensor_type]
        
        return sensor_data
    
    def get_filtered_alert_data(self, equipment=None, severity=None, status=None, start_date=None, end_date=None):
        """필터링된 알림 데이터 반환"""
        alert_data = self.get_alert_data()
        
        if not alert_data:
            return []
        
        filtered_alerts = alert_data
        
        # 날짜 필터링
        if start_date and end_date:
            filtered_alerts = []
            for alert in alert_data:
                try:
                    if self.use_weekly_data:
                        # 주간 데이터에서는 timestamp 컬럼 사용
                        alert_time = datetime.strptime(alert['timestamp'], '%Y-%m-%d %H:%M:%S')
                    else:
                        # 기존 로직 (실시간 데이터)
                        alert_time = datetime.strptime(alert['time'], '%Y-%m-%d %H:%M:%S')
                    
                    if start_date <= alert_time <= end_date:
                        filtered_alerts.append(alert)
                except:
                    # 날짜 파싱 실패 시 포함
                    filtered_alerts.append(alert)
        
        # 설비 필터링
        if equipment and equipment != "전체":
            filtered_alerts = [alert for alert in filtered_alerts if alert['equipment'] == equipment]
        
        # 심각도 필터링
        if severity and severity != "전체":
            filtered_alerts = [alert for alert in filtered_alerts if alert['severity'] == severity]
        
        # 상태 필터링
        if status and status != "전체":
            filtered_alerts = [alert for alert in filtered_alerts if alert['status'] == status]
        
        return filtered_alerts
    
    def get_equipment_by_type(self, equipment_type=None, target_date=None):
        """설비 타입별 필터링된 설비 상태 반환"""
        equipment_data = self.get_equipment_status(target_date)
        
        if not equipment_data:
            return []
        
        if equipment_type and equipment_type != "전체":
            filtered_equipment = [eq for eq in equipment_data if eq['type'] == equipment_type]
        else:
            filtered_equipment = equipment_data
        
        return filtered_equipment
    
    def get_ai_prediction_for_equipment(self, equipment_name):
        """특정 설비의 AI 예측 데이터 반환"""
        ai_data = self.get_ai_prediction_data()
        
        if not ai_data:
            return {}
        
        # 설비명으로 키 생성
        abnormal_key = f'{equipment_name}_abnormal'
        hydraulic_key = f'{equipment_name}_hydraulic'
        
        result = {}
        if abnormal_key in ai_data:
            result['abnormal_detection'] = ai_data[abnormal_key]
        if hydraulic_key in ai_data:
            result['hydraulic_detection'] = ai_data[hydraulic_key]
        
        return result
    
    def refresh_cache(self):
        """캐시 새로고침"""
        self._cached_data = {}
        print("더미 데이터 캐시가 새로고침되었습니다.")
    
    def get_available_dates(self):
        """사용 가능한 날짜 목록 반환"""
        if self.use_weekly_data:
            # 주간 데이터에서 사용 가능한 날짜 추출
            sensor_data = self._get_cached_data('sensor_data')
            if not sensor_data.empty and 'timestamp' in sensor_data.columns:
                dates = pd.to_datetime(sensor_data['timestamp']).dt.date.unique()
                return sorted([date.strftime('%Y-%m-%d') for date in dates])
            return []
        else:
            # 실시간 데이터의 경우 현재 날짜만 반환
            return [datetime.now().strftime('%Y-%m-%d')]
    
    def get_data_summary(self):
        """데이터 요약 정보 반환"""
        summary = {
            'sensor_records': len(self.get_sensor_data()),
            'equipment_status_records': len(self.get_equipment_status()),
            'alert_records': len(self.get_alert_data()),
            'ai_prediction_records': len(self.get_ai_prediction_data()) if isinstance(self.get_ai_prediction_data(), dict) else 0,
            'hydraulic_prediction_records': len(self.get_hydraulic_prediction_data()),
            'quality_records': len(self.get_quality_trend()) if not self.get_quality_trend().empty else 0,
            'kpi_records': len(self.get_production_kpi()),
            'users_records': len(self.get_users_data()),
            'equipment_users_records': len(self.get_equipment_users_data()),
            'available_dates': self.get_available_dates()
        }
        return summary
    
    def get_daily_summary(self, target_date):
        """특정 날짜의 요약 정보 반환"""
        daily_summary = {
            'date': target_date,
            'equipment_count': len(self.get_equipment_status(target_date)),
            'alert_count': len(self.get_alert_data(target_date)),
            'sensor_data_count': len(self.get_sensor_data_by_date(target_date)),
            'quality_score': self.get_quality_score_by_date(target_date),
            'production_volume': self.get_production_volume_by_date(target_date)
        }
        return daily_summary
    
    def get_sensor_data_by_date(self, target_date):
        """특정 날짜의 센서 데이터 반환"""
        sensor_data = self.get_sensor_data()
        if not sensor_data.empty:
            # 날짜 필터링
            sensor_data['date'] = pd.to_datetime(sensor_data['time']).dt.date
            target_date_obj = datetime.strptime(target_date, '%Y-%m-%d').date()
            filtered_data = sensor_data[sensor_data['date'] == target_date_obj]
            return filtered_data
        return pd.DataFrame()
    
    def get_quality_score_by_date(self, target_date):
        """특정 날짜의 품질 점수 반환"""
        quality_data = self._get_cached_data('quality_trend')
        if not quality_data.empty:
            # 날짜 필터링
            quality_data['date'] = pd.to_datetime(quality_data['date']).dt.date
            target_date_obj = datetime.strptime(target_date, '%Y-%m-%d').date()
            filtered_data = quality_data[quality_data['date'] == target_date_obj]
            if not filtered_data.empty:
                return filtered_data.iloc[0]['quality_score']
        return None
    
    def get_production_volume_by_date(self, target_date):
        """특정 날짜의 생산량 반환"""
        kpi_data = self._get_cached_data('production_kpi')
        if kpi_data:
            for kpi in kpi_data:
                if kpi.get('date') == target_date:
                    return kpi.get('production_volume')
        return None
    
    def get_kpi_summary(self):
        """KPI 요약 정보 반환 (대시보드용)"""
        kpi_data = self._get_cached_data('production_kpi')
        if not kpi_data:
            return {
                'total_production': 0,
                'avg_efficiency': 0,
                'avg_availability': 0,
                'total_downtime': 0
            }
        
        total_production = sum(kpi.get('production_volume', 0) for kpi in kpi_data)
        avg_efficiency = sum(kpi.get('efficiency', 0) for kpi in kpi_data) / len(kpi_data)
        avg_availability = sum(100 - kpi.get('downtime', 0) for kpi in kpi_data) / len(kpi_data)
        total_downtime = sum(kpi.get('downtime', 0) for kpi in kpi_data)
        
        return {
            'total_production': total_production,
            'avg_efficiency': round(avg_efficiency, 1),
            'avg_availability': round(avg_availability, 1),
            'total_downtime': round(total_downtime, 1)
        }
    
    def get_quality_summary(self):
        """품질 요약 정보 반환 (대시보드용)"""
        quality_data = self._get_cached_data('quality_trend')
        if quality_data.empty:
            return {
                'avg_quality_score': 0,
                'avg_defect_rate': 0,
                'best_quality_score': 0,
                'worst_quality_score': 0
            }
        
        quality_scores = quality_data['quality_score'].tolist()
        defect_rates = quality_data['defect_rate'].tolist()
        
        return {
            'avg_quality_score': round(sum(quality_scores) / len(quality_scores), 1),
            'avg_defect_rate': round(sum(defect_rates) / len(defect_rates), 2),
            'best_quality_score': max(quality_scores),
            'worst_quality_score': min(quality_scores)
        }
    
    def get_alert_summary(self):
        """알림 요약 정보 반환 (대시보드용)"""
        alert_data = self._get_cached_data('alert_data')
        if not alert_data:
            return {
                'total_alerts': 0,
                'critical_alerts': 0,
                'warning_alerts': 0,
                'info_alerts': 0,
                'resolved_alerts': 0
            }
        
        total_alerts = len(alert_data)
        critical_alerts = len([alert for alert in alert_data if alert.get('severity') == '긴급'])
        warning_alerts = len([alert for alert in alert_data if alert.get('severity') == '높음'])
        info_alerts = len([alert for alert in alert_data if alert.get('severity') in ['보통', '낮음']])
        resolved_alerts = len([alert for alert in alert_data if alert.get('status') == '처리완료'])
        
        return {
            'total_alerts': total_alerts,
            'critical_alerts': critical_alerts,
            'warning_alerts': warning_alerts,
            'info_alerts': info_alerts,
            'resolved_alerts': resolved_alerts
        }
    
    def get_equipment_summary(self):
        """설비 요약 정보 반환 (대시보드용)"""
        equipment_data = self._get_cached_data('equipment_status')
        if not equipment_data:
            return {
                'total_equipment': 0,
                'normal_equipment': 0,
                'warning_equipment': 0,
                'critical_equipment': 0,
                'avg_efficiency': 0
            }
        
        # 최신 날짜의 설비 상태만 사용
        latest_date = max(eq.get('date', '') for eq in equipment_data)
        latest_equipment = [eq for eq in equipment_data if eq.get('date') == latest_date]
        
        total_equipment = len(latest_equipment)
        normal_equipment = len([eq for eq in latest_equipment if eq.get('status') == '정상'])
        warning_equipment = len([eq for eq in latest_equipment if eq.get('status') in ['주의', '경고']])
        critical_equipment = len([eq for eq in latest_equipment if eq.get('status') == '위험'])
        avg_efficiency = sum(eq.get('efficiency', 0) for eq in latest_equipment) / total_equipment if total_equipment > 0 else 0
        
        return {
            'total_equipment': total_equipment,
            'normal_equipment': normal_equipment,
            'warning_equipment': warning_equipment,
            'critical_equipment': critical_equipment,
            'avg_efficiency': round(avg_efficiency, 1)
        }

# 전역 인스턴스 생성 (주간 데이터 사용)
dummy_loader = DummyDataLoader(use_weekly_data=True) 