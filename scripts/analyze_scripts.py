#!/usr/bin/env python3
"""分析和分类项目中的所有测试脚本"""
import os
import re
from pathlib import Path
from typing import Dict, List, Tuple


def extract_description(file_path: Path) -> str:
    """从脚本中提取描述"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read(500)  # 只读前500字符
            
            # 查找文档字符串
            match = re.search(r'"""(.+?)"""', content, re.DOTALL)
            if match:
                desc = match.group(1).strip()
                # 只取第一行
                return desc.split('\n')[0].strip()
            
            # 查找注释
            match = re.search(r'#\s*(.+)', content)
            if match:
                return match.group(1).strip()
            
            return "No description"
    except Exception as e:
        return f"Error reading file: {e}"


def categorize_script(file_name: str, description: str) -> str:
    """根据文件名和描述分类脚本"""
    name_lower = file_name.lower()
    desc_lower = description.lower()
    
    # JWT 相关
    if any(x in name_lower for x in ['jwt', 'jwk', 'token']):
        return "JWT验证"
    
    # E2E 测试
    if any(x in name_lower for x in ['e2e', 'anon', 'sse']):
        return "E2E测试"
    
    # Docker 相关
    if 'docker' in name_lower:
        return "Docker部署"
    
    # Supabase 相关
    if 'supabase' in name_lower:
        return "Supabase配置"
    
    # 验证脚本
    if any(x in name_lower for x in ['verify', 'check', 'validate']):
        return "验证工具"
    
    # 调试脚本
    if any(x in name_lower for x in ['debug', 'diagnose']):
        return "调试工具"
    
    # 测试脚本
    if 'test' in name_lower:
        return "测试工具"
    
    # K系列脚本
    if name_lower.startswith('k'):
        return "K系列工具"
    
    return "其他工具"


def analyze_directory(dir_path: Path) -> Dict[str, List[Tuple[str, str]]]:
    """分析目录中的所有脚本"""
    scripts = {}
    
    for file_path in sorted(dir_path.glob('*.py')):
        if file_path.name.startswith('__'):
            continue
        
        description = extract_description(file_path)
        category = categorize_script(file_path.name, description)
        
        if category not in scripts:
            scripts[category] = []
        
        scripts[category].append((file_path.name, description))
    
    # 也检查 shell 脚本
    for file_path in sorted(dir_path.glob('*.sh')):
        description = extract_description(file_path)
        category = categorize_script(file_path.name, description)
        
        if category not in scripts:
            scripts[category] = []
        
        scripts[category].append((file_path.name, description))
    
    return scripts


def main():
    """主函数"""
    project_root = Path(__file__).parent.parent
    
    print("=" * 80)
    print("GymBro 项目脚本分析报告")
    print("=" * 80)
    
    # 分析 scripts 目录
    print("\n## 1. scripts/ 目录")
    print("-" * 80)
    scripts_dir = project_root / "scripts"
    scripts_analysis = analyze_directory(scripts_dir)
    
    total_scripts = 0
    for category in sorted(scripts_analysis.keys()):
        scripts_list = scripts_analysis[category]
        total_scripts += len(scripts_list)
        print(f"\n### {category} ({len(scripts_list)} 个)")
        for name, desc in scripts_list:
            print(f"  - {name}")
            print(f"    {desc}")
    
    print(f"\n**scripts/ 总计**: {total_scripts} 个脚本")
    
    # 分析 e2e/anon_jwt_sse/scripts 目录
    print("\n" + "=" * 80)
    print("## 2. e2e/anon_jwt_sse/scripts/ 目录")
    print("-" * 80)
    e2e_scripts_dir = project_root / "e2e" / "anon_jwt_sse" / "scripts"
    e2e_analysis = analyze_directory(e2e_scripts_dir)
    
    total_e2e = 0
    for category in sorted(e2e_analysis.keys()):
        scripts_list = e2e_analysis[category]
        total_e2e += len(scripts_list)
        print(f"\n### {category} ({len(scripts_list)} 个)")
        for name, desc in scripts_list:
            print(f"  - {name}")
            print(f"    {desc}")
    
    print(f"\n**e2e/anon_jwt_sse/scripts/ 总计**: {total_e2e} 个脚本")
    
    # 总结
    print("\n" + "=" * 80)
    print("## 总结")
    print("-" * 80)
    print(f"- scripts/ 目录: {total_scripts} 个脚本")
    print(f"- e2e/anon_jwt_sse/scripts/ 目录: {total_e2e} 个脚本")
    print(f"- **总计**: {total_scripts + total_e2e} 个脚本")
    
    # 识别可能重复的脚本
    print("\n" + "=" * 80)
    print("## 可能重复的脚本")
    print("-" * 80)
    
    all_scripts = {}
    for name, desc in sum(scripts_analysis.values(), []):
        all_scripts[name] = ('scripts/', desc)
    
    duplicates = []
    for name, desc in sum(e2e_analysis.values(), []):
        if name in all_scripts:
            duplicates.append((name, all_scripts[name], ('e2e/anon_jwt_sse/scripts/', desc)))
    
    if duplicates:
        for name, (dir1, desc1), (dir2, desc2) in duplicates:
            print(f"\n### {name}")
            print(f"  - {dir1}: {desc1}")
            print(f"  - {dir2}: {desc2}")
    else:
        print("\n未发现明显重复的脚本")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()

