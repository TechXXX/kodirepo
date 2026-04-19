"""Standalone subtitle selector focused only on subtitle/source alignment.

This first version intentionally keeps the policy small and deterministic:

- direct subtitle filename evidence is preferred over comments
- comment parsing is fallback-only for a source with no direct useful match
- AI or machine-translated subtitles are demoted, but still remain candidates
- when no direct release match exists, strong shared structure can still score as fallback
- playback or stream resolution concerns are out of scope for this module

The selector accepts lightweight source/subtitle dictionaries so it can be
integrated into a larger pipeline before the surrounding models are finalized.
"""

from __future__ import annotations

import os
import re
from typing import Any

COMMON_TOKENS = {
    "1080p",
    "2160p",
    "720p",
    "480p",
    "web",
    "webrip",
    "webdl",
    "web-dl",
    "bluray",
    "brrip",
    "bdrip",
    "hdrip",
    "x264",
    "x265",
    "h264",
    "h265",
    "hevc",
    "aac",
    "ddp",
    "dts",
    "proper",
    "repack",
    "extended",
    "limited",
    "multi",
    "subs",
    "sub",
}

AI_HINTS = (
    "ai",
    "machine translated",
    "machine-translated",
    "machine translation",
    "translated by ai",
    "auto translated",
    "auto-translated",
)

KNOWN_EXTENSIONS = {
    ".srt",
    ".sub",
    ".ass",
    ".ssa",
    ".vtt",
    ".mkv",
    ".mp4",
    ".avi",
    ".m2ts",
    ".ts",
}

QUALITY_RANKS = {
    "2160p": 4,
    "4k": 4,
    "1080p": 3,
    "720p": 2,
    "480p": 1,
    "sd": 1,
}

BRACKET_TECH_TOKENS = {
    "2160p",
    "1080p",
    "720p",
    "480p",
    "4k",
    "web",
    "webrip",
    "webdl",
    "bluray",
    "bdrip",
    "brrip",
    "hdrip",
    "dvdrip",
    "remux",
    "x264",
    "x265",
    "h264",
    "h265",
    "hevc",
    "aac",
    "ddp",
    "dts",
    "ac3",
    "flac",
    "truehd",
    "atmos",
}

RELEASE_FAMILY_MAP = {
    "webrip": "web",
    "webdl": "web",
    "web": "web",
    "bluray": "disc",
    "bdrip": "disc",
    "brrip": "disc",
    "hdrip": "disc",
    "telesync": "prerelease",
    "cam": "prerelease",
    "telecine": "prerelease",
    "screener": "prerelease",
}

PRERELEASE_TYPES = {
    "telesync",
    "cam",
    "telecine",
    "screener",
}

AI_TRANSLATION_PENALTY = 20
PRERELEASE_PENALTY = 20
COMMENT_FALLBACK_MAX_SCORE = 79


