# coding: utf8

import yaml


# Metaclass for registering the API classes so they can be deserialized automagically
class Meta(type):
    _registry = {}

    def __init__(cls, name, bases, nmspc):
        super(Meta, cls).__init__(name, bases, nmspc)
        Meta._registry[name] = cls

    @staticmethod
    def registry(name):
        return Meta._registry[name]


class DungenObj(metaclass=Meta):
    def __init__(self, id=None):
        self.id = id


class State(DungenObj):
    def __init__(self, actions, **kwargs):
        super(State, self).__init__(**kwargs)
        self.actions = actions


class Action(DungenObj):
    def __init__(self, label, **kwargs):
        super(Action, self).__init__(**kwargs)
        self.label = label


class Message(Action):
    def __init__(self, message, **kwargs):
        super(Message, self).__init__(**kwargs)
        self.message = message


class Goto(Action):
    def __init__(self, to, **kwargs):
        super(Goto, self).__init__(**kwargs)
        self.to = to


class Game(DungenObj):
    def __init__(self, name, current, states, **kwargs):
        super(DungenObj, self).__init__(**kwargs)
        self.name = name
        self.states = states
        self._states_dict = {s.id: s for s in states}
        self.current = self._states_dict[current]


def load(path):
    with open(path) as fp:
        data = yaml.load(fp.read())
        return parse(Game, data)


def parse(cls, data):
    parsed_data = {}

    for k,v in data.items():
        if isinstance(v, dict):
            v = parse_item(v)
        elif isinstance(v, list):
            v = parse_list(v)

        parsed_data[k] = v

    return cls(**parsed_data)


def parse_item(data):
    if len(data) != 1:
        raise ValueError("")

    for k,v in data.items():
        cls = Meta.registry(k)
        return parse(cls, v)


def parse_list(data):
    return [parse_item(i) for i in data]
