#!/usr/bin/env bash
# Vue 代码检查脚本 - 防止 JSX 语法混入和反模式检测
# 使用方法: ./scripts/check-vue-syntax.sh [directory]

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 默认检查目录
TARGET_DIR="${1:-web/src}"
ERRORS_FOUND=0

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Vue 3 代码语法检查${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "检查目录: $TARGET_DIR"
echo ""

# 创建临时文件存储结果
TEMP_FILE=$(mktemp)
trap "rm -f $TEMP_FILE" EXIT

# ========================================
# 检查 1: JSX 语法混入检查
# ========================================
echo -e "${BLUE}[检查 1/7] JSX 语法混入检测${NC}"

# 检查 className 属性
echo "  检查 className 属性..."
if grep -rn "className=" "$TARGET_DIR" --include="*.vue" > "$TEMP_FILE" 2>/dev/null; then
    echo -e "${RED}  ❌ 发现 className 属性（应使用 class 或 :class）:${NC}"
    cat "$TEMP_FILE"
    ERRORS_FOUND=$((ERRORS_FOUND + 1))
else
    echo -e "${GREEN}  ✅ 未发现 className 属性${NC}"
fi

# 检查 JSX 事件绑定
echo "  检查 JSX 事件绑定..."
if grep -rn "onClick=\|onUpdate\|onChange=\|onInput=" "$TARGET_DIR" --include="*.vue" | grep -v "// " | grep -v "/\*" > "$TEMP_FILE" 2>/dev/null; then
    echo -e "${RED}  ❌ 发现 JSX 事件绑定（应使用 @click, @update 等）:${NC}"
    cat "$TEMP_FILE"
    ERRORS_FOUND=$((ERRORS_FOUND + 1))
else
    echo -e "${GREEN}  ✅ 未发现 JSX 事件绑定${NC}"
fi

# 检查 JSX 条件渲染
echo "  检查 JSX 条件渲染..."
if grep -rn "{.*&&.*<\|{.*?.*:.*<" "$TARGET_DIR" --include="*.vue" > "$TEMP_FILE" 2>/dev/null; then
    echo -e "${YELLOW}  ⚠️  可能存在 JSX 条件渲染（建议使用 v-if）:${NC}"
    cat "$TEMP_FILE"
    # 不计入错误，仅警告
else
    echo -e "${GREEN}  ✅ 未发现 JSX 条件渲染${NC}"
fi

echo ""

# ========================================
# 检查 2: v-if 和 v-for 同级使用
# ========================================
echo -e "${BLUE}[检查 2/7] v-if 和 v-for 同级使用检测${NC}"

if grep -rn "v-for=.*v-if=\|v-if=.*v-for=" "$TARGET_DIR" --include="*.vue" > "$TEMP_FILE" 2>/dev/null; then
    echo -e "${RED}  ❌ 发现 v-if 和 v-for 同级使用（应使用 computed 或嵌套 template）:${NC}"
    cat "$TEMP_FILE"
    ERRORS_FOUND=$((ERRORS_FOUND + 1))
else
    echo -e "${GREEN}  ✅ 未发现 v-if 和 v-for 同级使用${NC}"
fi

echo ""

# ========================================
# 检查 3: v-for 缺少 :key
# ========================================
echo -e "${BLUE}[检查 3/7] v-for 缺少 :key 检测${NC}"

# 查找 v-for 但没有 :key 的行
if grep -rn "v-for=" "$TARGET_DIR" --include="*.vue" | grep -v ":key=" | grep -v "v-bind:key=" > "$TEMP_FILE" 2>/dev/null; then
    echo -e "${YELLOW}  ⚠️  可能缺少 :key 的 v-for（请手动检查）:${NC}"
    cat "$TEMP_FILE"
    # 不计入错误，仅警告
else
    echo -e "${GREEN}  ✅ 所有 v-for 都有 :key${NC}"
fi

echo ""

# ========================================
# 检查 4: 直接修改 props
# ========================================
echo -e "${BLUE}[检查 4/7] 直接修改 props 检测${NC}"

# 检查 props.xxx = 的模式
if grep -rn "props\.[a-zA-Z_]*\s*=" "$TARGET_DIR" --include="*.vue" | grep -v "const props" | grep -v "defineProps" > "$TEMP_FILE" 2>/dev/null; then
    echo -e "${RED}  ❌ 可能存在直接修改 props（应使用 emit）:${NC}"
    cat "$TEMP_FILE"
    ERRORS_FOUND=$((ERRORS_FOUND + 1))
else
    echo -e "${GREEN}  ✅ 未发现直接修改 props${NC}"
fi

echo ""

# ========================================
# 检查 5: 组件导入检查
# ========================================
echo -e "${BLUE}[检查 5/7] Naive UI 组件导入检查${NC}"

# 检查全量导入
if grep -rn "import naive from 'naive-ui'" "$TARGET_DIR" --include="*.vue" > "$TEMP_FILE" 2>/dev/null; then
    echo -e "${YELLOW}  ⚠️  发现全量导入 Naive UI（建议按需导入）:${NC}"
    cat "$TEMP_FILE"
else
    echo -e "${GREEN}  ✅ 正确按需导入 Naive UI 组件${NC}"
fi

echo ""

# ========================================
# 检查 6: 响应式数据使用检查
# ========================================
echo -e "${BLUE}[检查 6/7] 响应式数据使用检查${NC}"

# 检查 reactive 解构
if grep -rn "const.*{.*}.*=.*reactive(" "$TARGET_DIR" --include="*.vue" | grep -v "toRefs" > "$TEMP_FILE" 2>/dev/null; then
    echo -e "${YELLOW}  ⚠️  可能直接解构 reactive 对象（应使用 toRefs）:${NC}"
    cat "$TEMP_FILE"
else
    echo -e "${GREEN}  ✅ 响应式数据使用正确${NC}"
fi

# 检查 store 解构
if grep -rn "const.*{.*}.*=.*store\$" "$TARGET_DIR" --include="*.vue" | grep -v "storeToRefs" | grep -v "// " > "$TEMP_FILE" 2>/dev/null; then
    echo -e "${YELLOW}  ⚠️  可能直接解构 store（应使用 storeToRefs）:${NC}"
    cat "$TEMP_FILE"
else
    echo -e "${GREEN}  ✅ store 解构使用正确${NC}"
fi

echo ""

# ========================================
# 检查 7: 生命周期清理检查
# ========================================
echo -e "${BLUE}[检查 7/7] 生命周期清理检查${NC}"

# 检查 setInterval 是否有对应的 clearInterval
if grep -rn "setInterval" "$TARGET_DIR" --include="*.vue" > "$TEMP_FILE" 2>/dev/null; then
    echo -e "${YELLOW}  ⚠️  发现 setInterval，请确保在 onBeforeUnmount 中清理:${NC}"
    cat "$TEMP_FILE"
else
    echo -e "${GREEN}  ✅ 未发现定时器使用${NC}"
fi

# 检查 addEventListener 是否有对应的 removeEventListener
if grep -rn "addEventListener" "$TARGET_DIR" --include="*.vue" > "$TEMP_FILE" 2>/dev/null; then
    echo -e "${YELLOW}  ⚠️  发现 addEventListener，请确保在 onBeforeUnmount 中移除:${NC}"
    cat "$TEMP_FILE"
else
    echo -e "${GREEN}  ✅ 未发现事件监听器${NC}"
fi

echo ""

# ========================================
# 统计和总结
# ========================================
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}检查完成${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

if [ $ERRORS_FOUND -eq 0 ]; then
    echo -e "${GREEN}✅ 未发现严重问题！代码质量良好。${NC}"
    exit 0
else
    echo -e "${RED}❌ 发现 $ERRORS_FOUND 个问题需要修复。${NC}"
    echo ""
    echo -e "${YELLOW}建议操作:${NC}"
    echo "  1. 查看上述错误信息"
    echo "  2. 参考 docs/coding-standards/vue-best-practices.md"
    echo "  3. 运行 npm run lint:fix 自动修复部分问题"
    exit 1
fi
