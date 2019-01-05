# coding: utf-8

import yaml


def dobj(cls):
    def constructor(loader, node):
        instance = cls.__new__(cls)
        yield instance
        state = loader.construct_mapping(node, deep=True)
        instance.__init__(**state)

    yaml.add_constructor('!%s' % cls.__name__, constructor)
    return cls


class DungenObj:
    def __init__(self, *args, **kwargs):
        self._extra = kwargs

    def __getattr__(self, key):
        return self._extra[key]


@dobj
class State(DungenObj):
    yaml_tag = '!State'
    def __init__(self, actions, **kwargs):
        super(State, self).__init__(**kwargs)
        self._actions = actions

    def actions(self):
        return self._actions


class Action(DungenObj):
    def __init__(self, label, **kwargs):
        super(Action, self).__init__(**kwargs)
        self._label = label

    def label(self):
        return self._label

    def execute(self, game):
        raise NotImplementedError()


@dobj
class Message(Action):
    yaml_tag = '!Message'
    def __init__(self, message, **kwargs):
        super(Message, self).__init__(**kwargs)
        self._message = message

    def execute(self, game):
        return game.send_message(self._message)


@dobj
class Goto(Action):
    yaml_tag = '!Goto'
    def __init__(self, to, **kwargs):
        super(Goto, self).__init__(**kwargs)
        self._to = to

    def execute(self, game):
        return game.change_state(self._to)


@dobj
class Game(DungenObj):
    yaml_tag = '!Game'
    def __init__(self, name, start, states, **kwargs):
        super(Game, self).__init__(**kwargs)
        self._name = name
        self._states = states
        self._current = start
        self._listeners = []

    def add_listener(self, lst):
        self._listeners.append(lst)

    def current_state(self):
        return self._states[self._current]

    def change_state(self, state):
        self._current = state

    def send_message(self, msg):
        for lst in self._listeners:
            lst.send_message(msg)


def load(path):
    with open(path) as fp:
        yml = []
        parsing = False

        for line in fp:
            if line.startswith('```yaml') or line.startswith('```yml'):
                parsing = True
            elif line.startswith('```'):
                parsing = False
            elif parsing:
                yml.append(line)

        data = "\n".join(yml)
        game = yaml.load(data)

        if isinstance(game, dict):
            game = Game(**game)

        return game
