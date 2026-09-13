"""Frontend development must not inherit backend credentials."""

import pytest

from scripts.dev import web_environment


@pytest.mark.parametrize(
    "name",
    [
        "WALLY_DATABASE_URL",
        "WALLY_REDIS_URL",
        "WALLY_ENCRYPTION_KEY",
        "WALLY_BOOTSTRAP_TOKEN",
        "WALLY_FUTURE_PROVIDER_SECRET",
        "wally_encryption_key",
        "Wally_Bootstrap_Token",
    ],
)
def test_backend_and_unknown_settings_are_not_inherited(name: str) -> None:
    source = {"PATH": "test-bin", name: "synthetic-test-only"}

    assert web_environment(source) == {"PATH": "test-bin"}
    assert source[name] == "synthetic-test-only"


@pytest.mark.parametrize("key", ["WALLY_DEV_API", "wally_dev_api"])
def test_explicit_proxy_setting_and_runtime_environment_are_preserved(key: str) -> None:
    source = {
        "PATH": "test-bin",
        "SYSTEMROOT": "test-windows",
        "NODE_ENV": "development",
        key: "http://127.0.0.1:8000",
        "WALLY_DATABASE_URL": "synthetic-test-only",
    }

    assert web_environment(source) == {
        "PATH": "test-bin",
        "SYSTEMROOT": "test-windows",
        "NODE_ENV": "development",
        "WALLY_DEV_API": "http://127.0.0.1:8000",
    }


def test_web_environment_is_an_independent_copy() -> None:
    source = {"PATH": "test-bin"}
    result = web_environment(source)
    result["PATH"] = "changed-bin"

    assert source == {"PATH": "test-bin"}
