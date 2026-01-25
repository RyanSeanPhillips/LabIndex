# 11 — Plugins & Iteration (Hot-Swap without Reload)

## Goal
Rapid iteration by selecting implementations at runtime, not reloading modules inside Qt.

## Registries
- ExtractorRegistry
- LinkerRegistry
- RankerRegistry
- AgentPlannerRegistry
- TokenizerRegistry

## Versioning
- extraction_version
- strategy_version
- llm_prompt_version
- preserve prior outputs for A/B comparisons

## Optional worker-process
Run pipeline workers in a separate process so you can restart them to load new code without restarting the UI.
