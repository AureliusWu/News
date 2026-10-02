from .event_evidence import cached, summary_overlap_possible
from app.services.event_acceptance import quality_status
"""Conservative event grouping shared by publication and future API ingestion.

The bounded registry is an input/output document, never an implicit process cache.
No translation or language-model call is involved.
"""
from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from .event_evidence import actor_action_score, build_summary_context, evidence_action_conflict, summary_score
import hashlib
import math
import re
import unicodedata

METHOD_VERSION = 'lexical-complete-link-v1'
MATCHER_VERSION = 'title-summary-v4'
MAX_EVENTS = 5000
MAX_MAPPINGS = 10000
RETENTION_DAYS = 90
WINDOW_HOURS = 48
THRESHOLD = 0.82
STOP = set('a an the of to in on at for by with from and or as is are was were after'.split())
ACTIONS = {
    'up': set('raise raises raised rise rises rising increase increases increased 上调 上涨'.split()),
    'down': set('cut cuts cutting lower lowers lowered decrease decreases decreased 下调 下跌'.split()),
    'approve': set('approve approves approved accept accepts accepted 批准 同意'.split()),
    'reject': set('reject rejects rejected deny denies denied 拒绝 否认'.split()),
    'negation': set('not never no 不会 不再'.split()),
}

# Keep the persisted v1 signature unchanged. Rewriting is a separate, versioned
# comparison layer, so an upgrade does not invalidate anchors or reset IDs.
COMPARE_STOP = STOP | set('s says say said s why how what now temporarily temporary latest news wrap happened historic cheers huge goes go off again just people person officials official'.split())
LEXEMES = {
    'allow': 'allow allows allowed allowing lets permit permits permitted approval approve approves approved',
    'deport': 'deport deports deported deporting deportation deportations',
    'perform': 'perform performs performed performing performance performances',
    'resign': 'resign resigns resigned resigning quit quits quitting',
    'kill': 'kill kills killed killing dead deaths death',
    'shooting': 'shooting shootings', 'price': 'price prices',
    'reach': 'reach reaches reached reaching hit hits',
    'woman': 'woman women female females', 'staff': 'staff employees employee',
    'defend': 'defend defends defended defending',
    'investigation': 'investigation investigations', 'concern': 'concern concerns',
    'release': 'release releases released releasing rollout',
    'delay': 'delay delays delayed delaying scraps scrap',
    'execution': 'execution executions execute executes executed executing',
    'survive': 'survive survives survived surviving',
    'fail': 'fail fails failed failing failure',
    'appoint': 'appoint appoints appointed appointment appointments',
    'country': 'country countries', 'blasts': 'blast blasts explosions explosion',
    'surprise': 'surprise surprises surprised surprising',
    'uk': 'uk british britain', 'us': 'us american',
    'canada': 'canada canadian', 'australia': 'australia australian',
    'france': 'france french', 'germany': 'germany german',
    'china': 'china chinese', 'japan': 'japan japanese',
    'indonesia': 'indonesia indonesian', 'malaysia': 'malaysia malaysian',
    'morocco': 'morocco moroccan', 'iran': 'iran iranian',
    'israel': 'israel israeli', 'russia': 'russia russian',
    'ukraine': 'ukraine ukrainian', 'india': 'india indian',
}
CANONICAL = {word: canonical for canonical, words in LEXEMES.items() for word in words.split()}
COUNTRIES = set('uk us canada australia france germany china japan indonesia malaysia morocco iran israel russia ukraine india myanmar singapore ethiopia eritrea sudan egypt greece italy brazil spain'.split())
ENTITY_STOP = COMPARE_STOP | set('supreme court prime minister king chief president officials staff public workers latest world news north south united states fat bear eiffel tower fashion week arts festival space first second third police'.split()) | set(CANONICAL)


