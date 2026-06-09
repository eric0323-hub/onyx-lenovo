from unittest.mock import patch

import litellm

from onyx.llm.litellm_singleton.config import register_ollama_models


def test_register_ollama_models_does_not_probe_model_info() -> None:
    model_cost: dict = {}

    with (
        patch.object(litellm, "model_cost", model_cost),
        patch.object(litellm, "register_model") as register_model_mock,
    ):
        register_ollama_models()

    register_model_mock.assert_not_called()
    assert model_cost["ollama_chat/qwen3-coder:latest"][
        "supports_function_calling"
    ] is True
    assert model_cost["ollama/qwen3-coder:latest"]["supports_function_calling"] is True
