# ===================================================================
# 1. model.py - 모델 구조 정의 (서빙용)
# ===================================================================

import torch
import torch.nn as nn

class LSTMModel(nn.Module):
    """
    기계 고장 진단용 LSTM 모델
    
    사용법:
    model = LSTMModel(input_dim=4, hidden_dim=128, num_layers=2, output_dim=5, dropout_rate=0.5)
    model.load_state_dict(torch.load("model.pth"))
    model.eval()
    output = model(input_tensor)
    """
    def __init__(self, input_dim, hidden_dim, num_layers, output_dim, dropout_rate):
        super(LSTMModel, self).__init__()
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers

        self.lstm = nn.LSTM(
            input_dim, 
            hidden_dim, 
            num_layers, 
            batch_first=True, 
            dropout=dropout_rate if num_layers > 1 else 0
        )
        self.fc = nn.Linear(hidden_dim, output_dim)

    def forward(self, x):
        # x shape: (batch_size, sequence_length, input_dim)
        batch_size = x.size(0)
        
        # 초기 은닉 상태 및 셀 상태
        h0 = torch.zeros(self.num_layers, batch_size, self.hidden_dim).to(x.device)
        c0 = torch.zeros(self.num_layers, batch_size, self.hidden_dim).to(x.device)

        # LSTM forward
        lstm_out, _ = self.lstm(x, (h0, c0))
        
        # 마지막 타임스텝의 출력 사용
        out = self.fc(lstm_out[:, -1, :])
        
        return out


# ===================================================================
# 2. predict.py - 서빙용 추론 클래스
# ===================================================================

import torch
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler
import joblib