def comparison_tokens(row):
    text = unicodedata.normalize('NFKC', row['title']).casefold()
    text = re.sub(r'\ball[ -]time high\b|\brecord high\b', 'recordhigh', text)
    text = re.sub(r'\bstep(?:s|ped)? down\b', 'resign', text)
    text = re.sub(r'\bkicks? off\b', 'start', text)
    if re.search(r'\b(prime minister|governor|president|king)\b', text):
        text = re.sub(r'\b(names|named)\b', 'appoint', text)
    tokens = set()
    for word in re.findall(r'[^\W_]+', text, re.UNICODE):
        if re.search(r'[\u3040-\u30ff\u3400-\u9fff]', word):
            tokens.update(word[i:i + 2] for i in range(len(word) - 1))
        elif word not in COMPARE_STOP and len(word) > 1:
            tokens.add(CANONICAL.get(word, word))
    return tokens


def named_people(row):
    result = set()
    # Mixed-case two-word names only, not whole Title Case headlines or roles.
    for phrase in re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b', row['title']):
        words = phrase.casefold().split()
        if len(words) == 2 and not any(word in ENTITY_STOP for word in words):
            result.add(' '.join(words))
    return result


def comparison_conflicts(left, right, a, b, contexts=None):
    la, ra = (set(left['actions']), set(right['actions']))
    if ('negation' in la) != ('negation' in ra):
        return True
    for first, second in [('up', 'down'), ('approve', 'reject')]:
        if first in la and second in ra or (second in la and first in ra):
            return True
    if 'allow' in a and 'reject' in ra or ('allow' in b and 'reject' in la):
        return True
    countries_a, countries_b = (a & COUNTRIES, b & COUNTRIES)
    if countries_a and countries_b and (not countries_a & countries_b):
        return True
    names_a, names_b = (cached(contexts, 'named_people', left['title'], lambda: named_people(left)), cached(contexts, 'named_people', right['title'], lambda: named_people(right)))
    if names_a and names_b and (not names_a & names_b):
        return True
    ordinals = {'first', 'second', 'third', 'fourth'}
    if a & ordinals and b & ordinals and (not a & b & ordinals):
        return True
    return False


def non_event_title(row):
    title = row['title'].casefold().strip()
    return bool(re.search(r'\b(latest news bulletin|tech now|promo codes?|coupon codes?)\b|\b(?:can|did) you solve it\b', title)
                or re.fullmatch(r"here(?:'|\u2019)s the latest[.!]?", title))


def utc(value):
    parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)


def identity(url):
    return 'a_' + hashlib.sha256(url.encode('utf-8')).hexdigest()[:24]


def publisher_identity(name):
    normalized = ' '.join(unicodedata.normalize('NFKC', name).casefold().split())
    return 'p_' + hashlib.sha256(normalized.encode('utf-8')).hexdigest()[:20]


def signature(title, language, published_at):
    normalized = unicodedata.normalize('NFKC', title).casefold()
    words = re.findall(r'[^\W_]+', normalized, re.UNICODE)
    tokens = set()
    for word in words:
        if re.search(r'[\u3040-\u30ff\u3400-\u9fff]', word):
            tokens.update(word[i:i + 2] for i in range(len(word) - 1))
        elif word not in STOP:
            tokens.add(word)
    return {'title': title, 'language': language, 'published_at': published_at,
            'normalized': ' '.join(words), 'tokens': sorted(tokens),
            'numbers': sorted(set(re.findall(r'\d+(?:[.,]\d+)*', normalized))),
            'actions': sorted(key for key, values in ACTIONS.items()
                              if any(value in tokens or (len(value) > 1 and value in normalized and not value.isascii()) for value in values))}


