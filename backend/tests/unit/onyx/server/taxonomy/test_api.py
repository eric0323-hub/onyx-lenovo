from io import BytesIO
from uuid import UUID

import pytest
from fastapi import UploadFile

from onyx.configs.constants import CELERY_TAXONOMY_ARTICLE_IMPORT_TASK_EXPIRES
from onyx.configs.constants import FileOrigin
from onyx.configs.constants import OnyxCeleryPriority
from onyx.configs.constants import OnyxCeleryQueues
from onyx.configs.constants import OnyxCeleryTask
from onyx.db import taxonomy_generation_config
from onyx.server.taxonomy import api
from onyx.taxonomy.models import GenerateTaxonomyDraftRequest
from onyx.taxonomy.models import TaxonomyGenerationConfig
from onyx.taxonomy.models import TaxonomyGenerationRuntimeConfig


class _FakeFileStore:
    def __init__(self) -> None:
        self.saved: list[tuple[str | None, FileOrigin, str]] = []

    def save_file(
        self,
        *,
        content,
        display_name: str | None,
        file_origin: FileOrigin,
        file_type: str,
    ) -> str:
        content.read()
        self.saved.append((display_name, file_origin, file_type))
        return f"stored-{len(self.saved)}"


class _FakeUser:
    id = UUID("00000000-0000-0000-0000-000000000001")


class _FakeKvStore:
    def __init__(self, stored: dict[str, object] | None = None) -> None:
        self.stored = stored or {}

    def load(
        self,
        _key: str,
        refresh_cache: bool = False,
    ) -> dict[str, object]:
        _ = refresh_cache
        return self.stored

    def store(self, _key: str, val: object, encrypt: bool = False) -> None:
        _ = encrypt
        self.stored = val


def _upload_file(name: str, content_type: str = "text/markdown") -> UploadFile:
    return UploadFile(
        filename=name,
        file=BytesIO(b"# Article\n\nBody"),
        headers={"content-type": content_type},
    )


def test_import_articles_enqueues_background_processing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    file_store = _FakeFileStore()
    sent_tasks = []

    monkeypatch.setattr(api, "get_default_file_store", lambda: file_store)
    monkeypatch.setattr(api, "get_current_tenant_id", lambda: "tenant-a")
    monkeypatch.setattr(
        api.client_app,
        "send_task",
        lambda *args, **kwargs: sent_tasks.append((args, kwargs)),
    )

    response = api.import_articles(files=[_upload_file("article.md")], user=_FakeUser())

    assert response.imported[0].status == "queued"
    assert response.imported[0].detail == "已上传，后台处理中"
    assert response.failed == []
    assert file_store.saved == [
        ("article.md", FileOrigin.CONNECTOR_FILE_UPLOAD, "text/markdown")
    ]
    assert sent_tasks == [
        (
            (OnyxCeleryTask.PROCESS_TAXONOMY_ARTICLE_IMPORT,),
            {
                "kwargs": {
                    "files": [{"file_id": "stored-1", "file_name": "article.md"}],
                    "created_by_user_id": str(_FakeUser.id),
                    "tenant_id": "tenant-a",
                },
                "queue": OnyxCeleryQueues.TAXONOMY_PROCESSING,
                "priority": OnyxCeleryPriority.HIGH,
                "expires": CELERY_TAXONOMY_ARTICLE_IMPORT_TASK_EXPIRES,
            },
        )
    ]


def test_generation_config_api_round_trip(monkeypatch: pytest.MonkeyPatch) -> None:
    saved_configs: list[TaxonomyGenerationConfig] = []
    config = TaxonomyGenerationConfig(
        first_level_candidate_multiplier=5,
        first_level_max_count=24,
        third_level_candidate_multiplier=3,
        third_level_max_count=7,
        third_level_parallelism=8,
        l1_l2_prompt_template="自定义一级二级模板 {{x}} {{y}}",
        leaf_prompt_template="自定义三级模板 {{m}} {{n}}",
    )

    monkeypatch.setattr(api, "get_taxonomy_generation_config", lambda: config)
    monkeypatch.setattr(
        api,
        "set_taxonomy_generation_config",
        lambda request: saved_configs.append(request) or request,
    )

    assert api.get_generation_config() == config
    assert api.update_generation_config(config) == config
    assert saved_configs == [config]


def test_generation_config_migrates_legacy_system_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy_prompt = "旧版单提示词"
    monkeypatch.setattr(
        taxonomy_generation_config,
        "get_kv_store",
        lambda: _FakeKvStore({"system_prompt": legacy_prompt}),
    )

    config = taxonomy_generation_config.get_taxonomy_generation_config()

    assert config.l1_l2_prompt_template == legacy_prompt
    assert config.leaf_prompt_template == legacy_prompt


def test_generate_draft_prefers_request_generation_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stored_config = TaxonomyGenerationConfig(
        first_level_candidate_multiplier=2,
        first_level_max_count=10,
        third_level_candidate_multiplier=2,
        third_level_max_count=4,
        third_level_parallelism=3,
        l1_l2_prompt_template="后端保存的一级二级模板",
        leaf_prompt_template="后端保存的三级模板",
    )
    request_config = TaxonomyGenerationRuntimeConfig(
        first_level_candidate_multiplier=5,
        first_level_max_count=24,
        third_level_candidate_multiplier=3,
        third_level_max_count=7,
        third_level_parallelism=8,
        l1_l2_system_prompt="前端渲染后的一级二级提示词",
        leaf_system_prompt="前端渲染后的三级提示词",
    )
    used_configs: list[TaxonomyGenerationRuntimeConfig | None] = []

    monkeypatch.setattr(api, "get_taxonomy_generation_config", lambda: stored_config)
    monkeypatch.setattr(
        api,
        "generate_taxonomy_draft",
        lambda **kwargs: used_configs.append(kwargs["generation_config"]) or [],
    )

    response = api.generate_draft(
        GenerateTaxonomyDraftRequest(
            company_description="业务背景",
            generation_config=request_config,
        )
    )

    assert response.nodes == []
    assert used_configs == [request_config]
