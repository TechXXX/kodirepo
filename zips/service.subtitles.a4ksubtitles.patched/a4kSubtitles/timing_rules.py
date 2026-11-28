# -*- coding: utf-8 -*-
"""When a timing match is strong enough to retime or replace a subtitle.

Shared by background subtitle sync (`background_sync.py`) and the AI source
timing check (`ai_source_timing.py`). The cue matching itself lives in
`subtitle_sync.py`; this module only decides what to do with its result.
"""

import os

from a4kSubtitles.subtitle_sync import find_best_offset

# Both retiming the selected subtitle and replacing it with an alternative
# change what Kodi renders. Require the same evidence for either operation.
FALLBACK_MIN_EMBEDDED_CUES = 16
FALLBACK_MIN_EXTERNAL_CUES = 30
FALLBACK_MIN_MATCHED_CUES = 8
FALLBACK_MAX_RESIDUAL_MS = 250
MIN_RETIME_MS = 150
SMALL_OFFSET_RANGE_MS = 400


def fallback_match_is_confirmed(result):
    """Return whether a timing result is safe enough to replace a subtitle."""
    if not result or result.get('matched_cues', 0) < FALLBACK_MIN_MATCHED_CUES:
        return False

    # The histogram fallback can count the same embedded event more than once
    # and reports only a median residual. Keep it for diagnostics, but require
    # the ordered one-to-one match before changing Kodi's active subtitle.
    if result.get('method') == 'histogram':
        return False

    # The accepted ordered match must also have tightly clustered starts.
    residual = result.get('mean_abs_residual_ms')
    if residual is None:
        residual = abs(result.get('median_residual_ms', FALLBACK_MAX_RESIDUAL_MS + 1))
    return residual <= FALLBACK_MAX_RESIDUAL_MS


def fallback_match_rank(result):
    """Prefer more shared starts, then a tighter fit and less correction."""
    return (
        result.get('matched_cues', 0),
        -result.get('mean_abs_residual_ms', abs(result.get('median_residual_ms', 0))),
        -abs(result.get('offset_ms', 0)),
    )


def best_embedded_match(reference_candidates, target_starts):
    """Use non-SDH timing when it is as convincing as the SDH timeline."""
    strongest = find_best_offset(reference_candidates, target_starts)
    if not strongest or not strongest.get('is_sdh'):
        return strongest

    normal_tracks = [candidate for candidate in reference_candidates if not candidate.get('is_sdh')]
    normal = find_best_offset(normal_tracks, target_starts)
    if not fallback_match_is_confirmed(normal):
        return strongest
    if not fallback_match_is_confirmed(strongest):
        return normal

    # SDH adds sound descriptions that can create extra chance cue matches.
    # Prefer the normal track when its ordered evidence is nearly as strong.
    if (normal['matched_cues'] >= strongest['matched_cues'] * 0.9 and
            normal['mean_abs_residual_ms'] <= strongest['mean_abs_residual_ms'] + 25):
        return normal
    return strongest


def offset_to_apply(result):
    """Require a material gain before making a small timing correction."""
    offset_ms = result.get('offset_ms', 0)
    if abs(offset_ms) < MIN_RETIME_MS:
        return 0
    if abs(offset_ms) >= SMALL_OFFSET_RANGE_MS:
        return offset_ms

    # A dense subtitle timeline can produce a broad plateau of nearly equal
    # offset scores. Sparse sampling can also move the best bucket away from
    # zero. A small shift is trustworthy only when zero has substantially
    # fewer ordered matches or appreciably worse timing residuals.
    best_matches = result.get('matched_cues', 0)
    zero_matches = result.get('zero_offset_matches')
    if zero_matches is not None and zero_matches <= best_matches * 0.75:
        return offset_ms
    zero_residual = result.get('zero_offset_mean_abs_residual_ms')
    best_residual = result.get('mean_abs_residual_ms')
    if zero_residual is not None and best_residual is not None and zero_residual - best_residual >= 75:
        return offset_ms
    return 0


def autosync_path(path, offset_ms):
    """Spell out the sign because Kodi drops punctuation in stream labels."""
    root, extension = os.path.splitext(path)
    direction = 'plus' if offset_ms > 0 else 'minus'
    return '%s.autosync.%s%dms%s' % (root, direction, abs(offset_ms), extension or '.srt')


def eligible_reference_candidates(reference_candidates):
    """Embedded tracks with enough cues to judge timing by."""
    return [
        candidate for candidate in reference_candidates
        if len(candidate.get('starts') or []) >= FALLBACK_MIN_EMBEDDED_CUES
    ]


def max_embedded_cues(reference_candidates):
    return max([len(candidate.get('starts') or []) for candidate in reference_candidates] or [0])
