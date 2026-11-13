"""Only tasks in the current catalog are persisted by the desktop console."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import training_console as tc
from studio import fresh_recipe
from training.official_spec import TASKS, CATALOG

CURRENT = 'Mjlab-Velocity-Flat-MicroDuck-Rollers'
OUTDATED = 'Mjlab-Archived-Flat-MicroDuck'


class CurrentCatalogCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.patch = patch.object(tc.BaseTrainingManager, '_run')
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def make_manager(self):
        manager = tc.TrainingManager(self.root)
        self.addCleanup(manager.close)
        return manager

    def test_cleanup_saved_recipe_archive_and_finished_job(self):
        assert CURRENT in TASKS
        recipe = fresh_recipe()
        recipe['version'] = 6
        recipe['task_overrides'] = {OUTDATED: [], CURRENT: []}
        (self.root / 'recipe.json').write_text(json.dumps(recipe), encoding='utf-8')
        (self.root / 'recipe-before-retired-tasks.json').write_text(json.dumps(recipe), encoding='utf-8')
        clean = copy.deepcopy(recipe)
        clean['task_overrides'] = {CURRENT: []}
        (self.root / 'recipes.json').write_text(json.dumps([
            {'name':'archived', 'recipe':recipe}, {'name':'current', 'recipe':clean}
        ]), encoding='utf-8')
        queue = {'version':1, 'enabled':False, 'failure_policy':'pause', 'entries':[]}
        for i, task in enumerate((OUTDATED, CURRENT)):
            queue['entries'].append({'id':str(i), 'client_id':'job-'+str(i),
                                     'status':'completed', 'recipe':clean,
                                     'request':{'task':task}})
        (self.root/'training-queue.json').write_text(json.dumps(queue), encoding='utf-8')
        runs = self.root/'runs'
        for name, task in (('a'*16,OUTDATED),('b'*16,CURRENT)):
            folder = runs/name
            folder.mkdir(parents=True)
            (folder/'run.json').write_text(json.dumps({
                'id':name, 'op':'train', 'request':{'task':task},
                'created':1, 'status':'completed', 'profile':{}
            }),encoding='utf-8')
        m = self.make_manager()
        self.assertEqual(m.recipe['version'],7)
        self.assertEqual(m.recipe['task_overrides'],{CURRENT:[]})
        self.assertFalse((self.root/'recipe-before-retired-tasks.json').exists())
        self.assertEqual([x['name'] for x in m.archives],['current'])
        self.assertEqual([e['request']['task'] for e in m.training_queue['entries']],[CURRENT])
        self.assertFalse((runs/('a'*16)).exists())
        self.assertTrue((runs/('b'*16)/'run.json').exists())
        self.assertEqual(set(m.jobs),{'b'*16})
        self.assertEqual(len(CATALOG['profiles']),14)
        self.assertEqual(len(TASKS),35)


if __name__ == '__main__':
    unittest.main()
