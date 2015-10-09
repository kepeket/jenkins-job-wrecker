import yaml
from yaml.representer import SafeRepresenter

# http://stackoverflow.com/questions/6432605/any-yaml-libraries-in-python-that-support-dumping-of-long-strings-as-block-liter

def represent_literal_str(dumper, data):
    node = SafeRepresenter.represent_str(dumper, data)
    if '\n' in data:
        node.style = '|'
    return node

def install_representer():
    yaml.add_representer(str, represent_literal_str)
