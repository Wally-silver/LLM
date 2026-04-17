# Industrial AI Agent (Windows-ready)

## 现在可在 Windows 本地运行（无需 vLLM）
默认 LLM 提供者已改为 **Ollama**：
- `LLM_PROVIDER=ollama`
- `OPENAI_COMPATIBLE_BASE_URL=http://localhost:11434`
- 默认模型：`qwen2.5:7b-instruct`

> 仍兼容 OpenAI/vLLM：把 `LLM_PROVIDER` 改为 `openai_compatible` 即可。

---

## 快速启动（Windows PowerShell）

```powershell
# 1) 安装并启动 Ollama（先在官网安装）
ollama pull qwen2.5:7b-instruct

# 2) 安装依赖
pip install -e .

# 3) 启动服务
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

---

## API
- `POST /ask`
- `POST /agent`
- `GET /health`
- `GET /datasources`
- `POST /datasources/ingest`
- `POST /datasources/bootstrap/windows-it-admin`
- `GET /tasks/windows-it-admin`
- `POST /rag/rebuild`

---

## 已内置真实 RAG 领域：Windows IT 管理

### 文档来源（Microsoft Learn）
1. WinGet 使用指南：
   - https://learn.microsoft.com/en-us/windows/package-manager/winget/
2. PowerShell 执行策略：
   - https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies
3. `sc.exe create`：
   - https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/sc-create
4. `netsh wlan`：
   - https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/netsh-wlan

### 一键导入该领域文档
```bash
curl -X POST http://127.0.0.1:8080/datasources/bootstrap/windows-it-admin
```

### 3~4 个具体任务（可直接问 `/ask` 或 `/agent`）
1. 使用 winget 安装/升级/卸载 VS Code。
2. 排查并修复 PowerShell 执行策略导致脚本无法运行。
3. 使用 `sc.exe` 创建/查询/配置/删除 Windows 服务。
4. 使用 `netsh wlan` 做 Wi-Fi 配置导出与故障诊断。

