# Vue 代码检查脚本（PowerShell 版本）
# 使用方法: .\scripts\check-vue-syntax.ps1 [directory]

param(
    [string]$TargetDir = "web\src"
)

$ErrorsFound = 0
$WarningsFound = 0

# 颜色函数
function Write-ColorOutput($ForegroundColor) {
    $fc = $host.UI.RawUI.ForegroundColor
    $host.UI.RawUI.ForegroundColor = $ForegroundColor
    if ($args) {
        Write-Output $args
    }
    $host.UI.RawUI.ForegroundColor = $fc
}

Write-ColorOutput Cyan "========================================"
Write-ColorOutput Cyan "Vue 3 代码语法检查"
Write-ColorOutput Cyan "========================================"
Write-Output ""
Write-Output "检查目录: $TargetDir"
Write-Output ""

# ========================================
# 检查 1: JSX 语法混入检查
# ========================================
Write-ColorOutput Cyan "[检查 1/7] JSX 语法混入检测"

# 检查 className 属性
Write-Output "  检查 className 属性..."
$classNameResults = Select-String -Path "$TargetDir\**\*.vue" -Pattern 'className=' -Exclude "node_modules" -ErrorAction SilentlyContinue
if ($classNameResults) {
    Write-ColorOutput Red "  ❌ 发现 className 属性（应使用 class 或 :class）:"
    $classNameResults | ForEach-Object { Write-Output "    $($_.Path):$($_.LineNumber): $($_.Line.Trim())" }
    $ErrorsFound++
} else {
    Write-ColorOutput Green "  ✅ 未发现 className 属性"
}

# 检查 JSX 事件绑定
Write-Output "  检查 JSX 事件绑定..."
$jsxEventResults = Select-String -Path "$TargetDir\**\*.vue" -Pattern '(onClick=|onUpdate|onChange=|onInput=)' -Exclude "node_modules" -ErrorAction SilentlyContinue | Where-Object { $_.Line -notmatch '//' -and $_.Line -notmatch '/\*' }
if ($jsxEventResults) {
    Write-ColorOutput Red "  ❌ 发现 JSX 事件绑定（应使用 @click, @update 等）:"
    $jsxEventResults | ForEach-Object { Write-Output "    $($_.Path):$($_.LineNumber): $($_.Line.Trim())" }
    $ErrorsFound++
} else {
    Write-ColorOutput Green "  ✅ 未发现 JSX 事件绑定"
}

# 检查 JSX 条件渲染
Write-Output "  检查 JSX 条件渲染..."
$jsxConditionResults = Select-String -Path "$TargetDir\**\*.vue" -Pattern '\{.*&&.*<|\{.*\?.*:.*<' -Exclude "node_modules" -ErrorAction SilentlyContinue
if ($jsxConditionResults) {
    Write-ColorOutput Yellow "  ⚠️  可能存在 JSX 条件渲染（建议使用 v-if）:"
    $jsxConditionResults | ForEach-Object { Write-Output "    $($_.Path):$($_.LineNumber): $($_.Line.Trim())" }
    $WarningsFound++
} else {
    Write-ColorOutput Green "  ✅ 未发现 JSX 条件渲染"
}

Write-Output ""

# ========================================
# 检查 2: v-if 和 v-for 同级使用
# ========================================
Write-ColorOutput Cyan "[检查 2/7] v-if 和 v-for 同级使用检测"

$vIfVForResults = Select-String -Path "$TargetDir\**\*.vue" -Pattern 'v-for=.*v-if=|v-if=.*v-for=' -Exclude "node_modules" -ErrorAction SilentlyContinue
if ($vIfVForResults) {
    Write-ColorOutput Red "  ❌ 发现 v-if 和 v-for 同级使用（应使用 computed 或嵌套 template）:"
    $vIfVForResults | ForEach-Object { Write-Output "    $($_.Path):$($_.LineNumber): $($_.Line.Trim())" }
    $ErrorsFound++
} else {
    Write-ColorOutput Green "  ✅ 未发现 v-if 和 v-for 同级使用"
}

Write-Output ""

# ========================================
# 检查 3: v-for 缺少 :key
# ========================================
Write-ColorOutput Cyan "[检查 3/7] v-for 缺少 :key 检测"

$vForResults = Select-String -Path "$TargetDir\**\*.vue" -Pattern 'v-for=' -Exclude "node_modules" -ErrorAction SilentlyContinue | Where-Object { $_.Line -notmatch ':key=' -and $_.Line -notmatch 'v-bind:key=' }
if ($vForResults) {
    Write-ColorOutput Yellow "  ⚠️  可能缺少 :key 的 v-for（请手动检查）:"
    $vForResults | ForEach-Object { Write-Output "    $($_.Path):$($_.LineNumber): $($_.Line.Trim())" }
    $WarningsFound++
} else {
    Write-ColorOutput Green "  ✅ 所有 v-for 都有 :key"
}

Write-Output ""

# ========================================
# 检查 4: 直接修改 props
# ========================================
Write-ColorOutput Cyan "[检查 4/7] 直接修改 props 检测"

$propsMutationResults = Select-String -Path "$TargetDir\**\*.vue" -Pattern 'props\.[a-zA-Z_]*\s*=' -Exclude "node_modules" -ErrorAction SilentlyContinue | Where-Object { $_.Line -notmatch 'const props' -and $_.Line -notmatch 'defineProps' }
if ($propsMutationResults) {
    Write-ColorOutput Red "  ❌ 可能存在直接修改 props（应使用 emit）:"
    $propsMutationResults | ForEach-Object { Write-Output "    $($_.Path):$($_.LineNumber): $($_.Line.Trim())" }
    $ErrorsFound++
} else {
    Write-ColorOutput Green "  ✅ 未发现直接修改 props"
}

