"""Bounded, source-derived support for the conservative event matcher.

This is transient comparison evidence, not a new event identity or a fact
checker. Missing or ambiguous summaries abstain. Original anchor signatures
and persisted article-to-event mappings remain unchanged.
"""

from collections import Counter
from dataclasses import dataclass, field
import math
import re
import unicodedata


ACTION_WORDS = {
    'allow': 'allow allows allowed allowing approve approves approved approval permit permits permitted clear clears cleared lift lifts lifted',
    'reject': 'reject rejects rejected deny denies denied block blocks blocked',
    'resign': 'resign resigns resigned resigning quit quits quitting',
    'appoint': 'appoint appoints appointed appointment appointing name names named',
    'resume': 'resume resumes resumed resuming restart restarts restarted',
    'stop': 'stop stops stopped stopping suspend suspends suspended halt halts halted',
    'win': 'win wins winning won winner winners',
    'lose': 'lose loses losing lost loser losers',
    'orbit': 'orbit orbits orbital orbiting',
    'deport': 'deport deports deported deporting deportation deportations',
    'repatriate': 'repatriate repatriates repatriated repatriation repatriations',
    'charge': 'charge charges charged charging assault assaulting',
    'shoot': 'shoot shoots shot shooting shootings',
    'investigate': 'investigate investigates investigated investigation investigations probe probes',
    'rejoin': 'rejoin rejoins rejoining',
    'price_record': 'recordhigh',
    'execute': 'execute executes executed executing execution executions',
}
ACTION_LOOKUP = {word: action for action, words in ACTION_WORDS.items() for word in words.split()}
OPPOSITES = (('allow', 'reject'), ('resign', 'appoint'), ('resume', 'stop'), ('win', 'lose'))
NAME_STOP = set(('the a an this that these those it its he she they we you his her their '
                 'why how what new latest first second third monday tuesday wednesday '
                 'thursday friday saturday sunday january february march april may june '
                 'july august september october november december news world video '
                 'court government officials official president minister chief king '
                 'prison federal state report reports').split())


@dataclass(frozen=True)
class SummaryContext:
    summaries: dict
    weights: dict
    corpus_size: int
    derived: dict = field(default_factory=dict, compare=False, repr=False)


MAX_DERIVED_FEATURES = 100000


def cached(context, kind, key, compute):
    """Projection-local, bounded memoization; never persist derived evidence."""
    memo = getattr(context, 'derived', None)
    if memo is None:
        return compute()
    slot = (kind, key)
    if slot in memo:
        return memo[slot]
    value = compute()
    if len(memo) < MAX_DERIVED_FEATURES:
        memo[slot] = value
    return value


def context_key(row):
    normalized = row.get('normalized')
    if normalized is None:
        text = unicodedata.normalize('NFKC', row.get('title', '')).casefold()
        normalized = ' '.join(re.findall(r'[^\W_]+', text, re.UNICODE))
    return (row.get('language', ''), row.get('published_at', ''), normalized)


def build_summary_context(articles, tokenize):
    """Only use supplied summaries; do not guess or borrow a collided anchor."""
    candidates = {}
    frequency = Counter()
    count = 0
    for article in articles:
        summary = article.get('summary')
        if not isinstance(summary, str) or not summary.strip() or len(summary) > 2000:
            continue
        summary = unicodedata.normalize('NFKC', summary).strip()
        candidates.setdefault(context_key(article), set()).add(summary)
        frequency.update(tokenize({'title': summary}))
        count += 1
    summaries = {key: next(iter(values)) for key, values in candidates.items() if len(values) == 1}
    weights = {token: 1 + math.log((count + 1) / (frequency[token] + 1)) for token in frequency}
    return SummaryContext(summaries, weights, count)


def actions(text):
    text = unicodedata.normalize('NFKC', text).casefold()
    text = re.sub(r'\ball[ -]time[ -]high\b|\brecord[ -]high\b', 'recordhigh', text)
    text = re.sub(r'\b(?:steps?|stepped) down\b', 'resign', text)
    text = re.sub(r'\bcircles? (?:the )?earth\b', 'orbit', text)
    text = re.sub(r'\blethal[ -]+injections?\b', 'execute', text)
    return {ACTION_LOOKUP[word] for word in re.findall(r'[a-z]+', text) if word in ACTION_LOOKUP}


def evidence_action_conflict(left, right, context=None):
    """A summary must never override exclusive opposing title outcomes."""
    a = cached(context, 'actions', left.get('title', ''), lambda: actions(left.get('title', '')))
    b = cached(context, 'actions', right.get('title', ''), lambda: actions(right.get('title', '')))
    survived = lambda title: cached(context, 'survived', title, lambda: bool(re.search(r'\bsurviv(?:e|es|ed|ing)\b', title.casefold())))
    died = lambda title: cached(context, 'died', title, lambda: bool(re.search(r'\b(?:dies|died|put to death|(?:was|is) executed)\b', title.casefold())))
    if survived(left['title']) and died(right['title']) or survived(right['title']) and died(left['title']):
        return True
    for positive, negative in OPPOSITES:
        if positive in a and negative in b and negative not in a and positive not in b:
            return True
        if negative in a and positive in b and positive not in a and negative not in b:
            return True
    return False


