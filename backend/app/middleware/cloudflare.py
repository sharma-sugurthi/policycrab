"""
Cloudflare IP Trust Middleware

When Cloudflare is enabled, this middleware:
  1. Reads the real client IP from `CF-Connecting-IP` header
     (Cloudflare always sets this to the visitor's true IP)
  2. Overwrites `request.client` so all downstream code
     (rate limiting, logging, auth) sees the real IP
  3. Attaches CF metadata (CF-Ray, CF-IPCountry) to request.state
     for structured logging
  4. (Optional) Validates the connecting IP is actually a Cloudflare
     edge node — blocks direct-to-origin requests when cloudflare_only=True

Cloudflare IP ranges are published at:
  https://www.cloudflare.com/ips-v4  and  https://www.cloudflare.com/ips-v6

DDoS Protection (automatic, free tier):
  Cloudflare absorbs volumetric DDoS attacks at the edge (300+ Tbps capacity).
  Layer 7 HTTP floods are detected by ML and blocked automatically.
  This middleware does NOT need to implement DDoS logic — Cloudflare handles it
  before traffic ever reaches Heroku.
"""

import ipaddress
import logging
from dataclasses import dataclass

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)

# ── Cloudflare IPv4 and IPv6 ranges (as of 2026) ─────────────────
# Source: https://www.cloudflare.com/ips/
# These are updated infrequently. Last checked: 2026-07.
CLOUDFLARE_IPV4_RANGES = [
    "173.245.48.0/20",
    "103.21.244.0/22",
    "103.22.200.0/22",
    "103.31.4.0/22",
    "141.101.64.0/18",
    "108.162.192.0/18",
    "190.93.240.0/20",
    "188.114.96.0/20",
    "197.234.240.0/22",
    "198.41.128.0/17",
    "162.158.0.0/15",
    "104.16.0.0/13",
    "104.24.0.0/14",
    "172.64.0.0/13",
    "131.0.72.0/22",
]

CLOUDFLARE_IPV6_RANGES = [
    "2400:cb00::/32",
    "2606:4700::/32",
    "2803:f800::/32",
    "2405:b500::/32",
    "2405:8100::/32",
    "2a06:98c0::/29",
    "2c0f:f248::/32",
]

# Pre-parse into network objects for fast membership checks
_CF_NETWORKS = [
    ipaddress.ip_network(cidr)
    for cidr in CLOUDFLARE_IPV4_RANGES + CLOUDFLARE_IPV6_RANGES
]


def _is_cloudflare_ip(ip_str: str) -> bool:
    """Check if an IP address belongs to Cloudflare's published ranges."""
    try:
        addr = ipaddress.ip_address(ip_str)
        return any(addr in network for network in _CF_NETWORKS)
    except ValueError:
        return False


@dataclass
class _FakeClient:
    """Minimal stand-in for Starlette's client address tuple."""
    host: str
    port: int = 0


class CloudflareMiddleware(BaseHTTPMiddleware):
    """
    Starlette middleware that trusts Cloudflare's CF-Connecting-IP header.

    Args:
        app:              The ASGI application.
        enabled:          Master switch — when False, middleware is a no-op.
        cloudflare_only:  When True, reject requests NOT from Cloudflare IPs
                          with a 403. Use this after confirming all traffic
                          routes through CF to prevent direct-to-origin attacks.
    """

    def __init__(self, app, enabled: bool = False, cloudflare_only: bool = False):
        super().__init__(app)
        self.enabled = enabled
        self.cloudflare_only = cloudflare_only

        if enabled:
            logger.info(
                f"CloudflareMiddleware: ACTIVE "
                f"(cloudflare_only={'ON — blocking non-CF traffic' if cloudflare_only else 'OFF'})"
            )
        else:
            logger.info("CloudflareMiddleware: DISABLED (passthrough mode)")

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self.enabled:
            return await call_next(request)

        # ── Optional: Enforce Cloudflare-only access ──────────────
        if self.cloudflare_only:
            connecting_ip = request.client.host if request.client else "unknown"
            if not _is_cloudflare_ip(connecting_ip):
                logger.warning(
                    f"CloudflareMiddleware: Blocked non-CF request from {connecting_ip}"
                )
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Direct access not allowed. Use the domain."},
                )

        # ── Extract real client IP from CF header ─────────────────
        real_ip = request.headers.get("cf-connecting-ip")
        if real_ip:
            # Overwrite the Starlette client so all downstream code
            # (rate_limit.py, logging middleware, auth) sees the real IP
            request.scope["client"] = (real_ip, 0)

        # ── Attach CF metadata to request.state for logging ───────
        request.state.cf_ray = request.headers.get("cf-ray", "")
        request.state.cf_country = request.headers.get("cf-ipcountry", "")

        return await call_next(request)