Write-Output ""

# ========================================
# 检查 5: 组件导入检查
# ========================================
Write-ColorOutput Cyan "[检查 5/7] Naive UI 组件导入检查"

$naiveImportResults = Select-String -Path "$TargetDir\**\*.vue" -Pattern "import naive from 'naive-ui'" -Exclude "node_modules" -ErrorAction SilentlyContinue
if ($naiveImportResults) {
    Write-ColorOutput Yellow "  ⚠️  发现全量导入 Naive UI（建议按需导入）:"
    $naiveImportResults | ForEach-Object { Write-Output "    $($_.Path):$($_.LineNumber): $($_.Line.Trim())" }
    $WarningsFound++
} else {
    Write-ColorOutput Green "  ✅ 正确按需导入 Naive UI 组件"
}

Write-Output ""

# ========================================
# 检查 6: 响应式数据使用检查
# ========================================
Write-ColorOutput Cyan "[检查 6/7] 响应式数据使用检查"

# 检查 reactive 解构
$reactiveDestructureResults = Select-String -Path "$TargetDir\**\*.vue" -Pattern 'const.*\{.*\}.*=.*reactive\(' -Exclude "node_modules" -ErrorAction SilentlyContinue | Where-Object { $_.Line -notmatch 'toRefs' }
if ($reactiveDestructureResults) {
    Write-ColorOutput Yellow "  ⚠️  可能直接解构 reactive 对象（应使用 toRefs）:"
    $reactiveDestructureResults | ForEach-Object { Write-Output "    $($_.Path):$($_.LineNumber): $($_.Line.Trim())" }
    $WarningsFound++
} else {
    Write-ColorOutput Green "  ✅ 响应式数据使用正确"
}

# 检查 store 解构
$storeDestructureResults = Select-String -Path "$TargetDir\**\*.vue" -Pattern 'const.*\{.*\}.*=.*store$' -Exclude "node_modules" -ErrorAction SilentlyContinue | Where-Object { $_.Line -notmatch 'storeToRefs' -and $_.Line -notmatch '//' }
if ($storeDestructureResults) {
    Write-ColorOutput Yellow "  ⚠️  可能直接解构 store（应使用 storeToRefs）:"
    $storeDestructureResults | ForEach-Object { Write-Output "    $($_.Path):$($_.LineNumber): $($_.Line.Trim())" }
    $WarningsFound++
} else {
    Write-ColorOutput Green "  ✅ store 解构使用正确"
}

Write-Output ""

# ========================================
# 检查 7: 生命周期清理检查
# ========================================
Write-ColorOutput Cyan "[检查 7/7] 生命周期清理检查"

# 检查 setInterval
$setIntervalResults = Select-String -Path "$TargetDir\**\*.vue" -Pattern 'setInterval' -Exclude "node_modules" -ErrorAction SilentlyContinue
if ($setIntervalResults) {
    Write-ColorOutput Yellow "  ⚠️  发现 setInterval，请确保在 onBeforeUnmount 中清理:"
    $setIntervalResults | ForEach-Object { Write-Output "    $($_.Path):$($_.LineNumber): $($_.Line.Trim())" }
    $WarningsFound++
} else {
    Write-ColorOutput Green "  ✅ 未发现定时器使用"
}

# 检查 addEventListener
$addEventListenerResults = Select-String -Path "$TargetDir\**\*.vue" -Pattern 'addEventListener' -Exclude "node_modules" -ErrorAction SilentlyContinue
if ($addEventListenerResults) {
    Write-ColorOutput Yellow "  ⚠️  发现 addEventListener，请确保在 onBeforeUnmount 中移除:"
    $addEventListenerResults | ForEach-Object { Write-Output "    $($_.Path):$($_.LineNumber): $($_.Line.Trim())" }
    $WarningsFound++
} else {
    Write-ColorOutput Green "  ✅ 未发现事件监听器"
}

Write-Output ""

# ========================================
# 统计和总结
# ========================================
Write-ColorOutput Cyan "========================================"
Write-ColorOutput Cyan "检查完成"
Write-ColorOutput Cyan "========================================"
Write-Output ""

if ($ErrorsFound -eq 0 -and $WarningsFound -eq 0) {
    Write-ColorOutput Green "✅ 未发现问题！代码质量优秀。"
    exit 0
} elseif ($ErrorsFound -eq 0) {
    Write-ColorOutput Yellow "⚠️  发现 $WarningsFound 个警告，建议优化。"
    Write-Output ""
    Write-Output "建议操作:"
    Write-Output "  1. 查看上述警告信息"
    Write-Output "  2. 参考 docs\coding-standards\vue-best-practices.md"
    exit 0
} else {
    Write-ColorOutput Red "❌ 发现 $ErrorsFound 个错误和 $WarningsFound 个警告需要修复。"
    Write-Output ""
    Write-Output "建议操作:"
    Write-Output "  1. 查看上述错误信息"
    Write-Output "  2. 参考 docs\coding-standards\vue-best-practices.md"
    Write-Output "  3. 运行 npm run lint:fix 自动修复部分问题"
    exit 1
}
