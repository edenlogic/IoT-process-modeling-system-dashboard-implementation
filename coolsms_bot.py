#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import asyncio
import json
import logging
import requests
import time
import hashlib
import os
from datetime import datetime, timedelta
from typing import Dict, List, Set, Optional, Tuple, Deque
from dataclasses import dataclass, asdict, field
from collections import deque
from threading import Thread
import re

# 환경변수 로드
from dotenv import load_dotenv
load_dotenv()

# CoolSMS SDK
from sdk.api.message import Message
from sdk.exceptions import CoolsmsException

# FastAPI 통신용
from fastapi import FastAPI, Request, HTTPException, Form
from pydantic import BaseModel
import uvicorn

# 로깅 설정
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO  # 운영 환경에서는 INFO 레벨 사용
)
logger = logging.getLogger(__name__)

# 환경변수에서 설정 가져오기
COOLSMS_API_KEY = os.getenv("COOLSMS_API_KEY")
COOLSMS_API_SECRET = os.getenv("COOLSMS_API_SECRET")
COOLSMS_SENDER = os.getenv("COOLSMS_SENDER")
FASTAPI_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://localhost:8000")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000")
ADMIN_PHONE_NUMBERS = [num.strip() for num in os.getenv("ADMIN_PHONE_NUMBERS", "").split(",") if num.strip()]

# 설정 확인
if not all([COOLSMS_API_KEY, COOLSMS_API_SECRET, COOLSMS_SENDER]):
    logger.error("❌ CoolSMS 설정이 완료되지 않았습니다!")
    exit(1)
else:
    logger.info(f"✅ 환경변수 로드 성공")
    logger.info(f"  - API URL: {FASTAPI_BASE_URL}")
    logger.info(f"  - Public URL: {PUBLIC_BASE_URL}")
    logger.info(f"  - 발신번호: {COOLSMS_SENDER}")
    logger.info(f"  - 관리자 수: {len(ADMIN_PHONE_NUMBERS)}")

@dataclass
class Alert:
    """알림 데이터 클래스"""
    id: str
    equipment: str
    sensor_type: str
    value: float
    threshold: float
    severity: str
    timestamp: str
    message: str
    status: str = "미처리"
    assigned_to: str = None
    hash_key: str = field(default="", init=False)
    alert_number: int = field(default=0, init=False)
    action_link: str = field(default="", init=False)  # 웹 링크 추가
    
    def __post_init__(self):
        """알림 고유 해시 생성"""
        unique_string = f"{self.equipment}:{self.sensor_type}:{self.severity}"
        self.hash_key = hashlib.md5(unique_string.encode()).hexdigest()

@dataclass
class AlertHistory:
    """알림 이력 관리"""
    alert_hash: str
    equipment: str
    sensor_type: str
    severity: str
    first_occurrence: datetime
    last_occurrence: datetime
    occurrence_count: int = 1
    values: List[float] = field(default_factory=list)
    is_active: bool = True
    last_notification_time: Optional[datetime] = None

