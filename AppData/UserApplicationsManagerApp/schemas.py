#!/usr/bin/python3
# -*- coding: utf-8 -*-
"""Schemas for JSON data validation.

Attributes
----------
application_schema_archive_type : dict
    JSON schema.
applications_schema_global : dict
    JSON schema.
"""
applications_schema_global = {
    "description": "Schema to validate the 'applications' property inside a UserData/conf.py file.",
    "type": "object",
    "additionalProperties": True,
    "patternProperties": {
        ".*": {
            "type": "object",
            "additionalProperties": True,
            "required": [
                "name",
                "type",
                "url"
            ],
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of an application."
                },
                "type": {
                    "enum": [
                        "git_repo",
                        "hg_repo",
                        "file",
                        "archive"
                    ],
                    "description": "The application type that will decide how to handle downloaded application files."
                },
                "url": {
                    "type": "string",
                    "description": "The URL from where to download the application."
                },
                "destination": {
                    "type": "string",
                    "description": "The final destination for an application."
                },
                "frequency": {
                    "enum": ["d", "w", "m", "s"],
                    "description": "Frequency in which an application should be downloaded."
                },
                "github_api_asset_data": {
                    "type": "object",
                    "description": "This key must contain *matching data* and must be used only when an application ``url`` key points to a Github repository's *API URL*.",
                    "properties": {
                        "asset_name_contains": {
                            "type": "string"
                        },
                        "asset_name_starts": {
                            "type": "string"
                        },
                        "asset_name_ends": {
                            "type": "string"
                        }
                    }
                },
                "checkout_revision": {
                    "type": "string",
                    "description": "A branch name or a tag name or a commit hash."
                }
            }
        }
    }
}

application_schema_archive_type = {
    "description": "Schema to validate the 'applications' property inside a UserData/conf.py file.",
    "type": "object",
    "additionalProperties": True,
    "properties": {
        "unzip_prog": {
            "enum": ["tar"],
            "description": "The name of the command used to unpack an archive."
        },
        "untar_arg": {
            "enum": [
                "--xz",
                "-J",
                "--gzip",
                "-z",
                "--bzip2",
                "-j"
            ],
            "description": "The decompress argument used by the ``tar`` program."
        },
        "unzip_targets": {
            "type": "array",
            "description": "A list of tuples.",
            "items": {
                "type": "custom_tuple",
                "description": "A tuple. At index zero of each tuple should be defined the path to a file/folder inside a downloaded archive. At index one should be defined the path to the folder where the target should be extracted."
            }
        },
        "post_extraction_actions": {
            "type": "object",
            "description": "A list of actions to perform after an archive is extracted.",
            "properties": {
                "symlinks": {
                    "type": "array",
                    "description": "A list of tuples.",
                    "items": {
                        "type": "custom_tuple",
                        "description": "A tuple. At index zero, the path to a file/folder. At index one, the path to the generated symbolic link."
                    }
                },
                "set_exec": {
                    "type": "array",
                    "description": "A list of file paths to set as executable.",
                    "items": {
                        "type": "string",
                        "description": "A path to a file to set as executable."
                    }
                }
            }
        }
    }
}


if __name__ == "__main__":
    pass