def names(text):
    return {word.casefold() for word in re.findall(r'\b(?:[A-Z][a-z]{2,}|[A-Z]{2,})\b', text)
            if word.casefold() not in NAME_STOP and not re.fullmatch(r'[IVXLCDM]+', word)}


def actor_action_score(left, right, title_a, title_b, weights, context):
    """A narrow title-only identity/action fallback, not an entity whitelist.

    Both titles must name the same specific two-word actor and explicitly report
    the same action. Summaries must be available without anchor collisions.
    The caller still applies number, language, time, country and person guards.
    """
    if context is None or left['language'] != 'en' or right['language'] != 'en':
        return 0.0
    if not context.summaries.get(context_key(left)) or not context.summaries.get(context_key(right)):
        return 0.0
    generic = NAME_STOP | set('death row inmate execution attempt lethal injection hospital public school central bank high supreme prime united states'.split())
    def actors(title):
        return {phrase.casefold() for phrase in re.findall(r'(?=(\b[A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}\b))', title)
                if not set(phrase.casefold().split()) & generic}
    shared_actors = cached(context, 'actors', left['title'], lambda: actors(left['title'])) & cached(context, 'actors', right['title'], lambda: actors(right['title']))
    common_actions = cached(context, 'actions', left['title'], lambda: actions(left['title'])) & cached(context, 'actions', right['title'], lambda: actions(right['title']))
    shared = title_a & title_b
    if not shared_actors or not common_actions or len(shared) < 4:
        return 0.0
    actor_words = {word for phrase in shared_actors for word in phrase.split()}
    if len(weights or {}) >= 32 and sum((weights or {}).get(word, 1.0) >= 3.2 for word in actor_words) < 2:
        return 0.0
    if len(shared - actor_words) < 2:
        return 0.0
    return 0.84


def summary_overlap_possible(left, right, context, tokenize):
    """Loose summary upper bound; omits action/name guards, so never adds a merge."""
    if context is None or left.get('language') != 'en' or right.get('language') != 'en':
        return False
    sa = context.summaries.get(context_key(left))
    sb = context.summaries.get(context_key(right))
    if not sa or not sb:
        return False
    def compute():
        a = cached(context, 'summary_tokens', sa, lambda: tokenize({'title': sa}))
        b = cached(context, 'summary_tokens', sb, lambda: tokenize({'title': sb}))
        shared = a & b
        if min(len(a), len(b)) < 8 or len(shared) < 6:
            return False
        weights = context.weights
        rare = sum(weights.get(token, 1.0) >= 3.2 for token in shared) if context.corpus_size >= 32 else len(shared)
        total = lambda tokens: sum(weights.get(token, 1.0) for token in tokens)
        coverage = total(shared) / min(total(a), total(b))
        jaccard = total(shared) / total(a | b)
        return rare >= 3 and coverage >= 0.66 - 1e-9 and jaccard >= 0.38 - 1e-9
    return cached(context, 'summary_overlap_possible', (sa, sb), compute)


def summary_score(left, right, title_a, title_b, title_weights, context, tokenize):
    """Require corroborated action, named subject, and substantial rare overlap.

    Numeric/negation/time/language guards are applied by the caller first.
    Summary numbers are not treated as interchangeable measurements: merging
    coverage does not settle conflicting reported figures or select a winner.
    """
    if context is None or left.get('language') != 'en' or right.get('language') != 'en':
        return 0.0
    sa, sb = context.summaries.get(context_key(left)), context.summaries.get(context_key(right))
    if not sa or not sb:
        return 0.0
    shared_title = title_a & title_b
    tw = title_weights or {}
    total = lambda tokens, weights: sum(weights.get(token, 1.0) for token in tokens)
    if len(shared_title) < 3 or not title_a or not title_b:
        return 0.0
    title_coverage = total(shared_title, tw) / min(total(title_a, tw), total(title_b, tw))
    title_jaccard = total(shared_title, tw) / total(title_a | title_b, tw)
    if title_coverage < 0.5 or title_jaccard < 0.28:
        return 0.0
    common_actions = cached(context, 'combined_actions', (left['title'], sa), lambda: actions(left['title'] + ' ' + sa)) & cached(context, 'combined_actions', (right['title'], sb), lambda: actions(right['title'] + ' ' + sb))
    if not common_actions:
        return 0.0
    common_names = cached(context, 'combined_names', (left['title'], sa), lambda: names(left['title'] + ' ' + sa)) & cached(context, 'combined_names', (right['title'], sb), lambda: names(right['title'] + ' ' + sb))
    if len(common_names) < 2:
        return 0.0
    a = cached(context, 'summary_tokens', sa, lambda: tokenize({'title': sa}))
    b = cached(context, 'summary_tokens', sb, lambda: tokenize({'title': sb}))
    shared = a & b
    if min(len(a), len(b)) < 8 or len(shared) < 6:
        return 0.0
    weights = context.weights
    rare = sum(weights.get(token, 1.0) >= 3.2 for token in shared) if context.corpus_size >= 32 else len(shared)
    coverage = total(shared, weights) / min(total(a, weights), total(b, weights))
    jaccard = total(shared, weights) / total(a | b, weights)
    if rare < 3 or coverage < 0.66 or jaccard < 0.38:
        return 0.0
    return 0.84
