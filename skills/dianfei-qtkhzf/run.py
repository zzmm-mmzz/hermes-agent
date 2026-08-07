# -*- coding:utf-8 -*-
"""其他客户走访入口包装脚本"""
import sys
# import os
import argparse


def get_parse():
    """
        获取命令行参数
    """
    parser = argparse.ArgumentParser(description="帮助文档")
    parser.add_argument('-s','--step',type=str,help='步骤，qtkhzf/pre_audit/audit')
    parser.add_argument('-c','--cons_no',type=str,help='用户号编码')
    parser.add_argument('-e','--empl',type=str,help='接单人')

    args = vars(parser.parse_args())

    return {k:v for k,v in args.items() if v is not None}


sys.path.append('.')

kwargs = get_parse()
step = kwargs.get('step')

# 创建其他客户走访工单并派单
if step == 'qtkhzf':
    from scripts.assign_qtkhzf import main
    main(**kwargs)

# 待审核清单
elif step == 'pre_audit':
    from scripts.pre_audit_qtkhzf import main
    main(**kwargs)

# 工单审核
elif step == 'audit':
    from scripts.audit_qtkhzf import main
    main(**kwargs)


else:
    print('参数错误')
