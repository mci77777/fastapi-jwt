#!/usr/bin/env python3
"""
验证 Docker 部署配置
检查 Dockerfile、nginx 配置和 entrypoint 脚本
"""
import sys
import subprocess
from pathlib import Path


class DockerDeploymentVerifier:
    """Docker 部署验证器"""
    
    def __init__(self):
        self.project_root = Path(__file__).parent.parent
        self.checks_passed = 0
        self.checks_failed = 0
    
    def check_file_exists(self, file_path: Path, description: str) -> bool:
        """检查文件是否存在"""
        exists = file_path.exists()
        
        if exists:
            self.checks_passed += 1
            print(f"  [OK] {description}")
        else:
            self.checks_failed += 1
            print(f"  [FAIL] {description}")
            print(f"         Missing: {file_path}")
        
        return exists
    
    def verify_docker_files(self) -> bool:
        """验证 Docker 相关文件"""
        print("\n" + "=" * 60)
        print("1. Docker Files Verification")
        print("=" * 60)
        
        # 检查 Dockerfile
        self.check_file_exists(self.project_root / "Dockerfile", "Dockerfile")
        
        # 检查部署脚本
        self.check_file_exists(self.project_root / "deploy" / "entrypoint.sh", "entrypoint.sh")
        self.check_file_exists(self.project_root / "deploy" / "web.conf", "nginx config")
        
        # 检查依赖文件
        self.check_file_exists(self.project_root / "requirements.txt", "requirements.txt")
        self.check_file_exists(self.project_root / "run.py", "run.py")
        
        # 检查 Web 前端
        self.check_file_exists(self.project_root / "web" / "package.json", "web/package.json")
        self.check_file_exists(self.project_root / "web" / "vite.config.js", "web/vite.config.js")
        
        return True
    
    def verify_docker_installed(self) -> bool:
        """验证 Docker 是否安装"""
        print("\n" + "=" * 60)
        print("2. Docker Installation Verification")
        print("=" * 60)
        
        try:
            result = subprocess.run(
                ["docker", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                version = result.stdout.strip()
                print(f"  [OK] Docker installed: {version}")
                self.checks_passed += 1
                return True
            else:
                print(f"  [FAIL] Docker not working properly")
                self.checks_failed += 1
                return False
        except Exception as e:
            print(f"  [FAIL] Docker not found: {e}")
            self.checks_failed += 1
            return False
    
    def verify_dockerfile_syntax(self) -> bool:
        """验证 Dockerfile 语法"""
        print("\n" + "=" * 60)
        print("3. Dockerfile Syntax Verification")
        print("=" * 60)
        
        dockerfile = self.project_root / "Dockerfile"
        
        try:
            with open(dockerfile, 'r') as f:
                content = f.read()
            
            # 检查关键指令
            required_instructions = [
                ("FROM", "Base image"),
                ("WORKDIR", "Working directory"),
                ("COPY", "Copy files"),
                ("RUN", "Run commands"),
                ("EXPOSE", "Expose port"),
                ("ENTRYPOINT", "Entry point"),
            ]
            
            for instruction, description in required_instructions:
                if instruction in content:
                    print(f"  [OK] {description} ({instruction})")
                    self.checks_passed += 1
                else:
                    print(f"  [FAIL] Missing {description} ({instruction})")
                    self.checks_failed += 1
            
            return True
        except Exception as e:
            print(f"  [FAIL] Error reading Dockerfile: {e}")
            self.checks_failed += 1
            return False
    
    def verify_nginx_config(self) -> bool:
        """验证 nginx 配置"""
        print("\n" + "=" * 60)
        print("4. Nginx Configuration Verification")
        print("=" * 60)
        
        nginx_conf = self.project_root / "deploy" / "web.conf"
        
        try:
            with open(nginx_conf, 'r') as f:
                content = f.read()
            
            # 检查关键配置
            checks = [
                ("listen 80", "HTTP port"),
                ("location /", "Root location"),
                ("location ^~ /api/", "API proxy"),
                ("proxy_pass", "Proxy configuration"),
                ("try_files", "SPA routing"),
            ]
            
            for pattern, description in checks:
                if pattern in content:
                    print(f"  [OK] {description}")
                    self.checks_passed += 1
                else:
                    print(f"  [FAIL] Missing {description}")
                    self.checks_failed += 1
            
            return True
        except Exception as e:
            print(f"  [FAIL] Error reading nginx config: {e}")
            self.checks_failed += 1
            return False
    
    def verify_entrypoint_script(self) -> bool:
        """验证 entrypoint 脚本"""
        print("\n" + "=" * 60)
        print("5. Entrypoint Script Verification")
        print("=" * 60)
        
        entrypoint = self.project_root / "deploy" / "entrypoint.sh"
        
        try:
            with open(entrypoint, 'r') as f:
                content = f.read()
            
            # 检查关键命令
            checks = [
                ("#!/bin/sh", "Shebang"),
                ("nginx", "Start nginx"),
                ("python run.py", "Start FastAPI"),
            ]
            
            for pattern, description in checks:
                if pattern in content:
                    print(f"  [OK] {description}")
                    self.checks_passed += 1
                else:
                    print(f"  [FAIL] Missing {description}")
                    self.checks_failed += 1
            
            return True
        except Exception as e:
            print(f"  [FAIL] Error reading entrypoint script: {e}")
            self.checks_failed += 1
            return False
    
    def verify_web_build_config(self) -> bool:
        """验证 Web 构建配置"""
        print("\n" + "=" * 60)
        print("6. Web Build Configuration Verification")
        print("=" * 60)
        
        package_json = self.project_root / "web" / "package.json"
        
        try:
            import json
            with open(package_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # 检查构建脚本
            scripts = data.get('scripts', {})
            
            if 'build' in scripts:
                print(f"  [OK] Build script exists")
                print(f"       Command: {scripts['build']}")
                self.checks_passed += 1
            else:
                print(f"  [FAIL] Build script missing")
                self.checks_failed += 1
            
            # 检查依赖
            deps = data.get('dependencies', {})
            dev_deps = data.get('devDependencies', {})
            
            print(f"  [INFO] Dependencies: {len(deps)}")
            print(f"  [INFO] Dev dependencies: {len(dev_deps)}")
            
            return True
        except Exception as e:
            print(f"  [FAIL] Error reading package.json: {e}")
            self.checks_failed += 1
            return False
    
    def print_summary(self):
        """打印总结"""
        print("\n" + "=" * 60)
        print("Verification Summary")
        print("=" * 60)
        print(f"  Checks passed: {self.checks_passed}")
        print(f"  Checks failed: {self.checks_failed}")
        print(f"  Total checks: {self.checks_passed + self.checks_failed}")
        
        if self.checks_failed == 0:
            print(f"\n  [SUCCESS] Docker deployment configuration is ready!")
            print(f"\n  To build the Docker image, run:")
            print(f"    docker build -t gymbro-api:latest .")
            print(f"\n  To run the container, run:")
            print(f"    docker run -d -p 9999:80 --name gymbro-api gymbro-api:latest")
            return 0
        else:
            print(f"\n  [WARNING] {self.checks_failed} check(s) failed")
            print(f"  Please fix the issues before building Docker image.")
            return 1


def main():
    """主函数"""
    print("\nDocker Deployment Configuration Verification")
    print("=" * 60)
    
    verifier = DockerDeploymentVerifier()
    
    # 执行所有验证
    verifier.verify_docker_files()
    verifier.verify_docker_installed()
    verifier.verify_dockerfile_syntax()
    verifier.verify_nginx_config()
    verifier.verify_entrypoint_script()
    verifier.verify_web_build_config()
    
    # 打印总结
    return verifier.print_summary()


if __name__ == "__main__":
    sys.exit(main())

