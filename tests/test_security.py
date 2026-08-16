"""Security policy and Zero-Trust egress validation tests."""

from __future__ import annotations

import pytest

from xyo import XyoClientException
from xyo.security import DownloadSecurityPolicy, validate_api_user


@pytest.mark.parametrize(
    "url",
    [
        "https://api.xyo.financial/batches/archive.tar.gz",
        "https://download.xyo.financial/batches/archive.tar.gz",
        "https://xyo-financial.s3.amazonaws.com/batches/archive.tar.gz",
        "https://xyo-financial.s3.us-east-1.amazonaws.com/batches/archive.tar.gz",
    ],
)
def test_trusted_download_urls_pass(url: str) -> None:
    policy = DownloadSecurityPolicy("https://api.xyo.financial")
    validated = policy.validate_download_url(url)
    assert validated == url


@pytest.mark.parametrize(
    "url",
    [
        "http://api.xyo.financial/batches/archive.tar.gz",
        "ftp://api.xyo.financial/batches/archive.tar.gz",
        "file:///etc/passwd",
        "gopher://api.xyo.financial",
    ],
)
def test_insecure_schemes_rejected(url: str) -> None:
    policy = DownloadSecurityPolicy("https://api.xyo.financial")
    with pytest.raises(XyoClientException) as exc_info:
        policy.validate_download_url(url)
    assert exc_info.value.status_code == 400


@pytest.mark.parametrize(
    "url",
    [
        "https://malicious-attacker.com/archive.tar.gz",
        "https://evil.s3.amazonaws.com/archive.tar.gz",
        "https://api.xyo.financial.attacker.com/archive.tar.gz",
    ],
)
def test_untrusted_hosts_rejected(url: str) -> None:
    policy = DownloadSecurityPolicy("https://api.xyo.financial")
    with pytest.raises(XyoClientException) as exc_info:
        policy.validate_download_url(url)
    assert exc_info.value.status_code == 400
    assert "not in the trusted domain allowlist" in exc_info.value.message


def test_custom_trusted_host_passes() -> None:
    policy = DownloadSecurityPolicy(
        "https://api.xyo.financial",
        custom_trusted_hosts=["storage.internal.bank.corp"],
    )
    validated = policy.validate_download_url("https://storage.internal.bank.corp/batches/archive.tar.gz")
    assert "storage.internal.bank.corp" in validated


def test_external_storage_host_identification() -> None:
    policy = DownloadSecurityPolicy("https://api.xyo.financial")
    assert not policy.is_external_storage_host("api.xyo.financial")
    assert policy.is_external_storage_host("download.xyo.financial")
    assert policy.is_external_storage_host("xyo-financial.s3.amazonaws.com")


def test_validate_api_user_crlf_rejected() -> None:
    with pytest.raises(XyoClientException) as exc_info:
        validate_api_user("user\r\nInjected-Header: evil")
    assert exc_info.value.status_code == 400
    assert "CRLF injection" in exc_info.value.message
