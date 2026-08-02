# Changelog

All notable changes to the PolicyCrab platform will be documented in this file.

## [1.0.0] - 2026-08-02
### Added
- **Interactive AI Appeal Studio**: Line-by-line revision interface for AI-generated appeals with "Assertive", "State Penalties", "Simplify", and "Medical Urgency" modifiers.
- **Dossier Bundler**: Compiles the draft appeal letter, EOB highlights, policy contradictions, and regulatory citations into a structured PDF dossier.
- **Admin Analytics Dashboard**: Role-gated backend observability for platform admins.
- **Bill Auditor & Document Vault**: Persistent storage of bills and medical records synced securely to Supabase.
- **Carrier Routing Hub**: Dynamic network status lookups and statutory appeal deadline tracking.
- **Synthetic Benchmark Suite**: 200+ simulated claims (UPCD, COSM, NSA, LMIT, EMRG) for accuracy testing.
- **Multi-LLM Fallback Matrix**: Intelligent routing between Gemini 2.5 Pro, Llama 3, and Gemma models to ensure 100% uptime and bypass rate limits.
- **Empathetic Error Handling**: Resilient UX that gracefully catches backend errors and translates them into friendly patient-facing messages.
- **User Profile System**: Metadata-driven settings page backed by Supabase Auth.
