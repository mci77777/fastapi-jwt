#!/usr/bin/env python3
"""
增强版E2E测试主运行器
支持新的匿名用户JWT获取方式（Edge Function + 原生认证）
执行完整的匿名JWT→AI→APP（SSE）闭环测试
"""
import asyncio
import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

from dotenv import load_dotenv

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

# 加载环境变量
load_dotenv(Path(__file__).parent.parent / ".env.local")


class EnhancedE2ETestRunner:
    """增强版E2E测试运行器"""
    
    def __init__(self, auth_method: str = "auto"):
        self.base_dir = Path(__file__).parent.parent
        self.scripts_dir = self.base_dir / "scripts"
        self.artifacts_dir = self.base_dir / "artifacts"
        self.postman_dir = self.base_dir / "postman"
        
        # 认证方式: auto, edge, native, both
        self.auth_method = auth_method
        
        # 确保artifacts目录存在
        self.artifacts_dir.mkdir(exist_ok=True)
        
        self.test_results = {
            "start_time": time.time(),
            "auth_method": auth_method,
            "steps": [],
            "summary": {}
        }
    
    def log_step(self, step_name: str, success: bool, details: Dict[str, Any] = None):
        """记录测试步骤"""
        step = {
            "name": step_name,
            "success": success,
            "timestamp": time.time(),
            "details": details or {}
        }
        self.test_results["steps"].append(step)
        
        status = "✅" if success else "❌"
        print(f"{status} {step_name}")
        
        if not success and details:
            print(f"   错误详情: {details}")
    
    async def run_python_script(self, script_name: str, step_name: str, args: List[str] = None) -> bool:
        """运行Python脚本"""
        script_path = self.scripts_dir / script_name
        
        if not script_path.exists():
            self.log_step(step_name, False, {"error": f"脚本不存在: {script_path}"})
            return False
        
        try:
            print(f"🚀 执行: {script_name} {' '.join(args or [])}")
            
            # 构建命令
            cmd = [sys.executable, str(script_path)]
            if args:
                cmd.extend(args)
            
            # 使用subprocess运行脚本
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.base_dir)
            )
            
            stdout, stderr = await process.communicate()
            
            success = process.returncode == 0
            
            details = {
                "return_code": process.returncode,
                "stdout": stdout.decode('utf-8', errors='ignore'),
                "stderr": stderr.decode('utf-8', errors='ignore'),
                "command": ' '.join(cmd)
            }
            
            self.log_step(step_name, success, details)
            
            # 如果失败，打印错误信息
            if not success:
                print(f"   返回码: {process.returncode}")
                if stderr:
                    print(f"   错误输出: {stderr.decode('utf-8', errors='ignore')[:500]}...")
            
            return success
            
        except Exception as e:
            self.log_step(step_name, False, {"error": str(e)})
            return False
    
    async def test_anon_jwt_acquisition(self) -> bool:
        """测试匿名JWT获取"""
        print("\n🔑 测试匿名JWT获取...")
        
        if self.auth_method == "auto":
            # 自动选择：先尝试Edge Function，失败则尝试原生
            success = await self.run_python_script(
                "anon_signin_enhanced.py", 
                "匿名JWT获取(自动)", 
                ["--method", "both", "--verify"]
            )
        elif self.auth_method == "edge":
            # 仅Edge Function
            success = await self.run_python_script(
                "anon_signin_enhanced.py", 
                "匿名JWT获取(Edge Function)", 
                ["--method", "edge", "--verify"]
            )
        elif self.auth_method == "native":
            # 仅原生认证
            success = await self.run_python_script(
                "anon_signin_enhanced.py", 
                "匿名JWT获取(原生认证)", 
                ["--method", "native", "--verify"]
            )
        elif self.auth_method == "both":
            # 测试两种方式
            edge_success = await self.run_python_script(
                "anon_signin_enhanced.py", 
                "匿名JWT获取(Edge Function)", 
                ["--method", "edge"]
            )
            native_success = await self.run_python_script(
                "anon_signin_enhanced.py", 
                "匿名JWT获取(原生认证)", 
                ["--method", "native"]
            )
            success = edge_success or native_success
        else:
            self.log_step("匿名JWT获取", False, {"error": f"未知的认证方式: {self.auth_method}"})
            return False
        
        return success
    
    async def test_integration_validation(self) -> bool:
        """运行集成验证测试"""
        print("\n🔍 运行集成验证...")
        return await self.run_python_script(
            "validate_anon_integration.py", 
            "集成验证测试"
        )
    
    async def test_jwt_security(self) -> bool:
        """运行JWT安全测试"""
        print("\n🛡️ 运行JWT安全测试...")
        return await self.run_python_script(
            "jwt_mutation_tests.py", 
            "JWT安全测试"
        )
    
    async def test_sse_stability(self) -> bool:
        """运行SSE稳定性测试"""
        print("\n📡 运行SSE稳定性测试...")
        return await self.run_python_script(
            "sse_chaos.py", 
            "SSE稳定性测试"
        )
    
    async def test_sse_client(self) -> bool:
        """测试SSE客户端"""
        print("\n📡 测试SSE客户端...")
        return await self.run_python_script(
            "sse_client.py", 
            "SSE客户端测试"
        )
    
    def update_postman_env(self) -> bool:
        """更新Postman环境变量"""
        try:
            print("🔧 更新Postman环境...")
            
            # 读取token文件
            token_file = self.artifacts_dir / "token.json"
            if not token_file.exists():
                self.log_step("更新Postman环境", False, {"error": "token.json文件不存在"})
                return False
            
            with open(token_file, 'r', encoding='utf-8') as f:
                token_data = json.load(f)
            
            access_token = token_data.get("access_token")
            if not access_token:
                self.log_step("更新Postman环境", False, {"error": "token.json中没有access_token"})
                return False
            
            # 更新Postman环境文件
            env_file = self.postman_dir / "env.json"
            if env_file.exists():
                with open(env_file, 'r', encoding='utf-8') as f:
                    env_data = json.load(f)
                
                # 更新ACCESS_TOKEN
                for value in env_data.get("values", []):
                    if value.get("key") == "ACCESS_TOKEN":
                        value["value"] = access_token
                        break
                else:
                    # 如果不存在，添加新的
                    env_data.setdefault("values", []).append({
                        "key": "ACCESS_TOKEN",
                        "value": access_token,
                        "enabled": True
                    })
                
                with open(env_file, 'w', encoding='utf-8') as f:
                    json.dump(env_data, f, indent=2, ensure_ascii=False)
            
            self.log_step("更新Postman环境", True, {"access_token": access_token[:20] + "..."})
            return True
            
        except Exception as e:
            self.log_step("更新Postman环境", False, {"error": str(e)})
            return False
    
    def run_newman_test(self) -> bool:
        """运行Newman测试"""
        try:
            print("🚀 执行Newman API测试...")
            
            # 检查Newman是否安装
            try:
                subprocess.run(["newman", "--version"], 
                             capture_output=True, check=True)
            except (subprocess.CalledProcessError, FileNotFoundError):
                self.log_step("Newman测试", False, 
                            {"error": "Newman未安装，请运行: npm install -g newman"})
                return False
            
            # 运行Newman测试
            collection_file = self.postman_dir / "collection.json"
            env_file = self.postman_dir / "env.json"
            report_file = self.artifacts_dir / "newman-report.html"
            
            if not collection_file.exists():
                self.log_step("Newman测试", False, {"error": f"Collection文件不存在: {collection_file}"})
                return False
            
            cmd = [
                "newman", "run", str(collection_file),
                "-e", str(env_file),
                "--reporters", "cli,html",
                "--reporter-html-export", str(report_file),
                "--timeout", "30000",
                "--delay-request", "2000"  # 2秒延迟避免限流
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            success = result.returncode == 0
            
            details = {
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "report_file": str(report_file)
            }
            
            self.log_step("Newman测试", success, details)
            
            if success:
                print(f"   📊 Newman报告已生成: {report_file}")
            else:
                print(f"   返回码: {result.returncode}")
                if result.stderr:
                    print(f"   错误输出: {result.stderr[:500]}...")
            
            return success
            
        except Exception as e:
            self.log_step("Newman测试", False, {"error": str(e)})
            return False
    
    def generate_summary(self):
        """生成测试总结"""
        end_time = time.time()
        duration = end_time - self.test_results["start_time"]
        
        total_steps = len(self.test_results["steps"])
        passed_steps = sum(1 for step in self.test_results["steps"] if step["success"])
        failed_steps = total_steps - passed_steps
        
        self.test_results["summary"] = {
            "end_time": end_time,
            "duration_seconds": duration,
            "total_steps": total_steps,
            "passed_steps": passed_steps,
            "failed_steps": failed_steps,
            "success_rate": passed_steps / total_steps if total_steps > 0 else 0
        }
        
        # 保存详细结果
        result_file = self.artifacts_dir / "e2e_enhanced_results.json"
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, indent=2, ensure_ascii=False)
        
        # 打印总结
        print("\n" + "="*60)
        print("📊 增强版E2E测试总结")
        print("="*60)
        print(f"认证方式: {self.auth_method}")
        print(f"总耗时: {duration:.1f}秒")
        print(f"总步骤: {total_steps}")
        print(f"通过: {passed_steps}")
        print(f"失败: {failed_steps}")
        print(f"成功率: {self.test_results['summary']['success_rate']:.1%}")
        
        if failed_steps > 0:
            print("\n❌ 失败的步骤:")
            for step in self.test_results["steps"]:
                if not step["success"]:
                    print(f"   - {step['name']}")
        
        print(f"\n💾 详细结果已保存: {result_file}")
        
        return failed_steps == 0