def similarity(left, right, weights=None, contexts=None):
    if evidence_action_conflict(left, right, contexts):
        return 0.0
    if left['language'] != right['language'] or left['numbers'] != right['numbers']:
        return 0.0
    if abs((cached(contexts, 'utc', left['published_at'], lambda: utc(left['published_at'])) - cached(contexts, 'utc', right['published_at'], lambda: utc(right['published_at']))).total_seconds()) > WINDOW_HOURS * 3600:
        return 0.0
    a, b = (cached(contexts, 'title_tokens', left['title'], lambda: comparison_tokens(left)), cached(contexts, 'title_tokens', right['title'], lambda: comparison_tokens(right)))
    if cached(contexts, 'non_event_title', left['title'], lambda: non_event_title(left)) or cached(contexts, 'non_event_title', right['title'], lambda: non_event_title(right)) or comparison_conflicts(left, right, a, b, contexts):
        return 0.0
    if left['normalized'] == right['normalized']:
        return 1.0
    if min(len(a), len(b)) < 4:
        return 0.0
    weight = weights or {}
    total = lambda tokens: sum((weight.get(t, 1.0) for t in tokens))
    shared = a & b
    score = total(shared) / total(a | b) if a | b else 0.0
    coverage = total(shared) / min(total(a), total(b))
    specific = sum((weight.get(t, 1.0) >= 3.2 for t in shared)) if len(weight) >= 32 else len(shared)
    typed = bool(shared & COUNTRIES or shared & {word.casefold() for row in (left, right) for word in re.findall('\\b[A-Z][A-Za-z]+\\b', row['title']) if word.casefold() not in ENTITY_STOP})
    rewrite = len(shared) >= 4 and specific >= 2 and (score >= 0.5) and (coverage >= 0.8)
    extended = typed and len(shared) >= 6 and (specific >= 3) and (score >= 0.45) and (coverage >= 0.68)
    base_score = max(score, 0.84) if rewrite or extended else score
    return max(base_score, summary_score(left, right, a, b, weights, contexts, comparison_tokens), actor_action_score(left, right, a, b, weights, contexts))


def empty_registry():
    return {'schema_version': 1, 'method_version': METHOD_VERSION, 'events': {}, 'articles': {}, 'aliases': {}}


def validate_registry(value):
    if not isinstance(value, dict) or value.get('schema_version') != 1 or value.get('method_version') != METHOD_VERSION:
        raise ValueError('Event registry schema/method is incompatible; do not reset stable identities.')
    events, articles, aliases = (value.get(k) for k in ('events', 'articles', 'aliases'))
    if not isinstance(events, dict) or len(events) > MAX_EVENTS or not isinstance(articles, dict) or len(articles) > MAX_MAPPINGS or not isinstance(aliases, dict) or len(aliases) > MAX_EVENTS:
        raise ValueError('Event registry exceeds its bounds or is malformed.')
    for event_id, row in events.items():
        if not re.fullmatch(r'e_[a-f0-9]{24}', event_id) or not isinstance(row, dict):
            raise ValueError('Invalid event identity.')
        anchor = row.get('anchor', {})
        if not isinstance(anchor.get('tokens'), list) or not isinstance(anchor.get('title'), str):
            raise ValueError('Invalid event anchor.')
        for field in ('first_published_at', 'last_published_at', 'last_seen'):
            utc(row[field])
        if signature(anchor['title'], anchor['language'], anchor['published_at']) != anchor:
            raise ValueError('Event anchor signature does not match its text.')
    for article_id, row in articles.items():
        if not re.fullmatch(r'a_[a-f0-9]{24}', article_id) or row.get('event_id') not in events:
            raise ValueError('Invalid article mapping.')
        utc(row['last_seen'])
    for old, target in aliases.items():
        if not re.fullmatch(r'e_[a-f0-9]{24}', old) or old in events or target not in events or old == target:
            raise ValueError('Aliases must directly resolve to a current event, without cycles.')
    return value