class MemoryStorage:
    """메모리 기반 데이터 저장소"""
    
    def __init__(self):
        self.alerts: Dict[str, Alert] = {}
        self.equipment_status: Dict[str, Dict] = {}
        self.phone_subscriptions: Set[str] = set()
        self.action_history: List[Dict] = []
        self.alert_history: Dict[str, AlertHistory] = {}
        self.recent_raw_alerts: List[Dict] = []
        self.notification_cooldown: Dict[str, datetime] = {}
        self.alert_counter = 0
        self.processed_messages: Set[str] = set()  # 처리한 메시지 ID 저장
        
        self.cooldown_periods = {
            'error': timedelta(seconds=int(os.getenv("ERROR_COOLDOWN_SECONDS", "20"))),
            'warning': timedelta(seconds=int(os.getenv("WARNING_COOLDOWN_SECONDS", "30"))),
            'info': timedelta(seconds=int(os.getenv("INFO_COOLDOWN_SECONDS", "60")))
        }
        self.value_change_threshold = float(os.getenv("VALUE_CHANGE_THRESHOLD", "0.1"))
        self.max_raw_alerts_history = int(os.getenv("MAX_RAW_ALERTS_HISTORY", "100"))
        
        self.subscribers_file = "subscribers.json"
        self.load_subscribers()
        
    def should_send_notification(self, alert: Alert) -> Tuple[bool, str]:
        """알림 전송 여부 판단"""
        # FastAPI에서 이미 필터링했으므로 CoolSMS에서는 모두 통과
        return True, "FastAPI에서 이미 검증됨"
        
    def add_alert(self, alert: Alert) -> bool:
        """알림 추가"""
        should_notify, reason = self.should_send_notification(alert)
        
        if should_notify:
            self.alert_counter += 1
            alert.alert_number = self.alert_counter
            
            self.alerts[alert.id] = alert
            logger.info(f"알림 추가: {alert.equipment}/{alert.sensor_type} (#{alert.alert_number}) - {reason}")
            return True
        else:
            logger.info(f"알림 스킵: {alert.equipment}/{alert.sensor_type} - {reason}")
            return False
            
    def load_subscribers(self):
        """구독자 불러오기"""
        if os.path.exists(self.subscribers_file):
            try:
                with open(self.subscribers_file, 'r', encoding='utf-8') as f:
                    subscribers = json.load(f)
                    self.phone_subscriptions = set(subscribers)
                    logger.info(f"✅ 구독자 {len(self.phone_subscriptions)}명 로드됨")
            except Exception as e:
                logger.error(f"구독자 파일 로드 오류: {e}")
                self.phone_subscriptions = set()
        else:
            logger.info("구독자 파일이 없습니다. 새로 시작합니다.")
            self.phone_subscriptions = set(ADMIN_PHONE_NUMBERS)
            self.save_subscribers()
    
    def save_subscribers(self):
        """구독자 저장"""
        try:
            with open(self.subscribers_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.phone_subscriptions), f, indent=2)
            logger.info(f"구독자 {len(self.phone_subscriptions)}명 저장됨")
        except Exception as e:
            logger.error(f"구독자 파일 저장 오류: {e}")

# 전역 저장소
storage = MemoryStorage()

class CoolSMSService:
    """CoolSMS 서비스 핸들러 (웹 링크 방식)"""
    
    def __init__(self):
        self.api = Message(COOLSMS_API_KEY, COOLSMS_API_SECRET)
        self.sender = COOLSMS_SENDER
        
    def format_alert_message_with_link(self, alert: Alert) -> str:
        """알림을 웹 링크 포함 SMS 메시지로 포맷팅"""
        equipment = alert.equipment
        current_time = datetime.now().strftime('%H:%M:%S')
        
        sensor_short = {
            'temperature': '온도',
            'pressure': '압력',
            'vibration': '진동',
            'power': '전력'
        }.get(alert.sensor_type, alert.sensor_type[:2])
        
        severity_code = {
            'error': 'HH',
            'warning': 'H',
            'info': 'L'
        }.get(alert.severity, 'HH')
        
        # TinyURL로 URL 단축
        try:
            short_url = requests.get(f"http://tinyurl.com/api-create.php?url={alert.action_link}").text
        except:
            short_url = "링크 생성 실패"
        
        # 메시지 구성 (원하는 포맷)
        message = f"{current_time}\n"
        message += f"{equipment} {severity_code}\n"
        message += f"{sensor_short}: {alert.value:.1f} > {alert.threshold:.1f}(임계값)\n"
        message += f"{short_url}"
            
        return message

    def send_alert_sms_with_link(self, phone: str, alert: Alert) -> bool:
        """웹 링크 포함 알림 SMS 발송"""
        try:
            message = self.format_alert_message_with_link(alert)
            
            result = self.api.send({
                'to': phone,
                'from': self.sender,
                'text': message,
                'type': 'SMS'
            })
            
            logger.info(f"✅ SMS 발송 성공: {phone} - {alert.equipment}")
            logger.info(f"   메시지 ID: {result.get('message_id')}")
            logger.info(f"   처리 링크: {alert.action_link}")
            
            return True
            
        except CoolsmsException as e:
            logger.error(f"❌ CoolSMS 오류: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ SMS 발송 실패: {e}")
            return False

    def send_confirmation_sms(self, phone: str, message: str) -> bool:
        """확인 메시지 발송"""
        try:
            # 메시지를 그대로 전송 (추가 처리 없음)
            result = self.api.send({
                'to': phone,
                'from': self.sender,
                'text': message,  # full_message 대신 message를 그대로 사용
                'type': 'SMS'
            })
            
            logger.info(f"✅ 확인 SMS 발송: {phone}")
            return True
            
        except CoolsmsException as e:
            logger.error(f"❌ 확인 SMS 오류: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ 확인 SMS 발송 실패: {e}")
            return False

