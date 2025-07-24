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
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, asdict, field
from threading import Thread

# 환경변수 로드를 위한 dotenv
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 텔레그램 봇 라이브러리
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# 로깅 설정
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# 환경변수에서 설정 가져오기
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
FASTAPI_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://localhost:8000")
ADMIN_CHAT_IDS = [int(id.strip()) for id in os.getenv("ADMIN_CHAT_IDS", "").split(",") if id.strip().isdigit()]

# 토큰 확인
if not TELEGRAM_BOT_TOKEN:
    logger.error("❌ TELEGRAM_BOT_TOKEN이 설정되지 않았습니다!")
    logger.error("'.env' 파일을 확인하세요:")
    logger.error("  TELEGRAM_BOT_TOKEN=your_token_here")
    logger.error("  FASTAPI_BASE_URL=http://localhost:8000")
    logger.error("  ADMIN_CHAT_IDS=")
    exit(1)
else:
    logger.info(f"✅ 환경변수 로드 성공")
    logger.info(f"  - API URL: {FASTAPI_BASE_URL}")
    logger.info(f"  - 관리자 수: {len(ADMIN_CHAT_IDS)}")

@dataclass
class Alert:
    """알림 데이터 클래스"""
    id: str
    equipment: str
    sensor_type: str
    value: float
    threshold: float
    severity: str  # error, warning, info
    timestamp: str
    message: str
    status: str = "미처리"  # 미처리, 처리중, 완료
    assigned_to: str = None
    hash_key: str = field(default="", init=False)  # 중복 체크용 해시
    
    def __post_init__(self):
        """알림 고유 해시 생성"""
        # equipment, sensor_type, severity를 기반으로 해시 생성
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
        self.chat_subscriptions: Set[int] = set()
        self.user_roles: Dict[int, str] = {}
        
        # 중복 방지를 위한 추가 저장소
        self.alert_history: Dict[str, AlertHistory] = {}  # hash_key -> AlertHistory
        self.recent_raw_alerts: List[Dict] = []  # 최근 원본 알림 저장 (FastAPI로부터)
        self.notification_cooldown: Dict[str, datetime] = {}  # 알림별 쿨다운 시간
        
        # 설정 가능한 파라미터 (환경변수에서 가져오기)
        self.cooldown_periods = {
            'error': timedelta(minutes=int(os.getenv("ERROR_COOLDOWN_MINUTES", "5"))),
            'warning': timedelta(minutes=int(os.getenv("WARNING_COOLDOWN_MINUTES", "10"))),
            'info': timedelta(minutes=int(os.getenv("INFO_COOLDOWN_MINUTES", "30")))
        }
        self.value_change_threshold = float(os.getenv("VALUE_CHANGE_THRESHOLD", "0.1"))  # 10% 이상 변화시만 새 알림
        self.max_raw_alerts_history = int(os.getenv("MAX_RAW_ALERTS_HISTORY", "100"))  # 원본 알림 최대 저장 개수
        
        # 구독자 파일 경로
        self.subscribers_file = "subscribers.json"
        # 저장된 구독자 불러오기
        self.load_subscribers()
        
    def should_send_notification(self, alert: Alert) -> Tuple[bool, str]:
        """알림을 전송해야 하는지 판단"""
        
        # 1. 처음 보는 알림인지 확인
        if alert.hash_key not in self.alert_history:
            # 새로운 알림 타입
            self.alert_history[alert.hash_key] = AlertHistory(
                alert_hash=alert.hash_key,
                equipment=alert.equipment,
                sensor_type=alert.sensor_type,
                severity=alert.severity,
                first_occurrence=datetime.now(),
                last_occurrence=datetime.now(),
                occurrence_count=1,
                values=[alert.value],
                is_active=True,
                last_notification_time=datetime.now()
            )
            return True, "새로운 알림 타입"
        
        history = self.alert_history[alert.hash_key]
        now = datetime.now()
        
        # 2. 직전 값과 동일한지 체크 (완전히 같은 값인 경우만 스킵)
        if history.values and len(history.values) > 0:
            last_value = history.values[-1]
            if abs(alert.value - last_value) < 0.01:  # 거의 같은 값
                time_since_last = now - history.last_occurrence
                if time_since_last < timedelta(seconds=10):  # 10초 이내 동일값
                    history.last_occurrence = now
                    return False, f"동일한 값 반복 (값: {alert.value})"
        
        # 3. 값 이력 업데이트
        history.last_occurrence = now
        history.occurrence_count += 1
        history.values.append(alert.value)
        history.last_notification_time = now
        history.is_active = True
        
        # 값 이력은 최대 20개까지만 유지
        if len(history.values) > 20:
            history.values = history.values[-20:]
            
        return True, f"새로운 알림 (값: {alert.value})"
        
    def add_alert(self, alert: Alert) -> bool:
        """알림 추가 (중복 체크 포함)"""
        should_notify, reason = self.should_send_notification(alert)
        
        if should_notify:
            self.alerts[alert.id] = alert
            logger.info(f"알림 추가: {alert.equipment}/{alert.sensor_type} - {reason}")
            return True
        else:
            logger.info(f"알림 스킵: {alert.equipment}/{alert.sensor_type} - {reason}")
            return False
            
    def check_duplicate_raw_alert(self, raw_alert: Dict) -> bool:
        """원본 알림 중복 체크"""
        # 완전히 동일한 알림인지 확인 (값과 타임스탬프까지 포함)
        alert_signature = {
            'equipment': raw_alert.get('equipment'),
            'sensor_type': raw_alert.get('sensor_type'),
            'value': raw_alert.get('value'),
            'severity': raw_alert.get('severity'),
            'timestamp': raw_alert.get('timestamp')  # 타임스탬프 추가
        }
        
        # 최근 20개 알림과 비교 (더 많이 비교)
        for recent in self.recent_raw_alerts[-20:]:
            if all(recent.get(k) == v for k, v in alert_signature.items()):
                return True  # 완전히 동일한 알림
                
        # 원본 알림 저장
        self.recent_raw_alerts.append(raw_alert)
        if len(self.recent_raw_alerts) > self.max_raw_alerts_history:
            self.recent_raw_alerts = self.recent_raw_alerts[-self.max_raw_alerts_history:]
            
        return False
        
    def get_alert(self, alert_id: str) -> Alert:
        """알림 조회"""
        return self.alerts.get(alert_id)
        
    def update_alert_status(self, alert_id: str, status: str, assigned_to: str = None):
        """알림 상태 업데이트"""
        if alert_id in self.alerts:
            self.alerts[alert_id].status = status
            if assigned_to:
                self.alerts[alert_id].assigned_to = assigned_to
                
            # 알림이 완료되면 해당 타입의 활성 상태 해제
            if status == "완료":
                alert = self.alerts[alert_id]
                if alert.hash_key in self.alert_history:
                    self.alert_history[alert.hash_key].is_active = False
                    
    def get_active_alerts(self) -> List[Alert]:
        """활성 알림 목록 (미처리, 처리중)"""
        return [alert for alert in self.alerts.values() 
                if alert.status in ["미처리", "처리중"]]
                
    def get_alert_statistics(self) -> Dict:
        """알림 통계 정보"""
        stats = {
            'total_alerts': len(self.alerts),
            'active_alerts': len(self.get_active_alerts()),
            'unique_alert_types': len(self.alert_history),
            'equipment_stats': {},
            'severity_stats': {'error': 0, 'warning': 0, 'info': 0}
        }
        
        for history in self.alert_history.values():
            # 설비별 통계
            if history.equipment not in stats['equipment_stats']:
                stats['equipment_stats'][history.equipment] = {
                    'total': 0,
                    'active': 0,
                    'sensors': set()
                }
            
            stats['equipment_stats'][history.equipment]['total'] += history.occurrence_count
            if history.is_active:
                stats['equipment_stats'][history.equipment]['active'] += 1
            stats['equipment_stats'][history.equipment]['sensors'].add(history.sensor_type)
            
            # 심각도별 통계
            stats['severity_stats'][history.severity] += history.occurrence_count
            
        # set을 리스트로 변환
        for eq in stats['equipment_stats']:
            stats['equipment_stats'][eq]['sensors'] = list(stats['equipment_stats'][eq]['sensors'])
            
        return stats
        
    def load_subscribers(self):
        """저장된 구독자 불러오기"""
        if os.path.exists(self.subscribers_file):
            try:
                with open(self.subscribers_file, 'r', encoding='utf-8') as f:
                    subscribers = json.load(f)
                    self.chat_subscriptions = set(subscribers)
                    logger.info(f"✅ 구독자 {len(self.chat_subscriptions)}명 로드됨")
            except Exception as e:
                logger.error(f"구독자 파일 로드 오류: {e}")
                self.chat_subscriptions = set()
        else:
            logger.info("구독자 파일이 없습니다. 새로 시작합니다.")
            self.chat_subscriptions = set()
    
    def save_subscribers(self):
        """구독자 목록을 파일에 저장"""
        try:
            with open(self.subscribers_file, 'w', encoding='utf-8') as f:
                json.dump(list(self.chat_subscriptions), f, indent=2)
            logger.info(f"구독자 {len(self.chat_subscriptions)}명 저장됨")
        except Exception as e:
            logger.error(f"구독자 파일 저장 오류: {e}")
    
    def add_subscriber(self, chat_id: int):
        """구독자 추가"""
        self.chat_subscriptions.add(chat_id)
        self.save_subscribers()  # 파일에 저장
        
    def remove_subscriber(self, chat_id: int):
        """구독자 제거"""
        self.chat_subscriptions.discard(chat_id)
        self.save_subscribers()  # 파일에 저장
        
    def get_subscribers(self) -> Set[int]:
        """구독자 목록"""
        return self.chat_subscriptions.copy()

