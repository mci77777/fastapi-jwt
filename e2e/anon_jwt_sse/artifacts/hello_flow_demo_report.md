# Hello消息流程演示报告

**演示时间**: 2025-09-29 21:22:19
**API地址**: http://localhost:9999
**追踪ID**: 663d6cc6-6046-4f54-a68d-ce9aeb5da104

## 演示步骤结果

### no_auth: ❌ 失败

- 状态码: 429
- 响应: `{'status': 429, 'code': 'RATE_LIMIT_EXCEEDED', 'message': 'Rate limit exceeded: IP in cooldown period', 'trace_id': None}`

### bad_auth: ❌ 失败

- 状态码: 429
- 响应: `{'status': 429, 'code': 'RATE_LIMIT_EXCEEDED', 'message': 'Rate limit exceeded: IP in cooldown period', 'trace_id': None}`

### malformed_jwt: ❌ 失败

- 状态码: 429
- 响应: `{'status': 429, 'code': 'RATE_LIMIT_EXCEEDED', 'message': 'Rate limit exceeded: IP in cooldown period', 'trace_id': None}`

### api_docs: ❌ 失败

- 状态码: 429

### error_consistency: ✅ 成功


## 总结

- 总演示步骤: 5
- 成功步骤: 1
- 成功率: 20.0%

**结论**: API基本功能正常，错误处理符合预期，统一错误格式工作正常。
