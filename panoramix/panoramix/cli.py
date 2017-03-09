#!/usr/bin/env python
import sys

from cliff.app import App
from panoramix.cmdmanager import MyCommandManager


class Panoramix(App):
    DEFAULT_VERBOSE_LEVEL = 0

    def __init__(self):
        App.__init__(
            self,
            description='panoramix client',
            version='0.1',
            command_manager=MyCommandManager(
                'panoramix.commands', convert_underscores=True),
            deferred_help=True,
            )

    def initialize_app(self, argv):
        self.LOG.debug('initialize_app')

    def prepare_to_run_command(self, cmd):
        self.LOG.debug('prepare_to_run_command %s', cmd.__class__.__name__)

    def clean_up(self, cmd, result, err):
        self.LOG.debug('clean_up %s', cmd.__class__.__name__)
        if err:
            self.LOG.debug('got an error: %s', err)


def main(argv=sys.argv[1:]):
    return Panoramix().run(argv)


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
