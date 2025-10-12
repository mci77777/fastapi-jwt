/**
 * 在启动 Vite 开发服务器前,自动关闭占用 3101 端口的进程
 * 确保每次 npm run dev 都使用固定端口,不会递增端口号
 */
const { execSync } = require('child_process')
const os = require('os')

const PORT = process.env.VITE_PORT || 3101

function killPort() {
  const platform = os.platform()

  try {
    if (platform === 'win32') {
      // Windows: 查找并关闭占用端口的进程
      try {
        const output = execSync(`netstat -ano | findstr :${PORT}`, { encoding: 'utf-8' })
        const lines = output.trim().split('\n')

        const pids = new Set()
        lines.forEach((line) => {
          const match = line.match(/LISTENING\s+(\d+)/)
          if (match) {
            pids.add(match[1])
          }
        })

        if (pids.size > 0) {
          console.log(`\x1b[33m⚠ 检测到端口 ${PORT} 被占用,正在关闭旧进程...\x1b[0m`)
          pids.forEach((pid) => {
            try {
              execSync(`taskkill /F /PID ${pid}`, { stdio: 'ignore' })
              console.log(`\x1b[32m✓ 已关闭进程 PID: ${pid}\x1b[0m`)
            } catch (e) {
              console.log(`\x1b[31m✗ 无法关闭进程 PID: ${pid}\x1b[0m`)
            }
          })
          // 等待端口释放
          setTimeout(() => {}, 500)
        } else {
          console.log(`\x1b[32m✓ 端口 ${PORT} 可用\x1b[0m`)
        }
      } catch (e) {
        // netstat 无结果时会抛出异常,说明端口未被占用
        console.log(`\x1b[32m✓ 端口 ${PORT} 可用\x1b[0m`)
      }
    } else {
      // Linux/macOS: 使用 lsof
      try {
        const output = execSync(`lsof -ti:${PORT}`, { encoding: 'utf-8' })
        const pids = output.trim().split('\n').filter(Boolean)

        if (pids.length > 0) {
          console.log(`\x1b[33m⚠ 检测到端口 ${PORT} 被占用,正在关闭旧进程...\x1b[0m`)
          pids.forEach((pid) => {
            try {
              execSync(`kill -9 ${pid}`, { stdio: 'ignore' })
              console.log(`\x1b[32m✓ 已关闭进程 PID: ${pid}\x1b[0m`)
            } catch (e) {
              console.log(`\x1b[31m✗ 无法关闭进程 PID: ${pid}\x1b[0m`)
            }
          })
          // 等待端口释放
          setTimeout(() => {}, 500)
        } else {
          console.log(`\x1b[32m✓ 端口 ${PORT} 可用\x1b[0m`)
        }
      } catch (e) {
        // lsof 无结果时会抛出异常,说明端口未被占用
        console.log(`\x1b[32m✓ 端口 ${PORT} 可用\x1b[0m`)
      }
    }
  } catch (error) {
    console.error(`\x1b[31m✗ 端口检查失败: ${error.message}\x1b[0m`)
  }
}

killPort()
