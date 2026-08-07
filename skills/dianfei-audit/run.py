# -*- coding:utf-8 -*-
"""电费催收入口包装脚本 - 修复 utils 模块导入路径问题"""
import sys
# import os
import argparse


def get_parse():
    """
        获取命令行参数
    """
    parser = argparse.ArgumentParser(description="帮助文档")
    parser.add_argument('-s','--step',type=str,help='步骤')
    parser.add_argument('-o','--mode',type=str,help='playwright浏览器执行方式，1静默执行、0普通，默认1静默执行')
    
    args = vars(parser.parse_args())
    
    return {k:v for k,v in args.items() if v is not None}


sys.path.append('.')

kwargs = get_parse()
step = kwargs.pop('step')

# 待审核清单
if step == 'pre_audit':
    from scripts.audit_work_order import pre_audit as main
    main(**kwargs)

# 工单审核
elif step == 'audit':
    from scripts.audit_work_order import main
    main(**kwargs)
else:
    print('参数错误')

