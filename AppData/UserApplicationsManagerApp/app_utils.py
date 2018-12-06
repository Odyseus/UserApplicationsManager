#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Module with utility functions and classes.

Attributes
----------
base_app_keys : set
    Mandatory keys for all applications.
base_app_keys_for_archives : set
    Mandatory keys for applications of type "archive".
base_app_keys_for_files : set
    Mandatory keys for applications of type "file".
base_app_keys_for_repos : set
    Mandatory keys for applications of type "\*_repo".
conf_file : str
    Path to the configuration file.
home : str
    Path to the User's home folder.
root_folder : str
    The main folder containing the application. All commands must be executed
    from this location without exceptions.
update_data_file : str
    Path to the file where the update data for applications is stored.
"""
import json
import os
import socket
import tempfile
import time
import urllib.request

from .python_utils import cmd_utils
from .python_utils import exceptions
from .python_utils import file_utils
from .python_utils import hash_utils
from .python_utils import shell_utils
from .python_utils import tqdm_wget
from datetime import datetime
from datetime import timedelta
from runpy import run_path
from subprocess import CalledProcessError
from urllib.error import HTTPError
from urllib.error import URLError

root_folder = os.path.realpath(os.path.abspath(os.path.join(
    os.path.normpath(os.getcwd()))))

home = os.path.expanduser("~")
conf_file = os.path.join(root_folder, "UserData", "conf.py")
update_data_file = os.path.join(root_folder, "UserData", "update-data.json")
base_app_keys = {"name", "url", "type"}
base_app_keys_for_archives = base_app_keys.union(
    {"unzip_prog", "post_extraction_actions", "unzip_targets"})
base_app_keys_for_files = base_app_keys.union({"destination"})
base_app_keys_for_repos = base_app_keys.union({"destination"})


def get_applications(logger, validate=True):
    """Get applications.

    Parameters
    ----------
    logger : object
        See :any:`LogSystem`.
    validate : bool, optional
        Whether or not to validate each application. An application is "valid" if
        its dictionary data contains all mandatory keys. Validation is omitted when
        this method is called by the Bash completions script (to *keep things fast*).

    Returns
    -------
    dict
        All applications as found on the **conf.py** file.

    Raises
    ------
    exceptions.MissingMandatoryField
        See :any:`exceptions.MissingMandatoryField`.
    exceptions.MissingRequiredFile
        See :any:`exceptions.MissingRequiredFile`.
    """
    try:
        all_apps = run_path(conf_file)["applications"]
    except FileNotFoundError:
        logger.warning(conf_file)
        raise exceptions.MissingRequiredFile(
            "The <conf.py> file should exist at the above location.")
    except KeyError:
        raise exceptions.MissingMandatoryField(
            "The <conf.py> file should have the <applications> property defined.")

    missing_fields = []

    if validate:
        for app_id, app in all_apps.items():
            app_type = app.get("type")

            if not app_type:
                logger.error("Application ID: %s" % app_id)
                raise exceptions.MissingMandatoryField("The <type> field is required.")

            if app_type == "archive":
                validator_set = base_app_keys_for_archives
            elif app_type == "file":
                validator_set = base_app_keys_for_files
            elif app_type == "git_repo" or app_type == "hg_repo":
                validator_set = base_app_keys_for_repos

            if not validator_set.issubset(app):
                missing_fields += [field for field in validator_set if field not in app]

            if missing_fields:
                logger.error("Application ID: %s" % app_id)
                raise exceptions.MissingMandatoryField(
                    "The <%s> field/s is/are required." % ", ".join(missing_fields))

    return all_apps


def print_app_ids(logger):
    """Print application IDs.

    This method is called by the Bash completions script to auto-complete
    application IDs for the ``--id=`` and ``-i`` CLI options.

    Parameters
    ----------
    logger : object
        See :any:`LogSystem`.
    """
    for app_id in get_applications(logger, validate=False).keys():
        print(app_id)


class ApplicationsManager():
    """ApplicationsManager class.

    Attributes
    ----------
    all_apps : dict
        All applications as found in the conf.py file.
    app_ids : list
        All application IDs passed by the ``--id=`` or ``-i`` CLI options.
    app_type : str
        An application "type" as passed by the ``--type=`` or ``-t`` CLI options.
    current_date : str
        The current date.
    force_update : bool
        Ignore application update frequency and update its file/s anyway.
    logger : object
        See :any:`LogSystem`.
    """
    _apps_type_archive = {}
    _apps_type_file = {}
    _apps_type_git_repo = {}
    _apps_type_hg_repo = {}
    _last_update_data = {}
    _operation_aborted_msg = "Operations for <%s> aborted."
    _repo_types = ["git", "hg"]
    _repo_types_names_map = {
        "git": "Git",
        "hg": "Mercurial"
    }

    def __init__(self, app_ids=[], app_type=None, force_update=False, logger=None):
        """Initialize.

        Parameters
        ----------
        app_ids : list
            All application IDs passed by the ``--id=`` or ``-i`` CLI options.
        app_type : str
            An application "type" as passed by the ``--type=`` or ``-t`` CLI options.
        force_update : bool, optional
            Ignore application update frequency and update its file/s anyway.
        logger : object, optional
            See :any:`LogSystem`.
        """
        self.app_ids = app_ids
        self.app_type = app_type
        self.force_update = force_update
        self.logger = logger
        self.current_date = time.strftime("%B %d %Y", time.gmtime())  # Format = January 1 2018

        self.all_apps = get_applications(self.logger)

        self._filter_group_extend_apps()

    def _print_shell_separator(self, sep_char):
        """Print shell separator.

        Parameters
        ----------
        sep_char : str
            Character to use as a separator.
        """
        self.logger.info(shell_utils.get_cli_separator(sep_char), date=False)

    def _check_url(self, url):
        """Check if an URL can be reached.

        Parameters
        ----------
        url : str
            The URL to check.

        Returns
        -------
        tuple
            If the URL can be reached at index 0 and the URL itself at index 1.
        """
        if url is None:
            return False, None

        self.logger.info("Checking URL...")
        self.logger.info(url, date=False)
        can_download = False

        try:
            with urllib.request.urlopen(url, timeout=10) as req:
                status_code = req.getcode()
                can_download = status_code < 400
                self.logger.info("Status code: %s" % status_code)
        except HTTPError as err:
            self.logger.error(err)
        except URLError as err:
            if isinstance(err.reason, socket.timeout):
                self.logger.error("Socket timed out.")
            else:
                self.logger.error(err)
        else:
            return can_download, url

        return False, None

    def _get_github_asset_url(self, app_id, app):
        """Get GitHub asset URL.

        This method uses the GitHub API to download a JSON file with information on a
        release of a repository. The "name" key of each element of the array/list
        called "assets" of the downloaded JSON file is scanned for different matches to
        locate the URL of the asset that one actually want to download.

        Parameters
        ----------
        app_id : str
            The application ID.
        app : dict
            The application data.

        Returns
        -------
        str|None
            The URL of the asset that one wants to download or None.

        Raises
        ------
        exceptions.KeyboardInterruption
            See :any:`exceptions.KeyboardInterruption`.
        """
        self.logger.info("Attempting to get asset URL from GitHub API.")
        release_tag = None
        json_data = None

        can_download, github_api_url = self._check_url(app["url"])

        if can_download:
            with tempfile.NamedTemporaryFile(prefix=app_id, suffix=".json") as tmp_file:
                try:
                    tqdm_wget.download(github_api_url, tmp_file.name)
                except KeyboardInterrupt:
                    raise exceptions.KeyboardInterruption()
                except Exception as err:
                    self.logger.error(err)
                else:
                    with open(tmp_file.name, "r+", encoding="UTF-8") as file:
                        json_data = json.loads(file.read())

            if json_data is not None:
                release_tag = json_data.get("tag_name")
                checks = app["github_api_asset_data"]

                for asset in json_data.get("assets", []):
                    contains = True if not checks.get("asset_name_contains", False) else \
                        checks.get("asset_name_contains") in asset["name"]
                    starts = True if not checks.get("asset_name_starts", False) else \
                        asset["name"].startswith(checks.get("asset_name_starts"))
                    ends = True if not checks.get("asset_name_ends", False) else \
                        asset["name"].endswith(checks.get("asset_name_ends"))

                    if all([contains, starts, ends]):
                        return release_tag, asset["browser_download_url"]
                    else:
                        continue

        return release_tag, None

    def _filter_group_extend_apps(self):
        """Filter, group and extend applications data.
        """
        filtered_apps = {}

        try:
            with open(update_data_file, "r", encoding="UTF-8") as json_file:
                self._last_update_data = json.loads(json_file.read())
        except Exception:
            pass

        if self.app_type is not None:
            filtered_apps = {id: self.all_apps[id] for id in self.all_apps
                             if self.all_apps[id]["type"] == self.app_type}
        elif self.app_ids:
            filtered_apps = {id: self.all_apps[id] for id in self.app_ids
                             if id in self.all_apps}
        else:
            filtered_apps = self.all_apps

        if filtered_apps:
            for app_id, app in sorted(filtered_apps.items()):
                app.update(self._last_update_data.get(app_id, {}))

                # Do it here so it has to be done just once.
                if app.get("destination"):
                    app["destination"] = file_utils.expand_path(app["destination"])

                getattr(self, "_apps_type_%s" % app["type"], [])[app_id] = app

    def _get_check_repo_cmd(self, repo_type):
        """Get the command to check a repository.

        Returns
        -------
        list
            The command to check the repository.

        Parameters
        ----------
        repo_type : str
            "git" or "hg".
        """
        if repo_type == "git":
            return ["git", "ls-remote"]
        elif repo_type == "hg":
            return ["hg", "-R", ".", "root"]

    def _do_checkout(self, repo_type, repo_path, revision):
        """Check out revision.

        Parameters
        ----------
        repo_type : str
            "git" or "hg".
        repo_path : str
            Path to the local repository.
        revision : str
            Branch name/Tag name/Commit hash to check out.
        """
        self.logger.info("Checking out revision <%s>..." % revision)

        cmd_utils.run_cmd(
            "{cmd} {checkout_cmd} {revision}".format(
                cmd=repo_type,
                checkout_cmd="checkout" if repo_type is "git" else "update",
                revision=revision
            ),
            stdout=None,
            stderr=None,
            shell=True,
            check=True,
            cwd=repo_path
        )

    def _do_pull(self, repo_type, repo_path):
        """Pull from a repository.

        There are only two SCM software (that I know how to use), ``git`` and ``hg``, and they
        both have the same command structure to pull from a repository.

        Parameters
        ----------
        repo_type : str
            "git" or "hg".
        repo_path : str
            Path to the local repository.
        """
        cmd_utils.run_cmd(
            "%s pull" % repo_type,
            stdout=None,
            stderr=None,
            shell=True,
            check=True,
            cwd=repo_path
        )

    def _do_clone(self, repo_type, repo_path, repo_url):
        """Clone a repository.

        There are only two SCM software (that I know how to use), ``git`` and ``hg``, and they
        both have the same command structure to clone a repository.

        Parameters
        ----------
        repo_type : str
            "git" or "hg".
        repo_path : str
            Path to the local repository.
        repo_url : str
            URL of the on-line repository.
        """
        cmd_utils.run_cmd(
            "{cmd} clone {depth} {url} {path}".format(
                cmd=repo_type,
                depth="--depth=1" if repo_type is "git" else "",
                url=repo_url,
                path=os.path.basename(repo_path)
            ),
            stdout=None,
            stderr=None,
            shell=True,
            check=True,
            cwd=os.path.dirname(repo_path),
        )

    def _manage_repositories(self):
        """Manage applications of type "git_repo" or "hg_repo".
        """
        for repo_type in self._repo_types:
            apps = getattr(self, "_apps_type_%s_repo" % repo_type, None)

            if apps:
                self._print_shell_separator("#")
                self.logger.info("Handling %s repositories..." %
                                 self._repo_types_names_map[repo_type])

                for app_id, app in apps.items():
                    self._print_shell_separator("-")
                    self.logger.info("Handling %s's repository..." % app["name"])

                    if self.force_update or self._should_update(app):
                        repo_path = app["destination"]

                        if file_utils.is_real_dir(repo_path):
                            # If the repository path exists, check if it is a valid repository
                            # and proceed to attempt to pull from it.
                            p = cmd_utils.run_cmd(self._get_check_repo_cmd(repo_type),
                                                  stderr=None,
                                                  cwd=repo_path)
                        else:
                            # If the repository path doesn't exists, attempt to clone the
                            # repository and get out of the loop.
                            self.logger.warning(
                                "%s repository doesn't seem to exist." % app["name"])
                            self.logger.info("Cloning %s repository." % app["name"])
                            self._do_clone(repo_type, repo_path, app["url"])
                            self._set_update_data(app_id, "update_date", self.current_date)

                            if app["checkout_revision"]:
                                self._do_checkout(repo_type, repo_path, app["checkout_revision"])

                            continue

                        # Return code should be zero. If it isn't, then the destination
                        # isn't a repository.
                        if p and not p.returncode:
                            self.logger.info("Pulling from %s's repository." % app["name"])
                            self._do_pull(repo_type, repo_path)
                            self._set_update_data(app_id, "update_date", self.current_date)

                            if app["checkout_revision"]:
                                self._do_checkout(repo_type, repo_path, app["checkout_revision"])
                        else:
                            self.logger.warning("Manual intervention required!")
                            self.logger.warning(
                                "The following path doesn't seem to be a repository:")
                            self.logger.warning(repo_path)
                    else:
                        self.logger.info("%s doesn't need updating." % app["name"])

    def _manage_files(self):
        """Manage applications of type "file".

        Raises
        ------
        exceptions.KeyboardInterruption
            See :any:`exceptions.KeyboardInterruption`.
        """
        if self._apps_type_file:
            self._print_shell_separator("#")
            self.logger.info("Handling individual files...")

            for app_id, app in self._apps_type_file.items():
                self._print_shell_separator("-")
                self.logger.info("Handling %s's file..." % app["name"])

                if self.force_update or self._should_update(app):
                    release_tag = None
                    file_path = app["destination"]

                    if app.get("github_api_asset_data"):
                        release_tag, asset_download_url = self._get_github_asset_url(app_id, app)
                        can_download, download_url = self._check_url(asset_download_url)

                        # Logic:
                        # If an already downloaded file exists, only download a new one under the
                        # following conditions:
                        # - If an stored tag name is different from the newly obtained one.
                        # - If the tag names are identical, check for file hashes.
                        # - If the file hashes are different, then and only then download a
                        #   new copy of a file.
                        if download_url and can_download and file_utils.is_real_file(file_path) \
                                and not self.force_update:
                            # Do not bother comparing the tag versions. Just check that they are
                            # different and move on. Comparing version numbers in any language is a
                            # freaking nightmare.
                            if release_tag is not None:
                                can_download = release_tag != self._get_update_data(
                                    app_id, "tag_name")

                            if not can_download:
                                can_download = hash_utils.file_hash(
                                    file_path) != self._get_update_data(app_id, "hash")

                            if not can_download:
                                self.logger.info("%s doesn't need updating." % app["name"])
                    else:
                        can_download, download_url = self._check_url(app["url"])

                    if download_url is None:
                        self.logger.warning("No download URL could be determined. Aborted!")
                    elif download_url and can_download:
                        parent_dir = os.path.dirname(file_path)

                        if not file_utils.is_real_dir(parent_dir):
                            os.makedirs(parent_dir)

                        try:
                            tqdm_wget.download(download_url, file_path)
                        except KeyboardInterrupt:
                            raise exceptions.KeyboardInterruption()
                        except Exception as err:
                            self.logger.error(err)
                        else:
                            self._set_update_data(app_id, "update_date", self.current_date)

                            if release_tag is not None:
                                self._set_update_data(
                                    app_id, "hash", hash_utils.file_hash(file_path))
                                self._set_update_data(app_id, "tag_name", release_tag)

                            os.chmod(file_path, 0o755)
                else:
                    self.logger.info("%s doesn't need updating." % app["name"])

    def _handle_archive(self, app_id, app, archive, temp_wd):
        """Handle archive.

        Parameters
        ----------
        app_id : str
            The application ID.
        app : dict
            The application data.
        archive : str
            Path to an archive to handle.
        temp_wd : str
            Path to a temporary working directory.
        """
        errors = []
        post_extraction_actions = app.get("post_extraction_actions", {})
        self.logger.info("Handling <%s>'s archive." % app["name"])

        for unzip_target, d in app["unzip_targets"]:
            destination = file_utils.expand_path(d)

            cmd = []

            # if app["unzip_prog"] == "7z":
            #     cmd += ["7z", "e", "-y", app["downloaded_filename"]]
            # elif app["unzip_prog"] == "unzip":
            #     cmd += ["unzip", "-o", app["downloaded_filename"]]
            if app["unzip_prog"] == "tar":
                args = app.get("unzip_args")

                if not args:
                    errors.append((app_id, "Missing required <unzip_args> key."))
                    continue

                cmd += ["tar", app["unzip_args"], archive, "-C", destination, unzip_target]

            if cmd:
                try:
                    cmd_utils.run_cmd(cmd, stdout=None, stderr=None, cwd=temp_wd)
                except CalledProcessError as err:
                    errors.append((" ".join(cmd), err))
                    self.logger.error(err)
                    continue

        if errors:
            self.logger.warning(
                "The following errors were found while processing %s:" % app["name"])
            self.logger.warning("Post-extraction actions will not be performed.")

            for cmd_path_app, err in errors:
                self.logger.warning("Command, path or application ID:", date=False)
                self.logger.warning(cmd_path_app, date=False)
                self.logger.error("Error:", date=False)
                self.logger.error(err, date=False)
        else:
            if post_extraction_actions.get("set_exec"):
                self.logger.info("Setting files as executable...")

                for p in post_extraction_actions.get("set_exec"):
                    f_path = file_utils.expand_path(p)

                    if file_utils.is_real_file(f_path):
                        self.logger.info(f_path, date=False)

                        try:
                            os.chmod(f_path, 0o755)
                        except EnvironmentError as err:
                            errors.append((f_path, err))

            if post_extraction_actions.get("symlinks"):
                self.logger.info("Generating symbolic links...")

                for tgt, dst in post_extraction_actions.get("symlinks"):
                    tgt_path = file_utils.expand_path(tgt)
                    dst_path = file_utils.expand_path(dst)

                    self.logger.info("Target: %s" % tgt_path, date=False)
                    self.logger.info("Destination: %s" %
                                     dst_path, date=False)

                    file_utils.copy_create_symlink(tgt_path,
                                                   dst_path,
                                                   logger=self.logger)

    def _manage_archives(self):
        """Manage applications of type "archive".

        Raises
        ------
        exceptions.KeyboardInterruption
            See :any:`exceptions.KeyboardInterruption`.
        """
        if self._apps_type_archive:
            self._print_shell_separator("#")
            self.logger.info("Handling archives...")

            for app_id, app in self._apps_type_archive.items():
                self._print_shell_separator("-")
                self.logger.info("Handling %s's archive..." % app["name"])

                if not cmd_utils.which(app["unzip_prog"]):
                    self.logger.warning("Command <%s> not found on your system." %
                                        app["unzip_prog"])
                    self.logger.warning(self._operation_aborted_msg % app["name"])
                    continue

                if self.force_update or self._should_update(app):
                    release_tag = None

                    if app.get("github_api_asset_data"):
                        release_tag, asset_download_url = self._get_github_asset_url(app_id, app)
                        can_download, download_url = self._check_url(asset_download_url)

                        if download_url and can_download and not self.force_update:
                            if release_tag is not None:
                                can_download = release_tag != self._get_update_data(
                                    app_id, "tag_name")

                            if not can_download:
                                self.logger.info("%s doesn't need updating." % app["name"])
                    else:
                        can_download, download_url = self._check_url(app["url"])

                    if download_url is None:
                        self.logger.warning("No download URL could be determined. Aborted!")
                    elif download_url and can_download:
                        with tempfile.TemporaryDirectory(prefix=app_id) as tmp_dir:
                            # Use of app_id for the downloaded file name because getting it from
                            # the URL itself could be a nightmare.
                            archive_path = os.path.join(tmp_dir, app_id)

                            try:
                                tqdm_wget.download(download_url, archive_path)
                            except KeyboardInterrupt:
                                raise exceptions.KeyboardInterruption()
                            except Exception as err:
                                self.logger.error(err)
                            else:
                                try:
                                    self._handle_archive(app_id, app, archive_path, tmp_dir)
                                except Exception as err:
                                    self.logger.error(err)
                                except KeyboardInterrupt:
                                    raise exceptions.KeyboardInterruption()
                                else:
                                    self._set_update_data(app_id, "update_date", self.current_date)

                                    if release_tag is not None:
                                        self._set_update_data(app_id, "tag_name", release_tag)
                else:
                    self.logger.info("%s doesn't need updating." % app["name"])

    def _should_update(self, app):
        """Check if source should be updated.

        Parameters
        ----------
        app : dict
            The application data.

        Returns
        -------
        bool
            If the source needs to be updated depending on its configured specified
            update frequency.
        """
        frequency = app.get("frequency", "w")
        update_date = app.get("update_date", False)

        if not update_date:
            return True

        if frequency == "d":
            return True

        if app["type"] == "file" and not file_utils.is_real_file(app["destination"]):
            return True

        # Do not check for this for now. Archive types are kind of a PITA.
        # Considerations:
        # - Archive type destinations could be folders or files alike.
        # if app["type"] == "archive" and not file_utils.is_real_dir(app["destination"]):
        #     return True

        then = datetime.strptime(update_date, "%B %d %Y")
        now = datetime.strptime(self.current_date, "%B %d %Y")

        if frequency == "w":  # Weekly.
            return (now - then) > timedelta(days=6)
        elif frequency == "m":  # Monthly.
            return (now - then) > timedelta(days=29)
        elif frequency == "s":  # Semestrial.
            return (now - then) > timedelta(days=87)

    def _get_update_data(self, app_id, prop_key):
        """Get update data.

        Parameters
        ----------
        app_id : str
            The application ID.
        prop_key : str
            The property to get the value of.

        Returns
        -------
        str
            The value of a property.
        """
        app_update_data = self._last_update_data.get(app_id, {})
        return app_update_data.get(prop_key)

    def _set_update_data(self, app_id, prop_key, prop_val):
        """Set update data.

        Parameters
        ----------
        app_id : str
            The application ID.
        prop_key : str
            Property to modify.
        prop_val : str
            New value for the property.
        """
        app_update_data = self._last_update_data.get(app_id, {})
        app_update_data[prop_key] = prop_val
        self._last_update_data[app_id] = app_update_data

    def _save_update_data(self):
        """Save update data.
        """
        with open(update_data_file, "w", encoding="UTF-8") as data_file:
            data_file.write(json.dumps(self._last_update_data, indent=4, sort_keys=True))

    def manage_apps(self):
        """Manage applications.
        """
        self._manage_repositories()
        self._manage_files()
        self._manage_archives()
        self._save_update_data()


if __name__ == "__main__":
    pass
