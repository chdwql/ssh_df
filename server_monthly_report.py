import configparser
import paramiko
import pandas as pd
import datetime
import os
import re

def read_server_config(filename):
    """
    从配置文件中读取参数，并使用SSH连接执行命令获取磁盘、内存、CPU、型号以及硬件健康信息。
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
            
            # 增加硬件检测：ipmitool 获取传感器状态，dmesg 获取 I/O 错误
            command = (
                "echo '---DISK---'; [ -d '/usr/local/bin' ] && /usr/local/bin/df -h --block-size=1G --total 2>/dev/null | grep '^total' || df -h --block-size=1G --total 2>/dev/null | grep '^total';"
                "echo '---MEM---'; free -m;"
                "echo '---CPU---'; top -bn1 | grep 'Cpu(s)';"
                "echo '---MODEL---'; dmidecode -t system | grep -A 5 'System Information' 2>/dev/null;"
                "echo '---HEALTH---'; ipmitool sdr list 2>/dev/null; dmesg | grep -iE 'error|failed' | tail -n 3 2>/dev/null"
            )
            
            stdin, stdout, stderr = ssh.exec_command(command)
            res = stdout.read().decode('utf-8', errors='ignore')
            err = stderr.read().decode('utf-8', errors='ignore')
            
            results[section] = {
                'ip': host,
                'raw': res if res else err
            }
        except Exception as e:
            print(f"Failed to connect or execute command on {host}: {e}")
            results[section] = {'ip': host, 'raw': ""}
        finally:
            ssh.close()
    
    return results

def parse_server_data(raw_data):
    """解析获取到的原始字符串数据"""
    data = {
        'Model': '',
        'Disk_Total(G)': '',
        'Disk_Used(G)': '',
        'Disk_Usage': '',
        'Mem_Total(M)': '',
        'Mem_Used(M)': '',
        'Mem_Usage': '',
        'CPU_Usage': '',
        'Hardware_Health': '健康'
    }
    
    if not raw_data:
        data['Hardware_Health'] = '无法获取'
        return data

    # 1. 解析型号 (MODEL)
    manufacturer = re.search(r'Manufacturer:\s*(.*)', raw_data)
    product = re.search(r'Product Name:\s*(.*)', raw_data)
    if manufacturer and product:
        m_str = manufacturer.group(1).strip()
        p_str = product.group(1).strip()
        model_parts = []
        if m_str and m_str.lower() not in ['empty', 'unknown', 'to be filled by o.e.m.']:
            model_parts.append(m_str)
        if p_str and p_str.lower() not in ['empty', 'unknown', 'system product name']:
            model_parts.append(p_str)
        data['Model'] = " ".join(model_parts)

    # 2. 解析磁盘 (DISK)
    disk_match = re.search(r'total\s+(\d+)\s+(\d+)\s+\d+\s+(\d+%)', raw_data)
    if disk_match:
        data['Disk_Total(G)'] = disk_match.group(1)
        data['Disk_Used(G)'] = disk_match.group(2)
        data['Disk_Usage'] = disk_match.group(3)

    # 3. 解析内存 (MEM)
    mem_total_match = re.search(r'Mem:\s+(\d+)', raw_data)
    if mem_total_match:
        data['Mem_Total(M)'] = mem_total_match.group(1)
    
    mem_used_match = re.search(r'-\/\+ buffers\/cache:\s+(\d+)', raw_data)
    if mem_used_match:
        data['Mem_Used(M)'] = mem_used_match.group(1)
    else:
        mem_line = re.search(r'Mem:\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)', raw_data)
        if mem_line:
            total, used_raw, free, shared, buff, cache = map(int, mem_line.groups())
            data['Mem_Used(M)'] = str(used_raw - buff - cache) if (used_raw > buff + cache) else str(used_raw)

    if data['Mem_Total(M)'] and data['Mem_Used(M)']:
        try:
            usage = (int(data['Mem_Used(M)']) / int(data['Mem_Total(M)'])) * 100
            data['Mem_Usage'] = f"{usage:.1f}%"
        except: pass

    # 4. 解析 CPU
    cpu_match = re.search(r'(\d+\.?\d*)\s*[%]?\s*id', raw_data)
    if cpu_match:
        try:
            idle = float(cpu_match.group(1))
            data['CPU_Usage'] = f"{100 - idle:.1f}%"
        except: pass

    # 5. 解析硬件健康 (HEALTH)
    if '---HEALTH---' in raw_data:
        health_section = raw_data.split('---HEALTH---')[1]
        errors = []
        # 查找 ipmitool sdr 中不是 ok 的项
        for line in health_section.split('\n'):
            if '|' in line:
                parts = [p.strip() for p in line.split('|')]
                if len(parts) >= 3:
                    name, _, status = parts[0], parts[1], parts[2]
                    if status.lower() not in ['ok', 'ns', 'not readable']:
                        errors.append(f"{name}:{status}")
        
        # 查找 dmesg 中的磁盘报警
        if re.search(r'i/o error|disk error|failed', health_section, re.I):
            errors.append("内核磁盘告警")

        if errors:
            data['Hardware_Health'] = "异常: " + "; ".join(errors)
        elif not re.search(r'\|\s*ok', health_section, re.I): # 没找到 ok 也没报错，可能是没装工具
            data['Hardware_Health'] = '未知(无IPMI数据)'
    
    return data

def get_server_status(config_file):
    """统计服务器状态并拆分为性能表和硬件表"""
    print("Step 1: Fetching server status (Network, Load, Hardware)...")
    results_map = read_server_config(config_file)
    
    perf_data = []
    hw_data = []
    
    for name, info in results_map.items():
        stats = parse_server_data(info['raw'])
        
        # 性能表数据
        perf_item = {
            'Name': name,
            'Model': stats['Model'],
            'Host_IP': info['ip'],
            'Disk_Total(G)': stats['Disk_Total(G)'],
            'Disk_Used(G)': stats['Disk_Used(G)'],
            'Disk_Usage': stats['Disk_Usage'],
            'Mem_Total(M)': stats['Mem_Total(M)'],
            'Mem_Used(M)': stats['Mem_Used(M)'],
            'Mem_Usage': stats['Mem_Usage'],
            'CPU_Usage': stats['CPU_Usage']
        }
        perf_data.append(perf_item)
        
        # 硬件监控表数据
        hw_item = {
            'Name': name,
            'Model': stats['Model'],
            'Host_IP': info['ip'],
            'Hardware_Health': stats['Hardware_Health']
        }
        hw_data.append(hw_item)
    
    return pd.DataFrame(perf_data), pd.DataFrame(hw_data)

def get_table_space():
    """从网页抓取相关信息"""
    print("Step 2: Scrapping table space information from web...")
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
    perf_df, hw_df = get_server_status(config_file)
    table_df = get_table_space()

    # 一键生成整合的 Excel
    print(f"Step 3: Generating integrated report: {report_name}")
    try:
        with pd.ExcelWriter(report_name, engine='openpyxl') as writer:
            if not perf_df.empty:
                perf_df.to_excel(writer, sheet_name='服务器性能监控', index=False)
            if not hw_df.empty:
                hw_df.to_excel(writer, sheet_name='服务器硬件健康', index=False)
            if not table_df.empty:
                table_df.to_excel(writer, sheet_name='数据库表空间')
        print("Success: Report generated successfully.")
    except Exception as e:
        print(f"Error generating Excel file: {e}")

if __name__ == "__main__":
    main()
