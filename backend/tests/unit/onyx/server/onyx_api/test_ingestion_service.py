from onyx.configs.constants import DocumentSource
from onyx.connectors.models import DocumentBase
from onyx.connectors.models import TextSection
from onyx.server.onyx_api.ingestion_service import prepare_ingestion_document


def test_prepare_ingestion_document_preserves_metadata() -> None:
    document_base = DocumentBase(
        id="taxonomy article 1",
        sections=[TextSection(text="Article content", link=None)],
        source=DocumentSource.INGESTION_API,
        semantic_identifier="Article title",
        metadata={"audience": "support"},
        doc_metadata={"taxonomy_article_import": True},
        file_id=None,
    )

    document = prepare_ingestion_document(document_base)

    assert document.id == "taxonomy_article_1"
    assert document.source == DocumentSource.FILE
    assert document.from_ingestion_api is True
    assert document.doc_updated_at is not None
    assert document.metadata == {"audience": "support"}
    assert document.doc_metadata == {"taxonomy_article_import": True}
    assert document.file_id is None
