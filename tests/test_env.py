"""Tests for the tiny ``.env`` loader and its wiring into ``ModelConfig``."""

from __future__ import annotations

import os

import app.env as env_module
from app.env import find_dotenv, load_dotenv, parse_dotenv
from app.providers.config import ModelConfig, ModelProviderType


def test_parse_dotenv_basic() -> None:
    parsed = parse_dotenv(
        "\n".join(
            [
                "# a comment",
                "",
                "MODEL_PROVIDER=anthropic",
                "export ANTHROPIC_MODEL=claude-test-model",
                'ANTHROPIC_API_KEY="sk-ant-fake-quoted"',
                "ANTHROPIC_TEMPERATURE='0.3'",
                "IGNORED LINE WITHOUT EQUALS",
            ]
        )
    )
    assert parsed == {
        "MODEL_PROVIDER": "anthropic",
        "ANTHROPIC_MODEL": "claude-test-model",
        "ANTHROPIC_API_KEY": "sk-ant-fake-quoted",
        "ANTHROPIC_TEMPERATURE": "0.3",
    }


def test_load_dotenv_does_not_override_existing_env(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(env_module, "_loaded_paths", set())
    monkeypatch.setenv("ANTHROPIC_MODEL", "from-real-env")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "ANTHROPIC_MODEL=from-file\nANTHROPIC_API_KEY=sk-ant-fake-from-file\n"
    )

    loaded = load_dotenv(dotenv)

    assert loaded["ANTHROPIC_MODEL"] == "from-file"
    # real env wins:
    assert os.environ["ANTHROPIC_MODEL"] == "from-real-env"
    # missing key is filled from the file:
    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-fake-from-file"


def test_load_dotenv_override(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(env_module, "_loaded_paths", set())
    monkeypatch.setenv("ANTHROPIC_MODEL", "from-real-env")
    dotenv = tmp_path / ".env"
    dotenv.write_text("ANTHROPIC_MODEL=from-file\n")

    load_dotenv(dotenv, override=True)

    assert os.environ["ANTHROPIC_MODEL"] == "from-file"


def test_load_dotenv_missing_file_is_noop(tmp_path) -> None:
    assert load_dotenv(tmp_path / "nope.env") == {}


def test_find_dotenv_walks_upward(tmp_path) -> None:
    (tmp_path / ".env").write_text("X=1\n")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert find_dotenv(nested) == tmp_path / ".env"


def test_model_config_from_env_reads_dotenv(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(env_module, "_loaded_paths", set())
    for key in (
        "MODEL_PROVIDER",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_MODEL",
        "ANTHROPIC_MAX_TOKENS",
        "ANTHROPIC_TEMPERATURE",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "MODEL_PROVIDER=anthropic\n"
        "ANTHROPIC_API_KEY=sk-ant-fake-not-real\n"
        "ANTHROPIC_MODEL=claude-test-model\n"
    )

    config = ModelConfig.from_env()

    assert config.provider is ModelProviderType.ANTHROPIC
    assert config.api_key == "sk-ant-fake-not-real"
    assert config.model == "claude-test-model"


def test_model_config_from_env_can_skip_dotenv(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(env_module, "_loaded_paths", set())
    monkeypatch.delenv("MODEL_PROVIDER", raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("MODEL_PROVIDER=anthropic\n")

    config = ModelConfig.from_env(use_dotenv=False)

    assert config.provider is ModelProviderType.MOCK
