"""Small behavior check of the shipped detail renderer; Node is optional QA only."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from iconctl import BROWSER


@unittest.skipUnless(shutil.which("node"), "Node unavailable for optional JavaScript renderer check")
class BrowserDetailTest(unittest.TestCase):
    def test_alternatives_and_uncertainty_are_rendered_as_text(self):
        fragment = BROWSER.split("for(const [ns,label]", 1)[1].split("const facts=", 1)[0]
        fragment = "for(const [ns,label]" + fragment
        check = """
const assert = require('node:assert/strict');
const source = JSON.parse(require('node:fs').readFileSync(0, 'utf8'));
const lines = [], document = {createElement: () => ({})};
const detail = {append: node => lines.push(node.textContent)};
new Function('x','document','detail',source)({keywords:[
 {namespace:'reviewed_term',value:'orb'}, {namespace:'reviewed_term',value:'<img onerror=bad>'},
 {namespace:'uncertainty',value:'sphere or fireball'}, {namespace:'color',value:'red'}
]}, document, detail);
assert.deepEqual(lines, ['Alternative readings: orb; <img onerror=bad>', 'Uncertainty: sphere or fireball']);
"""
        result = subprocess.run([shutil.which("node"), "-e", check],
                                input=json.dumps(fragment), text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
