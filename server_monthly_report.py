import configparser
import paramiko
import pandas as pd
import datetime
import os

def read_server_config(filename):
    """
    从配置文件中读取参数，并使用SSH连接执行命令。
    """
    config = configparser.ConfigParser()
    try:
        config.read(filename, encoding='utf-8')
    except Exception as e:
        print(f"Error reading config file {filename}: {e}")
        return {}

    results = {}
    for section in config.sections():
        try:
            host = config.get(section, 'host')
            user = config.get(section, 'user')
            password = config.get(section, 'password')
        except Exception as e:
            print(f"Error getting config for section {section}: {e}")
            continue

        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        print(f'Checking host {host} ({section})...')
        
        try:
            ssh.connect(hostname=host, port=22, username=user, password=password, timeout=10)
            # 核心统计逻辑保持不变
            command = "[ -d '/usr/local/bin' ] && /usr/local/bin/df -h --block-size=1G --total | grep '^total' || df -h --block-size=1G --total | grep '^total'"
            stdin, stdout, stderr = ssh.exec_command(command)
            res, err = stdout.read(), stderr.read()
            result = res if res else err
            results[section] = result.decode().strip()
        except Exception as e:
            print(f"Failed to connect or execute command on {host}: {e}")
            results[section] = ""
        finally:
            ssh.close()
    
    return results

def get_disk_usage(config_file):
    """统计服务器硬盘使用"""
    print("Step 1: Fetching disk usage from servers...")
    results = read_server_config(config_file)
    
    # 核心统计逻辑保持不变
    for key, value in results.items():
        results[key] = value.replace('-', '')

    df = pd.DataFrame(((key, *value.replace('total', '').replace('\n', '').split())
                       for key, value in results.items() if value),  # 过滤掉空的
                      columns=['Name', 'Size', 'Used', 'Available', 'Use%'])
    return df

def get_table_space():
    """从网页抓取相关信息"""
    print("Step 2: Scrapping table space information from web...")
    # 爬虫匹配逻辑保持不变
    try:
        table_space = pd.read_html(
            'http://10.37.181.12:9292/qz/fzgongju/shcema/shcema_oper.jsp',
            index_col=0,
            encoding='GBK')
        
        table_space = table_space[0]
        table_space.columns = table_space.columns.droplevel(level=0)
        table_space.drop(table_space.index[-1], inplace=True)
        table_space_pivot = table_space.pivot(columns='方案名称', values='已用百分比')

        table_space_pivot = table_space_pivot.reindex([
            '主库', '备份库', '泰安地震监测中心站', '烟台地震监测中心站', '聊城地震监测中心站', '菏泽地震监测中心站',
            '潍坊地震监测中心站', '临沂地震监测中心站', '青岛地震监测中心站'
        ])
        return table_space_pivot
    except Exception as e:
        print(f"Error fetching table space data: {e}")
        return pd.DataFrame()

def main():
    config_file = 'config.ini'
    if not os.path.exists(config_file):
        print(f"Error: {config_file} not found.")
        return

    # 生成报表名称
    now = datetime.datetime.now()
    report_name = f"server_monthly_report_{now.strftime('%Y%m')}.xlsx"

    # 执行统计
    disk_df = get_disk_usage(config_file)
    table_df = get_table_space()

    # 一键生成整合的 Excel
    print(f"Step 3: Generating integrated report: {report_name}")
    try:
        with pd.ExcelWriter(report_name, engine='openpyxl') as writer:
            if not disk_df.empty:
                disk_df.to_excel(writer, sheet_name='服务器磁盘使用', index=False)
            if not table_df.empty:
                table_df.to_excel(writer, sheet_name='数据库表空间')
        print("Success: Report generated successfully.")
    except Exception as e:
        print(f"Error generating Excel file: {e}")

if __name__ == "__main__":
    main()