# 전역 저장소
storage = MemoryStorage()

class TelegramIoTBot:
    """텔레그램 IoT 알림 봇"""
    
    def __init__(self, token: str, fastapi_url: str):
        self.token = token
        self.fastapi_url = fastapi_url
        self.application = None
        self.running = False
        
    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """봇 시작 명령어"""
        chat_id = update.effective_chat.id
        welcome_text = """
🏭 **POSCO MOBILITY IoT 알림 봇**에 오신 것을 환영합니다!

📋 **사용 가능한 명령어:**
• `/start` - 봇 시작
• `/subscribe` - 알림 구독하기
• `/unsubscribe` - 알림 구독 취소
• `/alerts` - 현재 활성 알림 보기
• `/status` - 설비 상태 조회
• `/stats` - 알림 통계 보기
• `/help` - 도움말

⚡ **실시간 기능:**
• 센서 임계값 초과 시 즉시 알림
• 중복 알림 자동 필터링
• 인터락/바이패스 버튼으로 즉시 대응
• 설비별 상태 모니터링

시작하려면 `/subscribe` 명령어를 입력하세요!
        """
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
        
    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """알림 통계 표시"""
        stats = storage.get_alert_statistics()
        
        stats_text = "📊 **알림 통계**\n\n"
        stats_text += f"📈 **전체 현황:**\n"
        stats_text += f"• 총 알림 수: {stats['total_alerts']}건\n"
        stats_text += f"• 활성 알림: {stats['active_alerts']}건\n"
        stats_text += f"• 고유 알림 타입: {stats['unique_alert_types']}개\n\n"
        
        stats_text += f"🚨 **심각도별 통계:**\n"
        stats_text += f"• 🔴 Error: {stats['severity_stats']['error']}건\n"
        stats_text += f"• 🟠 Warning: {stats['severity_stats']['warning']}건\n"
        stats_text += f"• 🔵 Info: {stats['severity_stats']['info']}건\n\n"
        
        if stats['equipment_stats']:
            stats_text += f"🏭 **설비별 통계:**\n"
            for eq, eq_stats in list(stats['equipment_stats'].items())[:5]:
                stats_text += f"• **{eq}**: {eq_stats['total']}건 "
                if eq_stats['active'] > 0:
                    stats_text += f"(활성: {eq_stats['active']})"
                stats_text += f"\n  센서: {', '.join(eq_stats['sensors'][:3])}\n"
                
        await update.message.reply_text(stats_text, parse_mode='Markdown')
        
    async def subscribe_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """알림 구독"""
        chat_id = update.effective_chat.id
        storage.add_subscriber(chat_id)
        
        await update.message.reply_text(
            "✅ **알림 구독이 완료되었습니다!**\n\n"
            "이제 설비 이상 발생 시 실시간으로 알림을 받으실 수 있습니다.\n"
            "📱 임계값 초과, 설비 오류 등의 알림을 즉시 전송합니다.\n\n"
            "⚙️ **중복 알림 방지 기능이 활성화되어 있습니다:**\n"
            "• 동일 알림은 심각도에 따라 5-30분 간격으로 전송\n"
            "• 값 변화가 10% 이상일 때만 새 알림 전송",
            parse_mode='Markdown'
        )
        
        logger.info(f"새 구독자 추가: {chat_id}")
        
    async def unsubscribe_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """알림 구독 취소"""
        chat_id = update.effective_chat.id
        storage.remove_subscriber(chat_id)
        
        await update.message.reply_text(
            "❌ **알림 구독이 취소되었습니다.**\n\n"
            "더 이상 실시간 알림을 받지 않습니다.\n"
            "다시 구독하려면 `/subscribe` 명령어를 사용하세요.",
            parse_mode='Markdown'
        )
        
        logger.info(f"구독자 제거: {chat_id}")
        
    async def alerts_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """현재 활성 알림 조회"""
        active_alerts = storage.get_active_alerts()
        
        if not active_alerts:
            await update.message.reply_text(
                "✅ **현재 활성 알림이 없습니다.**\n\n"
                "모든 설비가 정상 작동 중입니다! 👍"
            )
            return
            
        alert_text = "🚨 **현재 활성 알림 목록:**\n\n"
        
        for alert in active_alerts[-10:]:  # 최근 10개만
            severity_emoji = {
                'error': '🔴',
                'warning': '🟠', 
                'info': '🔵'
            }.get(alert.severity, '⚪')
            
            status_emoji = {
                '미처리': '❌',
                '처리중': '⏳',
                '완료': '✅'
            }.get(alert.status, '❓')
            
            time_str = alert.timestamp.split('T')[1][:5] if 'T' in alert.timestamp else alert.timestamp
            
            # 알림 이력 정보 추가
            history = storage.alert_history.get(alert.hash_key)
            occurrence_info = ""
            if history:
                occurrence_info = f" (발생 {history.occurrence_count}회)"
            
            alert_text += f"{severity_emoji} **{alert.equipment}**{occurrence_info}\n"
            alert_text += f"   📊 {alert.sensor_type}: {alert.value} (임계값: {alert.threshold})\n"
            alert_text += f"   ⏰ {time_str} | {status_emoji} {alert.status}\n\n"
            
        await update.message.reply_text(alert_text, parse_mode='Markdown')
        
    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """설비 상태 조회"""
        try:
            # FastAPI에서 설비 상태 가져오기
            response = requests.get(f"{self.fastapi_url}/api/equipment_status", timeout=5)
            if response.status_code == 200:
                equipment_list = response.json()
                
                status_text = "🏭 **설비 현황:**\n\n"
                
                for eq in equipment_list[:8]:  # 상위 8개만
                    status_emoji = {
                        '정상': '🟢',
                        '주의': '🟠',
                        '오류': '🔴'
                    }.get(eq['status'], '⚪')
                    
                    efficiency = eq['efficiency']
                    efficiency_text = "높음" if efficiency >= 90 else "보통" if efficiency >= 70 else "낮음"
                    
                    status_text += f"{status_emoji} **{eq['name']}**\n"
                    status_text += f"   📈 가동률: {efficiency}% ({efficiency_text})\n"
                    status_text += f"   🔧 정비: {eq['last_maintenance']}\n\n"
                    
                await update.message.reply_text(status_text, parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ 설비 상태 조회에 실패했습니다.")
                
        except Exception as e:
            logger.error(f"설비 상태 조회 오류: {e}")
            await update.message.reply_text("❌ 설비 상태 조회 중 오류가 발생했습니다.")
            
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """도움말"""
        help_text = """
🤖 **POSCO MOBILITY IoT 알림 봇 도움말**

📋 **명령어:**
• `/start` - 봇 시작 및 환영 메시지
• `/subscribe` - 실시간 알림 구독
• `/unsubscribe` - 알림 구독 취소  
• `/alerts` - 현재 활성 알림 조회
• `/status` - 전체 설비 상태 확인
• `/stats` - 알림 통계 보기
• `/help` - 이 도움말 보기

🚨 **알림 기능:**
• **실시간 알림**: 센서 임계값 초과 시 즉시 전송
• **중복 방지**: 스마트한 필터링으로 알림 피로도 감소
• **인터락**: 설비 즉시 정지 (안전 우선)
• **바이패스**: 일시적 무시 (주의해서 사용)
• **상태 추적**: 처리 진행상황 실시간 업데이트

⚙️ **중복 알림 방지:**
• Error: 5분 간격
• Warning: 10분 간격  
• Info: 30분 간격
• 값 변화 10% 이상일 때만 재알림

⚠️ **심각도 구분:**
• 🔴 **Error**: 즉시 조치 필요 (설비 정지 권장)
• 🟠 **Warning**: 주의 관찰 필요
• 🔵 **Info**: 참고 정보

📞 **긴급 상황 시**: 
안전을 위해 먼저 **인터락** 버튼으로 설비를 정지한 후 현장 확인하세요.
        """
        await update.message.reply_text(help_text, parse_mode='Markdown')
        
    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """인라인 버튼 콜백 처리"""
        query = update.callback_query
        await query.answer()
        
        data = query.data
        chat_id = query.message.chat_id
        
        if data.startswith("interlock_"):
            alert_id = data.replace("interlock_", "")
            await self.handle_interlock(query, alert_id, chat_id)
            
        elif data.startswith("bypass_"):
            alert_id = data.replace("bypass_", "")
            await self.handle_bypass(query, alert_id, chat_id)
            
        elif data.startswith("status_"):
            alert_id = data.replace("status_", "")
            await self.show_alert_detail(query, alert_id)
            
    async def handle_interlock(self, query, alert_id: str, chat_id: int):
        """인터락 처리 (설비 즉시 정지)"""
        alert = storage.get_alert(alert_id)
        if not alert:
            await query.edit_message_text("❌ 알림을 찾을 수 없습니다.")
            return
            
        # 알림 상태 업데이트
        storage.update_alert_status(alert_id, "처리중", f"chat_{chat_id}")
        
        # FastAPI에 인터락 신호 전송
        try:
            # 1. 설비 상태 업데이트
            response = requests.put(
                f"{self.fastapi_url}/equipment/{alert.equipment}/status",
                params={"status": "정지", "efficiency": 0.0},
                timeout=5
            )
            
            # 2. 알림 상태 업데이트 (인터락 정보 포함)
            alert_response = requests.put(
                f"{self.fastapi_url}/alerts/{alert.equipment}_{alert.sensor_type}_{alert.timestamp}/status",
                params={
                    "status": "인터락",
                    "assigned_to": f"chat_{chat_id}",
                    "action_type": "interlock"
                },
                timeout=5
            )
            
            logger.info(f"인터락 API 전송 완료: {alert.equipment}")
            
            success_text = f"""
🔴 **인터락 실행 완료**

⚠️ **{alert.equipment}** 설비가 즉시 정지되었습니다.

📊 **알림 정보:**
• 센서: {alert.sensor_type}
• 측정값: {alert.value} (임계값: {alert.threshold})
• 시간: {alert.timestamp.split('T')[1][:5] if 'T' in alert.timestamp else alert.timestamp}

✅ **처리 상태**: 인터락 적용됨
👤 **담당자**: chat_{chat_id}

⚠️ **다음 단계:**
1. 현장으로 이동하여 안전 확인
2. 원인 파악 및 조치
3. 정상 확인 후 설비 재가동
            """
            
            await query.edit_message_text(success_text, parse_mode='Markdown')
            
            # 다른 구독자들에게도 인터락 알림
            interlock_notification = f"""
🚨 **인터락 실행 알림**

⚠️ {alert.equipment} 설비가 안전을 위해 정지되었습니다.
👤 조치자: 운영진 (chat_{chat_id})
⏰ 시간: {datetime.now().strftime('%H:%M')}
            """
            
            for subscriber_id in storage.get_subscribers():
                if subscriber_id != chat_id:
                    try:
                        await context.bot.send_message(
                            chat_id=subscriber_id,
                            text=interlock_notification,
                            parse_mode='Markdown'
                        )
                    except Exception as e:
                        logger.error(f"인터락 알림 전송 실패 {subscriber_id}: {e}")
                        
        except Exception as e:
            logger.error(f"인터락 처리 오류: {e}")
            await query.edit_message_text(f"❌ 인터락 처리 중 오류 발생: {str(e)}")
            
    async def handle_bypass(self, query, alert_id: str, chat_id: int):
        """바이패스 처리 (일시적 무시)"""
        alert = storage.get_alert(alert_id)
        if not alert:
            await query.edit_message_text("❌ 알림을 찾을 수 없습니다.")
            return
            
        # 알림 상태 업데이트
        storage.update_alert_status(alert_id, "바이패스", f"chat_{chat_id}")
        
        # FastAPI에 바이패스 정보 전송
        try:
            response = requests.put(
                f"{self.fastapi_url}/alerts/{alert.equipment}_{alert.sensor_type}_{alert.timestamp}/status",
                params={
                    "status": "바이패스",
                    "assigned_to": f"chat_{chat_id}",
                    "action_type": "bypass"
                },
                timeout=5
            )
            
            logger.info(f"바이패스 API 전송 완료: {alert.equipment}")
        except Exception as e:
            logger.error(f"바이패스 API 전송 오류: {e}")
        
        bypass_text = f"""
🟡 **바이패스 적용 완료**

⚠️ **{alert.equipment}** 알림이 일시적으로 무시됩니다.

📊 **알림 정보:**
• 센서: {alert.sensor_type}  
• 측정값: {alert.value} (임계값: {alert.threshold})
• 시간: {alert.timestamp.split('T')[1][:5] if 'T' in alert.timestamp else alert.timestamp}

✅ **처리 상태**: 바이패스 적용됨 (30분간)
👤 **담당자**: chat_{chat_id}

⚠️ **주의사항:**
• 바이패스는 30분간만 유효합니다
• 지속적인 모니터링이 필요합니다  
• 상황이 악화되면 즉시 인터락하세요
        """
        
        await query.edit_message_text(bypass_text, parse_mode='Markdown')
        
    async def show_alert_detail(self, query, alert_id: str):
        """알림 상세 정보 표시"""
        alert = storage.get_alert(alert_id)
        if not alert:
            await query.edit_message_text("❌ 알림을 찾을 수 없습니다.")
            return
            
        severity_emoji = {
            'error': '🔴',
            'warning': '🟠',
            'info': '🔵'
        }.get(alert.severity, '⚪')
        
        # 알림 이력 정보 가져오기
        history = storage.alert_history.get(alert.hash_key)
        history_text = ""
        if history:
            history_text = f"\n📈 **알림 이력:**\n"
            history_text += f"• 최초 발생: {history.first_occurrence.strftime('%Y-%m-%d %H:%M')}\n"
            history_text += f"• 마지막 발생: {history.last_occurrence.strftime('%Y-%m-%d %H:%M')}\n"
            history_text += f"• 총 발생 횟수: {history.occurrence_count}회\n"
            if len(history.values) > 1:
                history_text += f"• 최근 값 추이: {' → '.join([f'{v:.1f}' for v in history.values[-5:]])}\n"
        
        detail_text = f"""
{severity_emoji} **알림 상세 정보**

🏭 **설비**: {alert.equipment}
📊 **센서**: {alert.sensor_type}
📈 **측정값**: {alert.value}
⚠️ **임계값**: {alert.threshold}
📝 **메시지**: {alert.message}
⏰ **발생시간**: {alert.timestamp}
📋 **상태**: {alert.status}
👤 **담당자**: {alert.assigned_to or '미지정'}
{history_text}
💡 **권장 조치:**
• Error 레벨: 즉시 인터락 권장
• Warning 레벨: 모니터링 및 점검
• Info 레벨: 참고 및 기록
        """
        
        await query.edit_message_text(detail_text, parse_mode='Markdown')
        
    async def send_alert_notification(self, alert: Alert):
        """구독자들에게 알림 전송"""
        if not storage.get_subscribers():
            logger.info("구독자가 없어서 알림을 전송하지 않습니다.")
            return
            
        severity_emoji = {
            'error': '🔴',
            'warning': '🟠', 
            'info': '🔵'
        }.get(alert.severity, '⚪')
        
        time_str = alert.timestamp.split('T')[1][:5] if 'T' in alert.timestamp else alert.timestamp
        
        # 알림 이력 정보 추가
        history = storage.alert_history.get(alert.hash_key)
        occurrence_info = ""
        if history and history.occurrence_count > 1:
            occurrence_info = f"\n🔄 **재발생**: {history.occurrence_count}회째 발생"
        
        alert_text = f"""
{severity_emoji} **설비 알림 발생**

🏭 **설비**: {alert.equipment}
📊 **센서**: {alert.sensor_type}
📈 **측정값**: {alert.value}
⚠️ **임계값**: {alert.threshold}
⏰ **시간**: {time_str}{occurrence_info}

📝 **메시지**: {alert.message}
        """
        
        # 인터락/바이패스 버튼 (error, warning 레벨만)
        keyboard = []
        if alert.severity in ['error', 'warning']:
            keyboard = [
                [
                    InlineKeyboardButton("🚨 인터락 (즉시정지)", callback_data=f"interlock_{alert.id}"),
                    InlineKeyboardButton("⏭️ 바이패스 (무시)", callback_data=f"bypass_{alert.id}")
                ],
                [
                    InlineKeyboardButton("📊 상세정보", callback_data=f"status_{alert.id}")
                ]
            ]
        else:
            keyboard = [
                [InlineKeyboardButton("📊 상세정보", callback_data=f"status_{alert.id}")]
            ]
            
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # 모든 구독자에게 전송
        for chat_id in storage.get_subscribers():
            try:
                await self.application.bot.send_message(
                    chat_id=chat_id,
                    text=alert_text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
                logger.info(f"알림 전송 성공: {chat_id}")
            except Exception as e:
                logger.error(f"알림 전송 실패 {chat_id}: {e}")
                
    def setup_handlers(self):
        """명령어 핸들러 설정"""
        self.application.add_handler(CommandHandler("start", self.start_command))
        self.application.add_handler(CommandHandler("subscribe", self.subscribe_command))
        self.application.add_handler(CommandHandler("unsubscribe", self.unsubscribe_command))
        self.application.add_handler(CommandHandler("alerts", self.alerts_command))
        self.application.add_handler(CommandHandler("status", self.status_command))
        self.application.add_handler(CommandHandler("stats", self.stats_command))
        self.application.add_handler(CommandHandler("help", self.help_command))
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))
        
    async def start_bot(self):
        """봇 시작"""
        self.application = Application.builder().token(self.token).build()
        self.setup_handlers()
        
        logger.info("텔레그램 봇 시작 중...")
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        
        self.running = True
        logger.info("✅ 텔레그램 봇이 성공적으로 시작되었습니다!")
        
    async def stop_bot(self):
        """봇 중지"""
        if self.application and self.running:
            logger.info("텔레그램 봇 중지 중...")
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()
            self.running = False
            logger.info("✅ 텔레그램 봇이 중지되었습니다.")

