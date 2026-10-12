"""Read a native profiler export and resolve Mod lines to generated definitions.

The export's timing unit is preserved. Inclusive times overlap, so they are
ranked individually rather than added into a purported wall-clock duration.
"""
import argparse
import bisect
import csv
import json
from pathlib import Path
import re


ROOT = Path(__file__).resolve().parents[1]


def analyze(path, top=15):
    definitions = {}

    def owner(location):
        match = re.fullmatch(r'(.+?) @ (.+):(\d+)', location)
        if not match:
            return None
        filename, line = match[2], int(match[3])
        if 'eu5ab_' not in filename:
            return None
        if filename not in definitions:
            local = ROOT / 'in_game' / filename
            entries = []
            if local.is_file():
                for number, source in enumerate(local.read_text(encoding='utf-8-sig').splitlines(), 1):
                    definition = re.match(r'^([\w.]+)\s*=\s*\{', source)
                    if definition:
                        entries.append((number, definition[1]))
            definitions[filename] = entries
        entries = definitions[filename]
        index = bisect.bisect_right([entry[0] for entry in entries], line) - 1
        return entries[index][1] if index >= 0 else None

    with path.open(encoding='utf-8-sig', newline='') as stream:
        rows = []
        for number, raw in enumerate(csv.DictReader(stream, delimiter=';'), 2):
            row = {'csv_row': number, 'location': raw.pop('File Location')}
            row.update({key: float(value) for key, value in raw.items()})
            row['definition'] = owner(row['location'])
            rows.append(row)
    mod = [row for row in rows if row['definition']]
    callbacks = []
    for name in ('try_candidate', 'try_profit_candidate', 'sync_check',
                 'probe_approved', 'request_fire', 'confirm_candidate', 'confirm_sync'):
        candidates = [row for row in mod if row['definition'] == 'eu5ab_gui_queue_' + name
                      and row['location'].startswith('effect @ ')]
        callbacks.append(min(candidates, key=lambda row: int(row['location'].rsplit(':', 1)[1]))
                         if candidates else {'definition': 'eu5ab_gui_queue_' + name,
                                             'observed_effect': False})
    return {
        'source': str(path.resolve()), 'rows': len(rows), 'mod_rows': len(mod),
        'timing_unit': 'native export units (not declared in CSV)',
        'top_all_bottleneck': sorted(rows, key=lambda row: row['Bottleneck Time'], reverse=True)[:top],
        'top_mod_inclusive': sorted(mod, key=lambda row: row['Total Time'], reverse=True)[:top],
        'top_mod_self': sorted(mod, key=lambda row: row['Self Time'], reverse=True)[:top],
        'top_mod_calls': sorted(mod, key=lambda row: row['Call Count'], reverse=True)[:top],
        'queue_callbacks': callbacks,
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv', type=Path)
    parser.add_argument('--top', type=int, default=15)
    args = parser.parse_args()
    print(json.dumps(analyze(args.csv, args.top), ensure_ascii=False, indent=2))
