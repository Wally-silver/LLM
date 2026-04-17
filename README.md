# Industrial AI Agent (Windows-ready)

## 现在可在 Windows 本地运行（无需 vLLM）
默认 LLM 提供者已改为 **Ollama**：
- `LLM_PROVIDER=ollama`
- `OPENAI_COMPATIBLE_BASE_URL=http://localhost:11434`
- 默认模型：`qwen2.5:7b-instruct`

> 仍兼容 OpenAI/vLLM：把 `LLM_PROVIDER` 改为 `openai_compatible` 即可。

## 快速启动（Windows PowerShell）
```powershell
ollama pull qwen2.5:7b-instruct
pip install -e .
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

## API
- `POST /ask`
- `POST /agent`
- `GET /health`
- `GET /datasources`
- `POST /datasources/ingest`
- `POST /datasources/bootstrap/windows-it-admin`
- `GET /tasks/windows-it-admin`
- `POST /datasources/bootstrap/advanced-reasoning`
- `GET /tasks/advanced-reasoning`
- `GET /datasets/catalog`
- `POST /rag/rebuild`

---

## 领域包 A：Windows IT 管理（真实文档）
### 文档来源（Microsoft Learn）
1. https://learn.microsoft.com/en-us/windows/package-manager/winget/
2. https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.core/about/about_execution_policies
3. https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/sc-create
4. https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/netsh-wlan

### 一键导入
```bash
curl -X POST http://127.0.0.1:8080/datasources/bootstrap/windows-it-admin
```

---

## 领域包 B：高级推理落地（多跳 / 多轮 / 个性化推荐 / 多模态）
### 一键导入
```bash
curl -X POST http://127.0.0.1:8080/datasources/bootstrap/advanced-reasoning
```

### 真实可用数据集/文档（可项目落地）
- HotpotQA: https://hotpotqa.github.io/
- 2WikiMultiHopQA: https://github.com/Alab-NII/2wikimultihop
- MuSiQue: https://huggingface.co/datasets/dwhiii/musique
- MultiWOZ: https://github.com/budzianowski/multiwoz
- ReDial: https://redialdata.github.io/website/download
- ScienceQA: https://github.com/lupantech/ScienceQA
- DocVQA: https://www.docvqa.org/datasets

### 4个具体任务
1. 多跳推理问答（HotpotQA/2Wiki/MuSiQue）
2. 多轮任务型问答（MultiWOZ）
3. 个性化会话推荐（ReDial）
4. 多模态知识推理（ScienceQA + DocVQA）

