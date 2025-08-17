import os
from google.cloud import speech
import streamlit as st
from google.oauth2 import service_account

class VoiceToText:
    def __init__(self, credentials_path, project_id):
        # 서비스 계정 인증
        credentials = service_account.Credentials.from_service_account_file(
            credentials_path
        )
        
        # Speech-to-Text 클라이언트 초기화
        self.client = speech.SpeechClient(credentials=credentials)
        self.project_id = project_id
    
    def transcribe_audio(self, audio_data):
        """음성 데이터를 텍스트로 변환"""
        try:
            # Google Speech-to-Text 설정
            audio = speech.RecognitionAudio(content=audio_data)
            config = speech.RecognitionConfig(
                # encoding 파라미터 제거 - 자동 감지하도록 함
                sample_rate_hertz=48000,  # Streamlit audio_input의 기본 샘플레이트
                language_code="ko-KR",
                enable_automatic_punctuation=True
            )
            
            # 음성 인식 수행
            response = self.client.recognize(config=config, audio=audio)
            
            
            # 결과 텍스트 추출
            transcript = ""
            for result in response.results:
                transcript += result.alternatives[0].transcript + " "
            
            return transcript.strip()
            
        except Exception as e:
            return f"오류 발생: {str(e)}"

class GeminiAI:
    def __init__(self, project_id, credentials_path=None):
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
            
        self.model = GenerativeModel("gemini-2.0-flash-001")
    
    def get_response(self, text_input, context=None):
        """Gemini AI 응답 생성"""
        try:
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
            
            답변:
            """
            
            response = self.model.generate_content(prompt)
            return response.text
            
        except Exception as e:
            return f"AI 응답 생성 중 오류: {str(e)}"