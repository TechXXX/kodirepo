# -*- coding: utf-8 -*-
"""Bounded, cue-only timing alignment for external text subtitles.

The worker deliberately never extracts an embedded subtitle track.  For
Matroska sources it reads the header, track table and Cue index through small
local or HTTP range reads, then compares start times only.  That makes it safe
to run after playback begins without making subtitle selection wait.
"""

from __future__ import absolute_import

import bisect
import os
import re
import time

try:
    from urllib.request import Request, urlopen
except ImportError:  # Kodi 19 Python 2 compatibility.
    from urllib2 import Request, urlopen


# The fallback mirrors Subtitle Cycler's broad, bounded sampling strategy:
# inspect small cluster windows across the entire timeline, but never extract
# the subtitle stream or fetch the full media file.
MAX_READ_BYTES = 150 * 1024 * 1024
MAX_REQUESTS = 80
MAX_READ_SECONDS = 30
INITIAL_READ_BYTES = 768 * 1024
INDEX_READ_BYTES = 2 * 1024 * 1024
CLUSTER_READ_BYTES = 4 * 1024 * 1024
TEXT_CODECS = set((
    'S_TEXT/UTF8', 'S_TEXT/ASS', 'S_TEXT/SSA', 'S_TEXT/WEBVTT',
    'S_TEXT/USF', 'S_KATE',
))
TIMING_LINE = re.compile(
    r'(?P<start>\d{2}:\d{2}:\d{2}[,.]\d{3})(?P<join>\s*-->\s*)(?P<end>\d{2}:\d{2}:\d{2}[,.]\d{3})'
)


class RangeReader(object):
    """A strict byte/request budget around local and direct HTTP reads."""

    def __init__(self, source, max_bytes=MAX_READ_BYTES, max_requests=MAX_REQUESTS,
                 max_seconds=MAX_READ_SECONDS):
        self.source = source or ''
        self.max_bytes = max_bytes
        self.max_requests = max_requests
        self.bytes_read = 0
        self.requests = 0
        self.started_at = time.time()
        self.deadline = self.started_at + max_seconds
        self.cache = {}
        self.is_local = os.path.isfile(self.source)

    def read(self, offset, length):
        offset, length = max(0, int(offset)), max(0, int(length))
        if not length or self.requests >= self.max_requests or time.time() >= self.deadline:
            return b''
        remaining = self.max_bytes - self.bytes_read
        if remaining <= 0:
            return b''
        length = min(length, remaining)
        key = (offset, length)
        if key in self.cache:
            return self.cache[key]
        try:
            if self.is_local:
                with open(self.source, 'rb') as handle:
                    handle.seek(offset)
                    data = handle.read(length)
            elif self.source.startswith(('http://', 'https://')):
                request = Request(self.source, headers={'Range': 'bytes=%s-%s' % (offset, offset + length - 1)})
                response = urlopen(request, timeout=5)
                try:
                    data = response.read(length)
                finally:
                    response.close()
            else:
                return b''
        except Exception:
            return b''
        self.requests += 1
        self.bytes_read += len(data)
        self.cache[key] = data
        return data


def _vint(data, offset, keep_marker=False):
    if offset >= len(data):
        return None
    first = data[offset]
    if not isinstance(first, int):
        first = ord(first)
    mask, length = 0x80, 1
    while length <= 8 and not first & mask:
        mask >>= 1
        length += 1
    if length > 8 or offset + length > len(data):
        return None
    value = first if keep_marker else first & (mask - 1)
    for position in range(offset + 1, offset + length):
        byte = data[position]
        if not isinstance(byte, int):
            byte = ord(byte)
        value = (value << 8) | byte
    unknown = not keep_marker and value == (1 << (7 * length)) - 1
    return value, length, unknown


def _elements(data, start=0, end=None):
    end = len(data) if end is None else min(len(data), end)
    offset = start
    while offset < end:
        element_id = _vint(data, offset, keep_marker=True)
        if not element_id:
            return
        size = _vint(data, offset + element_id[1])
        if not size:
            return
        value, id_length, _ = element_id
        payload_size, size_length, unknown = size
        payload_start = offset + id_length + size_length
        payload_end = end if unknown else payload_start + payload_size
        if payload_end > end:
            # The initial range normally contains only the beginning of the
            # Segment.  Preserve that partial outer element so callers can
            # inspect its immediate header and seek table; never advance past
            # it because no following element is available in this buffer.
            yield value, payload_start, end, offset
            return
        yield value, payload_start, payload_end, offset
        offset = payload_end


