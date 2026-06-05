from uuid import UUID

from onyx.configs.constants import DocumentSource
from onyx.connectors.models import Document
from onyx.connectors.models import TextSection
from onyx.taxonomy.article_import import prepare_taxonomy_article_documents
from onyx.taxonomy.article_import import validate_taxonomy_article_file_name


def test_validate_taxonomy_article_file_name_strips_paths() -> None:
    assert (
        validate_taxonomy_article_file_name("../fixtures/article.markdown")
        == "article.markdown"
    )


def test_validate_taxonomy_article_file_name_rejects_unsupported_extension() -> None:
    try:
        validate_taxonomy_article_file_name("article.docx")
    except ValueError as e:
        assert "Markdown" in str(e)
    else:
        raise AssertionError("Expected unsupported article file extension to fail")


def test_prepare_taxonomy_article_documents_stamps_import_metadata() -> None:
    user_id = UUID("00000000-0000-0000-0000-000000000001")
    document = Document(
        id="FILE_CONNECTOR__source",
        sections=[TextSection(text="Article body", link=None)],
        source=DocumentSource.INGESTION_API,
        semantic_identifier="Original title",
        metadata={},
        doc_metadata={"existing": "metadata"},
    )

    imported = prepare_taxonomy_article_documents(
        file_id="file-1",
        file_name="article.md",
        documents=[document],
        created_by_user_id=user_id,
    )

    assert len(imported) == 1
    assert imported[0].id == "taxonomy_article__file-1"
    assert imported[0].source == DocumentSource.FILE
    assert imported[0].from_ingestion_api is True
    assert imported[0].doc_updated_at is not None
    assert imported[0].doc_metadata == {
        "existing": "metadata",
        "taxonomy_article_import": True,
        "taxonomy_article_file_id": "file-1",
        "taxonomy_article_file_name": "article.md",
        "taxonomy_article_imported_by": str(user_id),
    }
