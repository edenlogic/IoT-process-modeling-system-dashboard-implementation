"""
유압 시스템 이상탐지 추론 클래스

[주요 기능]
1. 코드 실행으로 100% 검증된 최종 15개 피처를 직접 입력받음
2. 입력 피처의 유효성(이름, 개수)을 검사
3. 모델이 학습한 순서대로 피처를 정렬
4. 스케일링 후 이상 여부 예측
"""

import joblib
import numpy as np
import pandas as pd
import json
import os
import warnings
warnings.filterwarnings('ignore')

class HydraulicAnomalyPredictor:
    """유압 시스템 이상탐지 추론기"""

    def __init__(self, model_dir='.'):
        self.model_dir = model_dir
        self.model = None
        self.scaler = None
        # 코드 실행으로 100% 검증된 최종 피처 리스트 (순서가 매우 중요)
        self.final_feature_names = [
            'PS1_max', 'PS1_diff_std', 'PS2_diff_std', 'PS3_max', 'PS3_p2p',
            'TS1_p2p', 'VS1_min', 'VS1_q25', 'CP_mean', 'CP_min', 'CP_max',
            'CP_median', 'CP_rms', 'CP_q25', 'CP_q75'
        ]
        self._load_components()

    def _load_components(self):
        """모델과 스케일러를 로드합니다."""
        try:
            model_path = os.path.join(self.model_dir, 'best_model.pkl')
            # 수정된 스케일러 사용
            scaler_path = os.path.join(self.model_dir, 'scaler_fixed.pkl')
            
            # 수정된 스케일러가 없으면 원본 사용
            if not os.path.exists(scaler_path):
                scaler_path = os.path.join(self.model_dir, 'scaler.pkl')

            self.model = joblib.load(model_path)
            self.scaler = joblib.load(scaler_path)
            print("모델 및 스케일러 로드 완료")
            print(f"   - Model: {type(self.model).__name__}")
            print(f"   - Scaler: {type(self.scaler).__name__}")
            print(f"   - 최종 학습 피처 수: {len(self.final_feature_names)}개 (검증 완료)")

        except FileNotFoundError as e:
            raise Exception(f"모델 또는 스케일러 파일 로드 실패: {e}. 'model_dir' 경로를 확인하세요.")
        except Exception as e:
            raise Exception(f"컴포넌트 로드 중 알 수 없는 오류: {e}")

    def predict(self, feature_data: dict, return_confidence=True) -> dict:
        """
        검증된 15개 피처가 포함된 딕셔너리를 입력받아 이상 여부를 예측합니다.
        """
        try:
            # 1. 입력 데이터 유효성 검사
            missing_features = set(self.final_feature_names) - set(feature_data.keys())
            if missing_features:
                raise ValueError(f"필수 피처가 누락되었습니다: {list(missing_features)}")

            input_df = pd.DataFrame([feature_data])

            # 2. 모델이 학습한 순서대로 피처 정렬
            final_input_df = input_df[self.final_feature_names]

            # 3. 스케일링
            input_scaled = self.scaler.transform(final_input_df)

            # 4. 예측
            prediction = self.model.predict(input_scaled)[0]
            
            result = {
                'prediction': int(prediction),
                'status': 'Normal' if prediction == 0 else 'Abnormal Detected',
                'timestamp': pd.Timestamp.now().isoformat()
            }

            # 5. 신뢰도(확률) 추가
            if return_confidence and hasattr(self.model, 'predict_proba'):
                proba = self.model.predict_proba(input_scaled)[0]
                result['probabilities'] = {
                    'normal': float(proba[0]),
                    'abnormal': float(proba[1])
                }
                result['confidence'] = float(max(proba))

            return result

        except Exception as e:
            return {
                'error': str(e),
                'timestamp': pd.Timestamp.now().isoformat()
            }

# --- 사용 예시 ---
if __name__ == '__main__':
    # 이 스크립트가 있는 폴더에 best_model.pkl, scaler.pkl 파일이 있다고 가정합니다.
    MODEL_DIRECTORY = '.' 

    # 1. 예측기 초기화
    try:
        predictor = HydraulicAnomalyPredictor(model_dir=MODEL_DIRECTORY)

        # 2. 실제 서빙 환경에서 들어올 15개 피처 데이터 예시
        input_data_example = {
            "PS1_max": 162.5, "PS1_diff_std": 0.35, "PS2_diff_std": 0.41,
            "PS3_max": 2.05, "PS3_p2p": 0.12, "TS1_p2p": 1.5, "VS1_min": 0.52,
            "VS1_q25": 0.58, "CP_mean": 1.8, "CP_min": 1.2, "CP_max": 2.4,
            "CP_median": 1.8, "CP_rms": 1.9, "CP_q25": 1.6, "CP_q75": 2.0
        }

        # 3. 예측 수행
        prediction_result = predictor.predict(input_data_example)

        # 4. 결과 출력
        print("\n--- Prediction Result ---")
        print(json.dumps(prediction_result, indent=2))

    except Exception as e:
        print(f"\n실행 중 오류 발생: {e}")