async def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="增强版E2E测试运行器")
    parser.add_argument(
        "--auth-method", 
        choices=["auto", "edge", "native", "both"], 
        default="auto",
        help="JWT获取方式: auto(自动选择), edge(Edge Function), native(原生), both(两种都测试)"
    )
    parser.add_argument(
        "--skip-newman", 
        action="store_true",
        help="跳过Newman测试"
    )
    parser.add_argument(
        "--quick", 
        action="store_true",
        help="快速模式，跳过部分测试"
    )
    
    args = parser.parse_args()
    
    print("🚀 增强版E2E测试开始...")
    print(f"📋 认证方式: {args.auth_method}")
    print(f"⚡ 快速模式: {'是' if args.quick else '否'}")
    print("="*60)
    
    runner = EnhancedE2ETestRunner(args.auth_method)
    
    try:
        # 1. 集成验证
        await runner.test_integration_validation()
        
        # 2. 匿名JWT获取
        jwt_success = await runner.test_anon_jwt_acquisition()
        
        if jwt_success:
            # 3. 更新Postman环境
            runner.update_postman_env()
            
            # 4. JWT安全测试
            if not args.quick:
                await runner.test_jwt_security()
            
            # 5. SSE稳定性测试
            if not args.quick:
                await runner.test_sse_stability()
            
            # 6. SSE客户端测试
            await runner.test_sse_client()
            
            # 7. Newman测试
            if not args.skip_newman:
                runner.run_newman_test()
        else:
            print("⚠️ JWT获取失败，跳过后续测试")
        
        # 生成总结
        success = runner.generate_summary()
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\n⚠️ 测试被用户中断")
        return 1
    except Exception as e:
        print(f"\n💥 测试过程中发生异常: {e}")
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
