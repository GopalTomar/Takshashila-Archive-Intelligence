"""Security: SSRF, path traversal, filename safety, signatures, secret redaction."""
from __future__ import annotations

import pytest

from app.security.crypto import decrypt_secret, encrypt_secret, mask_secret
from app.security.files import ensure_within, safe_filename, sniff_mime, validate_signature
from app.security.ssrf import SSRFError, validate_url


def test_ssrf_blocks_localhost_without_allowlist():
    with pytest.raises(SSRFError):
        validate_url("http://127.0.0.1/secret", allowed_domains=["example.com"])


def test_ssrf_blocks_private_ip():
    with pytest.raises(SSRFError):
        validate_url("http://192.168.0.1/", allowed_domains=[])


def test_ssrf_blocks_file_scheme():
    with pytest.raises(SSRFError):
        validate_url("file:///etc/passwd", allowed_domains=[])


def test_ssrf_allows_localhost_when_explicitly_allowed():
    # Fixture server case: explicit allowlist + allow_private.
    validate_url("http://127.0.0.1:8899/x", allowed_domains=["127.0.0.1"], allow_private=True)


def test_path_traversal_blocked(tmp_path):
    base = tmp_path / "store"
    base.mkdir()
    with pytest.raises(ValueError):
        ensure_within(base, base.parent / "etc" / "passwd")


def test_safe_filename():
    assert safe_filename("../../etc/passwd") == "etc_passwd"
    assert safe_filename("my file!.pdf") == "my_file_.pdf"


def test_signature_sniffing():
    assert sniff_mime(b"%PDF-1.7 ...") == "application/pdf"
    assert validate_signature(b"%PDF-1.7", "application/pdf")
    assert not validate_signature(b"NOTPDF", "application/pdf")


def test_secret_roundtrip_and_mask():
    token = encrypt_secret("gsk_supersecretkey")
    assert token != "gsk_supersecretkey"
    assert decrypt_secret(token) == "gsk_supersecretkey"
    assert mask_secret("gsk_supersecretkey").endswith("tkey")
    assert "supersecret" not in mask_secret("gsk_supersecretkey")


def test_logging_redacts_secrets(capsys):
    from app.logging_config import configure_logging, get_logger
    configure_logging()
    log = get_logger("test")
    log.info("provider_call", api_key="gsk_shouldnotappear", note="Bearer abcdef123456")
    captured = capsys.readouterr()
    assert "gsk_shouldnotappear" not in captured.out
    assert "[REDACTED]" in captured.out
