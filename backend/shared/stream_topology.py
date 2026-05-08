"""Redis Stream names and consumer groups (versioned)."""

STREAM_QUERY_COMMANDS_V1 = "semcache:stream:query:commands:v1"
STREAM_ANALYTICS_EVENTS_V1 = "semcache:stream:analytics:events:v1"
STREAM_OBSERVABILITY_EVENTS_V1 = "semcache:stream:observability:events:v1"
STREAM_CACHE_COMMANDS_V1 = "semcache:stream:cache:commands:v1"
STREAM_CACHE_RESULTS_V1 = "semcache:stream:cache:results:v1"
STREAM_AI_COMMANDS_V1 = "semcache:stream:ai:commands:v1"
STREAM_AI_RESULTS_V1 = "semcache:stream:ai:results:v1"
STREAM_RAG_COMMANDS_V1 = "semcache:stream:rag:commands:v1"
STREAM_RAG_RESULTS_V1 = "semcache:stream:rag:results:v1"
STREAM_DLQ_V1 = "semcache:stream:deadletter:v1"
STREAM_QUERY_RESULTS_V1 = "semcache:stream:query:results:v1"

CG_ORCHESTRATOR = "cg-orchestrator"
CG_CACHE = "cg-cache"
CG_AI = "cg-ai"
CG_RAG = "cg-rag"
CG_ANALYTICS = "cg-analytics"

# (stream, consumer_group) pairs with workers — for XPENDING / ops dashboards.
MONITORED_STREAM_GROUPS: tuple[tuple[str, str], ...] = (
    (STREAM_QUERY_COMMANDS_V1, CG_ORCHESTRATOR),
    (STREAM_CACHE_COMMANDS_V1, CG_CACHE),
    (STREAM_AI_COMMANDS_V1, CG_AI),
    (STREAM_RAG_COMMANDS_V1, CG_RAG),
    (STREAM_ANALYTICS_EVENTS_V1, CG_ANALYTICS),
)

JOB_KEY_PREFIX = "semcache:job:"
CMD_RESULT_PREFIX = "semcache:cmd_result:"
