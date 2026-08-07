# -*- coding:utf-8 -*-
"""电费催收入口包装脚本 - 修复 utils 模块导入路径问题"""

import sys
import os
import argparse


def get_parse():
    """
        获取命令行参数
    """
    parser = argparse.ArgumentParser(description="帮助文档")
    parser.add_argument('-s','--step',type=str,help='步骤')
    parser.add_argument('-k','--kw',type=str,help='关键字')
    parser.add_argument('-o','--mode',type=str,help='playwright浏览器执行方式，1静默执行、0普通，默认1静默执行')
    
    args = vars(parser.parse_args())
    
    return {k:v for k,v in args.items() if v is not None}


sys.path.append('.')

kwargs = get_parse()
step = kwargs.get('step')

# 批量创建工单
if step == "create_workst":
    from scripts.create_workst import main
    main(**kwargs)

# 查询欠费用户
elif step == 'cxqfyh':
    from scripts.owe_fee import main
    main(**kwargs)

# 打开工单界面
elif step == 'browser_workst':
    from scripts.create_workst import browser_workst as main
    main(**kwargs)
else:
    print('参数错误')

