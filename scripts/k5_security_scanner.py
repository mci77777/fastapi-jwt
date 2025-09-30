#!/usr/bin/env python3
"""K5 三类安全扫描器 - 检测非法导入、明文密钥、环境变量泄露。"""

import os
import re
import json
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class SecurityIssue:
    """安全问题数据类。"""
    file_path: str
    line_number: int
    issue_type: str
    severity: str
    description: str
    code_snippet: str


class SecurityScanner:
    """安全扫描器。"""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.issues: List[SecurityIssue] = []

        # 排除目录
        self.exclude_dirs = {
            'tools', '.github', '__pycache__', '.git', 'node_modules',
            '.venv', 'venv', '.pytest_cache', '.mypy_cache'
        }

        # 扫描文件类型
        self.scan_extensions = {'.py', '.js', '.ts', '.jsx', '.tsx', '.json', '.yaml', '.yml'}

    def scan_all(self) -> Dict:
        """执行所有扫描。"""
        print("🔍 开始三类安全扫描...")

        # 获取所有需要扫描的文件
        files_to_scan = self._get_files_to_scan()
        print(f"📁 扫描文件数量: {len(files_to_scan)}")

        # 执行三类扫描
        self._scan_illegal_firebase_imports(files_to_scan)
        self._scan_plaintext_bearer_tokens(files_to_scan)
        self._scan_environment_variable_leaks(files_to_scan)

        # 生成报告
        return self._generate_report()

    def _get_files_to_scan(self) -> List[Path]:
        """获取需要扫描的文件列表。"""
        files = []

        for file_path in self.project_root.rglob('*'):
            # 跳过目录
            if file_path.is_dir():
                continue

            # 跳过排除的目录
            if any(exclude_dir in file_path.parts for exclude_dir in self.exclude_dirs):
                continue

            # 只扫描指定类型的文件
            if file_path.suffix in self.scan_extensions:
                files.append(file_path)

        return files

    def _scan_illegal_firebase_imports(self, files: List[Path]):
        """扫描非法Firebase导入。"""
        print("🔥 扫描非法Firebase导入...")

        # Firebase相关的非法导入模式
        firebase_patterns = [
            r'from\s+firebase\s+import',
            r'import\s+firebase',
            r'from\s+firebase[.\w]*\s+import',
            r'require\([\'"]firebase[\'\"]\)',
            r'import\s+.*\s+from\s+[\'"]firebase[\'"]',
            r'firebase\.initializeApp',
            r'firebase\.auth\(\)',
            r'firebase\.firestore\(\)',
            r'getAuth\s*\(',
            r'getFirestore\s*\(',
        ]

        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()

                for line_num, line in enumerate(lines, 1):
                    line_clean = line.strip()

                    for pattern in firebase_patterns:
                        if re.search(pattern, line_clean, re.IGNORECASE):
                            self.issues.append(SecurityIssue(
                                file_path=str(file_path.relative_to(self.project_root)),
                                line_number=line_num,
                                issue_type="ILLEGAL_FIREBASE_IMPORT",
                                severity="HIGH",
                                description=f"检测到非法Firebase导入: {pattern}",
                                code_snippet=line_clean[:100]
                            ))

            except Exception as e:
                print(f"⚠️  扫描文件失败 {file_path}: {e}")

    def _scan_plaintext_bearer_tokens(self, files: List[Path]):
        """扫描明文Bearer令牌。"""
        print("🔑 扫描明文Bearer令牌...")

        # Bearer令牌模式
        bearer_patterns = [
            r'Bearer\s+[A-Za-z0-9+/=]{20,}',  # 标准Bearer格式
            r'bearer\s+[A-Za-z0-9+/=]{20,}',  # 小写bearer
            r'[\'"]Bearer\s+[A-Za-z0-9+/=]{20,}[\'"]',  # 引号包围
            r'Authorization[\'"]?\s*:\s*[\'"]?Bearer\s+[A-Za-z0-9+/=]{20,}',  # Authorization头
            r'token[\'"]?\s*:\s*[\'"]?[A-Za-z0-9+/=]{40,}[\'"]?',  # token字段
            r'access_token[\'"]?\s*:\s*[\'"]?[A-Za-z0-9+/=]{20,}[\'"]?',  # access_token字段
        ]

        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()

                for line_num, line in enumerate(lines, 1):
                    line_clean = line.strip()

                    # 跳过注释行
                    if line_clean.startswith('#') or line_clean.startswith('//'):
                        continue

                    for pattern in bearer_patterns:
                        matches = re.finditer(pattern, line_clean, re.IGNORECASE)
                        for match in matches:
                            # 检查是否是示例或测试数据
                            if self._is_example_token(match.group()):
                                continue

                            self.issues.append(SecurityIssue(
                                file_path=str(file_path.relative_to(self.project_root)),
                                line_number=line_num,
                                issue_type="PLAINTEXT_BEARER_TOKEN",
                                severity="CRITICAL",
                                description="检测到明文Bearer令牌",
                                code_snippet=line_clean[:100]
                            ))

            except Exception as e:
                print(f"⚠️  扫描文件失败 {file_path}: {e}")

    def _scan_environment_variable_leaks(self, files: List[Path]):
        """扫描环境变量泄露。"""
        print("🌍 扫描环境变量泄露...")

        # 环境变量泄露模式
        env_patterns = [
            r'System\.getenv\s*\(\s*[\'"][A-Z_]+[\'"]',  # Java System.getenv
            r'os\.getenv\s*\(\s*[\'"][A-Z_]+[\'"]',  # Python os.getenv
            r'process\.env\.[A-Z_]+',  # Node.js process.env
            r'ENV\[[\'"][A-Z_]+[\'"]',  # Ruby ENV
            r'\$ENV\{[A-Z_]+\}',  # Perl $ENV
            r'ENV_[A-Z_]+\s*=',  # 环境变量赋值
            r'SECRET_[A-Z_]+\s*=',  # SECRET前缀
            r'[\'"][A-Z_]*SECRET[A-Z_]*[\'"]',  # 包含SECRET的字符串
            r'[\'"][A-Z_]*PASSWORD[A-Z_]*[\'"]',  # 包含PASSWORD的字符串
            r'[\'"][A-Z_]*TOKEN[A-Z_]*[\'"]',  # 包含TOKEN的字符串
            r'[\'"][A-Z_]*KEY[A-Z_]*[\'"]',  # 包含KEY的字符串
        ]

        for file_path in files:
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    lines = f.readlines()

                for line_num, line in enumerate(lines, 1):
                    line_clean = line.strip()

                    # 跳过注释行
                    if line_clean.startswith('#') or line_clean.startswith('//'):
                        continue

                    for pattern in env_patterns:
                        matches = re.finditer(pattern, line_clean, re.IGNORECASE)
                        for match in matches:
                            # 检查是否是配置示例
                            if self._is_config_example(line_clean, match.group()):
                                continue

                            self.issues.append(SecurityIssue(
                                file_path=str(file_path.relative_to(self.project_root)),
                                line_number=line_num,
                                issue_type="ENVIRONMENT_VARIABLE_LEAK",
                                severity="MEDIUM",
                                description=f"检测到环境变量使用: {match.group()}",
                                code_snippet=line_clean[:100]
                            ))

            except Exception as e:
                print(f"⚠️  扫描文件失败 {file_path}: {e}")

    def _is_example_token(self, token: str) -> bool:
        """判断是否为示例令牌。"""
        example_indicators = [
            'example', 'test', 'demo', 'sample', 'placeholder',
            'your-token', 'your-key', 'xxx', 'yyy', 'zzz',
            'abcd', '1234', 'token-here', 'key-here'
        ]

        token_lower = token.lower()
        return any(indicator in token_lower for indicator in example_indicators)

    def _is_config_example(self, line: str, match: str) -> bool:
        """判断是否为配置示例。"""
        line_lower = line.lower()
        example_indicators = [
            'example', '.example', 'sample', 'template', 'placeholder',
            'your-', 'replace', 'change', 'modify', 'set-this'
        ]

        return any(indicator in line_lower for indicator in example_indicators)

    def _generate_report(self) -> Dict:
        """生成扫描报告。"""
        # 按类型统计
        issue_counts = {}
        for issue in self.issues:
            issue_counts[issue.issue_type] = issue_counts.get(issue.issue_type, 0) + 1

        # 按严重程度统计
        severity_counts = {}
        for issue in self.issues:
            severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1

        report = {
            "scan_summary": {
                "total_issues": len(self.issues),
                "scan_timestamp": "2025-09-29T13:50:00Z",
                "project_root": str(self.project_root),
                "excluded_dirs": list(self.exclude_dirs)
            },
            "issue_counts_by_type": issue_counts,
            "severity_counts": severity_counts,
            "issues": [
                {
                    "file_path": issue.file_path,
                    "line_number": issue.line_number,
                    "issue_type": issue.issue_type,
                    "severity": issue.severity,
                    "description": issue.description,
                    "code_snippet": issue.code_snippet
                }
                for issue in self.issues
            ],
            "scan_status": "PASS" if len(self.issues) == 0 else "FAIL",
            "recommendations": self._get_recommendations()
        }

        return report

    def _get_recommendations(self) -> List[str]:
        """获取修复建议。"""
        recommendations = []

        if any(issue.issue_type == "ILLEGAL_FIREBASE_IMPORT" for issue in self.issues):
            recommendations.append("移除所有Firebase相关导入，使用Supabase替代")

        if any(issue.issue_type == "PLAINTEXT_BEARER_TOKEN" for issue in self.issues):
            recommendations.append("将明文令牌移至环境变量或密钥管理系统")

        if any(issue.issue_type == "ENVIRONMENT_VARIABLE_LEAK" for issue in self.issues):
            recommendations.append("确保敏感环境变量不在代码中硬编码")

        if not recommendations:
            recommendations.append("未发现安全问题，代码符合安全规范")

        return recommendations


def main():
    """主函数。"""
    print("🛡️  开始K5三类安全扫描...")

    # 获取项目根目录
    project_root = os.getcwd()

    # 创建扫描器
    scanner = SecurityScanner(project_root)

    # 执行扫描
    report = scanner.scan_all()

    # 保存报告
    report_file = "docs/jwt改造/K5_security_scan_report.json"
    with open(report_file, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"📄 安全扫描报告已保存到: {report_file}")

    # 输出摘要
    print("\n🔍 安全扫描结果摘要:")
    print(f"   总问题数: {report['scan_summary']['total_issues']}")
    print(f"   扫描状态: {report['scan_status']}")

    if report['issue_counts_by_type']:
        print("   问题分类:")
        for issue_type, count in report['issue_counts_by_type'].items():
            print(f"     {issue_type}: {count}")

    if report['severity_counts']:
        print("   严重程度:")
        for severity, count in report['severity_counts'].items():
            print(f"     {severity}: {count}")

    print("\n💡 修复建议:")
    for recommendation in report['recommendations']:
        print(f"   - {recommendation}")

    # 返回退出码
    return 0 if report['scan_status'] == 'PASS' else 1


if __name__ == "__main__":
    exit(main())