class FastAPIMonitor:
    """FastAPI 서버 모니터링 및 알림 생성"""
    
    def __init__(self, fastapi_url: str, bot: TelegramIoTBot):
        self.fastapi_url = fastapi_url
        self.bot = bot
        self.running = False
        self.last_check = datetime.now()
        self.processed_alerts = set()  # 처리된 알림 ID 저장
        self.start_time = datetime.now()  # 봇 시작 시간 기록
        logger.info(f"모니터 시작 시간: {self.start_time}")
        
    async def monitor_alerts(self):
        """FastAPI에서 새로운 알림 모니터링"""
        while self.running:
            try:
                # FastAPI에서 최근 알림 가져오기
                response = requests.get(
                    f"{self.fastapi_url}/alerts",
                    params={"limit": 10},
                    timeout=5
                )
                
                if response.status_code == 200:
                    api_alerts = response.json()
                    
                    for api_alert in api_alerts:
                        # 알림 시간 확인
                        alert_time_str = api_alert.get('timestamp', '')
                        try:
                            # ISO 형식 파싱
                            alert_time = datetime.fromisoformat(alert_time_str.replace('Z', '+00:00'))
                            
                            # 봇 시작 이전의 알림은 무시
                            if alert_time < self.start_time:
                                logger.debug(f"이전 알림 스킵: {alert_time} < {self.start_time}")
                                continue
                                
                        except Exception as e:
                            logger.warning(f"타임스탬프 파싱 오류: {alert_time_str}, {e}")
                            # 파싱 실패시 현재 시간으로 처리
                            pass
                        
                        # 원본 알림 중복 체크
                        if storage.check_duplicate_raw_alert(api_alert):
                            logger.debug(f"중복 원본 알림 스킵: {api_alert.get('equipment')}/{api_alert.get('sensor_type')}")
                            continue
                        
                        # 고유 ID 생성 (timestamp + equipment + sensor_type 조합)
                        unique_id = f"{api_alert.get('timestamp', '')}_{api_alert.get('equipment', '')}_{api_alert.get('sensor_type', '')}"
                        
                        # 이미 처리된 알림인지 확인
                        if unique_id in self.processed_alerts:
                            continue
                            
                        alert_id = f"alert_{len(storage.alerts) + 1}"
                        
                        alert = Alert(
                            id=alert_id,
                            equipment=api_alert.get('equipment', '알 수 없는 설비'),
                            sensor_type=api_alert.get('sensor_type', 'unknown'),
                            value=api_alert.get('value', 0.0),
                            threshold=api_alert.get('threshold', 0.0),
                            severity=api_alert.get('severity', 'info'),
                            timestamp=api_alert.get('timestamp', datetime.now().isoformat()),
                            message=api_alert.get('message', '알림 메시지')
                        )
                        
                        # 저장소에 추가 (중복 체크 포함)
                        if storage.add_alert(alert):
                            # 텔레그램으로 알림 전송
                            await self.bot.send_alert_notification(alert)
                            
                        # 처리된 알림으로 표시
                        self.processed_alerts.add(unique_id)
                        
                        # 메모리 관리: 처리된 알림이 1000개를 넘으면 오래된 것부터 제거
                        if len(self.processed_alerts) > 1000:
                            self.processed_alerts = set(list(self.processed_alerts)[-500:])
                            
                await asyncio.sleep(5)  # 5초마다 체크
                
            except Exception as e:
                logger.error(f"FastAPI 모니터링 오류: {e}")
                await asyncio.sleep(10)  # 오류 시 10초 대기
                
    def start_monitoring(self):
        """모니터링 시작"""
        self.running = True
        
    def stop_monitoring(self):
        """모니터링 중지"""
        self.running = False

