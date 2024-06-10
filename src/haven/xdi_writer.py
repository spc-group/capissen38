import datetime as dt
import logging
import re
import unicodedata
import warnings
from pathlib import Path
from typing import Mapping, Optional, Sequence, Union

from bluesky.callbacks import CallbackBase

from . import exceptions, registry

log = logging.getLogger(__name__)


def slugify(value, allow_unicode=False):
    """
    Taken from https://github.com/django/django/blob/master/django/utils/text.py
    Convert to ASCII if 'allow_unicode' is False. Convert spaces or repeated
    dashes to single dashes. Remove characters that aren't alphanumerics,
    underscores, or hyphens. Also strip leading and
    trailing whitespace, dashes, and underscores.
    """
    value = str(value)
    if allow_unicode:
        value = unicodedata.normalize("NFKC", value)
    else:
        value = (
            unicodedata.normalize("NFKD", value)
            .encode("ascii", "ignore")
            .decode("ascii")
        )
    return re.sub(r"[-\s]+", "-", value).strip("-_")


class XDIWriter(CallbackBase):
    """A callback class for bluesky that will save data to an XDI file.

    The XAFS data interchange (XDI) format is a plain text,
    tab-separated file format that standardizes XAFS data. Metadata is
    also included in headers.

    The location of the file is determined by passing the *filename*
    parameter in when created the writer object:

    .. code-block:: python

      writer = XDIWriter(fd="./my_experiment.xdi")

    Placeholders can be included that will be filled-in with metadata
    during the start phase of the plan, for example:

    .. code-block:: python

      plan = energy_scan(..., E0="Ni_K", md=dict(sample_name="nickel oxide"))
      writer_callback = XDIWriter(fd="./{year}{month}{day}_{sample_name}_{edge}.xdi")
      RE(plan, writer)

    Assuming the date is 2022-08-19, then the filename will become
    "20220819_nickel-oxide_Ni_K.xdi".

    *{year}*, *{month}*, *{day}* describe the numerical, zero-padded
    year, month and day when the callback handles the start document
    for the plan. *{short_uid}* is the portion of the scan UID up to
    the first '-' character. *{manager_path}* will be the full path
    specified by the device labeled "beamline_manager" that has a
    ``local_storage.full_path`` signal. The remaining fields in the
    start document are also available, and will likely vary from plan
    to plan. Either consult the documentation for the plan being
    executed, or inspect the logs for the dictionary metadata at level
    ``logging.INFO`` when using an invalid placeholder.

    Parameters
    ==========
    fd
      Either an open file with write intent, or a Path or string with
      the file location. If *fd* is not already an open file, it will
      be created when the ``start()`` method is called.
    auto_directory
      If true, the current local storage directory will be prepended
      to *fd* if *fd* is not an open file object. The directory is
      determined from the
      :py:class:`~haven.instrument.beamline_manager.BeamlineManager`
      object.

    """

    fp: Optional[Union[str, Path]] = None
    column_names: Optional[Sequence[str]] = None
    start_time: dt.datetime = None
    stream_name: str = "primary"

    start_doc: Mapping = None
    descriptor_doc: Mapping = None

    _fd = None
    _fp_template: Optional[Union[str, Path]] = None
    _last_uid: str = ""
    _primary_uid: str
    _primary_descriptor: Mapping
    _secondary_uids: Sequence[str]

    def __init__(self, fd: Union[Path, str], *args, **kwargs):
        is_file_obj = hasattr(fd, "writable")
        if is_file_obj:
            # *fd* is an open file object
            # Make sure it is writable
            if fd.writable():
                log.debug(f"Found open, writable file: {fd}")
                self._fd = fd
            else:
                msg = f"No write intent on file: {fd}"
                log.error(msg)
                raise exceptions.FileNotWritable(msg)
        else:
            # Assume *fd* is a path to a file
            self._fp_template = Path(fd).expanduser()
            self.fp = self._fp_template
        return super().__init__(*args, **kwargs)

    @property
    def fd(self):
        """Retrieve the open writable file object for this writer."""
        if self._fd is None:
            log.debug(f"Opening file: {self.fp.resolve()}")
            self.fp.parent.mkdir(exist_ok=True, parents=True)
            self._fd = open(self.fp, mode="x")
        return self._fd

    def _path_metadata(self, doc={}):
        """Prepare the metadata for string formatting the output file path."""
        md = {
            "year": self.start_time.strftime("%Y"),
            "month": self.start_time.strftime("%m"),
            "day": self.start_time.strftime("%d"),
        }
        # Add a shortened version of the UID
        try:
            md["short_uid"] = doc["uid"].split("-")[0]
        except KeyError:
            pass
        # Add local storage directory
        try:
            manager_name = "beamline_manager.local_storage.full_path"
            md["manager_path"] = registry[manager_name].get(as_string=True)
        except exceptions.ComponentNotFound:
            log.warning(f"Could not find beamline manager {manager_name}")
        md.update(doc)
        return md

    def start(self, doc):
        self.start_time = dt.datetime.now().astimezone()
        self.column_names = None
        self._primary_uid = None
        self._secondary_uids = []
        # Format the file name based on metadata
        is_new_uid = doc.get("uid", "") != self._last_uid
        if self._fp_template is not None:
            # Make sure any previous runs are closed
            if is_new_uid:
                self.close()
            fp = str(self._fp_template)
            md = self._path_metadata(doc=doc)
            try:
                fp = fp.format(**md)
            except KeyError as e:
                msg = f"Could not find match key {e} in {fp}."
                log.error(msg)
                log.info(f"Metadata is: {md}")
                raise exceptions.XDIFilenameKeyNotFound(msg) from None
            fp = slugify(fp)
            self.fp = Path(fp)
        # Save the rest of the start doc so we can write the headers
        # when we get our first datum
        self.start_doc = doc
        self._last_uid = doc.get("uid", "")
        # Open the file, just to be sure we can
        self.fd

    def stop(self, doc):
        self.close()

    def descriptor(self, doc):
        if doc["name"] == self.stream_name:
            self._primary_uid = doc["uid"]
            self._primary_descriptor = doc
        else:
            self._secondary_uids.append(doc["uid"])
            return
        # Determine columns to use for storing events later
        if self.column_names is None:
            # Get column names from the scan hinted signals
            names = [val["fields"] for val in doc["hints"].values()]
            names = [n for sublist in names for n in sublist]
            # Sort column names so that energy-related fields are first
            names = sorted(names, key=lambda x: not x.startswith("energy"))
            self.column_names = names + ["time"]
            self.write_header(self.start_doc)
        # Save the descriptor doc for later
        self.descriptor_doc = doc

    def close(self):
        """Ensure any open files are closed."""
        try:
            self._fd.close()
        except ValueError:
            log.debug(f"Could not close file: {self.fd}")
        except AttributeError:
            log.debug(f"No file to close, skipping.")
        else:
            self._fd = None

    def write_header(self, doc):
        fd = self.fd
        # Write package version information
        versions = ["XDI/1.0"]
        versions += [f"{name}/{ver}" for name, ver in doc.get("versions", {}).items()]
        fd.write(f"# {' '.join(versions)}\n")
        # Column Names
        columns = [
            f"# Column.{num+1}: {name}\n" for num, name in enumerate(self.column_names)
        ]
        fd.write("".join(columns))
        # X-ray edge information
        edge_str = doc.get("edge", None)
        try:
            elem, edge = edge_str.split("_")
        except (AttributeError, ValueError):
            msg = f"Could not parse X-ray edge metadata: {edge_str}"
            warnings.warn(msg)
            log.warning(msg)
        else:
            fd.write(f"# Element.symbol: {elem}\n")
            fd.write(f"# Element.edge: {edge}\n")
        # Monochromator information
        try:
            d_spacing = doc["d_spacing"]
        except KeyError:
            pass
        else:
            fd.write(f"# Mono.d_spacing: {d_spacing}\n")
        # Facility information
        now = self.start_time
        fd.write(f"# Scan.start_time: {now.strftime('%Y-%m-%d %H:%M:%S%z')}\n")
        md_paths = [
            "facility.name",
            "facility.xray_source",
            "beamline.name",
            "beamline.pv_prefix",
        ]
        for path in md_paths:
            val = doc
            try:
                for piece in path.split("."):
                    val = val[piece]
                fd.write(f"# {path}: {val}\n")
            except KeyError:
                continue
        # Scan ID
        fd.write(f"# uid: {self.start_doc.get('uid', '')}\n")
        # Header end token
        fd.write("# -------------\n")

    def event(self, doc):
        """Save the data in tab-separated value, in order of
        ``self.column_names``.

        """
        # Ignore non-primary data streams
        if doc["descriptor"] in self._secondary_uids:
            return
        elif doc["descriptor"] != self._primary_uid:
            # We're getting data out of order, so we can't save to the file
            msg = (
                "No descriptor document available. "
                "The descriptor document should be passed to "
                f"{self}.descriptor() before providing event documents."
            )
            raise exceptions.DocumentNotFound(msg)
        # Read in and store the actual data
        data = doc["data"]
        fd = self.fd
        values = []
        for col in self.column_names:
            if col == "time":
                values.append(str(doc["time"]))
            else:
                try:
                    values.append(str(data[col]))
                except KeyError:
                    msg = f"Could not find signal {col} in datum."
                    log.warning(msg)
                    warnings.warn(msg)
        line = "\t".join(values)
        fd.write(line + "\n")


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
