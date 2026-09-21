"""The command center must render usable identity/CSRF JavaScript, not Jinja text."""
import json
import re
from pathlib import Path

from flask import Flask, g, render_template, session


def test_command_center_embeds_authenticated_identity_outside_raw_block():
    app = Flask(__name__, template_folder=str(Path(__file__).resolve().parents[2] / 'dashboard/templates'))
    app.secret_key = 'render-test-only'
    with app.test_request_context('/'):
        g.user = {'username': 'reviewer@example.test', 'role': 'reviewer'}
        session['csrf'] = 'test-csrf-value'
        html = render_template('index.html')
    for name, expected in [('ANALYST_ID', 'reviewer@example.test'), ('CSRF_TOKEN', 'test-csrf-value')]:
        value = re.search(r'const ' + name + r' = (.*?);', html).group(1)
        assert json.loads(value) == expected
    assert '{{' not in html and '{% raw %}' not in html
