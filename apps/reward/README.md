# Reward Service

Service responsible for computing implicit and explicit rewards, orchestrating LLM-judge evaluations, and persisting preference tuples.

## Planned components
- Metric calculators (edit distance, time-to-send, escalation penalties)
- LLM-as-judge batch jobs with caching and consensus strategies
- Preference tuple builder for DPO/IPO datasets
- APIs to expose reward distributions and health metrics
