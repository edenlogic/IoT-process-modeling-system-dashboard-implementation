#!/usr/bin/env python3
"""
음성 인식 AI 기능 테스트 스크립트
"""

import os
import sys
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

def test_voice_ai_import():
    """음성 AI 모듈 import 테스트"""
    try:
        from voice_ai import VoiceToText, GeminiAI
        print("✅ voice_ai 모듈 import 성공")
        return True
    except ImportError as e:
        print(f"❌ voice_ai 모듈 import 실패: {e}")
        return False

def test_google_cloud_credentials():
    """Google Cloud 인증 파일 테스트"""
    credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "C:/posco/gen-lang-client-0696719372-0f0c03eabd08.json")
    
    if os.path.exists(credentials_path):
        print(f"✅ Google Cloud 인증 파일 존재: {credentials_path}")
        return True
    else:
        print(f"❌ Google Cloud 인증 파일 없음: {credentials_path}")
        return False

def test_project_id():
    """프로젝트 ID 테스트"""
    project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "gen-lang-client-0696719372")
    print(f"📋 프로젝트 ID: {project_id}")
    return True

def test_voice_ai_initialization():
    """음성 AI 초기화 테스트"""
    try:
        from voice_ai import VoiceToText, GeminiAI
        
        project_id = os.getenv("GOOGLE_CLOUD_PROJECT_ID", "gen-lang-client-0696719372")
        credentials_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "C:/posco/gen-lang-client-0696719372-0f0c03eabd08.json")
        
        if not os.path.exists(credentials_path):
            print("❌ 인증 파일이 없어 초기화 테스트를 건너뜁니다.")
            return False
        
        # VoiceToText 초기화 테스트
        voice_to_text = VoiceToText(credentials_path, project_id)
        print("✅ VoiceToText 초기화 성공")
        
        # GeminiAI 초기화 테스트
        gemini_ai = GeminiAI(project_id, credentials_path)
        print("✅ GeminiAI 초기화 성공")
        
        return True
        
    except Exception as e:
        print(f"❌ 음성 AI 초기화 실패: {e}")
        return False

def main():
    """메인 테스트 함수"""
    print("🎤 음성 인식 AI 기능 테스트 시작\n")
    
    tests = [
        ("모듈 Import", test_voice_ai_import),
        ("Google Cloud 인증", test_google_cloud_credentials),
        ("프로젝트 ID", test_project_id),
        ("음성 AI 초기화", test_voice_ai_initialization),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 {test_name} 테스트...")
        if test_func():
            passed += 1
        print()
    
    print(f"\n📊 테스트 결과: {passed}/{total} 통과")
    
    if passed == total:
        print("🎉 모든 테스트 통과! 음성 인식 기능을 사용할 수 있습니다.")
    else:
        print("⚠️ 일부 테스트 실패. 설정을 확인해주세요.")
        print("\n🔧 해결 방법:")
        print("1. pip install google-cloud-speech google-cloud-aiplatform")
        print("2. Google Cloud 프로젝트 설정 확인")
        print("3. 서비스 계정 키 파일 경로 확인")
        print("4. Speech-to-Text API 및 Vertex AI API 활성화")

if __name__ == "__main__":
    main() 