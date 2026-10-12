"""Reassociate every saved building using configured recipes, without save writes.

python -B scripts/audit_saved_production.py --audit-dir ... --game-root ...
Original extraction and manifests stay immutable. Corrected results go into
production-corrected/; all saved zero-suffix and omitted-method buildings are
listed, including configured buildings with genuinely absent saved slot data.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import mmap
from pathlib import Path
import re
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.eu5autobuild.production import _definitions, extract_production_models
from src.eu5autobuild.save_production import associate_recipe, identify_saved_methods


def audit(audit_dir: Path, game_root: Path):
    definitions = _definitions(game_root / 'game/in_game/common/building_types')
    models = extract_production_models(game_root, SimpleNamespace(buildings=definitions))
    supported = {r['building_id'] for r in json.loads(
        (Path(__file__).resolve().parents[1] / '.metadata/eu5ab_production_recipes.json').read_text(encoding='utf-8-sig'))['buildings']}
    destination = audit_dir / 'production-corrected'
    destination.mkdir(exist_ok=True)
    common = game_root / 'game/in_game/common'
    configuration = [dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
                     for directory in ('building_types', 'production_methods', 'goods', 'advances')
                     for path in sorted((common / directory).glob('*.txt'))]
    (destination / 'configuration-manifest.json').write_text(json.dumps(configuration, indent=2), encoding='utf-8')
    summaries = []
    for day, source in enumerate(json.loads((audit_dir / 'save-manifest.json').read_text(encoding='utf-8-sig')), 2):
        compressed = audit_dir / f'{day:02}.json.gz'
        data = json.loads(gzip.decompress(compressed.read_bytes()))
        prices = {market: {match[1]: float(match[2]) for match in re.finditer(
            r'^\t\t(\w+)=\{\r?\n\t\t\tprice=([-\d.]+)', values['raw'], re.M)}
                  for market, values in data['markets'].items()}
        rows = []
        counts = Counter()
        with Path(source['path']).open('rb') as handle, mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as saved:
            digest = hashlib.sha256(saved).hexdigest()
            if digest != source['sha256']:
                raise ValueError(f'Changed original save: {source["path"]}')
            for identity, building in data['buildings'].items():
                position = building['offset']
                end = saved.find(b'\n}', position)
                model = models.get(building['type'])
                result = identify_saved_methods(saved[position:end], model)
                old = building['maintenance']
                building['production_methods'] = result['methods']
                building['production_method_identification'] = result
                # Legacy field retained for consumers; it now means configured
                # saved methods, not names ending in _maintenance.
                building['maintenance'] = result['methods']
                if not old or old != result['methods'] or result['status'] not in ('configured_saved_methods', 'no_configured_methods'):
                    loc = data['locations'].get(str(building['location']), {})
                    market = str(loc.get('market')) if 'market' in loc else None
                    association = associate_recipe(result, model, prices.get(market, {}),
                                                   saved_profit=building.get('last_months_profit'))
                    row = dict(building=identity, type=building['type'], location=building['location'],
                               market=market, eu5ab_supported=building['type'] in supported,
                               saved_level=building.get('level'), saved_employed=building.get('employed'),
                               gui_observed_output=None, gui_observed_input=None,
                               previous_suffix_methods=old, **result, **association)
                    rows.append(row)
                    counts[result['status']] += 1
        corrected = destination / compressed.name
        corrected.write_bytes(gzip.compress(json.dumps(data, ensure_ascii=False,
                                  separators=(',', ':')).encode('utf-8'), mtime=0))
        (destination / f'{day:02}.associations.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding='utf-8')
        summary = dict(date=data['date'], original_sha256=digest, original_unchanged=True,
                       corrected_sha256=hashlib.sha256(corrected.read_bytes()).hexdigest(),
                       buildings=len(data['buildings']), rechecked=len(rows), statuses=dict(counts),
                       recovered=sum(bool(r['methods']) and not r['previous_suffix_methods'] for r in rows),
                       recovered_supported=sum(bool(r['methods']) and not r['previous_suffix_methods'] and r['eu5ab_supported'] for r in rows))
        summaries.append(summary)
        print(json.dumps(summary), flush=True)
    (destination / 'summary.json').write_text(json.dumps(summaries, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit-dir', type=Path, required=True)
    parser.add_argument('--game-root', type=Path, required=True)
    arguments = parser.parse_args()
    audit(arguments.audit_dir, arguments.game_root)