def merge_reviewed_events(previous, event_ids, reviewed_at, evidence, contexts=None):
    """Explicit isolated migration; normal collection never calls this function."""
    state = deepcopy(validate_registry(previous))
    ids = sorted(set(event_ids))
    if len(ids) < 2 or any(key not in state['events'] for key in ids):
        raise ValueError('Reviewed merge requires at least two current event IDs.')
    if not isinstance(evidence, dict) or evidence.get('label_origin') not in ('ai', 'human') or not evidence.get('reference'):
        raise ValueError('A reviewed merge must retain its actual evidence origin.')
    utc(reviewed_at)
    for i, first in enumerate(ids):
        for second in ids[i + 1:]:
            if similarity(state['events'][first]['anchor'], state['events'][second]['anchor'], contexts=contexts) < THRESHOLD:
                raise ValueError('Reviewed merge fails the complete-link anchor safety gate.')
    survivor = ids[0]
    row = state['events'][survivor]
    row['first_published_at'] = min(state['events'][key]['first_published_at'] for key in ids)
    row['last_published_at'] = max(state['events'][key]['last_published_at'] for key in ids)
    row['last_seen'] = max(state['events'][key]['last_seen'] for key in ids)
    row['merge_review'] = {'reviewed_at': reviewed_at, 'label_origin': evidence['label_origin'], 'reference': str(evidence['reference'])[:512]}
    retired = set(ids[1:])
    for mapping in state['articles'].values():
        if mapping['event_id'] in retired:
            mapping['event_id'] = survivor
    for old, target in list(state['aliases'].items()):
        if target in retired:
            state['aliases'][old] = survivor
    for old in retired:
        state['aliases'][old] = survivor
        del state['events'][old]
    state['matcher_version'] = MATCHER_VERSION
    return validate_registry(state)


def split_reviewed_event(previous, event_id, groups, articles, reviewed_at, evidence):
    """Explicit correction with complete member evidence; never automatic.

    The first group retains the old URL. Other groups receive deterministic new
    IDs, not one-to-many aliases. Historical aliases still resolve to group one.
    Every retained mapping must be covered; missing history fails closed.
    """
    state = deepcopy(validate_registry(previous))
    if event_id not in state['events']:
        raise ValueError('A split requires a current canonical event ID.')
    if not isinstance(evidence, dict) or evidence.get('label_origin') not in ('ai', 'human') or not isinstance(evidence.get('reference'), str) or not evidence['reference'].strip():
        raise ValueError('A split requires its actual review origin and reference.')
    utc(reviewed_at)
    if not isinstance(groups, list) or len(groups) < 2 or any(not isinstance(group, list) or not group for group in groups):
        raise ValueError('A split requires at least two nonempty groups.')
    if any(not isinstance(key, str) for group in groups for key in group):
        raise ValueError('Split members must be stable article IDs.')
    flattened = [key for group in groups for key in group]
    members = {key for key, row in state['articles'].items() if row['event_id'] == event_id}
    if len(flattened) != len(set(flattened)) or set(flattened) != members:
        raise ValueError('A split must cover every retained member exactly once.')
    rows = {}
    for article in articles:
        key = identity(article['url'])
        if key in rows:
            raise ValueError('Split evidence contains duplicate article URLs.')
        if article.get('article_id', key) != key:
            raise ValueError('Split article identity does not match its URL.')
        rows[key] = article
    if not members <= rows.keys():
        raise ValueError('Full retained article evidence is required, including history.')
    if len(state['events']) + len(groups) - 1 > MAX_EVENTS:
        raise ValueError('Split would exceed the event registry bound.')
    contexts = build_summary_context([rows[key] for key in members], comparison_tokens)
    prepared = []
    for position, group in enumerate(groups):
        ordered = sorted((rows[key] for key in group), key=lambda a: (a['published_at'], identity(a['url'])))
        sigs = [signature(a['title'], a['language'], a['published_at']) for a in ordered]
        if any(similarity(first, second, contexts=contexts) < THRESHOLD for i, first in enumerate(sigs) for second in sigs[i + 1:]):
            raise ValueError('A proposed split group fails complete-link safety.')
        key = event_id if position == 0 else 'e_' + hashlib.sha256(('split:' + event_id + ':' + '|'.join(sorted(group))).encode()).hexdigest()[:24]
        if position and (key in state['events'] or key in state['aliases'] or any(key == item[0] for item in prepared)):
            raise ValueError('Split event identity collides with retained state.')
        prepared.append((key, group, {'anchor': sigs[0],
            'first_published_at': min(a['published_at'] for a in ordered),
            'last_published_at': max(a['published_at'] for a in ordered),
            'last_seen': max(state['articles'][member]['last_seen'] for member in group),
            'split_review': {'previous_event_id': event_id, 'reviewed_at': reviewed_at,
                'label_origin': evidence['label_origin'], 'reference': evidence['reference'][:512]}}))
    for key, group, row in prepared:
        state['events'][key] = row
        for member in group:
            state['articles'][member]['event_id'] = key
    state['matcher_version'] = MATCHER_VERSION
    return validate_registry(state)




