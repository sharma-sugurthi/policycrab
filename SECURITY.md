# Security Policy

PolicyCrab is designed to handle sensitive healthcare data. This document outlines the security measures implemented across the platform.

## Data Privacy (PHI & PII)

- **Regex & Presidio Scrubbing**: The backend uses local Regex and Microsoft Presidio to scrub Protected Health Information (PHI) and Personally Identifiable Information (PII) from user documents *before* any data is sent to external LLM providers.
- **Data Minimization**: AI models are strictly instructed not to record patient names or identifiable IDs in output artifacts.
- **No Third-Party Retention**: API calls to primary LLM providers (Google Gemini) are configured as zero-retention (API data is not used for model training).

## Authentication & Authorization

- **Supabase Auth**: All user sessions are managed securely by Supabase via JSON Web Tokens (JWT).
- **Row Level Security (RLS)**: The PostgreSQL database implements strict RLS policies. Users can only read, write, and query their own documents, policies, and claim history.
- **Admin Access**: Administrative endpoints are explicitly gated. Users must possess the `admin` role in their JWT app metadata to access dashboard analytics.

## Infrastructure & API Security

- **Cloudflare Edge Protection**: When enabled, Cloudflare intercepts DDoS attacks, malicious bot traffic, and enforces strict SSL/TLS encryption.
- **IP Allowlisting (Zero Trust)**: The FastAPI backend includes a `CloudflareMiddleware` that optionally blocks any incoming requests that do not originate from verified Cloudflare IP blocks, preventing direct-to-origin bypass attacks.
- [x] Rate Limiting: Built-in endpoints are rate-limited to prevent abuse and API exhaustion.

## Enterprise AI Security Framework (EASF)

PolicyCrab implements a deterministic "Zero Trust" boundary for its non-deterministic AI agents to defend against Prompt Injection and unauthorized autonomous execution.

- **Prompt Injection Shields (`prompt_shields.py`)**: Uses ultra-fast compiled regex heuristics to intercept known jailbreak and indirect prompt injection patterns in both user input and RAG context before it reaches the LLM.
- **Deterministic Policy Engine (`policy_engine.py`)**: AI Agents cannot execute tools or sensitive actions directly. They must format a `ProposedAction` and request permission. The Policy Engine evaluates this deterministically.
- **AI Security Gateway (`ai_gateway.py`)**: A centralized middleware intercepting all AI interactions, running the prompt shields on the input and the policy engine on the output.
- **Human-in-the-Loop (`REQUIRE_APPROVAL`)**: High-risk actions, such as generating/submitting legal appeals, trigger a deterministic halt, moving the action to a human approval queue.
- **Persistent Audit Logging (`audit_logger.py`)**: Every action proposed by an AI agent and the resulting deterministic policy decision is logged in structured JSON, optimized for ingestion by SIEMs (e.g., Google Cloud Logging).
