import numpy as np
import pandas as pd
import pytest
from tiled import queries

from haven.catalog import CatalogScan, unsnake


@pytest.fixture()
def scan(tiled_client):
    uid = "7d1daf1d-60c7-4aa7-a668-d1cd97e5335f"
    return CatalogScan(tiled_client[uid])


@pytest.fixture()
def grid_scan(tiled_client):
    uid = "85573831-f4b4-4f64-b613-a6007bf03a8d"
    return CatalogScan(tiled_client[uid])


def test_unsnake():
    # Make a snaked array
    arr = np.arange(27).reshape((3, 3, 3))
    snaked = np.copy(arr)
    snaked[::2] = snaked[::2, ::-1]
    snaked[:, ::2] = snaked[:, ::2, ::-1]
    # Do the unsnaking
    unsnaked = unsnake(snaked, [False, True, True])
    # Check the result
    np.testing.assert_equal(arr, unsnaked)


@pytest.mark.asyncio
async def test_client_fixture(tiled_client):
    """Does the client fixture load without stalling the test runner?"""


@pytest.mark.asyncio
async def test_load_scan(catalog):
    """Check that scans can be loaded from the catalog."""
    uid = "7d1daf1d-60c7-4aa7-a668-d1cd97e5335f"
    scan = await catalog[uid]
    assert isinstance(scan, CatalogScan)


@pytest.mark.asyncio
async def test_dataframe(scan):
    """Check that the catalogscan can produce a pandas dataframe."""
    df = await scan.to_dataframe()
    assert isinstance(df, pd.DataFrame)


@pytest.mark.asyncio
async def test_load_nd_data(grid_scan):
    """Check that the catalog scan can convert e.g. grid_scan results."""
    arr = await grid_scan["It_net_counts"]
    assert arr.ndim == 2
    assert arr.shape == (5, 21)


@pytest.mark.asyncio
async def test_distinct(catalog, tiled_client):
    distinct = tiled_client.distinct("plan_name")
    assert await catalog.distinct("plan_name") == distinct


@pytest.mark.asyncio
async def test_search(catalog, tiled_client):
    """Make sure we can query to database properly."""
    query = queries.Regex("plan_name", "xafs_scan")
    expected = tiled_client.search(query)
    response = await catalog.search(query)
    assert len(expected) == await response.__len__()


@pytest.mark.asyncio
async def test_values(catalog, tiled_client):
    """Get the individual scans in the catalog."""
    expected = [uid for uid in tiled_client.keys()]
    response = [val.uid async for val in catalog.values()]
    assert expected == response


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
