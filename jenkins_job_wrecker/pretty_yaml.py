import collections
import yaml
from yaml.representer import SafeRepresenter


class PrettyDumper(yaml.Dumper):
    def __init__(self, *args, **kwargs):
        super(PrettyDumper, self).__init__(*args, **kwargs)

    def represent_literal_str(self, data):
        node = SafeRepresenter.represent_str(self, data)
        if '\n' in data:
            node.style = '|'
        return node

    def represent_ordered_dict(self, odict):
        tag = u'tag:yaml.org,2002:map'
        value = []
        node = yaml.MappingNode(tag, value, flow_style=None)
        for item_key, item_value in odict.items():
            node_key = self.represent_data(item_key)
            node_value = self.represent_data(item_value)
            value.append((node_key, node_value))
        return node


PrettyDumper.add_representer(str, PrettyDumper.represent_literal_str)
PrettyDumper.add_representer(collections.OrderedDict, PrettyDumper.represent_ordered_dict)


def dump(data):
    return yaml.dump(data, Dumper=PrettyDumper, default_flow_style=False)
