import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from projects import MANAGED_ATTACHED, MANAGED_DETACHING, MANAGED_STATE_FILE, configure_projects, validate_projects

EINSTEIN = 'https://einsteinathome.org/'
ROSETTA = 'https://boinc.bakerlab.org/rosetta/'
WORLD_COMMUNITY_GRID = 'https://www.worldcommunitygrid.org/'

ACCOUNT_KEY = 'an account key'


def completed(stdout: str = '', returncode: int = 0) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr='')


def project_status(*projects) -> subprocess.CompletedProcess:
    """Reproduce what `boinccmd --get_project_status` prints, field for field, including the two
    lines this module reads and the surrounding ones it must skip -- `last RPC` in particular has a
    value full of colons, and `name` an empty one."""
    lines = ['======== Projects ========']
    for index, project in enumerate(projects, start=1):
        url = project if isinstance(project, str) else project[0]
        via_account_manager = 'no' if isinstance(project, str) else project[1]
        lines += [
            f'{index}) -----------',
            '   name: ',
            f'   master URL: {url}',
            '   resource share: 100.000000',
            f'   attached via Account Manager: {via_account_manager}',
            "   don't request more work: no",
            '   last RPC: Thu Jan  1 00:00:00 1970',
        ]
    return completed('\n'.join(lines) + '\n')


def executed_commands(run) -> list:
    return [call.args[0][1:] for call in run.call_args_list]


def configured(*urls) -> list[dict]:
    return [{'url': url, 'account_key': ACCOUNT_KEY} for url in urls]


class ValidateProjectsTestCase(unittest.TestCase):

    def test_should_accept_no_projects(self):
        self.assertTrue(validate_projects(None, None))
        self.assertTrue(validate_projects([], None))

    def test_should_accept_no_projects_alongside_an_account_manager(self):
        self.assertTrue(validate_projects([], 'https://scienceunited.org'))

    def test_should_reject_projects_alongside_an_account_manager(self):
        # An account manager re-asserts its own project list on every sync, so the two would keep
        # undoing each other for as long as the app ran.
        self.assertFalse(validate_projects(configured(EINSTEIN), 'https://scienceunited.org'))

    def test_should_reject_a_project_without_an_account_key(self):
        self.assertFalse(validate_projects([{'url': EINSTEIN}], None))

    def test_should_reject_a_project_without_a_url(self):
        self.assertFalse(validate_projects([{'account_key': ACCOUNT_KEY}], None))

    def test_should_reject_the_same_project_listed_twice(self):
        # Canonicalized, so these two spellings are one project with two different keys, and
        # choosing either would look arbitrary the first time it mattered.
        projects = [
            {'url': 'https://einsteinathome.org', 'account_key': 'one key'},
            {'url': 'https://einsteinathome.org/', 'account_key': 'another key'},
        ]

        self.assertFalse(validate_projects(projects, None))


