"""Thin adapters for feeding live Kodi/Fenlight/a4k-style records into the selector.

This module is intentionally read-only and shadow-mode friendly:

- it adapts live-ish source/subtitle dicts into selector inputs
- it preserves the original objects on output
- it returns a compact trace payload that is easy to log while comparing
  selector ranking against the current Kodi behavior
"""

from __future__ import annotations

from typing import Any

from .subtitle_selector import rank_sources_by_subtitle_match


def rank_kodi_sources_by_subtitles(
    fenlight_sources: list[dict[str, Any]],
    a4k_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Adapt Fenlight and a4k result objects to the standalone selector API."""

    selector_sources = [adapt_fenlight_source(source) for source in fenlight_sources]
    selector_subtitles = [adapt_a4k_subtitle(subtitle) for subtitle in a4k_results]
    ranked = rank_sources_by_subtitle_match(selector_sources, selector_subtitles)

    for item in ranked:
        item["source"] = item["source"]["original"]
        if item["matched_subtitle"] is not None:
            item["matched_subtitle"] = item["matched_subtitle"]["original"]
        translation_kind = _subtitle_translation_kind(item["matched_subtitle"])
        item["matched_subtitle_translation_kind"] = translation_kind
        item["should_notify_translated_subtitle_fallback"] = translation_kind is not None
        item["translated_subtitle_notification"] = (
            "Selected subtitle fallback is %s" % translation_kind if translation_kind else None
        )
    return ranked


def build_subtitle_fallback_candidates(
    fenlight_sources: list[dict[str, Any]],
    a4k_results: list[dict[str, Any]],
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Return the best subtitle-backed fallback candidates for playback retries."""

    ranked = rank_kodi_sources_by_subtitles(fenlight_sources, a4k_results)
    if limit <= 0:
        return []
    return [item for item in ranked if item["matched_subtitle"] is not None][:limit]


def build_kodi_selector_playback_metadata(
    source: dict[str, Any],
    ranked_item: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return source-attached selector metadata for runtime playback handoff."""

    source_key = build_kodi_playback_source_key(source)
    metadata: dict[str, Any] = {
        "selector_source_key": source_key,
    }

    if not ranked_item or ranked_item.get("matched_subtitle") is None:
        return metadata

    matched_subtitle = ranked_item["matched_subtitle"]
    metadata.update(
        {
            "selector_match_score": ranked_item["score"],
            "selector_match_reason": ranked_item["match_reason"],
            "selector_used_comments_fallback": ranked_item["used_comments_fallback"],
            "selector_matched_subtitle": matched_subtitle,
            "selector_matched_subtitle_translation_kind": ranked_item[
                "matched_subtitle_translation_kind"
            ],
            "selector_should_notify_translated_subtitle_fallback": ranked_item[
                "should_notify_translated_subtitle_fallback"
            ],
            "selector_translated_subtitle_notification": ranked_item[
                "translated_subtitle_notification"
            ],
            "selector_subtitle_payload": {
                "version": 1,
                "source_key": source_key,
                "match_score": ranked_item["score"],
                "match_reason": ranked_item["match_reason"],
                "used_comments_fallback": ranked_item["used_comments_fallback"],
                "matched_subtitle_translation_kind": ranked_item[
                    "matched_subtitle_translation_kind"
                ],
                "translated_subtitle_notification": ranked_item[
                    "translated_subtitle_notification"
                ],
                "matched_subtitle": matched_subtitle,
            },
        }
    )
    return metadata


def build_kodi_playback_source_key(source: dict[str, Any]) -> str:
    """Return a stable-enough identity key for one playback attempt."""

    parts = [
        source.get("name"),
        source.get("display_name"),
        source.get("scrape_provider"),
        source.get("debrid"),
        source.get("quality"),
        source.get("size"),
        source.get("hash"),
        source.get("id"),
    ]
    return "|".join("" if part is None else str(part) for part in parts)


def build_shadow_run_trace(
    fenlight_sources: list[dict[str, Any]],
    a4k_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Return a compact trace payload suitable for debug logging."""

    ranked = rank_kodi_sources_by_subtitles(fenlight_sources, a4k_results)
    fallback_candidates = build_subtitle_fallback_candidates(fenlight_sources, a4k_results)
    top_ranked = ranked[0] if ranked else None
    return {
        "source_count": len(fenlight_sources),
        "subtitle_count": len(a4k_results),
        "subtitle_fallback_candidate_count": len(fallback_candidates),
        "subtitle_fallback_candidates": [_ranked_trace(item) for item in fallback_candidates],
        "top_match_has_translated_subtitle_fallback": bool(
            top_ranked and top_ranked["should_notify_translated_subtitle_fallback"]
        ),
        "top_match_translation_kind": (
            top_ranked["matched_subtitle_translation_kind"] if top_ranked else None
        ),
        "top_match_notification": (
            top_ranked["translated_subtitle_notification"] if top_ranked else None
        ),
        "sources": [_source_trace(source) for source in fenlight_sources],
        "subtitles": [_subtitle_trace(subtitle) for subtitle in a4k_results],
        "ranked": [_ranked_trace(item) for item in ranked],
    }


def adapt_fenlight_source(source: dict[str, Any]) -> dict[str, Any]:
    release_name = (
        source.get("name")
        or source.get("display_name")
        or source.get("filename")
        or source.get("source")
        or ""
    )

    return {
        "release_name": str(release_name),
        "name": source.get("display_name") or source.get("name") or "",
        "scrape_provider": source.get("scrape_provider"),
        "quality": source.get("quality"),
        "size": source.get("size"),
        "extra_info": source.get("extraInfo", ""),
        "original": source,
    }


def adapt_a4k_subtitle(subtitle: dict[str, Any]) -> dict[str, Any]:
    action_args = subtitle.get("action_args") or {}
    release_name = (
        subtitle.get("name")
        or action_args.get("filename")
        or subtitle.get("filename")
        or ""
    )

    comment_parts = [
        subtitle.get("comment", ""),
        subtitle.get("comments", ""),
        subtitle.get("service", ""),
        action_args.get("release_name", ""),
        action_args.get("comment", ""),
    ]

    return {
        "release_name": str(release_name),
        "filename": str(action_args.get("filename") or subtitle.get("filename") or release_name),
        "comment": " | ".join(part for part in comment_parts if part),
        "service_name": subtitle.get("service_name"),
        "service": subtitle.get("service"),
        "sync": subtitle.get("sync"),
        "ai_translated": bool(subtitle.get("ai_translated") or action_args.get("ai_translated")),
        "machine_translated": bool(subtitle.get("machine_translated") or action_args.get("machine_translated")),
        "original": subtitle,
    }


def _source_trace(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "release_name": source.get("name") or source.get("display_name") or source.get("filename"),
        "display_name": source.get("display_name"),
        "scrape_provider": source.get("scrape_provider"),
        "quality": source.get("quality"),
        "size": source.get("size"),
    }


def _subtitle_trace(subtitle: dict[str, Any]) -> dict[str, Any]:
    action_args = subtitle.get("action_args") or {}
    return {
        "release_name": subtitle.get("name") or action_args.get("filename") or subtitle.get("filename"),
        "service_name": subtitle.get("service_name"),
        "service": subtitle.get("service"),
        "sync": subtitle.get("sync"),
        "ai_translated": bool(subtitle.get("ai_translated") or action_args.get("ai_translated")),
        "machine_translated": bool(subtitle.get("machine_translated") or action_args.get("machine_translated")),
    }


def _ranked_trace(item: dict[str, Any]) -> dict[str, Any]:
    source = item["source"]
    subtitle = item["matched_subtitle"]
    return {
        "source_release_name": source.get("name") or source.get("display_name") or source.get("filename"),
        "source_provider": source.get("scrape_provider"),
        "score": item["score"],
        "match_reason": item["match_reason"],
        "used_comments_fallback": item["used_comments_fallback"],
        "matched_subtitle_release_name": (
            subtitle.get("name")
            or (subtitle.get("action_args") or {}).get("filename")
            or subtitle.get("filename")
            if subtitle
            else None
        ),
        "subtitle_service": subtitle.get("service") if subtitle else None,
        "matched_subtitle_translation_kind": item["matched_subtitle_translation_kind"],
        "should_notify_translated_subtitle_fallback": item["should_notify_translated_subtitle_fallback"],
        "translated_subtitle_notification": item["translated_subtitle_notification"],
        "debug": item["debug"],
    }


def _subtitle_translation_kind(subtitle: dict[str, Any] | None) -> str | None:
    if not subtitle:
        return None

    action_args = subtitle.get("action_args") or {}
    is_ai_translated = bool(subtitle.get("ai_translated") or action_args.get("ai_translated"))
    is_machine_translated = bool(subtitle.get("machine_translated") or action_args.get("machine_translated"))

    if is_ai_translated:
        return "AI-translated"
    if is_machine_translated:
        return "machine-translated"
    return None
