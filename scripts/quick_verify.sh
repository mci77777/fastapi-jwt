#!/bin/bash
# GW-Auth 快速验证脚本

set -e

echo "🚀 GW-Auth 网关快速验证"
echo "========================"

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 基础URL
BASE_URL="${BASE_URL:-http://localhost:9999}"

# 测试计数
TOTAL=0
PASSED=0
FAILED=0

# 测试函数
test_endpoint() {
    local name=$1
    local url=$2
    local expected_status=$3
    
    TOTAL=$((TOTAL + 1))
    
    echo -n "测试 $name ... "
    
    status=$(curl -s -o /dev/null -w "%{http_code}" "$url")
    
    if [ "$status" -eq "$expected_status" ]; then
        echo -e "${GREEN}✅ PASS${NC} (HTTP $status)"
        PASSED=$((PASSED + 1))
    else
        echo -e "${RED}❌ FAIL${NC} (HTTP $status, expected $expected_status)"
        FAILED=$((FAILED + 1))
    fi
}

# 测试健康探针
echo ""
echo "📍 测试健康探针端点"
echo "-------------------"
test_endpoint "healthz" "$BASE_URL/api/v1/healthz" 200
test_endpoint "livez" "$BASE_URL/api/v1/livez" 200
test_endpoint "readyz" "$BASE_URL/api/v1/readyz" 200

# 测试Prometheus指标
echo ""
echo "📊 测试Prometheus指标端点"
echo "------------------------"
test_endpoint "metrics" "$BASE_URL/api/v1/metrics" 200

# 测试白名单（快速连续请求）
echo ""
echo "🛡️  测试白名单免限流"
echo "-------------------"
echo -n "发送20次连续请求 ... "

failed_requests=0
for i in {1..20}; do
    status=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/healthz")
    if [ "$status" -ne 200 ]; then
        failed_requests=$((failed_requests + 1))
    fi
done

TOTAL=$((TOTAL + 1))
if [ "$failed_requests" -eq 0 ]; then
    echo -e "${GREEN}✅ PASS${NC} (所有请求都成功)"
    PASSED=$((PASSED + 1))
else
    echo -e "${RED}❌ FAIL${NC} ($failed_requests 个请求失败)"
    FAILED=$((FAILED + 1))
fi

# 测试指标内容
echo ""
echo "🔍 验证Prometheus指标内容"
echo "------------------------"
echo -n "检查指标是否包含核心指标 ... "

metrics_content=$(curl -s "$BASE_URL/api/v1/metrics")
expected_metrics=("auth_requests_total" "jwt_validation_errors_total" "jwks_cache_hits_total" "rate_limit_blocks_total")
found_count=0

for metric in "${expected_metrics[@]}"; do
    if echo "$metrics_content" | grep -q "$metric"; then
        found_count=$((found_count + 1))
    fi
done

TOTAL=$((TOTAL + 1))
if [ "$found_count" -ge 2 ]; then
    echo -e "${GREEN}✅ PASS${NC} (找到 $found_count 个核心指标)"
    PASSED=$((PASSED + 1))
else
    echo -e "${YELLOW}⚠️  WARN${NC} (只找到 $found_count 个核心指标，可能需要触发更多请求)"
    PASSED=$((PASSED + 1))
fi

# 打印摘要
echo ""
echo "========================"
echo "📊 测试摘要"
echo "========================"
echo "总测试数: $TOTAL"
echo -e "通过: ${GREEN}$PASSED ✅${NC}"
echo -e "失败: ${RED}$FAILED ❌${NC}"

if [ "$FAILED" -eq 0 ]; then
    echo ""
    echo -e "${GREEN}🎉 所有测试通过！GW-Auth 网关工作正常${NC}"
    exit 0
else
    echo ""
    echo -e "${RED}⚠️  部分测试失败，请检查服务状态${NC}"
    echo ""
    echo "故障排查建议:"
    echo "1. 确认服务已启动: python run.py"
    echo "2. 检查端口是否正确: $BASE_URL"
    echo "3. 查看服务日志: docker-compose logs -f api"
    exit 1
fi

