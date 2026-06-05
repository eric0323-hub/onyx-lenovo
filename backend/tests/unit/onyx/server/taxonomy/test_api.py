from io import BytesIO
from uuid import UUID

import pytest
from fastapi import UploadFile

from onyx.configs.constants import CELERY_TAXONOMY_ARTICLE_IMPORT_TASK_EXPIRES
from onyx.configs.constants import FileOrigin
from onyx.configs.constants import OnyxCeleryPriority
from onyx.configs.constants import OnyxCeleryQueues
from onyx.configs.constants import OnyxCeleryTask
from onyx.server.taxonomy import api


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
