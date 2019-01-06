# coding: utf-8

import sys
from dungen.base import load, Game, State, Action


class CliListener:
    def send_message(self, msg):
        print(msg)


class CliRunner:
    def __init__(self, game):
        self.game = game

    def run(self):
        while True:
            print('')
            state:State = self.game.current_state()
            actions = state.actions()
            actions_list = list(actions.values())

            for i, label in enumerate(actions):
                print(i+1, label)

            try:
                option = int(input('> '))
                actions_list[option - 1].execute(self.game)
            except (IndexError, ValueError):
                pass
            except EOFError:
                return


def main():
    game = load(sys.argv[1])
    game.add_listener(CliListener())
    runner = CliRunner(game)
    runner.run()


if __name__ == '__main__':
    main()
