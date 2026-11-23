"""Conservative, offline Dutch check for unlabelled sidecar SRT files."""

import html
import re
from collections import Counter


_DUTCH_DISTINCTIVE = frozenset((
	'het een niet jij jullie mijn jouw zijn geen hebben heb hebt heeft wordt '
	'omdat terwijl misschien toch alsjeblieft alstublieft bedankt'
).split())
_DUTCH_SUPPORT = frozenset((
	'ik je jou wij we zij ze ons onze hun ben bent had hadden word worden werd '
	'werden zal zullen zou zouden kan kunt kunnen kon konden moet moeten mag '
	'mogen wel ook nog maar alleen juist hoewel tenzij doordat ergens nergens '
	'heel veel meer minder weinig genoeg goed graag even natuurlijk eigenlijk '
	'altijd nooit soms vaak straks vandaag gisteren iets niets iemand niemand '
	'iedereen elkaar zichzelf alweer helemaal gewoon inderdaad'
).split())
_OTHER_MARKERS = {
	'en': 'the and you your not this that with have has were are they them their what why where when who how could should would will dont didnt isnt cant wont im youre hes shes ive weve',
	'de': 'ich nicht und ist wir sie mich dich dir mir euch der die das den dem des ein eine einem einen eines kein keine haben habe hast hatte werden wird wurde aber noch auch schon weil wenn dass für über müssen sehr vielleicht',
	'sv': 'och att det jag inte är som för har med mig dig oss ni ska skulle kommer varför vad vem här där mycket också',
	'da': 'og at det jeg ikke er som for har med mig dig os skal ville kommer hvorfor hvad hvem hvor her der meget også',
}
_OTHER_MARKERS = {language: frozenset(words.split()) for language, words in _OTHER_MARKERS.items()}
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_TIMECODE = re.compile(r'^\s*\d{1,2}:\d{2}:\d{2}[,.]\d{3}\s*-->')
_HTML_TAG = re.compile(r'<[^>]+>')
_SRT_TAG = re.compile(r'\{[^}]+\}')


def detect_dutch_srt(path):
	"""Return True only when a useful subtitle sample clearly looks Dutch."""
	try:
		with open(path, 'rb') as stream: raw = stream.read(512 * 1024)
	except (OSError, TypeError): return False
	for encoding in ('utf-8-sig', 'utf-16', 'cp1252'):
		try:
			content = raw.decode(encoding)
			break
		except UnicodeError: continue
	else: return False
	words = []
	for line in content.splitlines():
		line = line.strip()
		if not line or line.isdigit() or _TIMECODE.match(line) or line.upper() == 'WEBVTT': continue
		line = _SRT_TAG.sub(' ', _HTML_TAG.sub(' ', html.unescape(line)))
		words.extend(_WORD.findall(line.lower()))
	if len(words) < 160: return False
	if len(words) > 1200:
		middle = len(words) // 2
		words = words[:400] + words[middle - 200:middle + 200] + words[-400:]
	counts = Counter(words)
	# Cap repetitions so one common word cannot decide the language alone.
	distinctive_score = sum(min(counts[word], 8) for word in _DUTCH_DISTINCTIVE)
	support_score = sum(min(counts[word], 4) for word in _DUTCH_SUPPORT)
	dutch_score = 2 * distinctive_score + support_score
	other_score = max(sum(min(counts[word], 8) for word in markers) for markers in _OTHER_MARKERS.values())
	distinct_dutch_markers = sum(counts[word] > 0 for word in _DUTCH_DISTINCTIVE)
	return (distinctive_score >= 12 and distinct_dutch_markers >= 5
		and dutch_score >= 2.5 * max(other_score, 1)
		and dutch_score >= 0.04 * len(words))
