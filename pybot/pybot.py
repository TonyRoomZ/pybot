import re
import traceback
from collections import namedtuple, defaultdict
from os import environ as env

from six import print_
from six.moves import input

User = namedtuple('User', ['id', 'name'])


class EventBus(object):
    def __init__(self):
        self._listeners = defaultdict(list)

    def publish(self, type, data=None):
        for listener in self._listeners[type]:
            listener(data)

    def subscribe(self, type, f):
        listeners = self._listeners[type]
        if f not in listeners:
            listeners.append(f)

    def unsubscribe(self, type, f):
        self._listeners[type].remove(f)


class Message(object):
    def __init__(self, user, room, text, id=None):
        self.user = user
        self.room = room
        self.text = text
        self.id = id


class Adapter(object):
    def __init__(self, robot):
        self.robot = robot

    def send(self, message, text):
        pass

    def emote(self, message, text):
        self.send(message, text)

    def reply(self, message, text):
        pass

    def topic(self, message, text):
        pass

    def play(self, message, text):
        pass

    def run(self):
        pass

    def close(self):
        pass

    def receive(self, text):
        self.robot.receive(text)


class ShellAdapter(Adapter):
    def send(self, message, text):
        print(text)

    def emote(self, message, text):
        self.send(message, '* {}'.format(text))

    def reply(self, message, text):
        self.send(message, '{}: {}'.format(message.user.name, text))

    def run(self):
        name = env.get('PYBOT_SHELL_USER_NAME', 'Shell')

        try:
            user_id = env.get('PYBOT_SHELL_USER_ID')
        except ValueError:
            user_id = 1

        self.robot.emit('connected')

        while True:
            try:
                text = input('{}> '.format(self.robot.name))
            except EOFError:
                print
                break

            if text == 'quit':
                break

            user = User(user_id, name)
            message = Message(user, 'shell', text)
            self.receive(message)

        self.robot.emit('disconnected')
        self.robot.shutdown()


class Response(object):
    def __init__(self, robot, message, match):
        self.robot = robot
        self.message = message
        self.match = match

    def send(self, text):
        self.robot.adapter.send(self.message, text)

    def emote(self, text):
        self.robot.adapter.emote(self.message, text)

    def reply(self, text):
        self.robot.adapter.reply(self.message, text)

    def topic(self, text):
        self.robot.adapter.topic(self.message, text)


class Robot(object):
    def __init__(self, name='Pybot'):
        self.name = name
        self._load_adapter()
        self._listeners = []
        self._bus = EventBus()

    def _load_adapter(self):
        # TODO: dynamically load the adapter based on args
        # TODO: catch all errors and exit if failure to load
        self.adapter = ShellAdapter(self)

    def run(self):
        self.adapter.run()

    def shutdown(self):
        self.adapter.close()

    def send(self, room, text):
        fake_message = Message(None, room, None)
        self.adapter.send(fake_message, text)

    def reply(self, user, room, text):
        fake_message = Message(user, room, None)
        self.adapter.reply(fake_message, text)

    def on(self, type):
        def wrapper(f):
            self._bus.subscribe(type, f)
            return f

        return wrapper

    def emit(self, type, data=None):
        self._bus.publish(type, data)

    def receive(self, message):
        for listener in self._listeners:
            try:
                listener(message)
            except:
                traceback.print_exc()


    def respond(self, pattern):
        def wrapper(f):
            matcher = RegexMatcher(pattern)
            wrapper = DirectMessageMatcher(matcher, self.name)
            self._add_listener(wrapper, f)

        return wrapper

    def hear(self, pattern):
        def wrapper(f):
            matcher = RegexMatcher(pattern)
            self._add_listener(matcher, f)
            return f

        return wrapper

    def listen(self, matcher):
        def wrapper(f):
            self._add_listener(matcher, f)
            return f

        return wrapper

    def _add_listener(self, matcher, func):
        listener = Listener(self, matcher, func)
        self._listeners.append(listener)


class Listener(object):
    def __init__(self, robot, matcher, func):
        self.robot = robot
        self.matcher = matcher
        self.func = func

    def __call__(self, message):
        match = self.matcher.match(message)
        if not match:
            return False

        response = Response(self.robot, message, match)
        self.func(response)
        return True


class Matcher(object):
    def match(self, message):
        pass


class RegexMatcher(Matcher):
    def __init__(self, pattern):
        self.regex = re.compile(pattern)

    def match(self, message):
        if message.text:
            return self.regex.search(message.text)


class DirectMessageMatcher(Matcher):
    def __init__(self, wrapped, name):
        self.wrapped = wrapped
        self.name = name.lower()

    def match(self, message):
        if not message.text:
            return

        tokens = message.text.lower().split(' ')
        if not tokens:
            return

        first_token = tokens[0].lstrip(' ').rstrip(' :-=')
        if first_token == self.name:
            return self.wrapped.match(message)