class FaultPredictor:
    """
    기계 고장 진단 예측기 - 서빙용
    
    초기화:
    predictor = FaultPredictor()
    predictor.load_model("model.pth", "scaler.pkl")
    
    예측:
    result = predictor.predict(sensor_data)
    """
    
    def __init__(self):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model = None
        self.scaler = None
        
        # 클래스 정보
        self.class_names = [
            'normal', 
            'bearing_fault', 
            'roll_misalignment', 
            'motor_overload', 
            'lubricant_shortage'
        ]
        
        self.class_descriptions = {
            'normal': '정상',
            'bearing_fault': '베어링 고장',
            'roll_misalignment': '롤 정렬 불량',
            'motor_overload': '모터 과부하',
            'lubricant_shortage': '윤활유 부족'
        }
    

    def load_model(self, model_path, scaler_path=None):
        """
        모델과 스케일러 로드
        
        Args:
            model_path (str): 모델 가중치 파일 경로 (.pth)
            scaler_path (str, optional): 스케일러 파일 경로 (.pkl)
        """
        # 1. 모델 구조 정의
        self.model = LSTMModel(
            input_dim=4,
            hidden_dim=128,
            num_layers=2,
            output_dim=5,
            dropout_rate=0.5
        )
        
        # 2. 가중치 로드
        self.model.load_state_dict(torch.load(model_path, map_location=self.device))
        self.model.to(self.device)
        
        # 3. 추론 모드 설정
        self.model.eval()
        
        # 4. 스케일러 로드 (있는 경우)
        if scaler_path:
            self.scaler = joblib.load(scaler_path)
        
        print(f"✅ 모델 로드 완료 (Device: {self.device})")
    
    def preprocess_data(self, data):
        """
        입력 데이터 전처리
        
        Args:
            data: numpy array, pandas DataFrame, 또는 list
                  Shape: (sequence_length, 4) 또는 (batch_size, sequence_length, 4)
        
        Returns:
            torch.Tensor: (batch_size, sequence_length, 4)
        """
        # DataFrame을 numpy로 변환
        if isinstance(data, pd.DataFrame):
            data = data.values
        elif isinstance(data, list):
            data = np.array(data)
        
        # 2D → 3D (배치 차원 추가)
        if len(data.shape) == 2:
            data = data[np.newaxis, :]  # (1, seq_len, features)
        
        # 정규화 (스케일러가 있는 경우)
        if self.scaler is not None:
            batch_size, seq_len, n_features = data.shape
            data_2d = data.reshape(-1, n_features)
            data_scaled = self.scaler.transform(data_2d)
            data = data_scaled.reshape(batch_size, seq_len, n_features)
        
        # 텐서로 변환
        tensor = torch.FloatTensor(data).to(self.device)
        return tensor
    
    def predict(self, data, temperature_scaling=1.0):
        """
        고장 진단 예측
        
        Args:
            data: 센서 데이터 (sequence_length, 4) 또는 (batch_size, sequence_length, 4)
            temperature_scaling (float): 확률 조정 파라미터
        
        Returns:
            dict: 예측 결과
        """
        if self.model is None:
            raise RuntimeError("모델이 로드되지 않았습니다. load_model()을 먼저 호출하세요.")
        
        # 추론 모드
        with torch.no_grad():
            # 전처리
            input_tensor = self.preprocess_data(data)
            
            # 모델 추론
            output = self.model(input_tensor)
            
            # Temperature scaling 적용
            scaled_output = output / temperature_scaling
            probabilities = torch.softmax(scaled_output, dim=1)
            
            # CPU로 이동 및 numpy 변환
            probs_np = probabilities.cpu().numpy()
            
            # 배치 처리 (여러 시퀀스인 경우)
            if probs_np.shape[0] == 1:
                # 단일 시퀀스
                probs = probs_np[0]
            
                
                predicted_class = int(np.argmax(probs))
                
                result = {
                    'predicted_class': predicted_class,
                    'predicted_class_name': self.class_names[predicted_class],
                    'predicted_class_description': self.class_descriptions[self.class_names[predicted_class]],
                    'confidence': float(np.max(probs)),
                    'is_normal': predicted_class == 0,
                    'probabilities': {
                        name: float(prob) 
                        for name, prob in zip(self.class_names, probs)
                    },

                }
            else:
                # 배치 처리
                results = []
                for i in range(probs_np.shape[0]):
                    probs = probs_np[i]

                    predicted_class = int(np.argmax(probs))
                    
                    results.append({
                        'predicted_class': predicted_class,
                        'predicted_class_name': self.class_names[predicted_class],
                        'confidence': float(np.max(probs)),
                        'is_normal': predicted_class == 0,
                        'probabilities': {
                            name: float(prob) 
                            for name, prob in zip(self.class_names, probs)
                        }
                    })
                result = {'batch_results': results}
        
        return result

    def determine_alert_level(self, probabilities):
        """
        확률 딕셔너리를 받아서 경고 레벨 결정
        
        Args:
            probabilities: {
                'normal': 0.65,
                'bearing_fault': 0.20,
                'roll_misalignment': 0.10,
                'motor_overload': 0.03,
                'lubricant_shortage': 0.02
            }
        
        Returns:
            dict: {
                'alert_level': '정상' | '모니터링 필요' | '점검 필요',
                'alert_color': 'green' | 'yellow' | 'red',
                'recommended_action': '구체적인 조치사항'
            }
        """
        
        # 확률 값들 추출
        normal_prob = probabilities.get('normal', 0.0)
        
        # 고장 확률들 합계
        fault_probs = {k: v for k, v in probabilities.items() if k != 'normal'}
        total_fault_prob = sum(fault_probs.values())
        
        # 가장 높은 고장 확률
        if fault_probs:
            max_fault_type = max(fault_probs, key=fault_probs.get)
            max_fault_prob = fault_probs[max_fault_type]
        else:
            max_fault_type = None
            max_fault_prob = 0.0
        
        # 고장 유형 한글명
        fault_korean = {
            'bearing_fault': '베어링 고장',
            'roll_misalignment': '롤 정렬 불량',
            'motor_overload': '모터 과부하',
            'lubricant_shortage': '윤활유 부족'
        }
        
        # 🎯 경고 레벨 결정
        if normal_prob >= 0.8:
            # 정상 확률 80% 이상
            return {
                'alert_level': '정상',
                'alert_color': 'green',
                'recommended_action': '정상 운영 계속'
            }
        
        elif total_fault_prob >= 0.7 or max_fault_prob >= 0.7:
            # 고장 확률 합계 70% 이상 OR 특정 고장 70% 이상
            fault_name = fault_korean.get(max_fault_type, '고장')
            return {
                'alert_level': '점검 필요',
                'alert_color': 'red',
                'recommended_action': f'즉시 점검 필요 ({fault_name} 가능성 높음)'
            }
        
        else:
            # 나머지 모든 경우
            if max_fault_prob >= 0.3:
                fault_name = fault_korean.get(max_fault_type, '고장')
                action = f'주의 관찰 ({fault_name} 의심)'
            else:
                action = '센서 데이터 지속 모니터링'
                
            return {
                'alert_level': '모니터링 필요',
                'alert_color': 'yellow',
                'recommended_action': action
            }