def _first(data, element_id, start=0, end=None):
    for current_id, payload_start, payload_end, element_start in _elements(data, start, end):
        if current_id == element_id:
            return payload_start, payload_end, element_start
    return None


def _integer(data):
    value = 0
    for byte in data:
        if not isinstance(byte, int):
            byte = ord(byte)
        value = (value << 8) | byte
    return value


def _text(data):
    try:
        return data.decode('utf-8', 'replace').strip('\x00')
    except AttributeError:
        return data.strip('\x00')


def _children(data, element_id):
    found = _first(data, element_id)
    if not found:
        return []
    start, end, _ = found
    return list(_elements(data, start, end))


def _seek_positions(segment_data, seek_head):
    positions = {}
    found = _first(seek_head, 0x114D9B74, segment_data)
    if not found:
        return positions
    start, end, _ = found
    for element_id, entry_start, entry_end, _ in _elements(seek_head, start, end):
        if element_id != 0x4DBB:
            continue
        seek_id, seek_position = None, None
        for child_id, value_start, value_end, _ in _elements(seek_head, entry_start, entry_end):
            if child_id == 0x53AB:
                seek_id = _integer(seek_head[value_start:value_end])
            elif child_id == 0x53AC:
                seek_position = _integer(seek_head[value_start:value_end])
        if seek_id is not None and seek_position is not None:
            positions[seek_id] = segment_data + seek_position
    return positions


def _read_element(reader, offset):
    data = reader.read(offset, INDEX_READ_BYTES)
    if not data:
        return b''
    return data


def _tracks(data, start=0):
    found = _first(data, 0x1654AE6B, start)
    if not found:
        return []
    start, end, _ = found
    tracks = []
    for element_id, entry_start, entry_end, _ in _elements(data, start, end):
        if element_id != 0xAE:
            continue
        track = {
            'number': None,
            'type': None,
            'codec': '',
            # Matroska's omitted Language element defaults to English.
            'language': 'eng',
            'name': '',
            'hearing_impaired': False,
        }
        ietf_language = None
        for child_id, value_start, value_end, _ in _elements(data, entry_start, entry_end):
            value = data[value_start:value_end]
            if child_id == 0xD7:
                track['number'] = _integer(value)
            elif child_id == 0x83:
                track['type'] = _integer(value)
            elif child_id == 0x86:
                track['codec'] = _text(value)
            elif child_id == 0x22B59C:
                track['language'] = _text(value).lower() or 'und'
            elif child_id == 0x22B59D:
                # LanguageIETF is the current Matroska language element. It
                # takes precedence over legacy Language regardless of order.
                ietf_language = _text(value).lower() or 'und'
            elif child_id == 0x536E:
                track['name'] = _text(value)
            elif child_id == 0x55AB:
                track['hearing_impaired'] = bool(_integer(value))
        if ietf_language is not None:
            track['language'] = ietf_language
        if track['number'] is not None and track['type'] == 17 and track['codec'] in TEXT_CODECS:
            tracks.append(track)
    return tracks


def _timecode_scale(data, start=0):
    found = _first(data, 0x1549A966, start)
    if not found:
        return 1000000
    start, end, _ = found
    for element_id, value_start, value_end, _ in _elements(data, start, end):
        if element_id == 0x2AD7B1:
            return _integer(data[value_start:value_end]) or 1000000
    return 1000000


def _cue_times(data, track_number, scale, start=0):
    found = _first(data, 0x1C53BB6B, start)
    if not found:
        return []
    start, end, _ = found
    result = []
    for element_id, point_start, point_end, _ in _elements(data, start, end):
        if element_id != 0xBB:
            continue
        cue_time, cue_tracks = None, []
        for child_id, value_start, value_end, _ in _elements(data, point_start, point_end):
            if child_id == 0xB3:
                cue_time = _integer(data[value_start:value_end])
            elif child_id == 0xB7:
                for position_id, position_start, position_end, _ in _elements(data, value_start, value_end):
                    if position_id == 0xF7:
                        cue_tracks.append(_integer(data[position_start:position_end]))
        if cue_time is not None and track_number in cue_tracks:
            result.append(int(round(cue_time * scale / 1000000.0)))
    return sorted(set(result))


