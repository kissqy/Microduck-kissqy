"""Rebuild bundled references from the pinned installed official CPU dependencies.

Run with MICRODUCK_OFFICIAL_SOURCE pointing to the frozen checkout and BAM
installed. This reads configurations; it neither trains nor writes upstream files.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if os.environ.get('MICRODUCK_OFFICIAL_SOURCE'):
    sys.path.insert(0, str(Path(os.environ['MICRODUCK_OFFICIAL_SOURCE']) / 'src'))

from training.official_spec import CATALOG, PIN, ENGINE, TASKS, REVISION, DEFAULT_TASK


def write(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    import mjlab.tasks
    import mjlab_microduck.tasks
    from training.official_adapter import register_tasks
    from training.runtime_adapter import describe
    from training.explanations import annotate_rows
    from studio import fresh_recipe
    register_tasks()
    write(ROOT/'data/tasks.json', CATALOG)
    write(ROOT/'data/pins.json', {ENGINE: PIN})
    recipe = fresh_recipe()
    recipe['task'] = DEFAULT_TASK
    write(ROOT/'examples/recipe-official-0151.json', recipe)
    (ROOT/'training/static/tasks.js').write_text(
        'const taskCatalog = ' + json.dumps(CATALOG, ensure_ascii=False, separators=(',', ':')) + ';\n', encoding='utf-8')
    for task in (sys.argv[1:] or TASKS):
        data = describe(task, {'task': task, 'engine': ENGINE, 'op': 'describe', 'studio_recipe': recipe})
        data['source_revision'] = REVISION
        data['inspection']['rows'] = annotate_rows(data['inspection']['rows'])
        missing = [r['path'] for r in data['inspection']['rows'] if r['help'].get('documentation_missing')]
        if missing:
            raise ValueError(f'{task}: unexplained fields: {missing}')
        write(ROOT/'data/task-configs'/(task+'.json'), data)
        print(f"{task}: {len(data['inspection']['rows'])} explained parameters", flush=True)


if __name__ == '__main__':
    main()