# ===================================================================
# 3. 사용 예시 
# ===================================================================

if __name__ == "__main__":
    
    # Step 1: 초기화
    predictor = FaultPredictor()
    
    # Step 2: 모델 로드
    predictor.load_model(
        model_path="trained_model.pth",
        scaler_path="scaler.pkl"  # 없으면 None
    )
    
    # Step 3: 예측 실행
    sensor_data = np.random.randn(60, 4)  # 실제로는 실시간 센서 데이터
    result = predictor.predict(sensor_data)
    
    print("=== 예측 결과 ===")
    print(f"예측 클래스: {result['predicted_class_description']}")
    print(f"신뢰도: {result['confidence']:.2%}")
    print(f"정상 여부: {'정상' if result['is_normal'] else '이상'}")
    
    '''배치 예측 (여러 시퀀스 동시 처리)
    batch_data = np.random.randn(5, 60, 4)  # 5개 시퀀스
    batch_result = predictor.predict(batch_data)
    
    print("\n=== 배치 예측 결과 ===")
    for i, res in enumerate(batch_result['batch_results']):
        print(f"시퀀스 {i+1}: {res['predicted_class_name']} (신뢰도: {res['confidence']:.2%})")
    '''

    #확률이 극단적일 때 Temperature Scaling
    if result['confidence'] > 0.95:
        print("\n=== Temperature Scaling 적용 ===")
        smooth_result = predictor.predict(sensor_data, temperature_scaling=2.0)
        print(f"조정된 신뢰도: {smooth_result['confidence']:.2%}")



    # 간단한 경고
    result = predictor.predict(sensor_data)

    # 경고 레벨 계산 (이것만 추가하면 됨!)
    alert = predictor.determine_alert_level(result['probabilities'])

    # 사용
    print(f"상태: {alert['alert_level']}")
    print(f"조치: {alert['recommended_action']}")

# ===================================================================
# 4. 설치 및 사용 가이드
# ===================================================================

"""
🚀 설치 및 사용 가이드

1. 필요한 파일:
   - trained_model.pth  (모델 가중치)
   - scaler.pkl         (정규화 스케일러, 선택사항)
   - model.py           (이 파일)

2. 라이브러리 설치:
   pip install torch scikit-learn numpy pandas joblib

3. 기본 사용법:
   ```python
   from model import FaultPredictor
   
   # 초기화 및 모델 로드
   predictor = FaultPredictor()
   predictor.load_model("trained_model.pth", "scaler.pkl")
   
   # 예측 (센서 데이터: 60개 타임스텝 x 4개 센서)
   result = predictor.predict(sensor_data)
   print(result['predicted_class_name'])  # 예: 'bearing_fault'
   print(result['confidence'])            # 예: 0.85
   ```

4. 주의사항:
   - 입력 데이터 형태: (60, 4) 또는 (batch_size, 60, 4)
   - 센서 순서: [Temperature, Machine Speed, Vibration Level, Energy Consumption]
   - GPU 있으면 자동 사용, 없으면 CPU 사용
"""