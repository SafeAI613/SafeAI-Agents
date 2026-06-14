"""Package init.

Configures TLS at import time for environments behind an SSL-inspection proxy
(e.g. Netfree, Zscaler, Netskope). Such proxies use a MITM root CA that the OS trusts
but whose certificate lacks the X.509 keyUsage extension — which Python 3.13+ rejects
by default (strict RFC 5280 enforcement). This runs on any entry point (CLI, server,
evals, tests) because importing the `core` package triggers it.

Opt out with the env var AGENTS_NO_TLS_FIX=1.
"""

from __future__ import annotations

import os
import ssl


def _configure_tls() -> None:
    if os.environ.get("AGENTS_NO_TLS_FIX") == "1":
        return

    # Preferred: use the OS trust store via truststore. On Windows this uses SChannel,
    # which already trusts the proxy's root CA and does not enforce OpenSSL's strict
    # keyUsage check. Full verification (chain/hostname/expiry) is preserved.
    try:
        import truststore
        truststore.inject_into_ssl()
        return
    except Exception:
        pass

    # Fallback (truststore not installed): relax only the RFC 5280 strict flag that
    # rejects CA certs missing keyUsage. Certificate verification stays ON.
    if hasattr(ssl, "VERIFY_X509_STRICT"):
        _orig = ssl.create_default_context

        def _ctx(*args, **kwargs):
            c = _orig(*args, **kwargs)
            c.verify_flags &= ~ssl.VERIFY_X509_STRICT
            return c

        ssl.create_default_context = _ctx


_configure_tls()