"""Deterministic, invariant-safe synthetic benchmark corruption."""

import re
import unicodedata
try:
    from .benchmark_metrics import TOKEN_RE, tokenize
except ImportError:
    from benchmark_metrics import TOKEN_RE, tokenize


_SUPPORTED = {"P5", "P6", "R3"}
_SEVERITY = {"P5": "minor", "P6": "major", "R3": "major"}
_CLASS = {"P5": "korean-translationese", "P6": "korean-translationese", "R3": "section-tense"}
_COUNT_MAP = {"is": "are", "are": "is", "was": "were", "were": "was", "has": "have", "have": "has"}
_METHODS_MAP = {
    "was": "is", "were": "are", "measured": "measure", "deposited": "deposit",
    "used": "use", "performed": "perform", "analyzed": "analyze", "analysed": "analyse",
    "collected": "collect", "prepared": "prepare", "calculated": "calculate",
    "recorded": "record", "obtained": "obtain", "applied": "apply", "added": "add",
    "mixed": "mix", "incubated": "incubate", "fabricated": "fabricate", "synthesized": "synthesize",
}
_FIGURE_MAP = {"shows": "showed", "lists": "listed", "indicates": "indicated", "demonstrates": "demonstrated"}
_SECTION_WORDS = {"methods", "method", "procedure", "procedures"}
_FIGURE_WORDS = {"figure", "fig", "table"}
_SENTENCE_STARTERS = {
    "a", "an", "the", "we", "this", "these", "it", "in", "after", "during", "using",
    "for", "when", "if", "because", "methods", "method", "results", "figure", "fig", "table",
}
_VERB_STARTERS = set(_COUNT_MAP) | set(_METHODS_MAP) | set(_FIGURE_MAP) | {"measured", "tested"}
_SAFE_SCIENTIFIC = {
    "analysis", "data", "dna", "film", "films", "ftir", "ir", "material",
    "materials", "measurement", "measurements", "methods", "nmr", "pcr", "results",
    "rna", "sample", "samples", "sem", "solution", "solutions", "tem", "uv", "xps",
    "graphene",
    "xrd", "xrf",
}
_NAME_MODIFIERS = {
    "also", "carefully", "currently", "directly", "further", "later", "newly",
    "previously", "quickly", "rapidly", "recently", "strongly", "subsequently",
    "unexpectedly", "widely",
}
_NAME_CONTEXT = {
    "agency", "association", "center", "centre", "college", "company", "corp",
    "corporation", "foundation", "group", "hospital", "institute", "laboratory",
    "laboratories", "ltd", "press", "researchers", "school", "society", "team",
    "university",
}
_UNKNOWN_VERBS = {
    "contains", "confirms", "decreases", "describes", "differs", "exhibits",
    "forms", "includes", "increases", "indicates", "interacts", "observes",
    "produces", "provides", "remains", "reports", "reveals", "shows", "supports",
    "uses", "yields",
}


def _token_spans(text):
    return [(match.group(), match.start(), match.end()) for match in TOKEN_RE.finditer(text)]


def _is_capitalized_word(token):
    return token.isalpha() and token[0].isupper()


def _is_safe_scientific(tokens, index):
    token = tokens[index]
    if token.lower() in _SAFE_SCIENTIFIC:
        return True
    return (
        token.lower() == "x"
        and index + 2 < len(tokens)
        and tokens[index + 1] == "-"
        and tokens[index + 2].lower() == "ray"
    ) or (
        token.lower() == "ray"
        and index >= 2
        and tokens[index - 1] == "-"
        and tokens[index - 2].lower() == "x"
    )


def _following_word(tokens, index):
    for token in tokens[index + 1:]:
        if token.isalpha():
            return token
        if token in {".", "?", "!", ":", ";"}:
            return None
    return None


def _looks_like_verb(token):
    lower = token.lower()
    return lower in _VERB_STARTERS or lower in _UNKNOWN_VERBS or lower.endswith(("ed", "ing"))


def _unsafe(text):
    if re.search(r"\d", text) or re.search(r"\[\s*\d|\bet\s+al\.?\b|\bdoi\s*:", text, re.I):
        return True
    tokens = tokenize(text)
    for index, token in enumerate(tokens):
        if not token.isalpha():
            continue
        previous = tokens[index - 1] if index else None
        boundary = index == 0 or previous in {".", "?", "!", ":", ";"}
        lower = token.lower()
        if _is_safe_scientific(tokens, index):
            continue
        if len(token) == 1 and token.isupper():
            if (
                index + 2 < len(tokens)
                and tokens[index + 1] == "."
                and _is_capitalized_word(tokens[index + 2])
            ):
                return True
        if token.isupper() and len(token) > 1:
            return True
        if not _is_capitalized_word(token):
            continue
        if boundary and lower in _SENTENCE_STARTERS:
            continue
        if not boundary:
            return True
        following = _following_word(tokens, index)
        if following and (
            _is_capitalized_word(following)
            or following.lower() in _NAME_MODIFIERS
            or following.lower() in _NAME_CONTEXT
            or _looks_like_verb(following)
        ):
            return True
        return True
    return False


