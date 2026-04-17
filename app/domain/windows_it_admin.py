"""Windows IT 管理领域 RAG 数据包。"""

WINDOWS_IT_ADMIN_SOURCES = [
    {
        "doc_id": "winget-overview",
        "source_type": "url",
        "source_value": "https://learn.microsoft.com/en-us/windows/package-manager/winget/",
        "task_tags": ["software_install", "package_management"],
    },
    {
        "doc_id": "powershell-execution-policy",
        "source_type": "url",
        "source_value": "https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies",
        "task_tags": ["script_policy", "powershell"],
    },
    {
        "doc_id": "windows-sc-create",
        "source_type": "url",
        "source_value": "https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/sc-create",
        "task_tags": ["service_management"],
    },
    {
        "doc_id": "windows-netsh-wlan",
        "source_type": "url",
        "source_value": "https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/netsh-wlan",
        "task_tags": ["network_troubleshooting", "wifi"],
    },
]

WINDOWS_IT_ADMIN_TASKS = [
    "任务1：根据文档给出使用 winget 安装/升级/卸载 VS Code 的完整命令与注意事项。",
    "任务2：排查并修复 PowerShell 脚本被执行策略阻止的问题，区分 Process / CurrentUser / LocalMachine。",
    "任务3：创建并管理 Windows 服务（sc.exe create/query/config/delete）的安全操作步骤。",
    "任务4：使用 netsh wlan 进行 Wi-Fi 配置与故障诊断（查看配置、导出配置、生成报告）。",
]
