# -*- coding:utf-8 -*-
"""电话号码核实入口包装脚本"""
import sys
# import os
import argparse


def get_parse():
    """
        获取命令行参数
    """
    parser = argparse.ArgumentParser(description="帮助文档")
    parser.add_argument('-s','--step',type=str,help='步骤')
    parser.add_argument('-c','--cons_no',type=str,help='用户号编码')
    parser.add_argument('-e','--empl',type=str,help='接单人')
    parser.add_argument('-d','--phone',type=str,help='待核实电话')
    parser.add_argument('-dp','--doc_phone',type=str,help='档案电话')

    args = vars(parser.parse_args())

    return {k:v for k,v in args.items() if v is not None}


sys.path.append('.')

kwargs = get_parse()
step = kwargs.get('step')

# 查询电话号码
if step == 'phone':
    from scripts.create_phone_task import main
    main(**kwargs)

# 创建电话号码核实工单并派单
elif step == 'dhhm':
    from scripts.assign_phone_task import main
    main(**kwargs)

# 待审核清单
elif step == 'pre_audit':
    from scripts.pre_audit_phone import main
    main(**kwargs)

# 工单审核
elif step == 'audit':
    from scripts.audit_phone_task import main
    main(**kwargs)

else:
    print('参数错误')

