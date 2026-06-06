from onyx.configs.constants import KV_TAXONOMY_GENERATION_CONFIG_KEY
from onyx.key_value_store.factory import get_kv_store
from onyx.key_value_store.interface import KvKeyNotFoundError
from onyx.taxonomy.models import DEFAULT_TAXONOMY_L1_L2_PROMPT_TEMPLATE
from onyx.taxonomy.models import DEFAULT_TAXONOMY_LEAF_PROMPT_TEMPLATE
from onyx.taxonomy.models import TaxonomyGenerationConfig
from onyx.utils.logger import setup_logger

logger = setup_logger()


def _normalize_taxonomy_generation_config_payload(
    stored_config: object,
) -> dict[str, object]:
    if not isinstance(stored_config, dict):
        return {}

    payload = dict(stored_config)
    legacy_prompt = payload.pop("system_prompt", None)
    if isinstance(legacy_prompt, str) and legacy_prompt.strip():
        payload.setdefault("l1_l2_prompt_template", legacy_prompt.strip())
        payload.setdefault("leaf_prompt_template", legacy_prompt.strip())

    if "l1_l2_prompt_template" not in payload:
        payload["l1_l2_prompt_template"] = DEFAULT_TAXONOMY_L1_L2_PROMPT_TEMPLATE
    if "leaf_prompt_template" not in payload:
        payload["leaf_prompt_template"] = DEFAULT_TAXONOMY_LEAF_PROMPT_TEMPLATE

    return payload


def get_taxonomy_generation_config() -> TaxonomyGenerationConfig:
    kv_store = get_kv_store()
    try:
        stored_config = kv_store.load(
            KV_TAXONOMY_GENERATION_CONFIG_KEY, refresh_cache=True
        )
        return TaxonomyGenerationConfig.model_validate(
            _normalize_taxonomy_generation_config_payload(stored_config)
        )
    except KvKeyNotFoundError:
        logger.debug(
            "No taxonomy generation config found in KV store for key: %s",
            KV_TAXONOMY_GENERATION_CONFIG_KEY,
        )
        return TaxonomyGenerationConfig()
    except Exception as e:
        logger.error("Error loading taxonomy generation config from KV store: %s", e)
        return TaxonomyGenerationConfig()


def set_taxonomy_generation_config(
    config: TaxonomyGenerationConfig,
) -> TaxonomyGenerationConfig:
    normalized_config = TaxonomyGenerationConfig.model_validate(config.model_dump())
    get_kv_store().store(
        KV_TAXONOMY_GENERATION_CONFIG_KEY,
        normalized_config.model_dump(),
    )
    return normalized_config
