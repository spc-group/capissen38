from haven.instrument import aps


def test_load_aps(sim_registry):
    aps.load_aps()
    aps_ = sim_registry.find(name="APS")
    assert hasattr(aps_, "current")


def test_read_attrs():
    device = aps.ApsMachine(name="Aps")
    read_attrs = ["current", "lifetime"]
    for attr in read_attrs:
        assert attr in device.read_attrs


def test_config_attrs():
    device = aps.ApsMachine(name="Aps")
    config_attrs = [
        "aps_cycle",
        "machine_status",
        "operating_mode",
        "shutter_permit",
        "fill_number",
        "orbit_correction",
        "global_feedback",
        "global_feedback_h",
        "global_feedback_v",
        "operator_messages",
    ]
    for attr in config_attrs:
        assert attr in device.configuration_attrs


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
