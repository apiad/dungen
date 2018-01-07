# Tutorial 01 - Basics

`dungen` is a text-based dungeon-like game engine and generator. Text-based games are played through a text interface, where players interact with the world by reading descriptions of the situation, and writing their actions in return.

A game in `dungen` is entirely described as a text file in `YAML` format.
Games are based entirely in the concept of a *state machine*. A state machine, basically, is entirely defined by a set of **states** and a set of transitions, which we call **actions**.

States can be used to represent anything, and the change between states is what defines "progress" in the game. One of the most common use for states is to define locations between which players can travel. However, as a game grows in complexity, a state will be the combination of many different things, including the current location, an inventory, the character stats, and any other progress performed during the game.

The actual purpose of states is to define which actions can be taken. Every state defines a set of actions, and only those actions are available to the player. Some of those actions may trigger a state change, and that's how the game progresses.

An action is simply a label associated with an outcome. The most basic action is `Goto`, which simply changes the current state. Another typical action is `Message` which displays a message to the player. How this message is displayed will depend on the *game runner* in use. The default game runner is a CLI runner which displays messages in the console. The game runner also defines how an action is selected by player. In the CLI runner the actions are typed by the player in the console. Other types of runners could include a GUI showing a menu of actions and display messages in a variety of different formats.

To put all of this in practice, let's create a very simple game. In this game the player starts in a room and has to find a way out. To do that the player must found the key to the door, which is inside a drawer. The player must *open* the drawer, *take* the key, and then *open* the door to win.

There are many ways to define this game in `dungen` with more advanced tools, but using only the basic elements of states and the two basic action, this is how it can be done. We'll define a state for each of the possible different situations in which the player can be, and define how some actions change them. The different states and actions available in each one are:

* **Start**: the door is closed, the drawer is closed and the key is inside the drawer.
  * **look** describes the door and drawer.
  * **open door** shows a message saying that the door is looked.
  * **open drawer** moves to the state **Drawer open**.
* **Drawer open**: the drawer is open:
  * **look** describes the door and drawer, specifying is open, and there is a key inside.
  * **open door** shows a message saying that the door is looked.
  * **close drawer** moves to the state **Start**.
  * **take key** moves to the state **Has key**.
* **Has key**: the key is player's possesion:
  * **look** describes the door and drawer, specifying is open, and that the player took the key that was inside.
  * **put key** moves to the state **Drawer open**.
  * **open door** moves to the state **Victory**.
* **Victory**: displays the game is won and exits.

This description basically defines the whole game. We use states to define the different moments in the game where progress is made, and actions to define what the player can do, and how he progresses through the game doing those actions.

Now we just need to convert this description into a propper `dungen` YAML file. This is it:

```yaml
name: Tutorial 01 - Basics
current: start
states:
  - State:
      name: start
      actions:
        - Message:
            label: look
            message: You are inside a room. The only way out seems
                     to be a closed door in front of you. There is
                     also a closed drawer nearby.
        - Message:
            label: open door
            message: The door is locked. Maybe there is a key somewhere?
        - Goto:
            label: open drawer
            to: drawer-open
  - State:
      name: drawer-open
      # ...
```

The basic structure is shown in this example. A game is basically just a collection of states, each of which is a collection of actions. The states are declared using the `State` *type* and then listing their *properties*. For now, just a `name` and a list of `actions` are important. Each action also has a *type* (either `Message` or `Goto` for now), and different *properties*, such as `label`, which is common to all actions, or `message` which is particular of the `Message` action.

To try this game, just run the CLI client:

    python3 -m dungen.cli games/tutorials/01-basics.yml

> **Implementation details**: under the hood this is just a plain YAML file, which is parsed and then interpreted to build an in-memory representation of the whole game. The top level structure is interpreted as the content of a `Game` class, and each child of the tree is recursively parsed and converted to some class. Basic types are mapped to corresponding Python types. Dictionary types are mapped to some class, and we take the convention to declare that class as the parent key. For example the `State` key maps directly to the `State` class in runtime.

Take a look at the full example in [the source file](01-basics.yml).