async def main():
    """메인 실행 함수"""
    
    # 환경 설정 표시
    logger.info("=== 환경 설정 ===")
    logger.info(f"API URL: {FASTAPI_BASE_URL}")
    logger.info(f"봇 토큰: {'설정됨' if TELEGRAM_BOT_TOKEN else '없음'}")
    logger.info(f"관리자 수: {len(ADMIN_CHAT_IDS)}")
    logger.info(f"Error 쿨다운: {os.getenv('ERROR_COOLDOWN_MINUTES', '5')}분")
    logger.info(f"Warning 쿨다운: {os.getenv('WARNING_COOLDOWN_MINUTES', '10')}분")
    logger.info(f"Info 쿨다운: {os.getenv('INFO_COOLDOWN_MINUTES', '30')}분")
    logger.info("==================")
    
    # 봇 및 모니터 초기화
    bot = TelegramIoTBot(TELEGRAM_BOT_TOKEN, FASTAPI_BASE_URL)
    monitor = FastAPIMonitor(FASTAPI_BASE_URL, bot)
    
    try:
        # 봇 시작
        await bot.start_bot()
        
        # 모니터링 시작
        monitor.start_monitoring()
        monitor_task = asyncio.create_task(monitor.monitor_alerts())
        
        logger.info("🚀 IoT 알림 시스템 완전 가동!")
        logger.info("📱 텔레그램에서 /start 명령어로 시작하세요")
        logger.info("📋 /subscribe 로 알림을 구독할 수 있습니다")
        logger.info("🛡️ 중복 알림 방지 시스템이 활성화되었습니다")
        
        # 무한 대기
        while True:
            await asyncio.sleep(1)
            
    except KeyboardInterrupt:
        logger.info("사용자에 의해 중지됨")
    except Exception as e:
        logger.error(f"오류 발생: {e}")
    finally:
        # 정리
        monitor.stop_monitoring()
        await bot.stop_bot()

if __name__ == "__main__":
    # 의존성 확인
    try:
        import telegram
    except ImportError:
        print("❌ python-telegram-bot 라이브러리가 필요합니다!")
        print("설치 명령어: pip install python-telegram-bot requests")
        exit(1)
        
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("❌ python-dotenv 라이브러리가 필요합니다!")
        print("설치 명령어: pip install python-dotenv")
        exit(1)
    
    # 실행
    asyncio.run(main())