def _cue_cluster_positions(data, start=0):
    """Return the Cue-indexed Cluster offsets, regardless of Cue track."""
    found = _first(data, 0x1C53BB6B, start)
    if not found:
        return []
    result = []
    cues_start, cues_end, _ = found
    for element_id, point_start, point_end, _ in _elements(data, cues_start, cues_end):
        if element_id != 0xBB:
            continue
        for child_id, value_start, value_end, _ in _elements(data, point_start, point_end):
            if child_id != 0xB7:
                continue
            for position_id, position_start, position_end, _ in _elements(data, value_start, value_end):
                if position_id == 0xF1:
                    result.append(_integer(data[position_start:position_end]))
    return sorted(set(result))


def _block_time(block, cluster_timecode, track_number, scale):
    track = _vint(block, 0)
    if not track or track[2] or track[0] != track_number:
        return None
    timestamp_offset = track[1]
    if len(block) < timestamp_offset + 3:
        return None
    first, second = block[timestamp_offset:timestamp_offset + 2]
    if not isinstance(first, int):
        first = ord(first)
    if not isinstance(second, int):
        second = ord(second)
    relative = (first << 8) | second
    if relative >= 32768:
        relative -= 65536
    return int(round((cluster_timecode + relative) * scale / 1000000.0))


def _one_cluster_times(data, start, end, track_number, scale):
    cluster_timecode = 0
    blocks = []
    for element_id, value_start, value_end, _ in _elements(data, start, end):
        value = data[value_start:value_end]
        if element_id == 0xE7:
            cluster_timecode = _integer(value)
        elif element_id == 0xA3:
            blocks.append(value)
        elif element_id == 0xA0:
            for nested_id, nested_start, nested_end, _ in _elements(data, value_start, value_end):
                if nested_id == 0xA1:
                    blocks.append(data[nested_start:nested_end])
    result = []
    for block in blocks:
        timestamp = _block_time(block, cluster_timecode, track_number, scale)
        if timestamp is not None:
            result.append(timestamp)
    return result


def _cluster_times(data, track_number, scale):
    """Read subtitle starts from every Cluster in a bounded range window."""
    result = []
    for element_id, start, end, _ in _elements(data):
        if element_id == 0x1F43B675:
            result.extend(_one_cluster_times(data, start, end, track_number, scale))
    return sorted(set(result))


