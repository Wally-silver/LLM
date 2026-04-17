"""Windows IT 管理领域 RAG 数据包（仅文档源，不再提供任务模板）。"""

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

WINDOWS_IT_ADMIN_TASKS: list[str] = []
