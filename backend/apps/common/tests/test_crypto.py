"""Tests for apps.common.crypto."""
from apps.common import crypto


def test_encrypt_decrypt_round_trip():
    plaintext = "supersecret-token-value"
    token = crypto.encrypt(plaintext)
    assert token != plaintext
    assert crypto.decrypt(token) == plaintext


def test_decrypt_empty_returns_empty():
    assert crypto.decrypt("") == ""


def test_decrypt_invalid_returns_empty():
    assert crypto.decrypt("not-a-valid-fernet-token") == ""


def test_hash_secret_deterministic():
    assert crypto.hash_secret("abc") == crypto.hash_secret("abc")
    assert crypto.hash_secret("abc") != crypto.hash_secret("abd")


def test_generate_token_has_prefix():
    token = crypto.generate_token("verify")
    assert token.startswith("verify_")
    assert len(token) > len("verify_")
