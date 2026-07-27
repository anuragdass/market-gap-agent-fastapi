from enum import StrEnum


class Platform(StrEnum):
    REDDIT = "reddit"
    HACKERNEWS = "hackernews"
    WEB = "web"
    LINKEDIN = "linkedin"
    G2 = "g2"
    NEWS = "news"


class Dimension(StrEnum):
    FEATURES = "features"
    PRICING = "pricing"
    UX = "ux"
    SUPPORT = "support"
    POSITIONING = "positioning"
    INTEGRATIONS = "integrations"
    PERFORMANCE = "performance"
    RELIABILITY = "reliability"


class Stance(StrEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class Scope(StrEnum):
    COMPANY_SPECIFIC = "company_specific"
    DOMAIN_WIDE = "domain_wide"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    PARTIAL = "partial"


class CompetitorStatus(StrEnum):
    ACCEPTED = "accepted"
    SKIPPED_DUPLICATE = "skipped_duplicate"
    SKIPPED_UNRESOLVED = "skipped_unresolved"


class SkipReason(StrEnum):
    UNREACHABLE = "unreachable"
    BLOCKED = "blocked"
    RATE_LIMITED = "rate_limited"
    EMPTY = "empty"
    NO_API_KEY = "no_api_key"
    PARSE_ERROR = "parse_error"
    TIMEOUT = "timeout"


class GapDirection(StrEnum):
    TARGET_BEHIND = "target_behind"
    TARGET_AHEAD = "target_ahead"
    UNCLEAR = "unclear"
