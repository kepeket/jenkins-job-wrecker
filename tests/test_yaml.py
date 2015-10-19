from jenkins_job_wrecker.cli import get_xml_root, root_to_yaml
import os

fixtures_path = os.path.join(os.path.dirname(__file__), 'fixtures')


class TestYAML(object):

    def run_jjw(self, name):
        xml_filename = os.path.join(fixtures_path, name + '.xml')
        expected_yaml_filename = os.path.join(fixtures_path, name + '.yaml')
        with open(expected_yaml_filename) as f:
            expected_yaml = f.read()
        root = get_xml_root(filename=xml_filename)
        yaml = root_to_yaml(root, name)
        actual_yaml_filename = os.path.join(fixtures_path, name + '.yaml.actual')
        with open(actual_yaml_filename, "w") as f:
            f.write(yaml)
        assert expected_yaml == yaml

    def test_yaml(self):
        self.run_jjw('html-publisher001')