class ConfigureProjectsTestCase(unittest.TestCase):

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.data_folder = directory.name

    def write_managed_state(self, attached=(), detaching=()) -> None:
        state = {MANAGED_ATTACHED: list(attached), MANAGED_DETACHING: list(detaching)}
        Path(self.data_folder, MANAGED_STATE_FILE).write_text(json.dumps(state))

    def managed_state(self) -> dict:
        return json.loads(Path(self.data_folder, MANAGED_STATE_FILE).read_text())

    @patch('projects.subprocess.run')
    def test_should_not_ask_the_client_anything_when_nothing_is_configured(self, run):
        # The overwhelmingly common case: an install that never used this option should not pay an
        # RPC for it on every start.
        self.assertEqual(configure_projects(self.data_folder, None), [])

        self.assertEqual(executed_commands(run), [])
        self.assertFalse(Path(self.data_folder, MANAGED_STATE_FILE).exists())

    @patch('projects.subprocess.run')
    def test_should_attach_a_configured_project(self, run):
        run.side_effect = [project_status(), completed()]

        self.assertEqual(configure_projects(self.data_folder, configured(EINSTEIN)), [])

        self.assertEqual(executed_commands(run), [
            ['--get_project_status'],
            ['--project_attach', EINSTEIN, ACCOUNT_KEY],
        ])
        self.assertEqual(self.managed_state(), {MANAGED_ATTACHED: [EINSTEIN], MANAGED_DETACHING: []})

    @patch('projects.subprocess.run')
    def test_should_leave_an_already_attached_project_alone(self, run):
        run.side_effect = [project_status(EINSTEIN)]
        self.write_managed_state(attached=[EINSTEIN])

        self.assertEqual(configure_projects(self.data_folder, configured(EINSTEIN)), [])

        self.assertEqual(executed_commands(run), [['--get_project_status']])

    @patch('projects.subprocess.run')
    def test_should_match_a_project_whose_url_is_spelled_differently(self, run):
        # The client reports the canonicalized master URL, so a URL typed without its scheme or
        # trailing slash is the same project, not a second one to attach.
        run.side_effect = [project_status(EINSTEIN)]
        self.write_managed_state(attached=[EINSTEIN])

        self.assertEqual(configure_projects(self.data_folder, configured('https://einsteinathome.org')), [])

        self.assertEqual(executed_commands(run), [['--get_project_status']])

    @patch('projects.subprocess.run')
    def test_should_detach_a_project_it_attached_once_it_is_no_longer_configured(self, run):
        run.side_effect = [project_status(EINSTEIN, ROSETTA), completed()]
        self.write_managed_state(attached=[EINSTEIN, ROSETTA])

        self.assertEqual(configure_projects(self.data_folder, configured(EINSTEIN)), [])

        self.assertEqual(executed_commands(run), [
            ['--get_project_status'],
            ['--project', ROSETTA, 'detach_when_done'],
        ])
        self.assertEqual(self.managed_state(), {MANAGED_ATTACHED: [EINSTEIN], MANAGED_DETACHING: [ROSETTA]})

    @patch('projects.subprocess.run')
    def test_should_never_detach_a_project_it_did_not_attach(self, run):
        # Attached from boinctui or a remote BOINC Manager: without the managed state file this
        # would be indistinguishable from one the operator attached and the user then removed.
        run.side_effect = [project_status(EINSTEIN, WORLD_COMMUNITY_GRID)]
        self.write_managed_state(attached=[EINSTEIN])

        self.assertEqual(configure_projects(self.data_folder, configured(EINSTEIN)), [])

        self.assertEqual(executed_commands(run), [['--get_project_status']])
        self.assertEqual(self.managed_state(), {MANAGED_ATTACHED: [EINSTEIN], MANAGED_DETACHING: []})

    @patch('projects.subprocess.run')
    def test_should_keep_asking_for_a_detach_until_the_client_lets_the_project_go(self, run):
        run.side_effect = [project_status(ROSETTA), completed()]
        self.write_managed_state(detaching=[ROSETTA])

        self.assertEqual(configure_projects(self.data_folder, None), [])

        self.assertEqual(executed_commands(run), [
            ['--get_project_status'],
            ['--project', ROSETTA, 'detach_when_done'],
        ])
        self.assertEqual(self.managed_state(), {MANAGED_ATTACHED: [], MANAGED_DETACHING: [ROSETTA]})

    @patch('projects.subprocess.run')
    def test_should_forget_a_project_the_client_has_finished_detaching(self, run):
        run.side_effect = [project_status()]
        self.write_managed_state(detaching=[ROSETTA])

        self.assertEqual(configure_projects(self.data_folder, None), [])

        self.assertEqual(executed_commands(run), [['--get_project_status']])
        self.assertEqual(self.managed_state(), {MANAGED_ATTACHED: [], MANAGED_DETACHING: []})

    @patch('projects.subprocess.run')
    def test_should_cancel_a_pending_detach_when_the_project_is_configured_again(self, run):
        # detach_when_done is not among the fields --get_project_status prints, so nothing but the
        # state file can tell that this project was on its way out.
        run.side_effect = [project_status(ROSETTA), completed(), completed()]
        self.write_managed_state(detaching=[ROSETTA])

        self.assertEqual(configure_projects(self.data_folder, configured(ROSETTA)), [])

        self.assertEqual(executed_commands(run), [
            ['--get_project_status'],
            ['--project', ROSETTA, 'dont_detach_when_done'],
            ['--project', ROSETTA, 'allowmorework'],
        ])
        self.assertEqual(self.managed_state(), {MANAGED_ATTACHED: [ROSETTA], MANAGED_DETACHING: []})

    @patch('projects.subprocess.run')
    def test_should_reattach_a_project_detached_outside_the_options(self, run):
        run.side_effect = [project_status(), completed()]
        self.write_managed_state(attached=[EINSTEIN])

        self.assertEqual(configure_projects(self.data_folder, configured(EINSTEIN)), [])

        self.assertEqual(executed_commands(run), [
            ['--get_project_status'],
            ['--project_attach', EINSTEIN, ACCOUNT_KEY],
        ])

    @patch('projects.subprocess.run')
    def test_should_leave_a_project_an_account_manager_attached_alone(self, run):
        # The account manager re-asserts its list on every sync, so attaching or detaching here
        # would start exactly the loop validate_projects refuses to allow.
        run.side_effect = [project_status((EINSTEIN, 'yes'))]

        self.assertEqual(configure_projects(self.data_folder, configured(EINSTEIN)), [])

        self.assertEqual(executed_commands(run), [['--get_project_status']])
        self.assertEqual(self.managed_state(), {MANAGED_ATTACHED: [], MANAGED_DETACHING: []})

    @patch('projects.subprocess.run')
    def test_should_report_a_project_it_could_not_attach_for_a_later_retry(self, run):
        run.side_effect = [project_status(), completed(returncode=1)]

        self.assertEqual(configure_projects(self.data_folder, configured(EINSTEIN)), [EINSTEIN])

        self.assertEqual(self.managed_state(), {MANAGED_ATTACHED: [], MANAGED_DETACHING: []})

    @patch('projects.subprocess.run')
    def test_should_attach_the_other_projects_when_one_of_them_fails(self, run):
        # Projects are attached in sorted URL order, so ROSETTA is the one that meets the failure
        # here. One project failing must not cost the others their attach.
        run.side_effect = [project_status(), completed(returncode=1), completed()]

        self.assertEqual(configure_projects(self.data_folder, configured(EINSTEIN, ROSETTA)), [ROSETTA])

        self.assertEqual(executed_commands(run), [
            ['--get_project_status'],
            ['--project_attach', ROSETTA, ACCOUNT_KEY],
            ['--project_attach', EINSTEIN, ACCOUNT_KEY],
        ])
        self.assertEqual(self.managed_state(), {MANAGED_ATTACHED: [EINSTEIN], MANAGED_DETACHING: []})

    @patch('projects.subprocess.run')
    def test_should_retry_everything_when_the_client_cannot_be_asked(self, run):
        # Without the current state there is no diff to compute, and acting blind could attach a
        # project twice or detach one the operator does not own.
        run.side_effect = [completed(returncode=1)]

        self.assertEqual(configure_projects(self.data_folder, configured(EINSTEIN)), [EINSTEIN])

        self.assertEqual(executed_commands(run), [['--get_project_status']])
        self.assertFalse(Path(self.data_folder, MANAGED_STATE_FILE).exists())

    @patch('projects.subprocess.run')
    def test_should_ignore_an_unreadable_managed_state_file(self, run):
        # Erring towards "the operator never attached this" only ever makes the removal branch do
        # less; erring the other way could detach a project it does not own.
        Path(self.data_folder, MANAGED_STATE_FILE).write_text('not json at all')
        run.side_effect = [project_status(EINSTEIN)]

        self.assertEqual(configure_projects(self.data_folder, configured(EINSTEIN)), [])

        self.assertEqual(executed_commands(run), [['--get_project_status']])


if __name__ == '__main__':
    unittest.main()
