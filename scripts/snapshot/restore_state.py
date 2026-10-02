"""Restore bounded durable event state from the previously published Pages site."""
import argparse
import json
from pathlib import Path
import re
import sys
from urllib.parse import urljoin, urlsplit
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from app.services.event_index import validate_registry


def restore(base, output, state):
    url = urlsplit(base)
    if url.scheme != 'https' or url.hostname != 'aureliuswu.github.io' or url.path != '/News/' or url.query or url.fragment:
        raise ValueError('State restore requires the configured News Pages HTTPS origin.')
    with httpx.Client(timeout=20, follow_redirects=False) as client:
        def get(name, budget):
            response = client.get(urljoin(base, 'data/' + name), headers={'Cache-Control': 'no-cache'})
            response.raise_for_status()
            if len(response.content) > budget: raise ValueError('Published checkpoint exceeds its budget.')
            return response.json()
        news = get('news.json', 8 * 1024 * 1024)
        if 'snapshot_id' not in news:
            print('Legacy snapshot: first event-registry bootstrap permitted.')
            return
        registry = validate_registry(get('event-registry.json', 4 * 1024 * 1024))
        if registry.get('snapshot_id') != news['snapshot_id']:
            raise ValueError('Published checkpoint generations differ; retry later, never reset IDs.')
        output.mkdir(parents=True, exist_ok=True)
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps(registry, ensure_ascii=False), encoding='utf-8')
        manifest = get('generations.json', 4096)
        generations = manifest.get('generations')
        if manifest.get('schema_version') != 1 or not isinstance(generations, list) or not 1 <= len(generations) <= 3 or generations[0] != news['snapshot_id'] or any(not re.fullmatch('[a-f0-9]{24}', g) for g in generations):
            raise ValueError('Invalid published generation manifest.')
        # Only two historical generations are needed beside the next candidate.
        kept = generations[:2]
        for generation in kept:
            for kind in ('news', 'events', 'source-health'):
                name = f'{kind}.{generation}.json'
                value = get(name, 8 * 1024 * 1024)
                if value.get('snapshot_id') != generation: raise ValueError('Checkpoint file generation mismatch.')
                (output / name).write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')), encoding='utf-8')
        (output / 'generations.json').write_text(json.dumps({'schema_version': 1, 'generations': kept}), encoding='utf-8')
        print(f'Restored durable registry and {len(kept)} generations from last published Pages checkpoint.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--base', default='https://aureliuswu.github.io/News/')
    parser.add_argument('--output', type=Path, default=Path('frontend/public/data'))
    parser.add_argument('--state', type=Path, default=Path('artifacts/event-registry.json'))
    args = parser.parse_args()
    restore(args.base, args.output, args.state)
