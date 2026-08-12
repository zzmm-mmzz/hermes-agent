import sys
sys.path.insert(0, 'E:/skill-market-api')
from skill_market_api import scan_local_skills

skills = scan_local_skills()
print(f'扫描到 {len(skills)} 个技能:')
for s in skills:
    print(f'  [{s["namespaceName"]}] {s["slug"]} -> {s["name"]}')