def _candidate_possible(left, right, weights, context):
    """Conservative upper bound: a rejected candidate cannot reach the threshold.

    Near a floating-point boundary we defer to the unchanged full matcher.
    This is not an inverted-index cap or a change to complete-link membership.
    """
    if left['language'] != right['language'] or left['numbers'] != right['numbers']:
        return False
    a_date = cached(context, 'utc', left['published_at'], lambda: utc(left['published_at']))
    b_date = cached(context, 'utc', right['published_at'], lambda: utc(right['published_at']))
    if abs((a_date - b_date).total_seconds()) > WINDOW_HOURS * 3600:
        return False
    if left['normalized'] == right['normalized']:
        return True
    a = cached(context, 'title_tokens', left['title'], lambda: comparison_tokens(left))
    b = cached(context, 'title_tokens', right['title'], lambda: comparison_tokens(right))
    if min(len(a), len(b)) < 4:
        return False
    def total(tokens):
        return cached(context, 'projection_title_total', frozenset(tokens), lambda: sum(weights.get(t, 1.0) for t in tokens))
    shared = a & b
    intersection, ta, tb = total(shared), total(a), total(b)
    denominator = ta + tb - intersection
    score = intersection / denominator if denominator else 0.0
    coverage = intersection / min(ta, tb)
    epsilon = 1e-9
    if score >= THRESHOLD - epsilon:
        return True
    specific = sum(weights.get(t, 1.0) >= 3.2 for t in shared) if len(weights) >= 32 else len(shared)
    # The original extended rule requires a typed subject; omitting it here is conservative.
    if len(shared) >= 4 and specific >= 2 and score >= 0.5 - epsilon and coverage >= 0.8 - epsilon:
        return True
    if len(shared) >= 6 and specific >= 3 and score >= 0.45 - epsilon and coverage >= 0.68 - epsilon:
        return True
    if actor_action_score(left, right, a, b, weights, context) >= THRESHOLD:
        return True
    return (len(shared) >= 3 and score >= 0.28 - epsilon and coverage >= 0.5 - epsilon
            and summary_overlap_possible(left, right, context, comparison_tokens))

