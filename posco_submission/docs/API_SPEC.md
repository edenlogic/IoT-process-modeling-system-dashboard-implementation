# API Spec

## Endpoints

### GET /health
- **200 OK**: `{"status":"ok"}`

### POST /predict/abnormal
- **Body**: `{"features":[...]}` # float list
- **200**: `{"score": float, "label": 0|1}`

### POST /predict/hydraulic
- **Body**: (see `ai_model/hydraulic_rf/추론입력포맷예시.json`)
- **200**: `{"rul": float, "class": "OK|WARN|FAIL", "prob": {...}}`

### GET /alerts/recent
- **200**: `[{"ts": "...", "type": "...", "message": "..."}]`

## Errors

- **400**: ValidationError
- **500**: InferenceError
