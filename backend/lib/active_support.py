"""Small general-purpose helpers: blank/present, inflections and JSON encoding."""

import json
import re
from datetime import datetime, timezone

# The code points of the Unicode White_Space property. A string made only of these is blank.
WHITE_SPACE = [
    0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x20, 0x85, 0xA0, 0x1680, *range(0x2000, 0x200B),
    0x2028, 0x2029, 0x202F, 0x205F, 0x3000,
]
BLANK_RE = re.compile('[%s]*' % ''.join(chr(code) for code in WHITE_SPACE))

# Escaped in JSON output so that a response can be embedded in HTML safely:
# <, >, & and the line and paragraph separators U+2028 and U+2029.
ESCAPED_CHARS = {code: '\\u%04x' % code for code in (0x3C, 0x3E, 0x26, 0x2028, 0x2029)}


def blank(value):
    """None, False, whitespace-only strings and empty collections are blank."""
    if value is None or value is False:
        return True
    if isinstance(value, str):
        return BLANK_RE.fullmatch(value) is not None
    if isinstance(value, (dict, list, tuple, set)):
        return len(value) == 0
    return False


def present(value):
    return not blank(value)


def underscore(camel_cased_word):
    """'CreatePlayers' -> 'create_players'"""
    return re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', camel_cased_word).lower()


def camelize(term):
    """'create_players' -> 'CreatePlayers'"""
    return ''.join(part.capitalize() for part in term.split('_'))


def pluralize(word):
    """'player' -> 'players' (regular nouns only)"""
    return word + 's'


def singularize(word):
    """'players' -> 'player' (regular nouns only)"""
    return word[:-1] if word.endswith('s') else word


def xmlschema(time):
    """A time as ISO 8601 in UTC with millisecond precision: 2021-12-28T18:47:06.265Z"""
    if time.tzinfo is not None:
        time = time.astimezone(timezone.utc)
    return time.strftime('%Y-%m-%dT%H:%M:%S') + '.%03dZ' % (time.microsecond // 1000)


def as_json(value):
    """Reduce a value to plain JSON types. Objects describe themselves through as_json()."""
    if hasattr(value, 'as_json'):
        return as_json(value.as_json())
    if isinstance(value, dict):
        return {str(key): as_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [as_json(item) for item in value]
    if isinstance(value, datetime):
        return xmlschema(value)
    return value


def to_json(value):
    """Compact JSON text, as rendered in response bodies."""
    text = json.dumps(as_json(value), separators=(',', ':'), ensure_ascii=False)
    return text.translate(ESCAPED_CHARS)
