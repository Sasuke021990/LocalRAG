"""
SSRF-safe URL validation — shared by any feature that has the backend fetch
a user-supplied URL (currently: webhook delivery).

Requires https and resolves the hostname to reject loopback, link-local
(this range includes the 169.254.169.254 cloud metadata endpoint), private,
multicast, and reserved address ranges, via Python's own IP classification
rather than a manually maintained CIDR list.

Callers should re-run this at *delivery* time as well as at registration
time — DNS can change between the two (rebinding): a hostname that resolved
safely when the webhook was created is not guaranteed to still resolve
safely when it's actually POSTed to.
"""

import ipaddress
import socket
from urllib.parse import urlparse


def _is_unsafe_ip(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return True  # unparseable -- treat as unsafe rather than let it through
    return (
        ip.is_private or ip.is_loopback or ip.is_link_local
        or ip.is_multicast or ip.is_reserved or ip.is_unspecified
    )


def is_safe_external_url(url: str) -> bool:
    """
    True only if ``url`` is an ``https://`` URL whose hostname resolves
    exclusively to public, non-internal addresses. Checks *every* address a
    hostname resolves to (A and AAAA) — a malicious or misconfigured host
    could return one public address alongside an internal one.
    """
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme != "https":
        return False
    if not parsed.hostname:
        return False
    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except (socket.gaierror, UnicodeError):
        return False
    if not infos:
        return False
    return not any(_is_unsafe_ip(info[4][0]) for info in infos)
