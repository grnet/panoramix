import os
import logging
import inspect
from cliff.commandmanager import CommandManager
from cliff.command import Command

LOG = logging.getLogger(__name__)


class CommandWrapper(object):
    """Wrap up a command class already imported to make it look like a plugin.
    """
    def __init__(self, name, cmdclass):
        self.name = name
        self.cmdclass = cmdclass

    def load(self, require=False):
        return self.cmdclass


class MyCommandManager(CommandManager):
    def __init__(self, namespace, convert_underscores=True):
        super(MyCommandManager, self).__init__(namespace, convert_underscores)

    def load_commands(self, namespace):
        """Load all the commands from a module"""

        m = __import__('{}'.format(namespace), fromlist=[''])
        namespace_dir = os.path.join(os.path.dirname(m.__file__))
        for entry in os.listdir(namespace_dir):
            filename = os.path.basename(entry)
            filename, file_ext = os.path.splitext(filename)
            if file_ext != ".py":
                continue

            m = __import__('{}.{}'.format(namespace, filename),
                           fromlist=[filename])

            for attr, value in inspect.getmembers(m, inspect.isclass):
                # Skip 'Command' class
                if value.__name__ in ['Command', 'Lister', 'ShowOne']:
                    continue

                if not issubclass(value, Command):
                    continue

                cmd_name = attr.lower()
                LOG.debug('Found command %r', cmd_name)
                if self.convert_underscores:
                    cmd_name = cmd_name.replace('_', ' ')

                self.commands[cmd_name] = CommandWrapper(cmd_name, value)
        return
