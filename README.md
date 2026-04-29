# Automated Folder/Directory Access Provisioning

A multi-agent system that automates the IT support workflow for granting,
denying, or escalating access requests to shared folders and AD groups.

Built with **LangGraph**, **OpenAI GPT-4**, and **ChromaDB** for RAG.

## Architecture

```
                       ┌─────────────────┐
   User request ─────► │  Intake Agent   │  classify + extract entities
                       └────────┬────────┘
                                │
                       ┌────────▼────────┐
                       │ Knowledge Agent │  RAG over policy KB → recommendation
                       └────────┬────────┘
                                │
                          (router decides)
                  ┌─────────────┼─────────────┐
                  ▼             ▼             ▼
           ┌──────────┐  ┌────────────┐  ┌────────────┐
           │ Workflow │  │ Escalation │  │ Escalation │
           │  (auto)  │  │  (review)  │  │   (deny)   │
           └────┬─────┘  └──────┬─────┘  └──────┬─────┘
                │               │               │
                └───────────────┼───────────────┘
                                ▼
                        Final response + audit log
```

### Agents

| Agent       | Responsibility                                          | Tools                          |
|-------------|---------------------------------------------------------|--------------------------------|
| Intake      | Parse free-text request → structured fields, classify   | LLM only                       |
| Knowledge   | Retrieve policies (RAG) + recommend action              | ChromaDB, embeddings, LLM      |
| Workflow    | Execute provisioning, audit, notify ticketing system    | Mock AD, mock Jira, audit log  |
| Escalation  | Route to humans, draft tickets, communicate decisions   | Mock Jira, audit log, LLM      |

## Quick Start

### 1. Install

```bash
cd folder_access_agent
python -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
# Edit .env and set OPENAI_API_KEY
```

### 3. Build the RAG index

```bash
python -m rag.ingest
```

This embeds the markdown files in `knowledge_base/` into a local Chroma index.

### 4. Run the demo

**Streamlit UI** (recommended for demos):
```bash
streamlit run app.py
```

**CLI demo** (good for testing):
```bash
python run_demo.py
```

**Run the test scenarios**:
```bash
pytest tests/ -v
```

## Project Layout

```
folder_access_agent/
├── app.py                      # Streamlit UI
├── run_demo.py                 # CLI demo runner
├── config.py                   # Settings + env loading
├── agents/
│   ├── state.py                # Shared LangGraph state
│   ├── intake.py               # Intake Agent
│   ├── knowledge.py            # Knowledge Agent (RAG)
│   ├── workflow.py             # Workflow Agent
│   ├── escalation.py           # Escalation Agent
│   └── orchestrator.py         # LangGraph builder
├── rag/
│   ├── ingest.py               # Build Chroma index
│   └── retriever.py            # Query Chroma
├── integrations/
│   ├── active_directory.py     # Mock AD adapter
│   ├── jira_client.py          # Mock Jira adapter
│   └── audit_log.py            # JSONL audit log
├── knowledge_base/             # Markdown policy docs (the RAG corpus)
├── data/                       # Mock users / groups / state
├── docs/
│   ├── ARCHITECTURE.md
│   ├── UX_WIREFRAMES.md
│   └── METRICS.md
└── tests/
    └── test_scenarios.py
```

## How RAG Grounds the Agents

The Knowledge Agent never answers from the LLM's parametric memory. Every
policy claim is grounded in a chunk retrieved from ChromaDB and surfaced to
the user as a citation. This is the primary defense against hallucinated
"policy" that doesn't exist in your actual SOPs.

The corpus in `knowledge_base/` is a small but realistic IT policy set:
access policies, compliance rules (SOX/PII/HIPAA), the AD group catalog,
escalation runbooks, and an FAQ. Replace these markdown files with your
real policy library to point the system at production data.

## Mocked Integrations

`integrations/active_directory.py` and `integrations/jira_client.py` are
realistic stubs: they read/write `data/groups.json` and `data/tickets.json`
and emit the same data shapes a real adapter would. Swap them for real
LDAP/Jira clients without changing any agent code.

## Why This Design

**Separation of concerns** — Each agent has one job. Adding a new
compliance check means a new node in the graph, not a new branch in a
1,000-line function.

**Auditability** — Every state transition writes to `audit_log.jsonl`.
Compliance can replay any decision and see which policy chunks were
retrieved and which agent made which call.

**Swap-friendly** — LLM provider, vector DB, and integrations are behind
small interfaces. Move from ChromaDB to Pinecone or from mock AD to real
LDAP without touching the agent layer.

## Reference

See `docs/ARCHITECTURE.md` for the full agent contract, `docs/UX_WIREFRAMES.md`
for the UI mockups, and `docs/METRICS.md` for how to measure success.
