# Trainer Service

Offline training pipeline for LoRA adapters using SFT and DPO recipes orchestrated via Hydra configurations.

## Planned components
- Data loaders that hydrate Hugging Face datasets from Parquet
- Training scripts wrapping TRL + PEFT with MLflow tracking
- Safety fine-tuning stages and replay buffer management
- Artifact publishing back to storage for deployment
