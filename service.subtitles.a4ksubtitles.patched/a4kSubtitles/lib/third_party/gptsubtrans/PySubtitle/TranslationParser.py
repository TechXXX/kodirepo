from __future__ import annotations

import logging
import re

from PySubtitle.Instructions import DEFAULT_TASK_TYPE
from PySubtitle.Options import Options
from PySubtitle.Helpers.Subtitles import MergeTranslations
from PySubtitle.Helpers.Text import IsTextContentEqual
from PySubtitle.SubtitleLine import SubtitleLine
from PySubtitle.SubtitleError import NoTranslationError, TranslationError, UntranslatedLinesError
from PySubtitle.SubtitleValidator import SubtitleValidator
from PySubtitle.Translation import Translation

default_pattern = (
    r"#(?P<number>\d+)"
    r"(?:[\s\r\n]+Original>[\s\r\n]+(?P<original>[\s\S]*?))?"
    r"[\s\r\n]+Translation>"
    r"(?:[\s\r\n]?(?P<body>[\s\S]*?))?"
    r"(?=\n#\d|\Z)"
)

fallback_patterns = [
    r"#(?P<number>\d+)(?:[\s\r\n]+Original>[\s\r\n]+(?P<original>[\s\S]*?))?[\s\r\n]*(?:Translation>(?:[\s\r\n]+(?P<body>[\s\S]*?))?(?:(?=\n{2,})|\Z))",
    r"#(?P<number>\d+)(?:[\s\r\n]+Original[>:][\s\r\n]+(?P<original>[\s\S]*?))?[\s\r\n]*(?:Translation[>:](?:[\s\r\n]+(?P<body>[\s\S]*?))?(?:(?=\n{2,})|\Z))",
    r"#(?P<number>\d+)(?:[\s\r\n]+Original[>:][\s\r\n]+(?P<original>[\s\S]*?))?[\s\r\n]*Translation[>:][\s\r\n]+(?P<body>[\s\S]*?)(?=(?:\n{2,}#)|\Z)",
    r"#(?P<number>\d+)(?:[\s\r\n]*Original[>:][\s\r\n]*(?P<original>[\s\S]*?))?[\s\r\n]*Translation[>:][\s\r\n]*(?P<body>[\s\S]*?)(?=(?:\n{2,}#)|\Z)",
    r"#(?P<number>\d+)[\s\r\n]+Translation[>:][\s\r\n]+(?P<body>[\s\S]*?)(?=(?:\n{2,}#)|\Z)",
    r"#(?P<number>\d+)(?:[\s\r\n]+(?P<body>[\s\S]*?))?(?:(?=\n{2,})|\Z)"  # Just the number and translation
    ]

