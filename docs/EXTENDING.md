# Extending the system

The system is built to be expanded by dropping files in, with no core edits.

## Add a data source / tool
Create `tools/plugins/<name>.py` defining `register(reg)`:

```python
async def my_tool(**params):
    return {"value": 42, "source": "...", "stale": False}

def register(reg):
    reg.register("my_tool", my_tool)
```

It's auto-loaded at startup and callable by any agent. (See
`tools/plugins/example_plugin.py.txt`.) A bad plugin is logged and skipped, never
breaks startup.

## Add an agent
Create `agents/briefings/<Name>.md`:

```markdown
---
name: EnergyAgent
profile: default          # default | dev (which model)
schedule: cycle           # cycle | idle | off
enabled: true
tools:
  - name: gdelt_search
    params: {query: "energy policy grid buildout", max_records: 10}
  - name: web_search
    params: {query: "electricity demand forecast"}
---
You are the EnergyAgent. Track power markets and policy... (this body is the system prompt)
```

It runs next cycle. Core agent names are reserved. The **MetaAgent** writes these
files itself during idle time to fill gaps. You can also create/list them from the
dashboard (`/api/briefings`).

## Add a quant method
The **QuantResearchAgent** writes/runs/saves its own methods to
`quant/scripts/library/` during idle time. To hand-add one, drop a module in
`quant/` and call it from an agent or the backtester.

## Change behavior / settings
Everything is in `config/*.yaml` and editable live from the dashboard **Settings**
tab (hot-reloaded, no restart). `STRATEGY.md` is the human-readable rulebook the
agents must obey.

## Architecture extension points
- **Model backend**: implement `models_adapter/base.LLMBackend` (LM Studio / OpenAI /
  Anthropic exist) and register it in `ModelRouter`.
- **Execution venue**: implement `execution/base.ExecutionAdapter` (dry exists;
  a live broker like IBKR is a drop-in).
- **Schemas**: all agent I/O is Pydantic in `schemas/models.py`.
- Agents communicate only via the blackboard; add one without touching others.
