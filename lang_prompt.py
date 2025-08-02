"""
POSCO IoT AI 서비스 - Gemini 버전 (개선됨)
"""
import os
import json
import random
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import logging
from dotenv import load_dotenv

# Google Gemini imports
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️ Google Gemini가 설치되지 않았습니다. pip install google-generativeai")

# 환경변수 로드
load_dotenv()

# 로거 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ===== 설정 섹션 =====
class AIConfig:
    """AI 관련 설정"""
    ENABLED = os.getenv("ENABLE_AI_FEATURES", "false").lower() == "true"
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    MODEL = os.getenv("GEMINI_MODEL", "gemini-pro")
    TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.3"))
    MAX_OUTPUT_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "500"))
    
    # 안전 설정
    SAFETY_SETTINGS = [
        {
            "category": "HARM_CATEGORY_HARASSMENT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        },
        {
            "category": "HARM_CATEGORY_HATE_SPEECH",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        },
        {
            "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        },
        {
            "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
            "threshold": "BLOCK_MEDIUM_AND_ABOVE"
        }
    ]
    
    # 캐시 설정
    CACHE_ENABLED = os.getenv("AI_CACHE_ENABLED", "true").lower() == "true"
    CACHE_TTL = int(os.getenv("AI_CACHE_TTL", "300"))  # 5분

# ===== Mock 데이터 섹션 =====
class MockData:
    """AI 서비스용 모의 데이터"""
    
    # 설비 특성
    EQUIPMENT_CHARACTERISTICS = {
        "프레스": {
            "critical_sensors": ["압력", "온도"],
            "maintenance_cycle": "30일",
            "risk_level": "높음",
            "typical_issues": ["오일 누유", "압력 저하", "과열"],
            "downtime_cost": "시간당 500만원"
        },
        "용접": {
            "critical_sensors": ["온도", "전류"],
            "maintenance_cycle": "45일",
            "risk_level": "중간",
            "typical_issues": ["전극 마모", "냉각수 부족", "전압 불안정"],
            "downtime_cost": "시간당 300만원"
        },
        "조립": {
            "critical_sensors": ["진동", "속도"],
            "maintenance_cycle": "60일",
            "risk_level": "낮음",
            "typical_issues": ["벨트 장력", "모터 과부하", "정렬 불량"],
            "downtime_cost": "시간당 200만원"
        },
        "검사": {
            "critical_sensors": ["카메라", "센서"],
            "maintenance_cycle": "90일",
            "risk_level": "낮음",
            "typical_issues": ["캘리브레이션", "렌즈 오염", "조명 불량"],
            "downtime_cost": "시간당 150만원"
        },
        "포장": {
            "critical_sensors": ["속도", "위치"],
            "maintenance_cycle": "45일",
            "risk_level": "낮음",
            "typical_issues": ["컨베이어 장력", "센서 정렬", "모터 과열"],
            "downtime_cost": "시간당 100만원"
        }
    }
    
    # 센서 트렌드 패턴
    SENSOR_TRENDS = {
        "급상승": "지난 30분간 {percent}% 상승, 가속도 증가 중",
        "점진상승": "지난 1시간 동안 서서히 {percent}% 상승",
        "불안정": "최근 30분간 ±{percent}% 범위에서 불규칙 변동",
        "급하락": "지난 30분간 {percent}% 하락, 급격한 감소",
        "정상": "지난 1시간 동안 안정적 유지 (±2% 이내)"
    }
    
    # 과거 사례
    HISTORICAL_CASES = [
        {
            "situation": "프레스기 온도 85도 초과",
            "actions": [
                {"action": "interlock", "result": "성공", "downtime": "2시간", "comment": "냉각 후 정상화"},
                {"action": "bypass", "result": "실패", "downtime": "8시간", "comment": "추가 손상으로 대형 정비"}
            ]
        },
        {
            "situation": "용접기 전류 불안정",
            "actions": [
                {"action": "bypass", "result": "성공", "downtime": "0시간", "comment": "자동 안정화됨"},
                {"action": "interlock", "result": "성공", "downtime": "1시간", "comment": "전극 교체 후 해결"}
            ]
        },
        {
            "situation": "조립기 진동 초과",
            "actions": [
                {"action": "interlock", "result": "성공", "downtime": "30분", "comment": "벨트 조정으로 해결"},
                {"action": "bypass", "result": "경고", "downtime": "0시간", "comment": "모니터링 강화 필요"}
            ]
        },
        {
            "situation": "검사기 센서 이상",
            "actions": [
                {"action": "interlock", "result": "성공", "downtime": "15분", "comment": "캘리브레이션으로 해결"},
                {"action": "bypass", "result": "실패", "downtime": "4시간", "comment": "불량품 대량 발생"}
            ]
        }
    ]

# ===== 프롬프트 템플릿 섹션 =====
class Prompts:
    """프롬프트 템플릿 관리"""
    
    ALERT_ANALYSIS = """당신은 포스코모빌리티 스마트팩토리의 IoT 전문가입니다.
현재 설비에서 이상 신호가 감지되었습니다. 즉시 취해야 할 조치를 추천하세요.

[현재 상황]
설비: {equipment}
센서: {sensor_type} 
측정값: {value} (임계값: {threshold} 초과)
센서 트렌드: {trend}

[설비 정보]
설비 타입: {equipment_type}
중요 센서: {critical_sensors}
일반적 문제: {typical_issues}
다운타임 비용: {downtime_cost}

[최근 이력]
- 24시간 내 알림: {alerts_24h}건
- 최근 주요 문제: {recent_issues}
- 마지막 정비: {last_maintenance}

[요구사항]
1. 인터락(즉시 정지) 또는 바이패스(일시 무시) 중 하나를 명확히 추천
2. 핵심 이유를 간단히 설명 (1-2문장)
3. 다음 형식으로 작성:
   "🚨 인터락 권장 - [이유]" 또는 "⏭️ 바이패스 가능 - [이유]"

현장 작업자가 즉시 이해할 수 있게 작성하세요."""

    ACTION_RECOMMENDATION = """당신은 20년 경력의 공장 운영 전문가입니다.
현재 설비 이상 상황에서 최적의 조치를 추천해야 합니다.

[현재 알림 상황]
설비: {equipment}
문제: {sensor_type} {value} (임계값 {threshold} 초과)
심각도: {severity}

[과거 유사 사례]
{similar_cases}

[현재 공장 상황]
- 전체 가동률: {factory_efficiency}
- 가동 중인 설비: {running_equipment}
- 현재 근무조: {shift}
- 설비 우선순위: {priority}

[선택 가능한 조치]
1. 인터락: 설비 즉시 정지
   - 장점: 안전 확보, 추가 손상 방지
   - 단점: 생산 중단, 다운타임 발생

2. 바이패스: 알림 일시 무시하고 계속 가동
   - 장점: 생산 지속, 다운타임 없음
   - 단점: 위험 가능성, 손상 확대 위험

정확히 아래 형식을 따라 작성하세요. 각 항목은 반드시 새 줄에서 시작하고, 콜론(:) 뒤에 내용을 작성하세요:

추천_조치: [인터락 또는 바이패스]
안전_분석: [현재 상황의 위험도와 즉시 조치 필요성을 1문장으로]
예상_결과: [조치 시 예상되는 결과와 소요 시간을 1문장으로]
과거_비교: [유사 사례와 비교한 분석을 1문장으로]

예시:
추천_조치: 인터락
안전_분석: 온도가 임계값을 20% 초과하여 설비 손상 위험이 높아 즉시 정지가 필요합니다
예상_결과: 설비 정지 후 15-20분 냉각 시간을 거쳐 정상 가동 가능합니다
과거_비교: 지난 3개월간 유사 상황 5건 중 4건이 인터락으로 2시간 내 해결되었습니다"""

# ===== 응답 파서 클래스 =====
class ResponseParser:
    """AI 응답을 안정적으로 파싱하는 헬퍼 클래스"""
    
    @staticmethod
    def parse_action_recommendation(content: str) -> dict:
        """조치 추천 응답 파싱"""
        # 기본값
        result = {
            "action": "interlock",  # 안전을 위한 기본값
            "safety_analysis": "",
            "expected_result": "",
            "historical_comparison": ""
        }
        
        # 정규식 패턴들
        patterns = {
            "action": [
                r"추천_조치\s*[:：]\s*(인터락|바이패스|interlock|bypass)",
                r"추천\s*조치\s*[:：]\s*(인터락|바이패스|interlock|bypass)",
                r"조치\s*[:：]\s*(인터락|바이패스|interlock|bypass)",
            ],
            "safety": [
                r"안전_분석\s*[:：]\s*(.+?)(?=예상_결과|과거_비교|$)",
                r"안전\s*분석\s*[:：]\s*(.+?)(?=예상\s*결과|과거\s*비교|$)",
            ],
            "result": [
                r"예상_결과\s*[:：]\s*(.+?)(?=과거_비교|$)",
                r"예상\s*결과\s*[:：]\s*(.+?)(?=과거\s*비교|$)",
            ],
            "history": [
                r"과거_비교\s*[:：]\s*(.+?)$",
                r"과거\s*비교\s*[:：]\s*(.+?)$",
            ]
        }
        
        # 전체 텍스트를 한 줄로 만들어 처리
        content_oneline = content.replace('\n', ' ').strip()
        
        # 각 패턴으로 시도
        for pattern in patterns["action"]:
            match = re.search(pattern, content_oneline, re.IGNORECASE)
            if match:
                action_text = match.group(1).lower()
                if "인터락" in action_text or "interlock" in action_text:
                    result["action"] = "interlock"
                elif "바이패스" in action_text or "bypass" in action_text:
                    result["action"] = "bypass"
                break
        
        # 안전 분석 파싱
        for pattern in patterns["safety"]:
            match = re.search(pattern, content_oneline, re.IGNORECASE | re.DOTALL)
            if match:
                result["safety_analysis"] = match.group(1).strip()
                break
        
        # 예상 결과 파싱
        for pattern in patterns["result"]:
            match = re.search(pattern, content_oneline, re.IGNORECASE | re.DOTALL)
            if match:
                result["expected_result"] = match.group(1).strip()
                break
        
        # 과거 비교 파싱
        for pattern in patterns["history"]:
            match = re.search(pattern, content_oneline, re.IGNORECASE | re.DOTALL)
            if match:
                result["historical_comparison"] = match.group(1).strip()
                break
        
        # 키워드 기반 백업 파싱
        if not result["action"]:
            if any(word in content.lower() for word in ["인터락", "interlock", "정지", "중단"]):
                result["action"] = "interlock"
            elif any(word in content.lower() for word in ["바이패스", "bypass", "계속", "무시"]):
                result["action"] = "bypass"
        
        logger.debug(f"파싱 결과: {result}")
        return result

# ===== 메인 AI 서비스 클래스 =====
class AIService:
    """통합 AI 서비스 - Gemini 버전"""
    
    def __init__(self):
        self.enabled = AIConfig.ENABLED and GEMINI_AVAILABLE
        self.model = None
        self.cache = {}  # 간단한 메모리 캐시
        self.parser = ResponseParser()
        
        if self.enabled:
            self._initialize_gemini()
        else:
            logger.warning("AI 기능이 비활성화되었습니다.")
    
    def _initialize_gemini(self):
        """Gemini 초기화"""
        try:
            genai.configure(api_key=AIConfig.GEMINI_API_KEY)
            
            # 모델 설정
            generation_config = {
                "temperature": AIConfig.TEMPERATURE,
                "top_p": 1,
                "top_k": 1,
                "max_output_tokens": AIConfig.MAX_OUTPUT_TOKENS,
            }
            
            self.model = genai.GenerativeModel(
                model_name=AIConfig.MODEL,
                generation_config=generation_config,
                safety_settings=AIConfig.SAFETY_SETTINGS
            )
            
            logger.info(f"Google Gemini 초기화 완료: {AIConfig.MODEL}")
            
        except Exception as e:
            logger.error(f"Gemini 초기화 실패: {e}")
            self.enabled = False
    
    def _get_cache_key(self, prefix: str, data: dict) -> str:
        """캐시 키 생성"""
        key_parts = [prefix]
        for k in sorted(['equipment', 'sensor_type', 'severity']):
            if k in data:
                key_parts.append(str(data[k]))
        return ":".join(key_parts)
    
    def _get_from_cache(self, key: str) -> Optional[str]:
        """캐시에서 가져오기"""
        if not AIConfig.CACHE_ENABLED:
            return None
        
        cached = self.cache.get(key)
        if cached and datetime.now() < cached['expires']:
            logger.info(f"캐시 히트: {key}")
            return cached['value']
        return None
    
    def _save_to_cache(self, key: str, value: str):
        """캐시에 저장"""
        if AIConfig.CACHE_ENABLED:
            self.cache[key] = {
                'value': value,
                'expires': datetime.now() + timedelta(seconds=AIConfig.CACHE_TTL)
            }
            logger.info(f"캐시 저장: {key}")
    
    def _clean_expired_cache(self):
        """만료된 캐시 정리"""
        now = datetime.now()
        expired_keys = [k for k, v in self.cache.items() if now > v['expires']]
        for key in expired_keys:
            del self.cache[key]
        if expired_keys:
            logger.info(f"캐시 정리: {len(expired_keys)}개 항목 삭제")
    
    def _generate_mock_context(self, alert_data: dict) -> dict:
        """Mock 데이터로 컨텍스트 생성"""
        equipment_type = alert_data['equipment'].split('_')[0]
        equipment_type_kr = {
            "press": "프레스", 
            "weld": "용접", 
            "assemble": "조립",
            "inspect": "검사",
            "pack": "포장"
        }.get(equipment_type, "기타")
        
        # 설비 특성
        characteristics = MockData.EQUIPMENT_CHARACTERISTICS.get(
            equipment_type_kr, 
            MockData.EQUIPMENT_CHARACTERISTICS["프레스"]
        )
        
        # 센서 트렌드 (측정값/임계값 비율에 따라)
        ratio = alert_data['value'] / alert_data['threshold']
        if ratio > 1.2:
            trend = MockData.SENSOR_TRENDS["급상승"].format(percent=random.randint(15, 30))
        elif ratio > 1.1:
            trend = MockData.SENSOR_TRENDS["점진상승"].format(percent=random.randint(5, 15))
        elif ratio < 0.8:
            trend = MockData.SENSOR_TRENDS["급하락"].format(percent=random.randint(10, 25))
        elif 0.9 < ratio < 1.1:
            trend = MockData.SENSOR_TRENDS["정상"]
        else:
            trend = MockData.SENSOR_TRENDS["불안정"].format(percent=random.randint(5, 15))
        
        # 최근 이력 (랜덤)
        recent_history = {
            "alerts_24h": random.randint(0, 5),
            "recent_issues": random.sample(
                ["온도 상승", "압력 이상", "진동 증가", "소음 발생", "전력 소비 증가"], 
                k=2
            ),
            "last_maintenance": (datetime.now() - timedelta(days=random.randint(5, 45))).strftime("%Y-%m-%d")
        }
        
        # 공장 현황 (랜덤)
        factory_status = {
            "efficiency": random.randint(85, 95),
            "running_equipment": f"{random.randint(12, 16)}/16",
            "shift": "주간" if 6 <= datetime.now().hour < 18 else "야간"
        }
        
        return {
            'equipment_type': equipment_type_kr,
            'characteristics': characteristics,
            'trend': trend,
            'recent_history': recent_history,
            'factory_status': factory_status
        }
    
    async def analyze_alert(self, alert_data: dict) -> str:
        """알림 분석 및 메시지 생성"""
        if not self.enabled:
            return self._get_fallback_message(alert_data)
        
        # 캐시 정리
        self._clean_expired_cache()
        
        # 캐시 확인
        cache_key = self._get_cache_key("alert", alert_data)
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        try:
            # 컨텍스트 생성
            context = self._generate_mock_context(alert_data)
            
            # 프롬프트 생성
            prompt = Prompts.ALERT_ANALYSIS.format(
                equipment=alert_data['equipment'],
                sensor_type=alert_data['sensor_type'],
                value=alert_data['value'],
                threshold=alert_data['threshold'],
                trend=context['trend'],
                equipment_type=context['equipment_type'],
                critical_sensors=", ".join(context['characteristics']['critical_sensors']),
                typical_issues=", ".join(context['characteristics']['typical_issues']),
                downtime_cost=context['characteristics']['downtime_cost'],
                alerts_24h=context['recent_history']['alerts_24h'],
                recent_issues=", ".join(context['recent_history']['recent_issues']),
                last_maintenance=context['recent_history']['last_maintenance']
            )
            
            # Gemini 호출
            response = self.model.generate_content(prompt)
            result = response.text.strip()
            
            # 응답 검증
            if len(result) < 10:
                raise ValueError("응답이 너무 짧습니다")
            
            # 캐시 저장
            self._save_to_cache(cache_key, result)
            
            logger.info(f"AI 알림 분석 완료: {alert_data['equipment']}")
            return result
            
        except Exception as e:
            logger.error(f"AI 알림 분석 실패: {e}")
            return self._get_fallback_message(alert_data)
    
    async def recommend_action(self, alert_data: dict) -> dict:
        """조치 추천"""
        if not self.enabled:
            return self._get_fallback_recommendation()
        
        try:
            # Mock 컨텍스트 생성
            context = self._generate_mock_context(alert_data)
            
            # 유사 사례 찾기
            relevant_cases = []
            equipment_type = alert_data['equipment'].split('_')[0]
            
            for case in MockData.HISTORICAL_CASES:
                if equipment_type in case['situation'].lower() or \
                   alert_data['sensor_type'] in case['situation']:
                    relevant_cases.append(case)
            
            if not relevant_cases:
                relevant_cases = random.sample(MockData.HISTORICAL_CASES, k=2)
            
            # 유사 사례 포맷팅
            cases_text = ""
            for i, case in enumerate(relevant_cases[:3], 1):
                cases_text += f"\n사례 {i}: {case['situation']}\n"
                for action in case['actions']:
                    cases_text += f"  - {action['action']}: {action['result']}, "
                    cases_text += f"다운타임 {action['downtime']}, {action['comment']}\n"
            
            # 프롬프트 생성
            prompt = Prompts.ACTION_RECOMMENDATION.format(
                equipment=alert_data['equipment'],
                sensor_type=alert_data['sensor_type'],
                value=alert_data['value'],
                threshold=alert_data['threshold'],
                severity=alert_data['severity'],
                similar_cases=cases_text,
                factory_efficiency=f"{context['factory_status']['efficiency']}%",
                running_equipment=context['factory_status']['running_equipment'],
                shift=context['factory_status']['shift'],
                priority="높음" if equipment_type in ["press", "weld"] else "중간"
            )
            
            # Gemini 호출
            response = self.model.generate_content(prompt)
            content = response.text.strip()
            
            # 응답 파싱
            parsed = self.parser.parse_action_recommendation(content)
            
            # 파싱 결과가 비어있으면 기본값 생성
            if not parsed["safety_analysis"]:
                ratio = alert_data['value'] / alert_data['threshold']
                if parsed["action"] == "interlock":
                    parsed["safety_analysis"] = f"{alert_data['sensor_type']} 측정값이 임계값을 {(ratio-1)*100:.0f}% 초과하여 즉시 정지가 필요합니다"
                else:
                    parsed["safety_analysis"] = f"{alert_data['sensor_type']} 수치가 경미하게 상승했으나 즉각적인 위험은 없습니다"
            
            if not parsed["expected_result"]:
                if parsed["action"] == "interlock":
                    parsed["expected_result"] = "설비 정지 후 10-30분 내 점검 완료 예상, 안전 확보 가능"
                else:
                    parsed["expected_result"] = "계속 모니터링하며 30분 내 자동 안정화 예상"
            
            if not parsed["historical_comparison"]:
                if parsed["action"] == "interlock":
                    parsed["historical_comparison"] = "과거 유사 상황에서 인터락 조치로 평균 2시간 내 정상화"
                else:
                    parsed["historical_comparison"] = "이전 3건의 유사 사례에서 바이패스 후 정상 복귀"
            
            # 신뢰도 계산
            confidence = 0.85
            if "즉시" in content or "긴급" in content or "심각" in content:
                confidence = 0.95
            elif "검토" in content or "모니터링" in content:
                confidence = 0.75
            
            return {
                "action": parsed["action"],
                "explanation": content,
                "safety_analysis": parsed["safety_analysis"],
                "expected_result": parsed["expected_result"],
                "historical_comparison": parsed["historical_comparison"],
                "confidence": confidence,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"AI 조치 추천 실패: {e}")
            return self._get_fallback_recommendation()
    
    def _get_fallback_message(self, alert_data: dict) -> str:
        """AI 실패 시 기본 메시지"""
        sensor_kr = {
            "temperature": "온도",
            "pressure": "압력",
            "vibration": "진동",
            "power": "전력"
        }.get(alert_data['sensor_type'], alert_data['sensor_type'])
        
        # 기본 추천 로직
        ratio = alert_data['value'] / alert_data['threshold']
        if ratio > 1.2:  # 20% 이상 초과
            return f"🚨 인터락 권장 - {sensor_kr} 심각 초과, 즉시 정지 필요"
        else:
            return f"⏭️ 바이패스 가능 - {sensor_kr} 경미한 이상, 모니터링 권장"
    
    def _get_fallback_recommendation(self) -> dict:
        """AI 실패 시 기본 추천"""
        return {
            "action": "interlock",
            "explanation": "안전을 위해 설비 정지를 권장합니다. AI 분석이 일시적으로 불가능하여 보수적인 접근을 추천합니다.",
            "safety_analysis": "AI 분석 불가로 안전을 우선시하여 설비 정지를 권장합니다",
            "expected_result": "설비 정지 후 수동 점검이 필요합니다",
            "historical_comparison": "과거 데이터 분석이 일시적으로 불가능합니다",
            "confidence": 0.5,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_status(self) -> dict:
        """AI 서비스 상태 확인"""
        return {
            "enabled": self.enabled,
            "model": AIConfig.MODEL if self.enabled else None,
            "cache_size": len(self.cache),
            "api_key_set": bool(AIConfig.GEMINI_API_KEY),
            "timestamp": datetime.now().isoformat()
        }

# ===== 싱글톤 인스턴스 =====
ai_service = AIService()

# ===== 헬퍼 함수들 (FastAPI에서 직접 호출용) =====
async def generate_alert_message(alert_data: dict) -> str:
    """알림 메시지 생성 (FastAPI용)"""
    return await ai_service.analyze_alert(alert_data)

async def get_action_recommendation(alert_data: dict) -> dict:
    """조치 추천 (FastAPI용)"""
    return await ai_service.recommend_action(alert_data)

def is_ai_enabled() -> bool:
    """AI 기능 활성화 여부"""
    return ai_service.enabled

def get_ai_status() -> dict:
    """AI 서비스 상태"""
    return ai_service.get_status()