def _token_index(text, character_offset):
    return len(tokenize(text[:character_offset]))


def _one_edit_result(gold, corrupted, start, replacement, error_id, source_doc_id, field, source_width=1):
    source_tokens = tokenize(corrupted)
    # The edit span is supplied by the caller as the first token of the corrupted form.
    source_span = [start, start + source_width]
    edit = {
        "span": source_span,
        "class": error_id,
        "severity": _SEVERITY[error_id],
        "accept": [tokenize(replacement)],
    }
    if source_tokens[source_span[0]:source_span[1]] == tokenize(replacement):
        raise ValueError("generator did not inject a corruption")
    return {
        "input": corrupted,
        "gold": gold,
        "edits": [edit],
        "meta": {
            "field": field,
            "error_class": None,
            "severity": None,
            "origin": "synthetic",
            "no_edit": False,
            "source_doc_id": source_doc_id,
            "protected_names": [],
            "review": "pending",
        },
    }


def _find_token(text, wanted, start=0):
    for token, left, right in _token_spans(text):
        if left >= start and token.lower() == wanted.lower():
            return token, left, right
    return None


def _p5(gold, article_targets):
    if not article_targets:
        raise ValueError("P5 requires article_targets, a manual tagged noun-phrase list")
    if not all(isinstance(target, str) and target.strip() for target in article_targets):
        raise ValueError("article_targets must contain non-empty strings")
    target = article_targets[0]
    target_tokens = tokenize(target)
    if len(target_tokens) < 2 or target_tokens[0].lower() not in {"a", "an", "the"}:
        raise ValueError("article_targets must tag an article plus its noun phrase")
    spans = _token_spans(gold)
    matches = []
    for index in range(len(spans) - len(target_tokens) + 1):
        if [item[0] for item in spans[index:index + len(target_tokens)]] == target_tokens:
            matches.append((index, spans[index], spans[index + 1]))
    if len(matches) != 1:
        raise ValueError("article_targets must identify exactly one phrase")
    index, article, next_token = matches[0]
    corrupted = gold[:article[1]] + gold[next_token[1]:]
    source_start = index
    return corrupted, source_start, target


def _replace_first_token(gold, wanted, replacement):
    found = _find_token(gold, wanted)
    if not found:
        return None
    token, left, right = found
    return gold[:left] + replacement + gold[right:], _token_index(gold, left), token


def generate_case(passage, error_id, *, article_targets=None, source_doc_id="synthetic", field="synthetic"):
    """Inject exactly one safe P5, P6, or R3 corruption into a CC BY passage.

    P5 requires manually tagged article+noun phrases. P6 uses its closed
    agreement/countability map. R3 selects a past-tense Methods procedure or a
    present-tense figure/table reference. Unsafe passages are rejected rather
    than attempting to infer protected content.
    """
    if error_id not in _SUPPORTED:
        raise ValueError(f"unsupported synthetic grade: {error_id}; supported grades are P5, P6, R3")
    gold = unicodedata.normalize("NFC", passage)
    if not isinstance(source_doc_id, str) or not source_doc_id:
        raise ValueError("source_doc_id must be a non-empty string")
    if _unsafe(gold):
        raise ValueError("unsafe passage: numbers, names, or citations are not eligible for synthesis")

    if error_id == "P5":
        corrupted, start, replacement = _p5(gold, article_targets)
    elif error_id == "P6":
        selected = next(((word, wrong) for word, wrong in _COUNT_MAP.items() if _find_token(gold, word)), None)
        if selected is None:
            raise ValueError("P6 passage has no is/are, was/were, or has/have target")
        word, wrong = selected
        corrupted, start, _ = _replace_first_token(gold, word, wrong)
        replacement = word
    else:
        lower = gold.lower()
        selected = None
        if any(re.search(rf"\b{re.escape(word)}\b", lower) for word in _SECTION_WORDS):
            selected = next(((word, replacement) for word, replacement in _METHODS_MAP.items() if _find_token(gold, word)), None)
        if selected is None and re.search(r"\b(?:figure|fig\.?|table)\b", lower):
            selected = next(((word, replacement) for word, replacement in _FIGURE_MAP.items() if _find_token(gold, word)), None)
        if selected is None:
            raise ValueError("R3 requires a Methods procedure or figure/table reference target")
        word, wrong = selected
        corrupted, start, _ = _replace_first_token(gold, word, wrong)
        replacement = word

    source_width = len(tokenize(replacement)) - 1 if error_id == "P5" else 1
    result = _one_edit_result(gold, corrupted, start, replacement, error_id, source_doc_id, field, source_width)
    if len([op for op in _token_opcodes(corrupted, gold) if op[0] != "equal"]) != 1:
        raise ValueError("generator must produce exactly one token edit")
    return result


def _token_opcodes(source, gold):
    import difflib

    return difflib.SequenceMatcher(None, tokenize(source), tokenize(gold), autojunk=False).get_opcodes()
