from enum import Enum


class AgentAction(str, Enum):
    CACHE_HIT = "CACHE_HIT"
    VALIDATE = "VALIDATE"
    LLM_FALLBACK = "LLM_FALLBACK"
    REJECT = "REJECT"


class ResponseSource(str, Enum):
    CACHE = "cache"
    LLM = "llm"
    VALIDATED_CACHE = "validated_cache"
    FALSE_HIT_FALLBACK = "false_hit_fallback"


class FeedbackRating(str, Enum):
    UP = "up"
    DOWN = "down"