def rank_sources_by_subtitle_match(
    sources: list[dict[str, Any]],
    subtitles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return sources ranked by how well they align with available subtitles."""

    ranked: list[dict[str, Any]] = []
    prepared_subtitles = [_prepare_subtitle(subtitle) for subtitle in subtitles]

    for index, source in enumerate(sources):
        prepared_source = _prepare_release_text(_source_release_name(source))
        source_quality_rank = _source_quality_rank(source, prepared_source)
        source_size = _source_size_value(source)
        best_direct = _best_match_for_source(
            prepared_source,
            prepared_subtitles,
            allow_comments=False,
        )
        best_match = best_direct

        if best_direct["score"] == 0:
            best_match = _best_match_for_source(
                prepared_source,
                prepared_subtitles,
                allow_comments=True,
            )

        ranked.append(
            {
                "source": source,
                "score": best_match["score"],
                "matched_subtitle": best_match["subtitle"],
                "match_reason": best_match["reason"],
                "used_comments_fallback": best_match["used_comments_fallback"],
                "debug": {
                    "source_release_name": prepared_source["raw"],
                    "source_normalized": prepared_source["normalized"],
                    "source_release_group": prepared_source["release_group"],
                    "subtitle_release_name": best_match["subtitle_release_name"],
                    "subtitle_release_group": best_match["subtitle_release_group"],
                    "token_overlap": best_match["token_overlap"],
                    "ai_penalty_applied": best_match["ai_penalty_applied"],
                    "prerelease_penalty_applied": best_match["prerelease_penalty_applied"],
                    "comment_candidate_count": best_match["comment_candidate_count"],
                    "source_quality_rank": source_quality_rank,
                    "source_size": source_size,
                    "source_type": prepared_source["source_type"],
                    "source_is_prerelease": prepared_source["is_prerelease"],
                    "subtitle_type": best_match["subtitle_source_type"],
                    "subtitle_is_prerelease": best_match["subtitle_is_prerelease"],
                },
                "_source_quality_rank": source_quality_rank,
                "_source_size": source_size,
                "_token_overlap": best_match["token_overlap"],
                "_matched_subtitle_is_translated": best_match["matched_subtitle_is_translated"],
                "_source_is_prerelease": prepared_source["is_prerelease"],
                "_subtitle_is_prerelease": best_match["subtitle_is_prerelease"],
                "_sort_index": index,
            }
        )

    ranked.sort(
        key=lambda item: (
            item["_matched_subtitle_is_translated"],
            item["_source_is_prerelease"] or item["_subtitle_is_prerelease"],
            -item["score"],
            -item["_source_quality_rank"],
            -item["_source_size"],
            -item["_token_overlap"],
            item["_sort_index"],
        )
    )
    for item in ranked:
        item.pop("_source_quality_rank", None)
        item.pop("_source_size", None)
        item.pop("_token_overlap", None)
        item.pop("_matched_subtitle_is_translated", None)
        item.pop("_source_is_prerelease", None)
        item.pop("_subtitle_is_prerelease", None)
        item.pop("_sort_index", None)
    return ranked


def _best_match_for_source(
    prepared_source: dict[str, Any],
    prepared_subtitles: list[dict[str, Any]],
    *,
    allow_comments: bool,
) -> dict[str, Any]:
    best = _empty_match()

    for subtitle_index, prepared_subtitle in enumerate(prepared_subtitles):
        candidates = [prepared_subtitle["direct_release"]]
        if allow_comments:
            candidates.extend(prepared_subtitle["comment_releases"])

        for candidate_index, candidate in enumerate(candidates):
            if candidate is None:
                continue

            result = _score_candidate_match(prepared_source, candidate)
            if result["score"] == 0:
                continue

            if candidate_index > 0:
                result["score"] = min(result["score"], COMMENT_FALLBACK_MAX_SCORE)

            ai_penalty_applied = 0
            if prepared_subtitle["is_ai_generated"]:
                ai_penalty_applied = AI_TRANSLATION_PENALTY
                result["score"] = max(0, result["score"] - ai_penalty_applied)

            prerelease_penalty_applied = 0
            if prepared_source["is_prerelease"] or candidate["is_prerelease"]:
                prerelease_penalty_applied = PRERELEASE_PENALTY
                result["score"] = max(0, result["score"] - prerelease_penalty_applied)

            result.update(
                {
                    "subtitle": prepared_subtitle["original"],
                    "subtitle_release_name": candidate["raw"],
                    "subtitle_release_group": candidate["release_group"],
                    "subtitle_source_type": candidate["source_type"],
                    "subtitle_is_prerelease": candidate["is_prerelease"],
                    "used_comments_fallback": candidate_index > 0,
                    "ai_penalty_applied": ai_penalty_applied,
                    "prerelease_penalty_applied": prerelease_penalty_applied,
                    "comment_candidate_count": len(prepared_subtitle["comment_releases"]),
                    "matched_subtitle_is_translated": prepared_subtitle["is_ai_generated"],
                    "_subtitle_index": subtitle_index,
                }
            )

            best = _choose_better_match(best, result)

    return best


def _score_candidate_match(
    prepared_source: dict[str, Any],
    prepared_subtitle_release: dict[str, Any],
) -> dict[str, Any]:
    source_normalized = prepared_source["normalized"]
    subtitle_normalized = prepared_subtitle_release["normalized"]
    source_group = prepared_source["release_group"]
    subtitle_group = prepared_subtitle_release["release_group"]
    source_type = prepared_source["source_type"]
    subtitle_type = prepared_subtitle_release["source_type"]
    source_family = prepared_source["release_family"]
    subtitle_family = prepared_subtitle_release["release_family"]

    token_overlap = len(prepared_source["meaningful_tokens"] & prepared_subtitle_release["meaningful_tokens"])
    same_group = bool(source_group and subtitle_group and source_group == subtitle_group)
    same_quality = bool(
        prepared_source["quality_rank"]
        and prepared_subtitle_release["quality_rank"]
        and prepared_source["quality_rank"] == prepared_subtitle_release["quality_rank"]
    )
    same_source_type = bool(source_type and subtitle_type and source_type == subtitle_type)
    same_source_family = bool(source_family and subtitle_family and source_family == subtitle_family)
    stable_release_family = source_family in {"web", "disc"} and subtitle_family in {"web", "disc"}

    if source_normalized and source_normalized == subtitle_normalized:
        return {
            "score": 100,
            "reason": "exact_normalized_match",
            "token_overlap": token_overlap,
        }

    if same_group and token_overlap >= 2:
        return {
            "score": 90,
            "reason": "release_group_and_token_overlap",
            "token_overlap": token_overlap,
        }

    if stable_release_family and same_source_type and same_quality and token_overlap >= 4:
        return {
            "score": 82,
            "reason": "source_type_and_quality_overlap",
            "token_overlap": token_overlap,
        }

    if _is_containment_match(source_normalized, subtitle_normalized):
        return {
            "score": 80,
            "reason": "containment_match",
            "token_overlap": token_overlap,
        }

    if stable_release_family and same_source_type and token_overlap >= 4:
        return {
            "score": 70,
            "reason": "source_type_and_token_overlap",
            "token_overlap": token_overlap,
        }

    if same_source_family and same_quality and token_overlap >= 4:
        return {
            "score": 65,
            "reason": "source_family_and_quality_overlap",
            "token_overlap": token_overlap,
        }

    if same_group:
        return {
            "score": 60,
            "reason": "release_group_match",
            "token_overlap": token_overlap,
        }

    if token_overlap >= 4:
        return {
            "score": 45,
            "reason": "strong_token_overlap_fallback",
            "token_overlap": token_overlap,
        }

    return {
        "score": 0,
        "reason": "no_useful_match",
        "token_overlap": token_overlap,
    }


def _choose_better_match(current_best: dict[str, Any], candidate: dict[str, Any]) -> dict[str, Any]:
    if candidate["score"] > current_best["score"]:
        return candidate
    if candidate["score"] < current_best["score"]:
        return current_best

    current_comment = current_best.get("used_comments_fallback", False)
    candidate_comment = candidate.get("used_comments_fallback", False)
    if current_comment != candidate_comment:
        return current_best if not current_comment else candidate

    current_penalty = current_best.get("ai_penalty_applied", 0)
    candidate_penalty = candidate.get("ai_penalty_applied", 0)
    if candidate_penalty != current_penalty:
        return candidate if candidate_penalty < current_penalty else current_best

    current_overlap = current_best.get("token_overlap", 0)
    candidate_overlap = candidate.get("token_overlap", 0)
    if candidate_overlap != current_overlap:
        return candidate if candidate_overlap > current_overlap else current_best

    return candidate if candidate.get("_subtitle_index", 0) < current_best.get("_subtitle_index", 0) else current_best


def _prepare_subtitle(subtitle: dict[str, Any]) -> dict[str, Any]:
    direct_release_name = _subtitle_release_name(subtitle)
    comment_releases = [_prepare_release_text(value) for value in _extract_comment_release_candidates(subtitle)]

    return {
        "original": subtitle,
        "direct_release": _prepare_release_text(direct_release_name) if direct_release_name else None,
        "comment_releases": comment_releases,
        "is_ai_generated": _is_ai_generated_subtitle(subtitle),
    }


def _prepare_release_text(value: str | None) -> dict[str, Any]:
    raw = (value or "").strip()
    normalized = _normalize_release_name(raw)
    meaningful_tokens = _meaningful_tokens(normalized)
    release_group = _extract_release_group(raw)
    source_type = _release_source_type(normalized)
    quality_rank = _quality_rank_from_text(normalized)

    return {
        "raw": raw,
        "normalized": normalized,
        "meaningful_tokens": meaningful_tokens,
        "release_group": release_group,
        "source_type": source_type,
        "release_family": RELEASE_FAMILY_MAP.get(source_type),
        "quality_rank": quality_rank,
        "is_prerelease": source_type in PRERELEASE_TYPES,
    }


def _source_release_name(source: dict[str, Any]) -> str:
    for key in ("release_name", "name", "filename", "source"):
        value = source.get(key)
        if value:
            return str(value)
    return ""


def _subtitle_release_name(subtitle: dict[str, Any]) -> str:
    for key in ("release_name", "filename", "name"):
        value = subtitle.get(key)
        if value:
            return _clean_subtitle_release_name(str(value))
    return ""


def _clean_subtitle_release_name(value: str) -> str:
    cleaned = _strip_known_extension(value.strip())
    cleanup_patterns = (
        r"(?i)(?:[._ -](?:track|trk)\d+)(?:[._ -]*\[[^\]]+\])*$",
        r"(?i)(?:[\s._-]*\[[a-z]{2,4}\])+$",
        r"(?i)(?:[\s._-](?:sdh|hi|cc|forced))+$",
    )
    for pattern in cleanup_patterns:
        cleaned = re.sub(pattern, "", cleaned)
    return cleaned.strip(" .-_")


def _normalize_release_name(value: str) -> str:
    base = _strip_known_extension(value.strip()).lower()
    base = re.sub(r"\[([^\]]*)\]", _normalize_bracketed_segment, base)
    base = base.replace("&", " and ")
    base = re.sub(r"[^a-z0-9]+", " ", base)
    base = re.sub(r"\s+", " ", base).strip()
    return base


def _normalize_bracketed_segment(match: re.Match[str]) -> str:
    content = match.group(1).strip()
    if _should_preserve_bracket_content(content):
        return f" {content} "
    return " "


def _should_preserve_bracket_content(content: str) -> bool:
    normalized = _strip_known_extension(content.strip()).lower()
    if not normalized:
        return False

    tokens = [token for token in re.split(r"[^a-z0-9]+", normalized) if token]
    if not tokens:
        return False

    if all(token.isalpha() and len(token) <= 4 for token in tokens):
        return False

    if any(token in BRACKET_TECH_TOKENS for token in tokens):
        return True

    if any(re.fullmatch(r"\d{4}", token) for token in tokens):
        return True

    if any(re.search(r"\d", token) for token in tokens) and len(tokens) > 1:
        return True

    return False


def _extract_release_group(value: str) -> str | None:
    cleaned = _strip_known_extension(value.strip())
    match = re.search(r"-([A-Za-z0-9]+)(?:\[[^\]]+\])?\s*$", cleaned)
    if not match:
        return None
    return match.group(1).lower()


def _strip_known_extension(value: str) -> str:
    lowered = value.lower()
    for extension in KNOWN_EXTENSIONS:
        if lowered.endswith(extension):
            return value[: -len(extension)]
    return value


def _extract_comment_release_candidates(subtitle: dict[str, Any]) -> list[str]:
    comments = str(subtitle.get("comment", "") or "")
    if not comments:
        return []

    candidates: list[str] = []
    patterns = (
        r"(?i)(?:release|source|sync|resynced|for)\s*[:\-]\s*([A-Za-z0-9.\-\[\] ]{6,})",
        r"(?i)\b([A-Za-z0-9]+(?:[.\-][A-Za-z0-9\[\]]+){3,})\b",
    )
    for pattern in patterns:
        for match in re.finditer(pattern, comments):
            candidate = match.group(1).strip(" .,-")
            if candidate:
                candidates.append(candidate)

    unique_candidates: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = _normalize_release_name(candidate)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_candidates.append(candidate)
    return unique_candidates


def _is_ai_generated_subtitle(subtitle: dict[str, Any]) -> bool:
    ai_flag = _coerce_optional_bool(subtitle.get("ai_translated"))
    machine_flag = _coerce_optional_bool(subtitle.get("machine_translated"))

    if ai_flag is True or machine_flag is True:
        return True
    if ai_flag is False or machine_flag is False:
        return False

    fields = [
        str(subtitle.get("comment", "") or ""),
        str(subtitle.get("name", "") or ""),
        str(subtitle.get("filename", "") or ""),
        str(subtitle.get("release_name", "") or ""),
    ]
    haystack = " ".join(fields).lower()
    return any(hint in haystack for hint in AI_HINTS)


def _coerce_optional_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    return bool(value)


def _meaningful_tokens(normalized_value: str) -> set[str]:
    tokens = set()
    for token in normalized_value.split():
        if len(token) <= 2:
            continue
        if token in COMMON_TOKENS:
            continue
        if token.isdigit() and len(token) != 4:
            continue
        tokens.add(token)
    return tokens


def _source_quality_rank(source: dict[str, Any], prepared_source: dict[str, Any]) -> int:
    explicit_quality = str(source.get("quality", "") or "")
    for value in (explicit_quality, prepared_source["normalized"], prepared_source["raw"]):
        rank = _quality_rank_from_text(value)
        if rank:
            return rank
    return 0


def _quality_rank_from_text(value: str) -> int:
    normalized = _normalize_release_name(value)
    tokens = set(normalized.split())
    for label in ("2160p", "4k", "1080p", "720p", "480p", "sd"):
        if label in tokens:
            return QUALITY_RANKS[label]
    return 0


def _release_source_type(normalized_value: str) -> str | None:
    patterns = (
        ("telesync", r"\b(?:telesync|hdts)\b"),
        ("cam", r"\b(?:camrip|hdcam|cam)\b"),
        ("telecine", r"\btelecine\b"),
        ("screener", r"\b(?:screener|dvdscr|r5)\b"),
        ("webrip", r"\bwebrip\b"),
        ("webdl", r"\bweb\s+dl\b"),
        ("bluray", r"\bbluray\b"),
        ("bdrip", r"\bbdrip\b"),
        ("brrip", r"\bbrrip\b"),
        ("hdrip", r"\bhdrip\b"),
        ("web", r"\bweb\b"),
        ("dcp", r"\bdcp\b"),
    )
    for label, pattern in patterns:
        if re.search(pattern, normalized_value):
            return label
    return None


def _source_size_value(source: dict[str, Any]) -> float:
    value = source.get("size")
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _is_containment_match(left: str, right: str) -> bool:
    if not left or not right or left == right:
        return False
    return left in right or right in left


def _empty_match() -> dict[str, Any]:
    return {
        "score": 0,
        "subtitle": None,
        "reason": "no_useful_match",
        "used_comments_fallback": False,
        "subtitle_release_name": None,
        "subtitle_release_group": None,
        "subtitle_source_type": None,
        "subtitle_is_prerelease": False,
        "token_overlap": 0,
        "ai_penalty_applied": 0,
        "prerelease_penalty_applied": 0,
        "comment_candidate_count": 0,
        "matched_subtitle_is_translated": False,
        "_subtitle_index": 10**9,
    }
