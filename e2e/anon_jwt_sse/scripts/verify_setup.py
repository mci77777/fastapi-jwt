#!/usr/bin/env python3
"""
E2E 测试环境验证脚本
验证所有必需的文件、配置和依赖是否就绪
"""
import sys
import os
import json
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


class SetupVerifier:
    """E2E 测试环境验证器"""
    
    def __init__(self):
        self.base_dir = Path(__file__).parent.parent
        self.project_root = self.base_dir.parent.parent
        self.checks_passed = 0
        self.checks_failed = 0
        self.checks_total = 0
    
    def check_file_exists(self, file_path: Path, description: str) -> bool:
        """检查文件是否存在"""
        self.checks_total += 1
        exists = file_path.exists()
        
        if exists:
            self.checks_passed += 1
            print(f"  [OK] {description}")
        else:
            self.checks_failed += 1
            print(f"  [FAIL] {description}")
            print(f"         Missing: {file_path}")
        
        return exists
    
    def check_directory_exists(self, dir_path: Path, description: str) -> bool:
        """检查目录是否存在"""
        self.checks_total += 1
        exists = dir_path.exists() and dir_path.is_dir()
        
        if exists:
            self.checks_passed += 1
            print(f"  [OK] {description}")
        else:
            self.checks_failed += 1
            print(f"  [FAIL] {description}")
            print(f"         Missing: {dir_path}")
        
        return exists
    
    def check_python_module(self, module_name: str) -> bool:
        """检查 Python 模块是否可导入"""
        self.checks_total += 1
        try:
            __import__(module_name)
            self.checks_passed += 1
            print(f"  [OK] Python module: {module_name}")
            return True
        except ImportError as e:
            self.checks_failed += 1
            print(f"  [FAIL] Python module: {module_name}")
            print(f"         Error: {e}")
            return False
    
    def check_env_var(self, var_name: str, required: bool = True) -> bool:
        """检查环境变量是否设置"""
        self.checks_total += 1
        value = os.getenv(var_name)
        
        if value:
            self.checks_passed += 1
            print(f"  [OK] Environment variable: {var_name}")
            return True
        else:
            if required:
                self.checks_failed += 1
                print(f"  [FAIL] Environment variable: {var_name} (required)")
            else:
                self.checks_passed += 1
                print(f"  [SKIP] Environment variable: {var_name} (optional)")
            return False
    
    def verify_file_structure(self) -> bool:
        """验证文件结构"""
        print("\n" + "=" * 60)
        print("1. File Structure Verification")
        print("=" * 60)
        
        # 检查脚本文件
        scripts_dir = self.base_dir / "scripts"
        required_scripts = [
            ("anon_signin_enhanced.py", "Anonymous signin script"),
            ("generate_test_token.py", "Test token generator"),
            ("jwt_mutation_tests.py", "JWT security tests"),
            ("sse_client.py", "SSE client script"),
            ("sse_chaos.py", "SSE stability tests"),
            ("validate_anon_integration.py", "Integration validation"),
            ("run_e2e_enhanced.py", "E2E test runner"),
        ]
        
        for script_name, description in required_scripts:
            self.check_file_exists(scripts_dir / script_name, description)
        
        # 检查配置文件
        self.check_file_exists(self.base_dir / "package.json", "package.json")
        self.check_file_exists(self.base_dir / "requirements.txt", "requirements.txt")
        self.check_file_exists(self.base_dir / "README.md", "README.md")
        
        # 检查目录
        self.check_directory_exists(self.base_dir / "artifacts", "artifacts directory")
        self.check_directory_exists(self.base_dir / "postman", "postman directory")
        self.check_directory_exists(self.base_dir / "sql", "sql directory")
        
        return True
    
    def verify_python_dependencies(self) -> bool:
        """验证 Python 依赖"""
        print("\n" + "=" * 60)
        print("2. Python Dependencies Verification")
        print("=" * 60)
        
        required_modules = [
            "httpx",
            "aiohttp",
            "jwt",
            "dotenv",
        ]
        
        for module in required_modules:
            self.check_python_module(module)
        
        return True
    
    def verify_project_config(self) -> bool:
        """验证项目配置"""
        print("\n" + "=" * 60)
        print("3. Project Configuration Verification")
        print("=" * 60)
        
        # 检查 .env 文件
        env_file = self.project_root / ".env"
        self.check_file_exists(env_file, ".env file")
        
        # 检查关键配置
        try:
            from app.settings.config import get_settings
            settings = get_settings()
            
            self.checks_total += 1
            if settings.supabase_project_id:
                self.checks_passed += 1
                print("  [OK] SUPABASE_PROJECT_ID configured")
            else:
                self.checks_failed += 1
                print("  [FAIL] SUPABASE_PROJECT_ID not configured")
            
            self.checks_total += 1
            if settings.supabase_issuer:
                self.checks_passed += 1
                print("  [OK] SUPABASE_ISSUER configured")
            else:
                self.checks_failed += 1
                print("  [FAIL] SUPABASE_ISSUER not configured")
            
            self.checks_total += 1
            if settings.supabase_jwt_secret:
                self.checks_passed += 1
                print("  [OK] SUPABASE_JWT_SECRET configured")
            else:
                self.checks_failed += 1
                print("  [FAIL] SUPABASE_JWT_SECRET not configured")
            
        except Exception as e:
            self.checks_total += 3
            self.checks_failed += 3
            print(f"  [FAIL] Failed to load settings: {e}")
        
        return True
    
    def verify_jwt_verifier(self) -> bool:
        """验证 JWT 验证器"""
        print("\n" + "=" * 60)
        print("4. JWT Verifier Verification")
        print("=" * 60)
        
        try:
            from app.auth.jwt_verifier import get_jwt_verifier
            
            self.checks_total += 1
            verifier = get_jwt_verifier()
            self.checks_passed += 1
            print("  [OK] JWT verifier instance created")
            
            # 检查 JWKS 缓存
            self.checks_total += 1
            cache = verifier._cache
            keys = cache.get_keys()
            if keys:
                self.checks_passed += 1
                print(f"  [OK] JWKS cache has {len(keys)} key(s)")
            else:
                self.checks_failed += 1
                print("  [FAIL] JWKS cache has no keys")
            
        except Exception as e:
            self.checks_total += 2
            self.checks_failed += 2
            print(f"  [FAIL] JWT verifier error: {e}")
        
        return True
    
    def verify_test_token(self) -> bool:
        """验证测试 token"""
        print("\n" + "=" * 60)
        print("5. Test Token Verification")
        print("=" * 60)
        
        token_file = self.base_dir / "artifacts" / "token.json"
        
        if not token_file.exists():
            print("  [INFO] No test token found, generating...")
            # 生成测试 token
            try:
                import subprocess
                result = subprocess.run(
                    [sys.executable, str(self.base_dir / "scripts" / "generate_test_token.py")],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    self.checks_total += 1
                    self.checks_passed += 1
                    print("  [OK] Test token generated")
                else:
                    self.checks_total += 1
                    self.checks_failed += 1
                    print("  [FAIL] Failed to generate test token")
                    return False
            except Exception as e:
                self.checks_total += 1
                self.checks_failed += 1
                print(f"  [FAIL] Error generating test token: {e}")
                return False
        
        # 验证 token
        try:
            with open(token_file, 'r') as f:
                token_data = json.load(f)
            
            self.checks_total += 1
            if 'access_token' in token_data:
                self.checks_passed += 1
                print("  [OK] Test token file valid")
                
                # 尝试验证 token
                try:
                    from app.auth.jwt_verifier import get_jwt_verifier
                    verifier = get_jwt_verifier()
                    user = verifier.verify_token(token_data['access_token'])
                    
                    self.checks_total += 1
                    self.checks_passed += 1
                    print("  [OK] Test token verification passed")
                    print(f"       User ID: {user.uid}")
                    print(f"       User type: {user.user_type}")
                except Exception as e:
                    self.checks_total += 1
                    self.checks_failed += 1
                    print(f"  [FAIL] Test token verification failed: {e}")
            else:
                self.checks_failed += 1
                print("  [FAIL] Test token file missing access_token")
        except Exception as e:
            self.checks_total += 1
            self.checks_failed += 1
            print(f"  [FAIL] Error reading test token: {e}")
        
        return True
    
    def print_summary(self):
        """打印总结"""
        print("\n" + "=" * 60)
        print("Verification Summary")
        print("=" * 60)
        print(f"  Total checks: {self.checks_total}")
        print(f"  Passed: {self.checks_passed}")
        print(f"  Failed: {self.checks_failed}")
        
        if self.checks_failed == 0:
            print("\n  [SUCCESS] All checks passed!")
            print("  Ready to run E2E tests.")
            return 0
        else:
            print(f"\n  [WARNING] {self.checks_failed} check(s) failed")
            print("  Please fix the issues before running E2E tests.")
            return 1


def main():
    """主函数"""
    print("\nE2E Test Environment Verification")
    print("=" * 60)
    
    verifier = SetupVerifier()
    
    # 执行所有验证
    verifier.verify_file_structure()
    verifier.verify_python_dependencies()
    verifier.verify_project_config()
    verifier.verify_jwt_verifier()
    verifier.verify_test_token()
    
    # 打印总结
    return verifier.print_summary()


if __name__ == "__main__":
    sys.exit(main())

