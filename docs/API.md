# API (V0.1)

- `GET /`
  - 返回应用基本信息。

- `GET /health`
  - 返回运行状态、数据库连通信息。

- `GET /ready`
  - 应用可对外服务时返回 `200`；数据库不可用时返回 `503`。

- `GET /api/v1/health`
  - 与 `/health` 一致，供前端消费。

响应示例：

```json
{
  "status": "healthy",
  "app_name": "Global News",
  "app_version": "0.1.2",
  "environment": "development",
  "database_connected": true,
  "checked_at": "2026-09-07T00:00:00+00:00"
}
```
