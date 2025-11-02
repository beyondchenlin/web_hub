# 论坛TTS自动化系统启动脚本
# 按照 docs/当前问题和测试说明.md 中的步骤执行

Write-Host "================================" -ForegroundColor Cyan
Write-Host "论坛TTS自动化系统启动脚本" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""

# 设置Python路径
$PYTHON_EXE = "D:\index-tts-2-6G-0914\index-tts-2\tts\indextts2\py312\python.exe"
$PROJECT_ROOT = "D:\index-tts-2-6G-0914\index-tts-2"

# 检查Python环境
if (-not (Test-Path $PYTHON_EXE)) {
    Write-Host "❌ 错误：找不到Python环境: $PYTHON_EXE" -ForegroundColor Red
    exit 1
}
Write-Host "✅ Python环境检查通过" -ForegroundColor Green

# 设置环境变量
$env:PYTHONPATH = $PROJECT_ROOT
$env:TASK_DISPATCH_MODE = "local"
$env:FORUM_TEST_MODE = "true"

Write-Host "✅ 环境变量已设置" -ForegroundColor Green
Write-Host "   PYTHONPATH=$env:PYTHONPATH"
Write-Host "   TASK_DISPATCH_MODE=$env:TASK_DISPATCH_MODE"
Write-Host "   FORUM_TEST_MODE=$env:FORUM_TEST_MODE"
Write-Host ""

# 1. 启动监控节点
Write-Host "🚀 步骤1: 启动监控节点 (端口 8000)..." -ForegroundColor Yellow
$monitorJob = Start-Job -ScriptBlock {
    param($python, $root)
    Set-Location $root
    $env:PYTHONPATH = $root
    $env:TASK_DISPATCH_MODE = "local"
    $env:FORUM_TEST_MODE = "true"
    & $python web_hub/cluster_monitor/forum_monitor.py --port 8000
} -ArgumentList $PYTHON_EXE, $PROJECT_ROOT

Write-Host "✅ 监控节点已启动 (Job ID: $($monitorJob.Id))" -ForegroundColor Green
Write-Host "   等待5秒让服务启动..." -ForegroundColor Gray
Start-Sleep -Seconds 5

# 2. 启动工作节点
Write-Host "🚀 步骤2: 启动工作节点 (端口 8005)..." -ForegroundColor Yellow
$workerJob = Start-Job -ScriptBlock {
    param($python, $root)
    Set-Location $root
    $env:PYTHONPATH = $root
    & $python web_hub/start_lightweight.py --port 8005
} -ArgumentList $PYTHON_EXE, $PROJECT_ROOT

Write-Host "✅ 工作节点已启动 (Job ID: $($workerJob.Id))" -ForegroundColor Green
Write-Host "   等待5秒让服务启动..." -ForegroundColor Gray
Start-Sleep -Seconds 5

# 3. 启动监控
Write-Host "🚀 步骤3: 启动论坛监控..." -ForegroundColor Yellow
try {
    $response = Invoke-WebRequest -Uri "http://localhost:8000/api/start-monitoring" -Method POST -TimeoutSec 10
    Write-Host "✅ 监控已启动" -ForegroundColor Green
    Write-Host "   响应: $($response.Content)" -ForegroundColor Gray
} catch {
    Write-Host "⚠️ 启动监控失败: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "   可能服务还未完全启动，请稍后手动执行：" -ForegroundColor Yellow
    Write-Host "   Invoke-WebRequest -Uri 'http://localhost:8000/api/start-monitoring' -Method POST" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "================================" -ForegroundColor Cyan
Write-Host "系统已启动！" -ForegroundColor Cyan
Write-Host "================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "📊 服务地址：" -ForegroundColor Yellow
Write-Host "   监控节点: http://localhost:8000" -ForegroundColor White
Write-Host "   工作节点: http://localhost:8005" -ForegroundColor White
Write-Host ""
Write-Host "📝 查看日志：" -ForegroundColor Yellow
Write-Host "   Get-Content logs/forum_monitor.log -Tail 50 -Wait" -ForegroundColor White
Write-Host ""
Write-Host "🛑 停止系统：" -ForegroundColor Yellow
Write-Host "   Stop-Job $($monitorJob.Id); Stop-Job $($workerJob.Id)" -ForegroundColor White
Write-Host "   Remove-Job $($monitorJob.Id); Remove-Job $($workerJob.Id)" -ForegroundColor White
Write-Host ""
Write-Host "按 Ctrl+C 退出脚本（服务将继续在后台运行）" -ForegroundColor Gray
Write-Host ""

# 持续显示日志
Write-Host "📋 实时日志输出..." -ForegroundColor Cyan
Write-Host ""
Get-Content logs/forum_monitor.log -Tail 20 -Wait

