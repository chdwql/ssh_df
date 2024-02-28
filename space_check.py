import configparser
import paramiko

def read_config(filename):
    """
    从配置文件中读取参数，并使用SSH连接执行命令。

    Args:
        filename (str): 配置文件的路径。

    Returns:
        dict: 包含每个配置段执行命令结果的字典，以配置段名称作为键。

    """
    config = configparser.ConfigParser()
    config.read(filename)

    results = {}
    
    for section in config.sections():
        # 从配置文件中读取参数
        host = config.get(section, 'host')
        user = config.get(section, 'user')
        password = config.get(section, 'password')

        # SSH连接和执行命令
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        print(f'checking host {host}...')
        ssh.connect(hostname=host, port=22, username=user, password=password)
        # stdin, stdout, stderr = ssh.exec_command("df -h --total | grep '^total'")
        stdin, stdout, stderr = ssh.exec_command("[ -d '/usr/local/bin' ] && /usr/local/bin/df -h --total | grep '^total' || df -h --total | grep '^total'")
        res, err = stdout.read(), stderr.read()
        result = res if res else err
        ssh.close()

        # 将结果添加到字典中
        results[section] = result.decode()
    
    return results
