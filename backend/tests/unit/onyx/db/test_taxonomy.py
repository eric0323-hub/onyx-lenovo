from types import SimpleNamespace

import pytest

from onyx.db import taxonomy


class _FakeSession:
    def __init__(self, document: SimpleNamespace) -> None:
        self.document = document

    def get(self, _model: type, _document_id: str) -> SimpleNamespace:
        return self.document


def test_delete_imported_taxonomy_article_deletes_import_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = SimpleNamespace(
        file_id=None,
        doc_metadata={
            "taxonomy_article_import": True,
            "taxonomy_article_file_id": "upload-file-1",
        },
    )
    deleted_document_ids: list[str] = []
    deleted_file_calls: list[tuple[list[str], str]] = []

    def delete_documents_complete(
        _db_session: _FakeSession,
        document_ids: list[str],
    ) -> None:
        deleted_document_ids.extend(document_ids)

    def delete_files_best_effort(file_ids: list[str], context: str) -> None:
        deleted_file_calls.append((file_ids, context))

    monkeypatch.setattr(
        taxonomy,
        "delete_documents_complete",
        delete_documents_complete,
    )
    monkeypatch.setattr(
        taxonomy,
        "delete_files_best_effort",
        delete_files_best_effort,
    )

    taxonomy.delete_imported_taxonomy_article(
        _FakeSession(document),
        document_id="taxonomy_article__upload-file-1",
    )

    assert deleted_document_ids == ["taxonomy_article__upload-file-1"]
    assert deleted_file_calls == [
        (["upload-file-1"], "taxonomy article import cleanup")
    ]
