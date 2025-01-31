"""
Provide beamline configuration from the iconfig.toml file.

Example TOML configuration file: iconfig_default.toml

"""

__all__ = [
    "load_config",
]

import argparse
from datetime import datetime, date, time
import logging
import os
from pathlib import Path
from pprint import pprint
from typing import Optional, Sequence

import tomli
from mergedeep import merge

log = logging.getLogger(__name__)


Table = dict[str, dict | int | float | str | bool | list | datetime | date | time]


def load_files(file_paths: Sequence[Path]):
    """Generate the configs for files as dictionaries."""
    for fp in file_paths:
        fp = Path(fp)
        if fp.exists():
            with open(fp, mode="rb") as fd:
                log.debug(f"Loading config file: {fp}")
                config = tomli.load(fd)
                yield config
        else:
            log.debug(f"Could not find config file, skipping: {fp}")


def lookup_file_paths():
    if os.environ.get("HAVEN_CONFIG_FILES", "") != "":
        return [Path(fp) for fp in os.environ["HAVEN_CONFIG_FILES"].split(",")]
    else:
        return [Path(__file__).parent / "iconfig_testing.toml"]


def load_config(file_paths: Optional[Sequence[Path]] = None):
    """Load TOML config files.

    Will load files specified in the following locations:

    1. *file_paths* argument
    2. The $HAVEN_CONFIG_FILES environmental variable.
    3. iconfig_default.toml file included with Haven.

    """
    if file_paths is None:
        file_paths = lookup_file_paths()
    else:
        file_paths = list(file_paths).copy()
    # Add config file from environmental variable
    # Load configuration from TOML files
    config: Table = {}
    merge(config, *load_files(file_paths))
    return config


def print_config_value(args: Sequence[str] | None = None) -> None:
    """Print a config value from TOML files.

    Parameters
    ----------
    key
      The path to the value to retrieve from config files. Sections
      should be separated by dots, e.g. "shutter.A.open_pv"

    """
    # Set up command line arguments
    parser = argparse.ArgumentParser(
        prog="haven_config",
        description="Retrieve a value from Haven's config files.",
    )
    parser.add_argument("key", help="The dot-separated key to look up.")
    args_ = parser.parse_args(args=args)
    # Get the keys from the config file
    value = load_config()
    for part in args_.key.split("."):
        value = value[part]
    try:
        value = value.strip()
    except AttributeError:
        # It's not a simple string, so pretty print it
        pprint(value)
    else:
        # Simple string, so just print it
        print(value)


# -----------------------------------------------------------------------------
# :author:    Mark Wolfman
# :email:     wolfman@anl.gov
# :copyright: Copyright © 2023, UChicago Argonne, LLC
#
# Distributed under the terms of the 3-Clause BSD License
#
# The full license is in the file LICENSE, distributed with this software.
#
# DISCLAIMER
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR
# A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT
# HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL,
# SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT
# LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
# DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
# THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
# OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# -----------------------------------------------------------------------------
