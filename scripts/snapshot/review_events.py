"""Prepare a human review packet and score completed, attributable labels."""
import argparse
from collections import Counter
import hashlib
from itertools import combinations
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from app.services.event_index import signature, similarity


def prepare(snapshot, count=240):
    articles = snapshot['articles']
    signatures = {a['article_id']: signature(a['title'], a['language'], a['published_at']) for a in articles}
    positives, boundaries, others = [], [], []
    for a, b in combinations(articles, 2):
        ids = sorted([a['article_id'], b['article_id']])
        pair_id = hashlib.sha256('|'.join(ids).encode()).hexdigest()[:24]
        predicted = a['event_id'] == b['event_id']
        score = similarity(signatures[a['article_id']], signatures[b['article_id']])
        row = (score, pair_id, a, b, predicted)
        if predicted: positives.append(row)
        elif score >= .35: boundaries.append(row)
        else: others.append(row)
    positives.sort(key=lambda row: row[1])
    boundaries.sort(key=lambda row: (-row[0], row[1]))
    others.sort(key=lambda row: row[1])
    selected = positives[:min(len(positives), count // 2)]
    selected += boundaries[:min(len(boundaries), count // 2)]
    selected += others[:count - len(selected)]
    if len(selected) < count:
        used = {row[1] for row in selected}
        selected += [row for row in positives + boundaries if row[1] not in used][:count - len(selected)]
    if len(selected) < 200: raise ValueError('At least 200 distinct article pairs are required.')
    selected.sort(key=lambda row: row[1])
    def evidence(article):
        return {key: article.get(key) for key in ('article_id', 'title', 'summary', 'url', 'published_at', 'language')} | {'source_name': article['source']['name'], 'publisher': article['source']['publisher']}
    return {'schema_version': 1, 'snapshot_id': snapshot['snapshot_id'], 'content_sha256': snapshot['content_sha256'],
            'method_version': 'lexical-complete-link-v1', 'reviewer_name': '', 'reviewed_at': None, 'label_origin': 'unreviewed',
            'sampling': {'strategy': 'predicted merges, lexical boundary negatives, deterministic broad negatives',
                         'not_representative_of_all_traffic': True, 'pair_count': len(selected),
                         'predicted_same_count': sum(row[4] for row in selected)},
            'pairs': [{'pair_id': pair_id, 'left': evidence(a), 'right': evidence(b), 'predicted_same': predicted,
                       'similarity': round(score, 4), 'label': None} for score, pair_id, a, b, predicted in selected]}


def evaluate(packet, reviewed):
    if reviewed.get('snapshot_id') != packet['snapshot_id'] or reviewed.get('content_sha256') != packet['content_sha256']:
        raise ValueError('Labels belong to another snapshot.')
    if reviewed.get('label_origin') != 'human' or not str(reviewed.get('reviewer_name', '')).strip() or not reviewed.get('reviewed_at'):
        raise ValueError('A named human reviewer and completion time are required; generated labels are not accepted.')
    expected = {row['pair_id']: row for row in packet['pairs']}
    incoming = reviewed.get('pairs', [])
    ids = [row['pair_id'] for row in incoming]
    if len(ids) != len(set(ids)) or set(ids) != set(expected): raise ValueError('Review packet contains missing, duplicated or foreign pairs.')
    counts = Counter()
    for row in incoming:
        label = row.get('label')
        if label in (None, 'uncertain'): counts['unscored'] += 1; continue
        if label not in ('same', 'different'): raise ValueError('Invalid human label.')
        predicted = expected[row['pair_id']]['predicted_same']
        counts['labeled'] += 1
        counts['tp' if predicted and label == 'same' else 'fp' if predicted else 'fn' if label == 'same' else 'tn'] += 1
    precision = counts['tp'] / (counts['tp'] + counts['fp']) if counts['tp'] + counts['fp'] else None
    recall = counts['tp'] / (counts['tp'] + counts['fn']) if counts['tp'] + counts['fn'] else None
    return {'schema_version': 1, 'snapshot_id': packet['snapshot_id'], 'reviewer_name': reviewed['reviewer_name'],
            'reviewed_at': reviewed['reviewed_at'], 'label_origin': 'human', 'counts': dict(counts),
            'precision': precision, 'recall': recall, 'minimum_200_labeled_pass': counts['labeled'] >= 200,
            'precision_95_percent_pass': precision is not None and precision >= .95,
            'gate_pass': counts['labeled'] >= 200 and precision is not None and precision >= .95,
            'sampling': packet['sampling'], 'caveat': 'Stratified review metrics are not an estimate of all-traffic accuracy. Report positive-pair counts and recall separately.'}


HTML = r'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>News 事件人工审核</title>
<style>body{margin:0;background:#f0f5f6;color:#153b48;font:16px/1.7 Georgia,"Noto Serif SC",serif}main{max-width:1040px;margin:auto;padding:24px}h1{font-size:30px}.cards{display:grid;grid-template-columns:1fr 1fr;gap:20px}article{background:white;padding:24px;border:1px solid #ccd9dd;border-radius:8px}a{color:#125e72;overflow-wrap:anywhere}button,input{font:inherit;padding:10px 16px;margin:8px 8px 8px 0;min-height:44px}button{cursor:pointer;color:inherit;border:1px solid #98b1ba;background:white;border-radius:4px}button[aria-pressed=true]{background:#153b48;color:white}p{overflow-wrap:anywhere}.notice{background:#fff0cc;padding:16px}progress{width:100%}@media(max-width:650px){.cards{grid-template-columns:1fr}main{padding:16px}}</style>
<main><h1>事件人工审核</h1><p class="notice">请判断两篇报道是否属于同一具体事件。相同广泛话题不一定是同一事件；主体、地点、日期或关键数字冲突通常应分开。标题和摘要无法判断时，打开原文或选择“无法判断”。系统不会展示模型预测，避免影响标注。</p>
<label>审核者姓名 <input id="reviewer" maxlength="100" placeholder="填写实际审核者"></label><p id="progress-text"></p><progress id="progress" max="240"></progress><div id="cards" class="cards"></div><div id="choices"><button data-label="same">同一事件（1）</button><button data-label="different">不同事件（2）</button><button data-label="uncertain">无法判断（3）</button></div><p><button id="previous">上一对</button><button id="next">下一对</button><button id="export">导出人工标注</button></p><p id="message" role="status"></p></main>
<script>const packet=__PACKET__;let position=0;const key='news-human-review:'+packet.snapshot_id;try{const saved=JSON.parse(localStorage.getItem(key));if(saved?.snapshot_id===packet.snapshot_id){packet.reviewer_name=saved.reviewer_name||'';for(const row of packet.pairs){const match=saved.pairs.find(p=>p.pair_id===row.pair_id);if(match)row.label=match.label}}}catch{}document.querySelector('#reviewer').value=packet.reviewer_name;
function save(){packet.reviewer_name=document.querySelector('#reviewer').value;try{localStorage.setItem(key,JSON.stringify(packet))}catch{document.querySelector('#message').textContent='浏览器无法保存进度，请及时导出备份。'}}
function paint(){const pair=packet.pairs[position],done=packet.pairs.filter(p=>p.label).length;document.querySelector('#progress-text').textContent=`第 ${position+1} / ${packet.pairs.length} 对 · 已标注 ${done} 对`;const progress=document.querySelector('#progress');progress.max=packet.pairs.length;progress.value=done;const cards=document.querySelector('#cards');cards.replaceChildren();for(const evidence of [pair.left,pair.right]){const article=document.createElement('article');const heading=document.createElement('h2');heading.textContent=evidence.title;heading.lang=evidence.language;article.append(heading);for(const text of [evidence.source_name+' · '+evidence.publisher,evidence.published_at,evidence.summary||'该报道未提供摘要。']){const p=document.createElement('p');p.textContent=text;article.append(p)}const link=document.createElement('a');link.href=evidence.url;link.target='_blank';link.rel='noopener noreferrer';link.textContent='阅读原文';article.append(link);cards.append(article)}for(const button of document.querySelectorAll('[data-label]'))button.setAttribute('aria-pressed',String(button.dataset.label===pair.label));}
function label(value){packet.pairs[position].label=value;save();if(position<packet.pairs.length-1)position++;paint();}
for(const button of document.querySelectorAll('[data-label]'))button.onclick=()=>label(button.dataset.label);document.querySelector('#reviewer').oninput=save;document.querySelector('#previous').onclick=()=>{position=Math.max(0,position-1);paint()};document.querySelector('#next').onclick=()=>{position=Math.min(packet.pairs.length-1,position+1);paint()};document.onkeydown=e=>{if(e.target.tagName==='INPUT')return;if(['1','2','3'].includes(e.key)){e.preventDefault();label({1:'same',2:'different',3:'uncertain'}[e.key])}};
document.querySelector('#export').onclick=()=>{save();if(!packet.reviewer_name.trim()){document.querySelector('#message').textContent='请填写实际审核者姓名。';return}packet.label_origin='human';packet.reviewed_at=new Date().toISOString();const payload=JSON.stringify(packet,null,2),url=URL.createObjectURL(new Blob([payload],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download='news-event-human-review-'+packet.snapshot_id+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);document.querySelector('#message').textContent='标注已导出。至少需要 200 对明确标注；无法判断的样本不计入准确率门禁。'};paint();</script></html>'''


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', type=Path)
    parser.add_argument('--output', type=Path, default=Path('artifacts/v1-m2/review'))
    parser.add_argument('--packet', type=Path)
    parser.add_argument('--labels', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.labels:
        result = evaluate(json.loads(args.packet.read_text(encoding='utf-8')), json.loads(args.labels.read_text(encoding='utf-8')))
        (args.output / 'evaluation.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit(0 if result['gate_pass'] else 1)
    packet = prepare(json.loads(args.snapshot.read_text(encoding='utf-8')))
    serialized = json.dumps(packet, ensure_ascii=False)
    (args.output / 'pairs.json').write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding='utf-8')
    (args.output / 'index.html').write_text(HTML.replace('__PACKET__', serialized.replace('<', '\\u003c')), encoding='utf-8')
    print(json.dumps({'snapshot_id': packet['snapshot_id'], 'sampling': packet['sampling'], 'status': 'AWAITING_HUMAN_LABELS', 'review_page': str(args.output / 'index.html')}, ensure_ascii=False, indent=2))
