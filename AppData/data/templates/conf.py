# -*- coding: utf-8 -*-
"""Functional example configuration file.
"""


applications = {
    # ##################
    # Git repositories #
    # ##################
    "bash-it": {
        "name": "Bash-it",
        "type": "git_repo",
        "url": "https://github.com/Bash-it/bash-it.git",
        "destination": "~/.bash_it"
    },

    # ##############
    # Single files #
    # ##############
    "devdocs-desktop": {
        "name": "DevDocs Desktop",
        "url": "https://api.github.com/repos/egoist/devdocs-desktop/releases/latest",
        "type": "file",
        "destination": "~/.local/bin/DevDocs.AppImage",
        "frequency": "m",
        "github_api_asset_data": {
            "asset_name_contains": "x86_64",
            "asset_name_starts": "DevDocs",
            "asset_name_ends": "AppImage",
        }
    },

    # ##########
    # Archives #
    # ##########
    "dart-sass": {
        "name": "Dart Sass",
        "url": "https://api.github.com/repos/sass/dart-sass/releases/latest",
        "type": "archive",
        "unzip_prog": "tar",
        "unzip_args": "xzvf",
        "unzip_targets": [
            ("dart-sass", "~/.local/lib"),
        ],
        "post_extraction_actions": {
            "symlinks": [
                ("~/.local/lib/dart-sass/sass", "~/.local/bin/sass")
            ],
            "set_exec": [
                "~/.local/lib/dart-sass/sass"
            ]
        },
        "github_api_asset_data": {
            "asset_name_contains": "linux-x64",
            "asset_name_starts": "dart-sass",
            "asset_name_ends": "tar.gz",
        }
    }
}


if __name__ == "__main__":
    pass