def build_event_index(articles, generated_at, previous=None):
    contexts = build_summary_context(articles, comparison_tokens)
    state = deepcopy(validate_registry(previous)) if previous is not None else empty_registry()
    now = cached(contexts, 'utc', generated_at, lambda: utc(generated_at))
    signatures = {identity(a['url']): signature(a['title'], a['language'], a['published_at']) for a in articles}
    frequency = Counter((t for row in signatures.values() for t in cached(contexts, 'title_tokens', row['title'], lambda: comparison_tokens(row))))
    weights = {t: 1 + math.log((len(articles) + 1) / (count + 1)) for t, count in frequency.items()}

    def pair_similarity(left, right):
        keys = ('title', 'language', 'normalized', 'numbers', 'actions')
        if all((left[key] == right[key] for key in keys)):
            a = cached(contexts, 'utc', left['published_at'], lambda: utc(left['published_at']))
            b = cached(contexts, 'utc', right['published_at'], lambda: utc(right['published_at']))
            if abs((a - b).total_seconds()) > WINDOW_HOURS * 3600:
                return 0.0
            key = (left['title'], left['language'], left['normalized'], tuple(left['numbers']), tuple(left['actions']))
            return cached(contexts, 'identical_pair_score', key, lambda: similarity(left, right, weights, contexts))
        return similarity(left, right, weights, contexts)
    members = {}
    inverted = {}
    for event_id, row in state['events'].items():
        for token in cached(contexts, 'title_tokens', row['anchor']['title'], lambda: comparison_tokens(row['anchor'])):
            inverted.setdefault((row['anchor']['language'], token), set()).add(event_id)
    ordered = sorted(articles, key=lambda a: (identity(a['url']) not in state['articles'], a['published_at'], identity(a['url'])))
    for article in ordered:
        article_id = identity(article['url'])
        sig = signatures[article_id]
        event_id = state['articles'].get(article_id, {}).get('event_id')
        if event_id is None:
            tokens = cached(contexts, 'title_tokens', sig['title'], lambda: comparison_tokens(sig))
            candidates = set().union(*(inverted.get((sig['language'], t), set()) for t in tokens)) if tokens else set()
            ranked = []
            for candidate in candidates:
                row = state['events'][candidate]
                if not _candidate_possible(sig, row['anchor'], weights, contexts):
                    continue
                score = pair_similarity(sig, row['anchor'])
                if score >= THRESHOLD and all((pair_similarity(sig, signatures[identity(m['url'])]) >= THRESHOLD for m in members.get(candidate, []))):
                    ranked.append((score, candidate))
            if ranked:
                event_id = sorted(ranked, key=lambda pair: (-pair[0], pair[1]))[0][1]
            else:
                event_id = 'e_' + hashlib.sha256(('event:' + article_id).encode()).hexdigest()[:24]
                state['events'][event_id] = {'anchor': sig, 'first_published_at': article['published_at'], 'last_published_at': article['published_at'], 'last_seen': generated_at}
                for token in cached(contexts, 'title_tokens', sig['title'], lambda: comparison_tokens(sig)):
                    inverted.setdefault((sig['language'], token), set()).add(event_id)
        row = state['events'][event_id]
        row['first_published_at'] = min(row['first_published_at'], article['published_at'])
        row['last_published_at'] = max(row['last_published_at'], article['published_at'])
        row['last_seen'] = generated_at
        state['articles'][article_id] = {'event_id': event_id, 'last_seen': generated_at}
        article['article_id'], article['event_id'] = (article_id, event_id)
        members.setdefault(event_id, []).append(article)
    active = set(members)
    cutoff = now - timedelta(days=RETENTION_DAYS)
    retained = sorted((key for key, row in state['events'].items() if key in active or cached(contexts, 'utc', row['last_seen'], lambda: utc(row['last_seen'])) >= cutoff), key=lambda key: (key not in active, -cached(contexts, 'utc', state['events'][key]['last_seen'], lambda: utc(state['events'][key]['last_seen'])).timestamp(), key))[:MAX_EVENTS]
    state['events'] = {key: state['events'][key] for key in retained}
    mapped = sorted((key for key, row in state['articles'].items() if row['event_id'] in state['events'] and (key in signatures or cached(contexts, 'utc', row['last_seen'], lambda: utc(row['last_seen'])) >= cutoff)), key=lambda key: (key not in signatures, -cached(contexts, 'utc', state['articles'][key]['last_seen'], lambda: utc(state['articles'][key]['last_seen'])).timestamp(), key))[:MAX_MAPPINGS]
    state['articles'] = {key: state['articles'][key] for key in mapped}
    state['aliases'] = {key: target for key, target in state['aliases'].items() if target in state['events']}
    state['matcher_version'] = MATCHER_VERSION
    events = []
    for event_id, group in members.items():
        row = state['events'][event_id]
        ordered_group = sorted(group, key=lambda a: (a['published_at'], a['article_id']))
        publishers = sorted({publisher_identity(a['source']['publisher']) for a in group})
        events.append({'event_id': event_id, 'title': row['anchor']['title'], 'language': row['anchor']['language'], 'first_published_at': row['first_published_at'], 'last_published_at': row['last_published_at'], 'article_ids': [a['article_id'] for a in ordered_group], 'publisher_ids': publishers, 'publisher_count': len(publishers), 'source_names': sorted({a['source']['name'] for a in group}), 'article_count': len(group)})
    events.sort(key=lambda e: (e['last_published_at'], e['event_id']), reverse=True)
    index = {'schema_version': 1, 'method_version': METHOD_VERSION, 'matcher_version': MATCHER_VERSION, 'aliases': deepcopy(state['aliases']), 'generated_at': generated_at, 'acceptance_status': quality_status(MATCHER_VERSION), 'events': events}
    return (index, validate_registry(state))
