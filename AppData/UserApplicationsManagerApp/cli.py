# -*- coding: utf-8 -*-
"""Main command line application.

Attributes
----------
docopt_doc : str
    Used to store/define the docstring that will be passed to docopt as the "doc" argument.
root_folder : str
    The main folder containing the application. All commands must be executed from this location
    without exceptions.
"""

import os

from . import app_utils
from .__init__ import __appdescription__
from .__init__ import __appname__
from .__init__ import __status__
from .__init__ import __version__
from .python_utils import cli_utils

root_folder = os.path.realpath(os.path.abspath(os.path.join(
    os.path.normpath(os.getcwd()))))

docopt_doc = """{appname} {version} ({status})

{appdescription}

Usage:
    app.py (-h | --help | --manual | --version)
    app.py manage [-i <app_id>... | --id=<app_id>...
                  | -t <app_type> | --type=<app_type>]
                  [-f | --force-update]
    app.py print_app_ids
    app.py generate system_executable

Options:

-h, --help
    Show this screen.

--manual
    Show this application manual page.

--version
    Show application version.

-f, --force-update
    Force the update of all applications, ignoring the frequency in which they
    should be updated.

-i <app_id>, --id=<app_id>
    The application's ID/s to perform tasks on.

-t <app_type>, --type=<app_type>
    Perform tasks on applications of this specified type.

""".format(appname=__appname__,
           appdescription=__appdescription__,
           version=__version__,
           status=__status__)


class CommandLineInterface(cli_utils.CommandLineInterfaceSuper):
    """Command line interface.

    It handles the arguments parsed by the docopt module.

    Attributes
    ----------
    a : dict
        Where docopt_args is stored.
    action : method
        Set the method that will be executed when calling CommandLineTool.run().
    apps_manager : class
        See :any:`app_utils.ApplicationsManager`.
    """
    action = None

    def __init__(self, docopt_args):
        """
        Parameters
        ----------
        docopt_args : dict
            The dictionary of arguments as returned by docopt parser.
        """
        self.a = docopt_args
        self._cli_header_blacklist = [self.a["--manual"], self.a["print_app_ids"]]

        super().__init__(__appname__)

        if self.a["--manual"]:
            self.action = self.display_manual_page
        elif self.a["print_app_ids"]:
            self.action = self.print_app_ids
        elif self.a["manage"]:
            self.init_app_manager()
            self.action = self.manage_apps
        elif self.a["generate"]:
            if self.a["system_executable"]:
                self.logger.info("**System executable generation...**")
                self.action = self.system_executable_generation

    def run(self):
        """Execute the assigned action stored in self.action if any.
        """
        if self.action is not None:
            self.action()

    def init_app_manager(self):
        """See :any:`app_utils.ApplicationsManager`.
        """
        self.apps_manager = app_utils.ApplicationsManager(app_ids=list(set(self.a["--id"])),
                                                          app_type=self.a["--type"],
                                                          force_update=self.a["--force-update"],
                                                          logger=self.logger)

    def system_executable_generation(self):
        """See :any:`cli_utils.CommandLineInterfaceSuper._system_executable_generation`.
        """
        self._system_executable_generation(
            exec_name="user-applications-manager-cli",
            app_root_folder=root_folder,
            sys_exec_template_path=os.path.join(
                root_folder, "AppData", "data", "templates", "system_executable"),
            bash_completions_template_path=os.path.join(
                root_folder, "AppData", "data", "templates", "bash_completions.bash"),
            logger=self.logger
        )

    def display_manual_page(self):
        """See :any:`cli_utils.CommandLineInterfaceSuper._display_manual_page`.
        """
        self._display_manual_page(os.path.join(root_folder, "AppData", "data", "man", "app.py.1"))

    def print_app_ids(self):
        """See :any:`app_utils.print_app_ids`.
        """
        app_utils.print_app_ids(self.logger)

    def manage_apps(self):
        """See :any:`app_utils.ApplicationsManager.manage_apps`.
        """
        self.apps_manager.manage_apps()


def main():
    """Initialize command line interface.
    """
    cli_utils.run_cli(flag_file=".user-applications-manager.flag",
                      docopt_doc=docopt_doc,
                      app_name=__appname__,
                      app_version=__version__,
                      app_status=__status__,
                      cli_class=CommandLineInterface)


if __name__ == "__main__":
    pass
