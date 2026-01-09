# 服务器月报脚本使用指南 (小白版)

本指南将手把手教你如何从零开始配置环境并运行 `server_monthly_report.py` 脚本。

## 1. 安装 Python 环境 (推荐使用 Miniconda)

Miniconda 是一个轻量级的 Python 管理工具，非常适合零基础用户。

1.  **下载**: 访问 [Miniconda 官网](https://docs.conda.io/en/latest/miniconda.html)，下载 Windows 版的 **Miniconda3 Windows 64-bit** 安装包。
2.  **安装**: 双击安装包，一路点击 "Next"。
    *   **注意**: 在 "Advanced Options" 界面，建议勾选 "Add Miniconda3 to my PATH environment variable" (虽然它显示红色不建议，但勾选后在命令行直接输入指令更方便)。
3.  **验证**: 按下键盘上的 `Win + R` 键，输入 `cmd` 并回车。在黑窗口中输入 `conda --version`，如果显示版本号，说明安装成功。

## 2. 配置脚本运行环境

在刚才的黑窗口 (命令行) 中，依次输入以下指令：

```bash
# 1. 创建一个名为 report 的虚拟环境
conda create -n report python=3.10 -y

# 2. 激活这个环境
conda activate report

# 3. 安装脚本需要的依赖包 (直接复制下面这一行)
pip install pandas paramiko openpyxl lxml html5lib
```

## 3. 准备配置文件

在脚本所在的文件夹中，确保有一个名为 `config.ini` 的文件。其格式如下：

```ini
[服务器名称1]
host = 192.168.1.1
user = root
password = 你的密码

[服务器名称2]
host = 192.168.1.2
user = root
password = 你的密码
```
> [!TIP]
> 你可以根据需要添加任意多个服务器。

## 4. 运行脚本

1.  打开存放 `server_monthly_report.py` 的文件夹。
2.  在文件夹地址栏输入 `cmd` 并回车，打开命令行窗口。
3.  输入以下指令运行：
    ```bash
    conda activate report
    python server_monthly_report.py
    ```

## 5. 查看结果

脚本运行成功后，文件夹下会生成一个名为 `server_monthly_report_202601.xlsx` (日期会随月份变化) 的文件。
*   **Sheet1 (服务器磁盘使用)**: 列出所有服务器的硬盘剩余情况。
*   **Sheet2 (数据库表空间)**: 列出网页抓取的数据库表空间使用率。

---
> [!NOTE]
> 如果以后再次使用，只需执行第 4 步即可。
