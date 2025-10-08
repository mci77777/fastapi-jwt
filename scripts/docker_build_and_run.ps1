# GymBro Docker 一键构建和启动脚本
# 用法: .\scripts\docker_build_and_run.ps1

$ErrorActionPreference = "Stop"

$IMAGE_NAME = "gymbro-api"
$IMAGE_TAG = "latest"
$CONTAINER_NAME = "gymbro-api"
$HOST_PORT = 9999
$CONTAINER_PORT = 80

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "GymBro Docker 一键构建和启动" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

# 步骤 1: 停止并删除旧容器
Write-Host "`n[1/5] 检查并清理旧容器..." -ForegroundColor Yellow

$existingContainer = docker ps -a --filter "name=$CONTAINER_NAME" --format "{{.Names}}"
if ($existingContainer -eq $CONTAINER_NAME) {
    Write-Host "  发现旧容器,正在停止..." -ForegroundColor Gray
    docker stop $CONTAINER_NAME | Out-Null
    Write-Host "  正在删除旧容器..." -ForegroundColor Gray
    docker rm $CONTAINER_NAME | Out-Null
    Write-Host "  [OK] 旧容器已清理" -ForegroundColor Green
} else {
    Write-Host "  [OK] 无需清理" -ForegroundColor Green
}

# 步骤 2: 删除旧镜像(可选)
Write-Host "`n[2/5] 检查旧镜像..." -ForegroundColor Yellow

$existingImage = docker images --filter "reference=${IMAGE_NAME}:${IMAGE_TAG}" --format "{{.Repository}}:{{.Tag}}"
if ($existingImage -eq "${IMAGE_NAME}:${IMAGE_TAG}") {
    Write-Host "  发现旧镜像: $existingImage" -ForegroundColor Gray
    $removeOld = Read-Host "  是否删除旧镜像? (y/N)"
    if ($removeOld -eq "y" -or $removeOld -eq "Y") {
        Write-Host "  正在删除旧镜像..." -ForegroundColor Gray
        docker rmi "${IMAGE_NAME}:${IMAGE_TAG}" | Out-Null
        Write-Host "  [OK] 旧镜像已删除" -ForegroundColor Green
    } else {
        Write-Host "  [SKIP] 保留旧镜像" -ForegroundColor Yellow
    }
} else {
    Write-Host "  [OK] 无旧镜像" -ForegroundColor Green
}

# 步骤 3: 构建新镜像
Write-Host "`n[3/5] 构建 Docker 镜像..." -ForegroundColor Yellow
Write-Host "  镜像名称: ${IMAGE_NAME}:${IMAGE_TAG}" -ForegroundColor Gray
Write-Host "  这可能需要几分钟时间,请耐心等待..." -ForegroundColor Gray

$buildStart = Get-Date

try {
    docker build -t "${IMAGE_NAME}:${IMAGE_TAG}" . 2>&1 | ForEach-Object {
        Write-Host "  $_" -ForegroundColor DarkGray
    }
    
    $buildEnd = Get-Date
    $buildDuration = ($buildEnd - $buildStart).TotalSeconds
    
    Write-Host "  [OK] 镜像构建成功 (耗时: $([math]::Round($buildDuration, 1))秒)" -ForegroundColor Green
} catch {
    Write-Host "  [FAIL] 镜像构建失败" -ForegroundColor Red
    Write-Host "  错误: $_" -ForegroundColor Red
    exit 1
}

# 步骤 4: 运行容器
Write-Host "`n[4/5] 启动 Docker 容器..." -ForegroundColor Yellow
Write-Host "  容器名称: $CONTAINER_NAME" -ForegroundColor Gray
Write-Host "  端口映射: ${HOST_PORT}:${CONTAINER_PORT}" -ForegroundColor Gray

try {
    $containerId = docker run -d `
        -p "${HOST_PORT}:${CONTAINER_PORT}" `
        --name $CONTAINER_NAME `
        --env-file .env `
        "${IMAGE_NAME}:${IMAGE_TAG}"
    
    Write-Host "  [OK] 容器已启动" -ForegroundColor Green
    Write-Host "  容器 ID: $containerId" -ForegroundColor Gray
} catch {
    Write-Host "  [FAIL] 容器启动失败" -ForegroundColor Red
    Write-Host "  错误: $_" -ForegroundColor Red
    exit 1
}

# 步骤 5: 健康检查
Write-Host "`n[5/5] 健康检查..." -ForegroundColor Yellow
Write-Host "  等待服务启动..." -ForegroundColor Gray

Start-Sleep -Seconds 5

$maxRetries = 12
$retryCount = 0
$healthCheckPassed = $false

while ($retryCount -lt $maxRetries) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:${HOST_PORT}/api/v1/healthz" -TimeoutSec 5 -UseBasicParsing
        if ($response.StatusCode -eq 200) {
            Write-Host "  [OK] 健康检查通过" -ForegroundColor Green
            Write-Host "  响应: $($response.Content)" -ForegroundColor Gray
            $healthCheckPassed = $true
            break
        }
    } catch {
        $retryCount++
        if ($retryCount -lt $maxRetries) {
            Write-Host "  尝试 $retryCount/$maxRetries 失败,等待重试..." -ForegroundColor Gray
            Start-Sleep -Seconds 5
        }
    }
}

if (-not $healthCheckPassed) {
    Write-Host "  [WARN] 健康检查超时" -ForegroundColor Yellow
    Write-Host "  请手动检查容器日志: docker logs $CONTAINER_NAME" -ForegroundColor Yellow
}

# 总结
Write-Host "`n============================================================" -ForegroundColor Cyan
Write-Host "部署完成" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan

Write-Host "`n服务访问地址:" -ForegroundColor White
Write-Host "  前端: http://localhost:${HOST_PORT}/" -ForegroundColor Cyan
Write-Host "  API:  http://localhost:${HOST_PORT}/api/v1/" -ForegroundColor Cyan
Write-Host "  文档: http://localhost:${HOST_PORT}/docs" -ForegroundColor Cyan

Write-Host "`n常用命令:" -ForegroundColor White
Write-Host "  查看日志: docker logs -f $CONTAINER_NAME" -ForegroundColor Gray
Write-Host "  停止容器: docker stop $CONTAINER_NAME" -ForegroundColor Gray
Write-Host "  启动容器: docker start $CONTAINER_NAME" -ForegroundColor Gray
Write-Host "  删除容器: docker rm -f $CONTAINER_NAME" -ForegroundColor Gray
Write-Host "  进入容器: docker exec -it $CONTAINER_NAME /bin/sh" -ForegroundColor Gray

Write-Host "`n============================================================`n" -ForegroundColor Cyan

