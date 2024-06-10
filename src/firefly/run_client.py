import datetime as dt
import logging
from collections import OrderedDict
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
from qtpy.QtCore import Signal
from tiled import queries

from haven import exceptions
from haven.catalog import Catalog

log = logging.getLogger(__name__)


class DatabaseWorker:
    selected_runs: Sequence = []

    # Signals
    all_runs_changed = Signal(list)
    selected_runs_changed = Signal(list)
    distinct_fields_changed = Signal(dict)
    new_message = Signal(str, int)
    db_op_started = Signal()
    db_op_ended = Signal(list)  # (list of exceptions thrown)

    def __init__(self, catalog=None, *args, **kwargs):
        if catalog is None:
            catalog = Catalog()
        self.catalog = catalog
        super().__init__(*args, **kwargs)

    async def filtered_nodes(self, filters: Mapping):
        case_sensitive = False
        log.debug(f"Filtering nodes: {filters}")
        filter_params = [
            # (filter_name, query type, metadata key)
            ("user", queries.Regex, "proposal_users"),
            ("proposal", queries.Regex, "proposal_id"),
            ("esaf", queries.Regex, "esaf_id"),
            ("sample", queries.Regex, "sample_name"),
            # ('exit_status', queries.Regex, "exit_status"),
            ("plan", queries.Regex, "plan_name"),
            ("edge", queries.Regex, "edge"),
        ]
        # Apply filters
        runs = self.catalog
        for filter_name, Query, md_name in filter_params:
            val = filters.get(filter_name, "")
            if val != "":
                runs = await runs.search(
                    Query(md_name, val, case_sensitive=case_sensitive)
                )
        full_text = filters.get("full_text", "")
        if full_text != "":
            runs = await runs.search(
                queries.FullText(full_text, case_sensitive=case_sensitive)
            )
        return runs

    async def load_distinct_fields(self):
        """Get distinct metadata fields for filterable metadata.

        Emits
        =====
        distinct_fields_changed
          Emitted with the new dictionary of distinct metadata choices
          for each metadata key.

        """
        new_fields = {}
        target_fields = [
            "sample_name",
            "proposal_users",
            "proposal_id",
            "esaf_id",
            "sample_name",
            "plan_name",
            "edge",
        ]
        # Get fields from the database
        response = await self.catalog.distinct(*target_fields)
        # Build into a new dictionary
        for key, result in response["metadata"].items():
            field = key.split(".")[-1]
            new_fields[field] = [r["value"] for r in result]
        return new_fields

    async def load_all_runs(self, filters: Mapping = {}):
        all_runs = []
        nodes = await self.filtered_nodes(filters=filters)
        async for uid, node in nodes.items():
            # Get meta-data documents
            metadata = await node.metadata
            start_doc = metadata.get("start")
            if start_doc is None:
                log.debug(f"Skipping run with no start doc: {uid}")
                continue
            stop_doc = metadata.get("stop")
            if stop_doc is None:
                stop_doc = {}
            # Get a human-readable timestamp for the run
            timestamp = start_doc.get("time")
            if timestamp is None:
                run_datetime = ""
            else:
                run_datetime = dt.datetime.fromtimestamp(timestamp)
                run_datetime = run_datetime.strftime("%Y-%m-%d %H:%M:%S")
            # Get the X-ray edge scanned
            edge = start_doc.get("edge")
            E0 = start_doc.get("E0")
            E0_str = "" if E0 is None else str(E0)
            if edge and E0:
                edge_str = f"{edge} ({E0} eV)"
            elif edge:
                edge_str = edge
            elif E0:
                edge_str = E0_str
            else:
                edge_str = ""
            # Build the table item
            # Get sample data from: dd80f432-c849-4749-a8f3-bdeec6f9c1f0
            run_data = OrderedDict(
                plan_name=start_doc.get("plan_name", ""),
                sample_name=start_doc.get("sample_name", ""),
                edge=edge_str,
                E0=E0_str,
                exit_status=stop_doc.get("exit_status", ""),
                run_datetime=run_datetime,
                uid=uid,
                proposal_id=start_doc.get("proposal_id", ""),
                esaf_id=start_doc.get("esaf_id", ""),
                esaf_users=start_doc.get("esaf_users", ""),
            )
            all_runs.append(run_data)
        return all_runs

    async def signal_names(self, hinted_only: bool = False):
        """Get a list of valid signal names (data columns) for selected runs.

        Parameters
        ==========
        hinted_only
          If true, only signals with the kind="hinted" parameter get
          picked.

        """
        xsignals, ysignals = [], []
        for run in self.selected_runs:
            if hinted_only:
                xsig, ysig = await run.hints()
            else:
                df = await run.to_dataframe()
                xsig = ysig = df.columns
            xsignals.extend(xsig)
            ysignals.extend(ysig)
        # Remove duplicates
        xsignals = list(dict.fromkeys(xsignals))
        ysignals = list(dict.fromkeys(ysignals))
        return list(xsignals), list(ysignals)

    async def metadata(self):
        """Get all metadata for the selected runs in one big dictionary."""
        md = {}
        for run in self.selected_runs:
            md[run.uid] = await run.metadata
        return md

    async def load_selected_runs(self, uids):
        # Prepare the query for finding the runs
        uids = list(dict.fromkeys(uids))
        # Retrieve runs from the database
        runs = [await self.catalog[uid] for uid in uids]
        # runs = await asyncio.gather(*run_coros)
        self.selected_runs = runs

    async def images(self, signal):
        """Load the selected runs as 2D or 3D images suitable for plotting."""
        images = OrderedDict()
        for idx, run in enumerate(self.selected_runs):
            # Load datasets from the database
            try:
                image = await run[signal]
            except KeyError:
                log.warning(f"Signal {signal} not found in run {run}.")
            else:
                images[run.uid] = image
        return images

    async def all_signals(self, hinted_only=False):
        """Produce dataframe with all signals for each run.

        The keys of the dictionary are the labels for each curve, and
        the corresponding value is a pandas dataframe with the scan data.

        """
        xsignals, ysignals = await self.signal_names(hinted_only=hinted_only)
        # Build the dataframes
        dfs = OrderedDict()
        for run in self.selected_runs:
            # Get data from the database
            df = await run.to_dataframe(signals=xsignals + ysignals)
            dfs[run.uid] = df
        return dfs

    async def signals(
        self,
        x_signal,
        y_signal,
        r_signal=None,
        use_log=False,
        use_invert=False,
        use_grad=False,
    ) -> Mapping:
        """Produce a dictionary with the 1D datasets for plotting.

        The keys of the dictionary are the labels for each curve, and
        the corresponding value is a pandas dataset with the data for
        each signal.

        """
        # Check for sensible inputs
        use_reference = r_signal is not None
        if "" in [x_signal, y_signal] or (use_reference and r_signal == ""):
            msg = (
                f"Empty signal name requested: x={repr(x_signal)}, y={repr(y_signal)},"
                f" r={repr(r_signal)}"
            )
            log.debug(msg)
            raise exceptions.EmptySignalName(msg)
        signals = [x_signal, y_signal]
        if use_reference:
            signals.append(r_signal)
        # Remove duplicates
        signals = list(dict.fromkeys(signals).keys())
        # Build the dataframes
        dfs = OrderedDict()
        for run in self.selected_runs:
            # Get data from the database
            df = await run.to_dataframe(signals=signals)
            # Check for missing signals
            missing_x = x_signal not in df.columns
            missing_y = y_signal not in df.columns
            missing_r = r_signal not in df.columns
            if missing_x or missing_y or (use_reference and missing_r):
                log.warning(
                    "Could not find signals {x_signal}, {y_signal} and {r_signal}"
                )
                continue
            # Apply transformations
            if use_reference:
                df[y_signal] /= df[r_signal]
            if use_log:
                df[y_signal] = np.log(df[y_signal])
            if use_invert:
                df[y_signal] *= -1
            if use_grad:
                df[y_signal] = np.gradient(df[y_signal], df[x_signal])
            series = pd.Series(df[y_signal].values, index=df[x_signal].values)
            dfs[run.uid] = series
        return dfs


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
