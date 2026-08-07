# -*- coding:utf-8 -*-
"""低压台区巡视入口包装脚本"""
import sys
import argparse


def get_parse():
    """
        获取命令行参数
    """
    parser = argparse.ArgumentParser(description="帮助文档")
    parser.add_argument('-s','--step',type=str,help='步骤，import/pms30/yx20')
    parser.add_argument('-o','--mode',type=str,help='playwright浏览器执行方式，1静默执行、0普通，默认1静默执行')


    args = vars(parser.parse_args())

    return {k:v for k,v in args.items() if v is not None}


sys.path.append('.')

kwargs = get_parse()
step = kwargs.get('step')

# 检测并查看导入模板
if step == 'import':
    from scripts.import_excel import main
    main(**kwargs)

# 配网微应用创建低压台区巡视计划
elif step == 'pms30':
    from scripts.pms30_create import main
    main(**kwargs)

# 全量业务工单生成低压台区巡视计划
elif step == 'yx20':
    from scripts.yx20_create import main
    main(**kwargs)

else:
    print('参数错误')