def _spread_cluster_positions(cue_positions, windows=24, per_window=3):
    """Visit every timeline window before revisiting its nearby clusters."""
    count = len(cue_positions)
    positions, seen, runs = [], set(), []
    if not count:
        return positions
    window_count = min(windows, count)
    for window in range(window_count):
        center = int((window + 0.5) * count / float(window_count))
        start = max(0, min(count - per_window, center - per_window // 2))
        runs.append(cue_positions[start:start + per_window])
    for neighbor in range(per_window):
        for run in runs:
            if neighbor >= len(run):
                continue
            position = run[neighbor]
            if position not in seen:
                positions.append(position)
                seen.add(position)
    return positions


def _sample_cluster_times(reader, segment_data, cue_positions, track_number, scale):
    # Some Matroska writers only index a handful of subtitle cues even though
    # the actual track is complete. Spread bounded range reads across 24
    # windows. A range may contain several Clusters, including unindexed ones;
    # read all of their block headers before moving to the next window.
    remaining_requests = max(0, reader.max_requests - reader.requests)
    positions = _spread_cluster_positions(cue_positions)[:remaining_requests]
    result = []
    attempted = nonempty = 0
    sampled_fractions = []
    for position in positions:
        if time.time() >= reader.deadline:
            break
        cluster = reader.read(segment_data + position, CLUSTER_READ_BYTES)
        starts = _cluster_times(cluster, track_number, scale)
        result.extend(starts)
        attempted += 1
        nonempty += bool(starts)
        sampled_fractions.append(position / float(cue_positions[-1]) if cue_positions[-1] else 0.0)
    reader.sample_stats = {
        'indexed_clusters': len(cue_positions),
        'planned_clusters': len(positions),
        'attempted_clusters': attempted,
        'cue_clusters': nonempty,
        'coverage_percent': int(round(100 * (max(sampled_fractions) - min(sampled_fractions)))) if sampled_fractions else 0,
        'requests': reader.requests,
        'bytes_mb': round(reader.bytes_read / 1048576.0, 1),
        'elapsed_seconds': round(time.time() - reader.started_at, 1),
        'limit': 'time' if time.time() >= reader.deadline else 'requests' if reader.requests >= reader.max_requests else 'bytes' if reader.bytes_read >= reader.max_bytes else 'positions',
    }
    return sorted(set(result))


def _is_english(track):
    language = (track.get('language') or '').lower().replace('_', '-')
    if language in ('eng', 'en') or language.startswith('en-'):
        return True
    if language not in ('und', ''):
        return False
    # Some releases mark the language undefined but label the subtitle track
    # explicitly, for example "English [CC]". Never override a specified
    # non-English language with a free-form track name.
    return bool(re.match(r'^\s*(?:english|eng)\b', track.get('name') or '', re.I))


def _is_sdh(track):
    name = (track.get('name') or '').lower()
    return bool(track.get('hearing_impaired')) or any(
        token in name for token in ('sdh', 'hearing impaired', 'closed caption', 'closed-caption', 'cc')
    )


def embedded_cue_candidates(source):
    """Return bounded timing samples for every embedded English text track.

    Unsupported containers and incomplete/non-subtitle Cue indexes deliberately
    return no result. The caller can then leave the active subtitle alone
    rather than performing an expensive fallback extraction.
    """
    reader = RangeReader(source)
    header = reader.read(0, INITIAL_READ_BYTES)
    if not header or header[:4] != b'\x1aE\xdf\xa3':
        return []
    segment = _first(header, 0x18538067)
    if not segment:
        return []
    segment_data, _, _ = segment
    positions = _seek_positions(segment_data, header)
    tracks_data = header
    tracks_position = positions.get(0x1654AE6B)
    tracks_start = segment_data if tracks_data is header else 0
    if not _first(tracks_data, 0x1654AE6B, tracks_start) and tracks_position is not None:
        tracks_data = _read_element(reader, tracks_position)
        tracks_start = 0
    tracks = _tracks(tracks_data, tracks_start)
    if not tracks:
        return []
    cues_data = header
    cues_position = positions.get(0x1C53BB6B)
    cues_start = segment_data if cues_data is header else 0
    if not _first(cues_data, 0x1C53BB6B, cues_start) and cues_position is not None:
        cues_data = _read_element(reader, cues_position)
        cues_start = 0
    scale = _timecode_scale(header, segment_data)
    candidates = []
    for track in tracks:
        if not _is_english(track):
            continue
        starts = _cue_times(cues_data, track['number'], scale, cues_start)
        sample_stats = {}
        if len(starts) < 16:
            # Most release files index video/audio in Cues but omit subtitles,
            # or record too few subtitle points to validate a replacement.
            # Add bounded samples from Cue-indexed clusters across the timeline;
            # only block headers are read, never subtitle text or media streams.
            starts = sorted(set(starts + _sample_cluster_times(
                reader,
                segment_data,
                _cue_cluster_positions(cues_data, cues_start),
                track['number'],
                scale,
            )))
            sample_stats = getattr(reader, 'sample_stats', {})
        if starts:
            candidates.append({
                'starts': starts,
                'track_number': track['number'],
                'track_name': track.get('name') or '',
                'is_sdh': _is_sdh(track),
                'sample_stats': sample_stats,
            })
    return candidates


def embedded_cue_starts(source):
    """Return the richest embedded English text timing sample, for compatibility."""
    candidates = embedded_cue_candidates(source)
    if not candidates:
        return []
    # Legacy callers only accept one timeline. Preserve the former preference
    # for the richest cue set, but avoid SDH when cue counts are identical.
    selected = max(candidates, key=lambda candidate: (len(candidate['starts']), not candidate['is_sdh']))
    return selected['starts']


def subtitle_starts(text):
    """Parse external SRT cue start times without looking at subtitle text."""
    if isinstance(text, bytes):
        text = text.decode('utf-8-sig', 'replace')
    starts = []
    for hours, minutes, seconds, milliseconds in re.findall(r'(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->', text or ''):
        starts.append(((int(hours) * 3600 + int(minutes) * 60 + int(seconds)) * 1000) + int(milliseconds))
    return sorted(set(starts))


def _sample(values, limit=320):
    if len(values) <= limit:
        return values
    step = float(len(values) - 1) / float(limit - 1)
    return [values[int(round(index * step))] for index in range(limit)]


def _histogram_offset(reference_starts, target_starts, maximum_offset_ms=30000):
    """Legacy exact-start vote used when ordered matching is inconclusive."""
    reference_starts, target_starts = sorted(set(reference_starts)), sorted(set(target_starts))
    if len(reference_starts) < 6 or len(target_starts) < 12:
        return None
    bins = {}
    for reference in _sample(reference_starts):
        for target in _sample(target_starts):
            offset = reference - target
            if abs(offset) <= maximum_offset_ms:
                bucket = int(round(offset / 100.0)) * 100
                bins[bucket] = bins.get(bucket, 0) + 1
    if not bins:
        return None
    ranked = sorted(bins.items(), key=lambda item: item[1], reverse=True)
    offset, votes = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0
    # Cluster sampling can yield only a handful of subtitle blocks on a sparse
    # release.  Five matching events are sufficient only when the next offset
    # peak is clearly weaker; otherwise no timing is changed.
    if votes < 5 or votes < runner_up * 1.6 + 1:
        return None
    errors = []
    for target in target_starts:
        wanted = target + offset
        index = bisect.bisect_left(reference_starts, wanted)
        nearby = reference_starts[max(0, index - 1):index + 1]
        if not nearby:
            continue
        error = min(nearby, key=lambda value: abs(value - wanted)) - wanted
        if abs(error) <= 400:
            errors.append(error)
    minimum_matches = max(5, int(min(len(reference_starts), len(target_starts)) * 0.18))
    if len(errors) < minimum_matches:
        return None
    errors.sort()
    return {
        'offset_ms': offset,
        'votes': votes,
        'runner_up_votes': runner_up,
        'matched_cues': len(errors),
        'median_residual_ms': errors[len(errors) // 2],
        'method': 'histogram',
    }


def _ordered_match_errors(reference_starts, target_starts, offset_ms, tolerance_ms=400):
    """Pair nearby cue starts in order, using every cue at most once."""
    reference_index, target_index = 0, 0
    errors = []
    while reference_index < len(reference_starts) and target_index < len(target_starts):
        error = reference_starts[reference_index] - (target_starts[target_index] + offset_ms)
        if abs(error) <= tolerance_ms:
            errors.append(error)
            reference_index += 1
            target_index += 1
        elif error < 0:
            # This embedded cue has no Dutch counterpart near this offset.
            reference_index += 1
        else:
            # This Dutch cue is an extra/split cue with no nearby counterpart.
            target_index += 1
    return errors


def _median(values):
    if not values:
        return 0
    values = sorted(values)
    middle = len(values) // 2
    if len(values) % 2:
        return values[middle]
    return int(round((values[middle - 1] + values[middle]) / 2.0))


def _ordered_offset(reference_starts, target_starts, maximum_offset_ms=30000):
    """Find a fixed offset from ordered cue pairs despite split/merged captions."""
    reference_starts, target_starts = sorted(set(reference_starts)), sorted(set(target_starts))
    if len(reference_starts) < 6 or len(target_starts) < 12:
        return None

    tolerance_ms = 400
    step_ms = 100
    minimum_matches = max(5, int(min(len(reference_starts), len(target_starts)) * 0.18))
    candidates = {}
    for offset_ms in range(-maximum_offset_ms, maximum_offset_ms + 1, step_ms):
        errors = _ordered_match_errors(reference_starts, target_starts, offset_ms, tolerance_ms)
        if len(errors) < minimum_matches:
            continue
        # Move the coarse scan result to the median observed timing error,
        # then score the resulting one-to-one pairing again.
        refined_offset = int(round((offset_ms + _median(errors)) / float(step_ms))) * step_ms
        refined_errors = _ordered_match_errors(reference_starts, target_starts, refined_offset, tolerance_ms)
        if len(refined_errors) < minimum_matches:
            continue
        result = {
            'offset_ms': refined_offset,
            'votes': len(refined_errors),
            'matched_cues': len(refined_errors),
            'median_residual_ms': _median(refined_errors),
            'mean_abs_residual_ms': int(round(sum(abs(error) for error in refined_errors) / float(len(refined_errors)))),
            'method': 'ordered',
        }
        current = candidates.get(refined_offset)
        if current is None or (
            result['matched_cues'], -result['mean_abs_residual_ms']
        ) > (
            current['matched_cues'], -current['mean_abs_residual_ms']
        ):
            candidates[refined_offset] = result

    if not candidates:
        return None

    ranked = sorted(
        candidates.values(),
        key=lambda result: (
            -result['matched_cues'],
            result['mean_abs_residual_ms'],
            abs(result['median_residual_ms']),
        ),
    )
    winner = ranked[0]
    # Nearby offsets are the same broad alignment peak. Only an alternative
    # beyond two matching tolerances can make the winner ambiguous.
    rivals = [
        result for result in ranked[1:]
        if abs(result['offset_ms'] - winner['offset_ms']) > tolerance_ms * 2
    ]
    runner_up = rivals[0] if rivals else None
    runner_up_votes = runner_up['matched_cues'] if runner_up else 0
    if runner_up and winner['matched_cues'] < runner_up_votes * 1.15 + 1:
        return None
    winner['runner_up_votes'] = runner_up_votes
    zero_errors = _ordered_match_errors(reference_starts, target_starts, 0, tolerance_ms)
    winner['zero_offset_matches'] = len(zero_errors)
    winner['zero_offset_mean_abs_residual_ms'] = (
        int(round(sum(abs(error) for error in zero_errors) / float(len(zero_errors))))
        if zero_errors else None
    )
    return winner


def find_offset(reference_starts, target_starts, maximum_offset_ms=30000):
    """Find an unambiguous fixed offset from ordered embedded/external cues."""
    return (
        _ordered_offset(reference_starts, target_starts, maximum_offset_ms)
        or _histogram_offset(reference_starts, target_starts, maximum_offset_ms)
    )


def find_best_offset(reference_candidates, target_starts, maximum_offset_ms=30000):
    """Find the strongest safe offset across English tracks.

    A non-SDH track wins only after matched-cue count, vote count and residual
    accuracy are equal. This keeps SDH as a valid reference when it is the
    only or materially stronger timing match.
    """
    matches = []
    for candidate in reference_candidates or []:
        result = find_offset(candidate.get('starts') or [], target_starts, maximum_offset_ms)
        if not result:
            continue
        result = dict(result)
        result['track_number'] = candidate.get('track_number')
        result['track_name'] = candidate.get('track_name') or ''
        result['is_sdh'] = bool(candidate.get('is_sdh'))
        matches.append(result)
    if not matches:
        return None
    return sorted(
        matches,
        key=lambda result: (
            -result['matched_cues'],
            -result['votes'],
            abs(result['median_residual_ms']),
            result['is_sdh'],
            result['track_number'] if result['track_number'] is not None else -1,
        ),
    )[0]


def _parse_timestamp(value):
    hours, minutes, seconds, milliseconds = re.match(r'(\d{2}):(\d{2}):(\d{2})[,.](\d{3})', value).groups()
    return ((int(hours) * 3600 + int(minutes) * 60 + int(seconds)) * 1000) + int(milliseconds)


def _format_timestamp(milliseconds):
    milliseconds = max(0, int(milliseconds))
    hours, milliseconds = divmod(milliseconds, 3600000)
    minutes, milliseconds = divmod(milliseconds, 60000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return '%02d:%02d:%02d,%03d' % (hours, minutes, seconds, milliseconds)


def retime_srt(text, offset_ms):
    """Shift all SRT timing rows and preserve the cue body verbatim."""
    def replace(match):
        return '%s%s%s' % (
            _format_timestamp(_parse_timestamp(match.group('start')) + offset_ms),
            match.group('join'),
            _format_timestamp(_parse_timestamp(match.group('end')) + offset_ms),
        )
    return TIMING_LINE.sub(replace, text)
