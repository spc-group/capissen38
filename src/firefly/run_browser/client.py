import asyncio
import datetime as dt
import logging
import warnings
from collections import ChainMap, OrderedDict
from functools import partial
from typing import Mapping, Sequence

import numpy as np
import pandas as pd
from qasync import asyncSlot
from tiled import queries

from haven import exceptions
from haven.catalog import Catalog, run_in_executor

log = logging.getLogger(__name__)


class DatabaseWorker:
    selected_runs: Sequence = []
    catalog: Catalog = None

    def __init__(self, tiled_client, *args, **kwargs):
        self.client = tiled_client
        super().__init__(*args, **kwargs)

    @asyncSlot(str)
    async def change_catalog(self, catalog_name: str):
        """Change the catalog being used for pulling data.

        *catalog_name* should be an entry in *worker.tiled_client()*.
        """

        def get_catalog(name):
            return Catalog(self.client[catalog_name])

        loop = asyncio.get_running_loop()
        self.catalog = await loop.run_in_executor(None, get_catalog, catalog_name)

    @run_in_executor
    def catalog_names(self):
        return list(self.client.keys())

    async def stream_names(self):
        awaitables = [scan.stream_names() for scan in self.selected_runs]
        all_streams = await asyncio.gather(*awaitables)
        # Flatten the lists
        streams = [stream for streams in all_streams for stream in streams]
        return list(set(streams))

    async def data_keys(self, stream: str):
        aws = [run.data_keys(stream=stream) for run in self.selected_runs]
        keys = await asyncio.gather(*aws)
        keys = ChainMap(*keys)
        keys["seq_num"] = {
            "dtype": "number",
            "dtype_numpy": "<i8",
            "precision": 0,
            "shape": [],
        }
        return keys

    async def data_frames(self, stream: str) -> dict:
        """Return the internal dataframes for selected runs as {uid: dataframe}."""
        aws = (run.data(stream=stream) for run in self.selected_runs)
        dfs = await asyncio.gather(*aws)
        dfs = {run.uid: df for run, df in zip(self.selected_runs, dfs)}
        return dfs

    async def filtered_nodes(self, filters: Mapping):
        case_sensitive = False
        log.debug(f"Filtering nodes: {filters}")
        filter_params = {
            # filter_name: (query type, metadata key)
            "plan": (queries.Eq, "start.plan_name"),
            "sample": (queries.Contains, "start.sample_name"),
            "formula": (queries.Contains, "start.sample_formula"),
            "edge": (queries.Contains, "start.edge"),
            "exit_status": (queries.Eq, "stop.exit_status"),
            "user": (queries.Contains, "start.proposal_users"),
            "proposal": (queries.Eq, "start.proposal_id"),
            "esaf": (queries.Eq, "start.esaf_id"),
            "beamline": (queries.Eq, "start.beamline_id"),
            "before": (partial(queries.Comparison, "le"), "end.time"),
            "after": (partial(queries.Comparison, "ge"), "start.time"),
            "full_text": (queries.FullText, ""),
            "standards_only": (queries.Eq, "start.is_standard"),
        }
        # Apply filters
        runs = self.catalog
        for filter_name, filter_value in filters.items():
            if filter_name not in filter_params:
                continue
            Query, md_name = filter_params[filter_name]
            if Query is queries.FullText:
                runs = await runs.search(Query(filter_value), case_sensitive=False)
            else:
                runs = await runs.search(Query(md_name, filter_value))
        return runs

    async def load_distinct_fields(self):
        """Get distinct metadata fields for filterable metadata."""
        new_fields = {}
        target_fields = [
            "start.plan_name",
            "start.sample_name",
            "start.sample_formula",
            "start.edge",
            "stop.exit_status",
            "start.proposal_id",
            "start.esaf_id",
            "start.beamline_id",
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

    async def hints(self, stream: str = "primary") -> tuple[list, list]:
        """Get hints for this stream, as two lists.

        (*independent_hints*, *dependent_hints*)

        *independent_hints* are those operated by the experiment,
         while *dependent_hints* are those measured as a result.
        """
        aws = [run.hints(stream) for run in self.selected_runs]
        all_hints = await asyncio.gather(*aws)
        # Flatten arrays
        ihints, dhints = zip(*all_hints)
        ihints = [hint for hints in ihints for hint in hints]
        dhints = [hint for hints in dhints for hint in hints]
        return ihints, dhints

    async def signal_names(self, stream: str, *, hinted_only: bool = False):
        """Get a list of valid signal names (data columns) for selected runs.

        Parameters
        ==========
        stream
          The Tiled stream name to fetch.
        hinted_only
          If true, only signals with the kind="hinted" parameter get
          picked.

        """
        xsignals, ysignals = [], []
        for run in self.selected_runs:
            if hinted_only:
                xsig, ysig = await run.hints(stream=stream)
            else:
                df = await run.data(stream=stream)
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
        if len(self.selected_runs) == 0:
            warnings.warn("No runs selected, metadata will be empty.")
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
        return runs

    async def images(self, signal: str, stream: str):
        """Load the selected runs as 2D or 3D images suitable for plotting."""
        images = OrderedDict()
        for idx, run in enumerate(self.selected_runs):
            # Load datasets from the database
            try:
                image = await run.__getitem__(signal, stream=stream)
            except KeyError as exc:
                log.exception(exc)
            else:
                images[run.uid] = image
        return images

    async def all_signals(self, stream: str, *, hinted_only=False) -> dict:
        """Produce dataframes with all signals for each run.

        The keys of the dictionary are the labels for each curve, and
        the corresponding value is a pandas dataframe with the scan data.

        """
        xsignals, ysignals = await self.signal_names(
            hinted_only=hinted_only, stream=stream
        )
        # Build the dataframes
        dfs = OrderedDict()
        for run in self.selected_runs:
            # Get data from the database
            df = await run.data(signals=xsignals + ysignals, stream=stream)
            dfs[run.uid] = df
        return dfs

    async def dataset(
        self,
        dataset_name: str,
        *,
        stream: str,
        uids: Sequence[str] | None = None,
    ) -> Mapping:
        """Produce a dictionary with the n-dimensional datasets for plotting.

        The keys of the dictionary are the UIDs for each scan, and
        the corresponding value is a pandas dataset with the data for
        each signal.

        Parameters
        ==========
        uids
          If not ``None``, only runs with UIDs listed in this
          parameter will be included.

        """
        # Build the dataframes
        arrays = OrderedDict()
        for run in self.selected_runs:
            # Get data from the database
            arr = await run.external_dataset(dataset_name, stream=stream)
            arrays[run.uid] = arr
        return arrays

    async def signals(
        self,
        x_signal,
        y_signal,
        r_signal=None,
        *,
        stream: str,
        use_log=False,
        use_invert=False,
        use_grad=False,
        uids: Sequence[str] | None = None,
    ) -> Mapping:
        """Produce a dictionary with the 1D datasets for plotting.

        The keys of the dictionary are the labels for each curve, and
        the corresponding value is a pandas dataset with the data for
        each signal.

        Parameters
        ==========
        uids
          If not ``None``, only runs with UIDs listed in this
          parameter will be included.

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
            # Check that the UID matches
            if uids is not None and run.uid not in uids:
                break
            # Get data from the database
            df = await run.data(signals=signals, stream=stream)
            # Check for missing signals
            missing_x = x_signal not in df.columns and df.index.name != x_signal
            missing_y = y_signal not in df.columns
            missing_r = r_signal not in df.columns
            if missing_x or missing_y or (use_reference and missing_r):
                log.warning(
                    f"Could not find signals {x_signal=}, {y_signal=} and {r_signal=} in {df.columns}"
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

    async def export_runs(self, filenames: Sequence[str], formats: Sequence[str]):
        for filename, run, format in zip(filenames, self.selected_runs, formats):
            await run.export(filename, format=format)


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