class TranslationParser:
    """
    Extract translated subtitles from the AI translation response
    """
    def __init__(self, task_type : str, options : Options):
        self.options = options
        self.text = None
        self.translations = {}
        self.translated = []
        self.errors = []
        self.metatags = ["<summary>", "scene"]
        self.task_type = task_type
        self.regex_patterns = self.GetRegularExpressionPatterns(task_type)

    def GetRegularExpressionPatterns(self, task_type : str = DEFAULT_TASK_TYPE):
        """
        Returns a list of regular expressions to try for extracting translations
        """
        # Use the current default pattern, and fall back on alternative/older patterns if no matches are found
        patterns = [
            re.compile(
                pattern.replace(DEFAULT_TASK_TYPE, task_type), re.MULTILINE) for pattern in [default_pattern] + fallback_patterns
            ]
        return patterns

    def ProcessTranslation(self, translation : Translation):
        """
        Extract lines from a batched translation, using the
        pre-defined pattern to match each line, or a list of fallbacks
        if the match fails.
        """
        self.text = translation.text if isinstance(translation, Translation) else str(translation)

        if not self.text:
            raise TranslationError("No translated text provided", translation=translation)

        for template in self.regex_patterns:
            matches = self.FindMatches(f"{self.text}\n\n", template)

            if matches:
                break

        logging.debug(f"Matches: {str(matches)}")

        subs = [SubtitleLine.FromDictionary(match) for match in matches]
        # Keep every parsed cue: a repeated or wrong model-supplied number must not
        # discard a distinct cue before its echoed source text can identify it.
        self.parsed_lines = subs
        self.translations = {
            sub.key: sub for sub in subs
            }

        if not self.translations:
            return None

        self.translated = MergeTranslations(self.translated, self.translations.values())

        self.errors = self.ValidateTranslations()

        if self.errors and self.translated:
            self._fix_unclosed_tags()
            self.errors = self.ValidateTranslations()

        return self.translated

    def FindMatches(self, text, template):
        """
        re.findall has some very unhelpful behaviour, so we use finditer instead.
        """
        return [{
            'body': match.group('body'),
            'number': match.groupdict().get('number'),
            'start': match.groupdict().get('start'),
            'end': match.groupdict().get('end'),
            'original': match.groupdict().get('original')
            } for match in template.finditer(text)]

    def MatchTranslations(self, originals : list[SubtitleLine]):
        """Match response cues to source cues without trusting incorrect numbers."""
        if not originals:
            raise ValueError("Original subtitles not provided")

        candidates = list(getattr(self, 'parsed_lines', self.translations.values()))
        remaining = list(candidates)
        assigned = {}

        def assign(item, candidate, reason):
            supplied_number = candidate.number
            if candidate.original and IsTextContentEqual(candidate.text, item.text):
                # Some responses put the English source under Translation>.
                candidate.text, candidate.original = candidate.original, item.text
            candidate.number = item.number
            candidate.start = item.start
            candidate.end = item.end
            item.translation = candidate.text
            assigned[id(item)] = candidate
            remaining[:] = [other for other in remaining if other is not candidate]
            if supplied_number != item.number:
                logging.warning(
                    "Recovered AI subtitle cue number %s as %s using %s"
                    % (supplied_number, item.number, reason)
                )

        # The model usually echoes Original>. Match unique source text first, so a
        # wrong number inside this batch cannot steal another cue's translation.
        for item in originals:
            source_matches = [
                source for source in originals
                if IsTextContentEqual(source.text, item.text)
            ]
            text_matches = [
                candidate for candidate in remaining
                if candidate.original and IsTextContentEqual(candidate.original, item.text)
            ]
            if len(source_matches) == 1 and len(text_matches) == 1:
                assign(item, text_matches[0], 'echoed source text')

        # Fall back to the supplied number only when it is unique and its echoed
        # source, if present, does not contradict the numbered source cue.
        for item in originals:
            if id(item) in assigned:
                continue
            number_matches = [
                candidate for candidate in remaining
                if candidate.number == item.number
            ]
            if len(number_matches) != 1:
                continue
            candidate = number_matches[0]
            if candidate.original and not (
                IsTextContentEqual(candidate.original, item.text)
                or IsTextContentEqual(candidate.text, item.text)
            ):
                continue
            assign(item, candidate, 'unique cue number')

        matched = [assigned[id(item)] for item in originals if id(item) in assigned]
        unmatched = [item for item in originals if id(item) not in assigned]
        for item in unmatched:
            item.translation = None

        if unmatched:
            self.TryFuzzyMatches(unmatched)
            self.LogUnmatchedLines(originals, unmatched)
            self.errors.append(UntranslatedLinesError(
                f"No translation found for {len(unmatched)} lines",
                lines=unmatched,
                translation=candidates[0] if candidates else None,
            ))

        return matched, unmatched

    def LogUnmatchedLines(self, originals : list[SubtitleLine], unmatched : list[SubtitleLine]):
        """Log cue numbers and match facts only; subtitle text never goes into the log."""
        def line_number(line):
            try:
                return int(line.number)
            except (TypeError, ValueError):
                return None

        returned = list(getattr(self, 'parsed_lines', self.translations.values()))
        expected_numbers = {line_number(line) for line in originals}
        returned_numbers = {line_number(line) for line in returned}
        logging.warning(
            "AI subtitle match diagnostics: source=%d parsed=%d matched=%d missing=%d missing_numbers=%s unexpected_numbers=%s"
            % (len(originals), len(returned), len(originals) - len(unmatched),
               len(unmatched), [line.number for line in unmatched[:10]],
               sorted(number for number in returned_numbers - expected_numbers if number is not None)[:10])
        )
        for item in unmatched[:5]:
            number = line_number(item)
            nearby = [
                line for line in returned
                if number is not None and line_number(line) is not None
                and abs(line_number(line) - number) <= 2
            ][:5]
            # Repeated source text (e.g. "Yes.") is ambiguous, so it is never matched by text.
            duplicate_source = sum(
                1 for source in originals if IsTextContentEqual(source.text, item.text)
            ) > 1
            logging.warning(
                "AI subtitle unmatched cue: number=%s start=%s words=%d duplicate_source=%s fuzzy_found=%s nearby_numbers=%s"
                % (item.number, item.srt_start, len(str(item.text or "").split()),
                   duplicate_source, bool(item.translation),
                   [line.number for line in nearby])
            )

    def TryFuzzyMatches(self, unmatched : list [SubtitleLine]):
        """
        Try to match translations to their source lines using heuristics
        """
        possible_matches : list[(SubtitleLine,SubtitleLine)] = []
        for item in (item for item in unmatched if item.number is not None):
            for translation in self.translations.values():
                if translation.original:
                    if IsTextContentEqual(translation.original, item.text):
                        # A match on the original text is pretty compelling
                        possible_matches.append((item, translation))
                        continue
                    elif IsTextContentEqual(translation.text, item.text):
                        # GPT sometimes swaps the original and translated text - swap them back
                        translation.text = translation.original
                        translation.original = item.text
                        possible_matches.append((item, translation))
                        continue

                    #TODO: check for merged lines

        if possible_matches:
            for item, translation in possible_matches:
                logging.warning(
                    f"Found fuzzy match for line {item.number} in translation line {translation.number}"
                )
                item.translation = f"#Fuzzy: {translation.text}"
                #unmatched.remove(item)

    def ValidateTranslations(self):
        """
        Check if the translation seems at least plausible
        """
        if not self.translated:
            return [ NoTranslationError("Failed to extract translations from response", translation=self.text) ]

        validator = SubtitleValidator(self.options)
        return validator.ValidateTranslations(self.translated)

    def _fix_unclosed_tags(self):
        """
        Check if the last line of the translation picked up a summary without a closing tag
        """
        last_line : SubtitleLine = self.translated[-1]

        # Use a regex to check for opening metatags and ensure there is a matching close tag. If not, truncate the text at the tag.
        re_opening = re.compile(rf"<({'|'.join(self.metatags)})>", re.IGNORECASE)

        for match in re_opening.finditer(last_line.text):
            tag = match.group(1)
            if not re.search(rf"</{tag}>", last_line.text):
                logging.warning(f"Found unclosed tag {tag} in translation: {tag}")
                last_line.text = last_line.text[:match.start()]
