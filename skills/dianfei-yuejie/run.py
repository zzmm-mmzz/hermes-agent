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
    parser.add_argument('-u','--username',type=str,help='用户名')
    parser.add_argument('-p','--password',type=str,help='密码')
    parser.add_argument('-k','--kw',type=str,help='关键字')
    parser.add_argument('-o','--mode',type=str,help='playwright浏览器执行方式，1静默执行、0普通，默认1静默执行')

    parser.add_argument('-n','--unit',type=str,help='计划时限单位')
    parser.add_argument('-v','--val',type=str,help='计划时限数值')
    parser.add_argument('-d','--dt',type=str,help='触发时间')
    
    args = vars(parser.parse_args())
    
    return {k:v for k,v in args.items() if v is not None}


sys.path.append('.')

kwargs = get_parse()
step = kwargs.get('step')

# 登录
if step == 'login':
    from references.login import main 
    # 根据mode参数决定headless（mode=1为静默/headless，mode=0为普通）
    if kwargs.get('mode') == '1':
        kwargs['headless'] = True
    main(**kwargs)

# 批量创建工单
if step == "yuejie":
    from references.yuejie import main
    main(**kwargs)
else:
    print('参数错误')