# 전역 SMS 서비스
sms_service = CoolSMSService()

class FastAPIMonitor:
    """FastAPI 서버 모니터링"""
    
    def __init__(self, fastapi_url: str):
        self.fastapi_url = fastapi_url
        self.running = False
        self.processed_alerts = set()
        self.start_time = datetime.now()
        logger.info(f"🕐 모니터링 시작 시간: {self.start_time.strftime('%H:%M:%S')}")
        
    async def monitor_alerts(self):
        """알림 모니터링"""
        logger.info("📡 알림 모니터링 시작...")
        check_count = 0
        
        while self.running:
            try:
                check_count += 1
                
                if check_count % 10 == 0:
                    logger.info(f"[모니터링 #{check_count}] 활성 감시 중... (처리된 알림: {len(self.processed_alerts)}개)")
                
                response = requests.get(
                    f"{self.fastapi_url}/alerts",
                    params={"limit": 20},
                    timeout=5
                )
                
                if response.status_code == 200:
                    api_alerts = response.json()
                    
                    # 새 알림이 있을 때만 로그 출력
                    if api_alerts:
                        # 5초 이내의 알림만 카운트
                        recent_alerts = []
                        for api_alert in api_alerts:
                            try:
                                alert_time = datetime.fromisoformat(api_alert.get('timestamp', '').replace('Z', '+00:00'))
                                if alert_time >= self.start_time and alert_time >= datetime.now() - timedelta(seconds=5):
                                    recent_alerts.append(api_alert)
                            except:
                                pass
                        
                        if recent_alerts:
                            logger.info(f"[API 응답] 최근 알림 {len(recent_alerts)}개 발견")
                        else:
                            pass  # 총 {len(api_alerts)}개 알람 수신 (모두 이전 알림)
                    
                    for api_alert in api_alerts:
                        alert_time_str = api_alert.get('timestamp', '')
                        try:
                            alert_time = datetime.fromisoformat(alert_time_str.replace('Z', '+00:00'))
                            
                            # 봇 시작 시간 이후의 알림만 처리
                            if alert_time < self.start_time:
                                continue
                                
                            # 5초 이내의 알림만 처리 (빠른 대응)
                            five_seconds_ago = datetime.now() - timedelta(seconds=5)
                            if alert_time < five_seconds_ago:
                                continue
                                
                        except Exception as e:
                            logger.warning(f"시간 파싱 오류: {e}, 알림 처리 계속")
                        
                        unique_id = f"{api_alert.get('equipment', '')}_{api_alert.get('sensor_type', '')}_{api_alert.get('timestamp', '')}"
                        
                        if unique_id in self.processed_alerts:
                            continue

                        # ===== severity 필터링 전 로그 추가 =====
                        current_severity = api_alert.get('severity')
                        if current_severity != 'error':
                            pass  # severity={current_severity} 알람 스킵
                            continue
                        
                        # ===== error 알람만 통과했을 때 로그 =====
                        logger.info(f"🚨 새 알림 발견: {api_alert.get('equipment')} {api_alert.get('sensor_type')} "
                                f"= {api_alert.get('value')} (임계값: {api_alert.get('threshold')}) "
                                f"severity={api_alert.get('severity')}")
                            
                        alert = Alert(
                            id=unique_id,
                            equipment=api_alert.get('equipment', '알 수 없는 설비'),
                            sensor_type=api_alert.get('sensor_type', 'unknown'),
                            value=api_alert.get('value', 0.0),
                            threshold=api_alert.get('threshold', 0.0),
                            severity=api_alert.get('severity', 'info'),
                            timestamp=api_alert.get('timestamp', datetime.now().isoformat()),
                            message=api_alert.get('message', '알림 메시지')
                        )
                        
                        # 알림 추가 (중복 체크 포함)
                        if storage.add_alert(alert):
                            self.processed_alerts.add(unique_id)
                            
                            # 처리 링크 가져오기 (API에서 생성된 링크)
                            if 'action_link' in api_alert:
                                alert.action_link = api_alert['action_link']
                            else:
                                # 링크가 없으면 생성 요청
                                logger.warning(f"⚠️ action_link가 없음. API 서버에서 생성해야 합니다.")
                                continue
                            
                            # 모든 구독자에게 웹 링크 포함 SMS 발송
                            for phone in storage.phone_subscriptions:
                                logger.info(f"📤 웹 링크 SMS 발송: {phone} ← {alert.equipment}")
                                success = sms_service.send_alert_sms_with_link(phone, alert)
                                
                                if not success:
                                    logger.error(f"❌ SMS 발송 실패: {phone}")
                        else:
                            self.processed_alerts.add(unique_id)
                            logger.info(f"⏭️ 알림 스킵 (CoolSMS 자체 필터): {api_alert.get('equipment')}/{api_alert.get('sensor_type')}")
                        
                        if len(self.processed_alerts) > 1000:
                            self.processed_alerts = set(list(self.processed_alerts)[-500:])
                            
                await asyncio.sleep(1)
                
            except requests.exceptions.ConnectionError:
                logger.error("❌ FastAPI 서버 연결 실패! 서버가 실행 중인지 확인하세요.")
                await asyncio.sleep(10)
            except Exception as e:
                logger.error(f"모니터링 오류: {e}")
                await asyncio.sleep(10)

