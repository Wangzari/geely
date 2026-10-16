# 车辆视频与定位服务

对外提供三个接口，内部包装吉利上游接口并做安全加固。上游 AK/SK 只留在服务端。

## 目录结构

```
geely-vehicle-service/
├── .env                # 实际配置（含密钥，不要提交）
├── .env.example        # 配置样例
├── requirements.txt
├── run.py              # 本地启动入口
└── app/
    ├── config.py       # 读取 .env
    ├── upstream.py     # 上游签名 + HTTP 调用
    ├── security.py     # API Key 鉴权 + 限流 + 车辆白名单
    ├── models.py       # 响应模型
    ├── routes.py       # 三个接口
    └── main.py         # FastAPI 装配
```

## 快速开始

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env      # 然后填写 T6_AK / T6_SK / SERVICE_API_KEYS

python run.py             # 或：uvicorn app.main:app --host 0.0.0.0 --port 8000
```

接口文档：<http://127.0.0.1:8000/docs>

## 接口

调用都需带请求头 `X-API-Key: <你的密钥>`。

### 1. 开启多路视频

```
POST /api/v1/vehicles/{vehicleCode}/video?channels=0,1,2,3
```

响应：

```json
{
  "vehicleCode": "LA9CABED8TW100164",
  "streams": [{"channel": 0, "direction": "前", "m3u8": "https://..."}],
  "failedChannels": [],
  "timestamp": 1690000000000
}
```

### 2. 实时车辆位置

```
GET /api/v1/vehicles/{vehicleCode}/location
```

响应：

```json
{
  "vehicleCode": "LA9CABED8TW100164",
  "longitude": 120.1, "latitude": 30.2, "azimuth": 90.0,
  "online": 1, "status": 0,
  "locationStatus": 0, "locationStatusText": "有效",
  "timestamp": 1690000000000
}
```

调用示例：

```bash
curl -H "X-API-Key: 你的密钥" \
  http://127.0.0.1:8000/api/v1/vehicles/LA9CABED8TW100164/location
```

### 3. 查询车辆详情

```
GET /api/v1/vehicles/{vehicleCode}/detail
```

响应（节选，枚举字段均附带 `*Text` 中文描述）：

```json
{
  "vehicleCode": "LA9CABED7TW100138",
  "vehicleId": "2061351919179677697",
  "licensePlateNumber": "T6-W100138",
  "vehicleModelName": "GL-T6",
  "status": 0, "statusText": "正常",
  "online": 1, "onlineText": "在线",
  "chargeType": 0, "chargeTypeText": "未充电",
  "residualFuel": 97.2,
  "programVersion": "20260410-v3.4.1-T6-j6m-release",
  "longitude": 116.99321, "latitude": 33.69521, "azimuth": 266.92999,
  "locationStatus": 2, "locationStatusText": "定位无效",
  "tireInfoList": [{"name": "LF", "positionDesc": "左前轮", "pressure": 4.046}],
  "timestamp": 1690000000000
}
```

说明：

- `vehicleId` / `siteId` / `executeTaskId` 为雪花 ID，已按字符串返回，避免前端精度丢失。
- 上游业务失败（如车辆不存在）返回 409，并透传上游真实原因。

## 安全说明

- **鉴权**：`X-API-Key`，常量时间比较。
- **车辆白名单**：只允许查询 `SERVICE_ALLOWED_VEHICLES` 中的车，越权返回 404。
- **限流**：按 Key 滑动窗口（`SERVICE_RATE_LIMIT` 次/分钟），超限 429。
- **上游密钥保密**：AK/SK 只在服务端，错误信息统一脱敏。
- **其它**：CORS、可信 Host、安全响应头、输入校验。

## 生产部署注意

1. **务必挂在 HTTPS 反向代理后**（Nginx/Caddy），否则 API Key 明文传输。
2. 当前限流是**进程内**的；若多 worker（`--workers >1`）部署，需换成 Redis 等共享存储。
