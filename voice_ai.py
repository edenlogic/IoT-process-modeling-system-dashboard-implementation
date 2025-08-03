import os
from google.cloud import speech
import streamlit as st
from google.oauth2 import service_account

class VoiceToText:
    def __init__(self, credentials_path, project_id):
        try:
            # 서비스 계정 인증
            credentials = service_account.Credentials.from_service_account_file(
                credentials_path
            )
            
            # Speech-to-Text 클라이언트 초기화
            self.client = speech.SpeechClient(credentials=credentials)
            self.project_id = project_id
            print(f"VoiceToText 초기화 성공: {project_id}")
        except Exception as e:
            print(f"VoiceToText 초기화 실패: {e}")
            raise e
    
    def transcribe_audio(self, audio_data):
        """음성 데이터를 텍스트로 변환"""
        try:
            if not audio_data:
                return "오류 발생: 음성 데이터가 없습니다."
            
            # Google Speech-to-Text 설정
            audio = speech.RecognitionAudio(content=audio_data)
            config = speech.RecognitionConfig(
                # encoding 파라미터 제거 - 자동 감지하도록 함
                sample_rate_hertz=48000,  # Streamlit audio_input의 기본 샘플레이트
                language_code="ko-KR",
                enable_automatic_punctuation=True,
                enable_word_time_offsets=False,
                enable_word_confidence=True
            )
            
            # 음성 인식 수행
            response = self.client.recognize(config=config, audio=audio)
            
            # 결과 텍스트 추출
            transcript = ""
            for result in response.results:
                if result.alternatives:
                    transcript += result.alternatives[0].transcript + " "
            
            if not transcript.strip():
                return "오류 발생: 음성을 인식할 수 없습니다. 다시 시도해주세요."
            
            return transcript.strip()
            
        except Exception as e:
            error_msg = f"오류 발생: {str(e)}"
            print(f"음성 인식 오류: {e}")
            return error_msg

class GeminiAI:
    def __init__(self, project_id, credentials_path=None):
        try:
            # 환경변수에서 AI 설정 로드
            import os
            from dotenv import load_dotenv
            load_dotenv()
            
            # AI 기능 활성화 확인
            enable_ai = os.getenv("ENABLE_AI_FEATURES", "false").lower() == "true"
            if not enable_ai:
                raise Exception("AI 기능이 비활성화되어 있습니다.")
            
            # Vertex AI 초기화
            import vertexai
            from vertexai.generative_models import GenerativeModel
            from google.oauth2 import service_account
            
            # 인증 정보 설정
            if credentials_path:
                credentials = service_account.Credentials.from_service_account_file(
                    credentials_path
                )
                vertexai.init(project=project_id, location='us-central1', credentials=credentials)
            else:
                vertexai.init(project=project_id, location='us-central1')
            
            # 모델 설정 (환경변수에서 로드)
            model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
            self.model = GenerativeModel(model_name)
            print(f"GeminiAI 초기화 성공: {project_id}, 모델: {model_name}")
        except Exception as e:
            print(f"GeminiAI 초기화 실패: {e}")
            raise e
    
    def get_response(self, text_input, context=None):
        """Gemini AI 응답 생성"""
        try:
            if not text_input or not text_input.strip():
                return "질문을 입력해주세요."
            
            # 환경변수에서 설정 로드
            import os
            temperature = float(os.getenv("LLM_TEMPERATURE", "0.3"))
            max_tokens = int(os.getenv("LLM_MAX_TOKENS", "500"))
            
            # 대시보드 맥락을 포함한 프롬프트
            prompt = f"""
            당신은 POSCO MOBILITY IoT 대시보드의 AI 어시스턴트입니다.
            현재 대시보드의 실시간 데이터를 보고 분석하여 답변해야 합니다.
            
            {context if context else ""}
            
            사용자 질문: {text_input}
            
            답변 규칙:
            1. 실제 대시보드의 현재 수치를 정확히 언급하세요
            2. 데이터를 분석하여 인사이트를 제공하세요
            3. 이상 징후가 있다면 반드시 언급하세요
            4. 구체적인 숫자와 퍼센트를 사용하세요
            5. 필요시 권장 조치사항을 제안하세요
            6. 한국어로 자연스럽게 답변하세요
            7. 전문적이면서도 이해하기 쉽게 설명하세요
            
            답변:
            """
            
            # 생성 설정 적용
            generation_config = {
                "temperature": temperature,
                "max_output_tokens": max_tokens,
            }
            
            response = self.model.generate_content(prompt, generation_config=generation_config)
            return response.text
            
        except Exception as e:
            error_msg = f"AI 응답 생성 중 오류: {str(e)}"
            print(f"Gemini AI 응답 생성 오류: {e}")
            return error_msg