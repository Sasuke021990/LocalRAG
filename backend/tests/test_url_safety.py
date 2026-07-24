"""
Tests for utils.url_safety (SSRF guard used by webhook registration/delivery).

Uses IP literals (no DNS involved at all -- socket.getaddrinfo parses an IP
string locally) and a mocked resolver for the hostname-resolution path, so
this suite has no real network dependency and can't be flaky in an
offline/CI environment.
"""

from utils import url_safety


class TestSchemeAndShape:
    def test_rejects_non_https_scheme(self):
        assert url_safety.is_safe_external_url("http://8.8.8.8/x") is False
        assert url_safety.is_safe_external_url("ftp://8.8.8.8/x") is False

    def test_rejects_missing_hostname(self):
        assert url_safety.is_safe_external_url("https:///no-host") is False

    def test_rejects_unparseable_url(self):
        assert url_safety.is_safe_external_url("not a url at all") is False


class TestIpLiteralClassification:
    """No DNS needed -- getaddrinfo on an IP literal just parses it locally."""

    def test_loopback_rejected(self):
        assert url_safety.is_safe_external_url("https://127.0.0.1/x") is False
        assert url_safety.is_safe_external_url("https://[::1]/x") is False

    def test_cloud_metadata_link_local_rejected(self):
        # 169.254.169.254 -- the AWS/GCP/Azure instance-metadata endpoint,
        # inside the broader 169.254.0.0/16 link-local range.
        assert url_safety.is_safe_external_url("https://169.254.169.254/latest/meta-data/") is False

    def test_private_ranges_rejected(self):
        for ip in ("10.0.0.5", "172.16.0.5", "192.168.1.5"):
            assert url_safety.is_safe_external_url(f"https://{ip}/x") is False, ip

    def test_unique_local_ipv6_rejected(self):
        assert url_safety.is_safe_external_url("https://[fc00::1]/x") is False

    def test_public_ip_allowed(self):
        # 8.8.8.8 -- a long-standing, stable public address (Google DNS);
        # used only as a known-public IP literal, no actual DNS lookup.
        assert url_safety.is_safe_external_url("https://8.8.8.8/x") is True


class TestHostnameResolution:
    """Mocks socket.getaddrinfo so hostname-based checks are hermetic too."""

    def test_hostname_resolving_to_public_ip_allowed(self, monkeypatch):
        # 8.8.8.8 -- a real, non-reserved public IP (not one of the RFC
        # 5737 documentation ranges like 203.0.113.0/24, which Python's
        # ipaddress module correctly classifies as private/reserved).
        monkeypatch.setattr(
            url_safety.socket, "getaddrinfo",
            lambda host, port: [(2, 1, 6, "", ("8.8.8.8", 0))],
        )
        assert url_safety.is_safe_external_url("https://example.com/hook") is True

    def test_hostname_resolving_to_internal_ip_rejected(self, monkeypatch):
        monkeypatch.setattr(
            url_safety.socket, "getaddrinfo",
            lambda host, port: [(2, 1, 6, "", ("10.0.0.5", 0))],
        )
        assert url_safety.is_safe_external_url("https://internal.example.com/hook") is False

    def test_hostname_with_one_internal_and_one_public_address_rejected(self, monkeypatch):
        # A hostname returning multiple A/AAAA records where *any* of them
        # is internal must be rejected -- an attacker (or a rebinding DNS
        # server) only needs one of the resolved addresses to be internal.
        monkeypatch.setattr(
            url_safety.socket, "getaddrinfo",
            lambda host, port: [
                (2, 1, 6, "", ("203.0.113.5", 0)),
                (2, 1, 6, "", ("169.254.169.254", 0)),
            ],
        )
        assert url_safety.is_safe_external_url("https://mixed.example.com/hook") is False

    def test_unresolvable_hostname_rejected(self, monkeypatch):
        import socket as socket_module

        def _raise(host, port):
            raise socket_module.gaierror("name or service not known")

        monkeypatch.setattr(url_safety.socket, "getaddrinfo", _raise)
        assert url_safety.is_safe_external_url("https://does-not-resolve.invalid/hook") is False