# FastAPI 웹훅 서버 (SMS 수신용 - 웹 링크 방식에서는 사용 안 함)
app = FastAPI(title="CoolSMS Webhook Server (Web Link Mode)")

@app.get("/health")
async def health_check():
    """헬스체크"""
    return {
        "status": "healthy",
        "mode": "web_link",
        "subscribers": len(storage.phone_subscriptions),
        "total_alerts_sent": storage.alert_counter,
        "timestamp": datetime.now().isoformat()
    }

@app.post("/subscribe/{phone}")
async def subscribe(phone: str):
    """구독자 추가"""
    phone = phone.replace('-', '')
    storage.phone_subscriptions.add(phone)
    storage.save_subscribers()
    
    sms_service.send_confirmation_sms(phone, "✅IoT알림구독\n설비이상시 링크 전송")
    
    return {"status": "subscribed", "phone": phone}

@app.post("/unsubscribe/{phone}")
async def unsubscribe(phone: str):
    """구독 취소"""
    phone = phone.replace('-', '')
    if phone in storage.phone_subscriptions:
        storage.phone_subscriptions.remove(phone)
        storage.save_subscribers()
        
        sms_service.send_confirmation_sms(phone, "❌IoT알림구독 취소\n더이상 알림을 받지 않습니다")
        
        return {"status": "unsubscribed", "phone": phone}
    else:
        return {"status": "not_found", "phone": phone}

@app.get("/subscribers")
async def get_subscribers():
    """구독자 목록"""
    return {
        "subscribers": list(storage.phone_subscriptions),
        "count": len(storage.phone_subscriptions)
    }

