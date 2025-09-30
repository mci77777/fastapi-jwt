// 用 artifacts/token.json 的 access_token 替换 postman/env.json 中的 ACCESS_TOKEN
// 运行：node e2e/anon_jwt_sse/scripts/patch_postman_env.mjs
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const tokenPath = path.join(__dirname, '..', 'artifacts', 'token.json');
const envPath = path.join(__dirname, '..', 'postman', 'env.json');

console.log('🔧 Postman环境自动注入工具');
console.log(`📖 读取token: ${tokenPath}`);
console.log(`📝 更新环境: ${envPath}`);

try {
  // 读取token
  const token = JSON.parse(fs.readFileSync(tokenPath, 'utf8')).access_token;
  console.log(`✅ Token读取成功: ${token.substring(0, 50)}...`);

  // 读取或创建环境文件
  let env;
  try {
    env = JSON.parse(fs.readFileSync(envPath, 'utf8'));
    console.log('✅ 环境文件读取成功');
  } catch (e) {
    console.log('📁 环境文件不存在，创建新文件');
    env = {
      id: "e2e-anon-env",
      name: "E2E Anonymous Environment",
      values: []
    };
    // 确保目录存在
    fs.mkdirSync(path.dirname(envPath), { recursive: true });
  }

  function setVar(env, key, val) {
    const v = env.values?.find(x => x.key === key);
    if (v) {
      v.value = val;
      console.log(`🔄 更新变量: ${key}`);
    } else {
      (env.values ||= []).push({ key, value: val, enabled: true });
      console.log(`➕ 新增变量: ${key}`);
    }
  }

  // 设置ACCESS_TOKEN
  setVar(env, 'ACCESS_TOKEN', token);

  // 设置其他常用变量
  setVar(env, 'API_BASE', process.env.API_BASE || 'http://localhost:9999');
  setVar(env, 'TRACE_ID', `postman-${Date.now()}`);

  // 写入文件
  fs.writeFileSync(envPath, JSON.stringify(env, null, 2));
  console.log('✅ Postman环境文件更新完成');
  console.log(`📊 当前变量数量: ${env.values.length}`);

} catch (error) {
  console.error('❌ 更新失败:', error.message);
  process.exit(1);
}
