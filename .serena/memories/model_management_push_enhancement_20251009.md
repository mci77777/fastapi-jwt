WHY: 推送需支持覆盖/删除并保留多份备份以降低回滚风险。
HOW: 扩展AIConfigService实现备份轮转、覆盖判定、缺失清理，补充后端API参数传递并新增pytest用例。
DONE: tests/test_ai_config_service_push.py 通过，备份文件保留最近3份并更新文档说明。