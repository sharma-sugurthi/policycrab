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
- **Rate Limiting**: Built-in endpoints are rate-limited to prevent abuse and API exhaustion.
