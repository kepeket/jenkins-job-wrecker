from jenkins_job_wrecker.cli import get_xml_root, root_to_yaml
import os

fixtures_path = os.path.join(os.path.dirname(__file__), 'fixtures')


class TestYAML(object):

    def run_jjw(self, name):
        xml_filename = os.path.join(fixtures_path, name + '.xml')
        root = get_xml_root(filename=xml_filename)
        yaml = root_to_yaml(root, name)
        actual_yaml_filename = os.path.join(fixtures_path, name + '.yaml.actual')
        with open(actual_yaml_filename, "w") as f:
            f.write(yaml)
        expected_yaml_filename = os.path.join(fixtures_path, name + '.yaml')
        with open(expected_yaml_filename) as f:
            expected_yaml = f.read()
        assert expected_yaml == yaml

    def test_htmlpublisher(self):
        self.run_jjw('html-publisher001')

    def test_git_browser_gitblit(self):
        self.run_jjw('git-browser-gitblit')

    def test_git_browser_githubweb(self):
        self.run_jjw('git-browser-githubweb')

    def test_git_extensions(self):
        self.run_jjw('git-extensions')

    def test_email_ext(self):
        self.run_jjw('email-ext')

    def test_email_ext_notdefaults(self):
        self.run_jjw('email-ext-notdefaults')

    def test_single_conditional_builder(self):
        self.run_jjw('single-conditional-builder')

    def test_trigger_builder(self):
        self.run_jjw('trigger-builder')

    def test_slack(self):
        self.run_jjw('slack')

    def test_slack_disabled(self):
        self.run_jjw('slack-disabled')

    def test_timeout(self):
        self.run_jjw('timeout')

    def test_gerrit_trigger(self):
        self.run_jjw('gerrit-trigger')