@app.get("/stats")
async def get_stats():
    """통계 정보"""
    return {
        "mode": "web_link",
        "total_alerts": len(storage.alerts),
        "total_sent": storage.alert_counter,
        "active_subscribers": len(storage.phone_subscriptions),
        "alert_history": len(storage.alert_history),
        "equipment_stats": {},  # 필요시 구현
        "timestamp": datetime.now().isoformat()
    }

# 웹 링크 처리 결과 콜백 (API 서버에서 호출)
@app.post("/action_callback")
async def action_callback(data: dict):
    """웹 링크 처리 완료 콜백"""
    logger.info(f"✅ 웹 링크 처리 완료 콜백: {data}")
    
    # 처리 완료 SMS 발송 (옵션)
    if data.get("send_confirmation") and data.get("phone"):
        equipment = data.get("equipment", "알 수 없음")
        action = "인터락" if data.get("action_type") == "interlock" else "바이패스"
        
        message = f"✅ 처리 완료\n{equipment}\n조치: {action}\n시간: {datetime.now().strftime('%H:%M:%S')}"
        sms_service.send_confirmation_sms(data["phone"], message)
    
    return {"status": "ok"}

async def run_webhook_server():
    """웹훅 서버 실행"""
    config = uvicorn.Config(app, host="0.0.0.0", port=8001)
    server = uvicorn.Server(config)
    await server.serve()

async def periodic_status_report():
    """주기적 상태 리포트"""
    while True:
        await asyncio.sleep(3600)  # 1시간마다
        
        try:
            total_sent = storage.alert_counter
            
            if total_sent > 0:
                logger.info("="*50)
                logger.info("📊 시간별 처리 통계 (웹 링크 모드)")
                logger.info(f"총 발송: {total_sent}건")
                logger.info(f"구독자: {len(storage.phone_subscriptions)}명")
                logger.info("="*50)
                
        except Exception as e:
            logger.error(f"통계 리포트 오류: {e}")

async def main():
    """메인 실행 함수"""
    
    logger.info("=== CoolSMS IoT 알림 시스템 (웹 링크 모드) ===")
    logger.info(f"발신번호: {COOLSMS_SENDER}")
    logger.info(f"API URL: {FASTAPI_BASE_URL}")
    logger.info(f"Public URL: {PUBLIC_BASE_URL}")
    logger.info(f"구독자 수: {len(storage.phone_subscriptions)}")
    logger.info("==========================================")
    
    try:
        test_response = requests.get(f"{FASTAPI_BASE_URL}/health", timeout=5)
        if test_response.status_code == 200:
            logger.info("✅ FastAPI 서버 연결 성공")
        else:
            logger.error("❌ FastAPI 서버 응답 오류")
    except Exception as e:
        logger.error(f"❌ FastAPI 서버 연결 실패: {e}")
    
    monitor = FastAPIMonitor(FASTAPI_BASE_URL)
    
    try:
        monitor.running = True
        
        monitor_task = asyncio.create_task(monitor.monitor_alerts())
        webhook_task = asyncio.create_task(run_webhook_server())
        status_task = asyncio.create_task(periodic_status_report())
        
        logger.info("🚀 CoolSMS IoT 시스템 가동! (웹 링크 모드)")
        logger.info("📱 SMS 알림에 처리 링크가 포함됩니다")
        logger.info("🔗 사용자가 링크를 클릭하여 처리합니다")
        logger.info("⏱️ 1초마다 새 알림 확인")
        logger.info(f"⏰ 쿨다운: error {storage.cooldown_periods['error'].seconds}초, "
                   f"warning {storage.cooldown_periods['warning'].seconds}초")
        
        await asyncio.gather(monitor_task, webhook_task, status_task)
        
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중지됨")
    except Exception as e:
        logger.error(f"오류 발생: {e}")
    finally:
        monitor.running = False

# 모듈로 사용할 때만 실행
if __name__ == "__main__":
    asyncio.run(main())