"""
文件路由脚本
根据文件名自动匹配已注册技能，返回技能名称。
每个技能通过 SKILL.md 头部 YAML 中的 file_patterns 字段声明自己能处理的文件模式。
"""

import os
import re
import yaml
from pathlib import Path

SKILLS_DIR = Path("C:/.hermes/skills")


def find_skill(filename: str):
    """根据文件名在所有技能中查找匹配的技能，返回技能名或 None"""
    if not SKILLS_DIR.is_dir():
        return None

    for skill_name in os.listdir(SKILLS_DIR):
        if skill_name == "file-router":
            continue

        skill_md = SKILLS_DIR / skill_name / "SKILL.md"
        if not skill_md.is_file():
            continue

        content = skill_md.read_text(encoding="utf-8")
        match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if not match:
            continue

        try:
            fm = yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            continue

        for pattern in fm.get("file_patterns", []):
            if pattern in filename:
                return skill_name

    return None


def list_skills():
    """列出所有已安装的技能及其匹配模式"""
    skills = []
    if not SKILLS_DIR.is_dir():
        return skills

    for skill_name in os.listdir(SKILLS_DIR):
        skill_md = SKILLS_DIR / skill_name / "SKILL.md"
        if not skill_md.is_file():
            continue

        content = skill_md.read_text(encoding="utf-8")
        match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if not match:
            continue

        try:
            fm = yaml.safe_load(match.group(1))
        except yaml.YAMLError:
            continue

        skills.append({
            "name": skill_name,
            "patterns": fm.get("file_patterns", []),
            "description": fm.get("description", "")
        })

    return skills


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("用法: python router.py <文件名>")
        print("      python router.py --list  (列出所有技能)")
        sys.exit(1)

    if sys.argv[1] == "--list":
        for s in list_skills():
            print(f"{s['name']}: {s['patterns']} - {s['description']}")
    else:
        filename = sys.argv[1]
        result = find_skill(filename)
        print(result if result else "no-match")