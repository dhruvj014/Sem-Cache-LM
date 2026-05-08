"""
Contract test suite aliases.

Keeps a stable `tests/contracts` entrypoint while legacy contract tests
remain in integration/unit paths during migration.
"""

from tests.integration.test_analytics_internal_service_contracts import *  # noqa: F401,F403
from tests.integration.test_cache_internal_service_contracts import *  # noqa: F401,F403
from tests.integration.test_internal_service_contracts import *  # noqa: F401,F403
from tests.integration.test_rag_internal_service_contracts import *  # noqa: F401,F403

