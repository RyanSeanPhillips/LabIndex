# 10 — PyQt6 UI + MVVM Design

## Two primary tabs
1. **Index & Build** (operator view)
   - roots/scope + tier selection
   - start/pause/stop
   - progress + jobs/errors
   - safety checks
2. **Search & Explore** (end-user view)
   - search bar + filters
   - results list/table
   - inspector (metadata + snippet + related)
   - graph view (contextual)
   - agent chat (tool-using)

## MVVM mapping
- **Model (core):** repositories + services + ReadOnlyFS + agent tools
- **ViewModels:** IndexStatusVM, SearchVM, GraphVM, InspectorVM, AgentVM
- **Views:** Qt widgets only; no DB/FS logic

## Graph behavior
- contextual subgraphs only (avoid “entire drive graph”)
- modes: Structure vs Relationships vs Entities (optional)

## Threading
- no network I/O on UI thread
- use QThreadPool/QRunnable (or worker process)
- DB writes serialized (DB thread) or per-thread connections
