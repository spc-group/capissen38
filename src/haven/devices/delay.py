import enum
from typing import Type

from ophyd_async.core import (
    SignalRW,
    StandardReadable,
    StandardReadableFormat,
    StrictEnum,
    SubsetEnum,
    T,
)
from ophyd_async.epics.core import epics_signal_r, epics_signal_rw, epics_signal_x


def epics_signal_io(datatype: Type[T], prefix: str, name: str = "") -> SignalRW[T]:
    """Create a `SignalRW` backed by 2 EPICS PVs.

    The write PV gets an extra 'O' and the read PV gets an extra 'I'
    added to the prefix.

    Parameters
    ----------
    datatype:
        Check that the PV is of this type
    prefix:
        The PV to read and monitor

    """
    return epics_signal_rw(
        datatype, read_pv=f"{prefix}I", write_pv=f"{prefix}O", name=name
    )


class DG645Channel(StandardReadable):
    class Reference(StrictEnum):
        T0 = "T0"
        A = "A"
        B = "B"
        C = "C"
        D = "D"
        E = "E"
        F = "F"
        G = "G"
        H = "H"

    def __init__(self, prefix: str, name: str = ""):
        with self.add_children_as_readables(StandardReadableFormat.CONFIG_SIGNAL):
            self.reference = epics_signal_io(self.Reference, f"{prefix}ReferenceM")
            self.delay = epics_signal_io(float, f"{prefix}DelayA")
        super().__init__(name=name)


class DG645Output(StandardReadable):
    class Polarity(StrictEnum):
        NEG = "NEG"
        POS = "POS"

    def __init__(self, prefix: str, name: str = ""):
        with self.add_children_as_readables(StandardReadableFormat.CONFIG_SIGNAL):
            self.polarity = epics_signal_io(self.Polarity, f"{prefix}OutputPolarityB")
            self.amplitude = epics_signal_io(float, f"{prefix}OutputAmpA")
            self.offset = epics_signal_io(float, f"{prefix}OutputOffsetA")
        self.output_mode_ttl = epics_signal_x(f"{prefix}OutputModeTtlSS.PROC")
        self.output_mode_nim = epics_signal_x(f"{prefix}OutputModeNimSS.PROC")
        super().__init__(name=name)


class DG645DelayOutput(DG645Output):
    def __init__(self, prefix: str, name: str = ""):
        with self.add_children_as_readables(StandardReadableFormat.CONFIG_SIGNAL):
            self.trigger_prescale = epics_signal_io(int, f"{prefix}TriggerPrescaleL")
            self.trigger_phase = epics_signal_io(int, f"{prefix}TriggerPhaseL")
        super().__init__(prefix=prefix, name=name)


class DG645Delay(StandardReadable):

    class BaudRate(SubsetEnum):
        B4800 = "4800"
        B9600 = "9600"
        B19200 = "19200"
        B38400 = "38400"
        B57600 = "57600"
        B115200 = "115200"

    class TriggerSource(SubsetEnum):
        INTERNAL = "Internal"
        EXT_RISING_EDGE = "Ext rising edge"
        EXT_FALLING_EDGE = "Ext falling edge"
        SS_EXT_RISE_EDGE = "SS ext rise edge"
        SS_EXT_FALL_EDGE = "SS ext fall edge"
        SINGLE_SHOT = "Single shot"
        LINE = "Line"

    class TriggerInhibit(SubsetEnum):
        OFF = "Off"
        TRIGGERS = "Triggers"
        AB = "AB"
        AB_CD = "AB,CD"
        AB_CD_EF = "AB,CD,EF"
        AB_CD_EF_GH = "AB,CD,EF,GH"

    class BurstConfig(SubsetEnum):
        ALL_CYCLES = "All Cycles"
        FIRST_CYCLE = "1st Cycle"

    def __init__(self, prefix: str, name: str = ""):
        # Conventional signals
        with self.add_children_as_readables(StandardReadableFormat.CONFIG_SIGNAL):
            self.label = epics_signal_rw(str, f"{prefix}Label")
            self.device_id = epics_signal_r(str, f"{prefix}IdentSI")
        self.status = epics_signal_r(str, f"{prefix}StatusSI")
        self.clear_error = epics_signal_x(f"{prefix}StatusClearBO")
        self.goto_remote = epics_signal_x(f"{prefix}GotoRemoteBO")
        self.goto_local = epics_signal_x(f"{prefix}GotoLocalBO")
        self.reset = epics_signal_x(f"{prefix}ResetBO")
        self.status_checking = epics_signal_rw(bool, f"{prefix}StatusCheckingBO")
        self.reset_serial = epics_signal_x(f"{prefix}IfaceSerialResetBO")
        self.serial_state = epics_signal_io(bool, f"{prefix}IfaceSerialStateB")
        self.serial_baud = epics_signal_io(self.BaudRate, f"{prefix}IfaceSerialBaudM")
        self.reset_gpib = epics_signal_x(f"{prefix}IfaceGpibResetBO")
        self.gpib_state = epics_signal_io(bool, f"{prefix}IfaceGpibStateB")
        self.gpib_address = epics_signal_io(int, f"{prefix}IfaceGpibAddrL")
        self.reset_lan = epics_signal_x(f"{prefix}IfaceLanResetBO")
        self.mac_address = epics_signal_r(str, f"{prefix}IfaceMacAddrSI")
        self.lan_state = epics_signal_io(bool, f"{prefix}IfaceLanStateB")
        self.dhcp_state = epics_signal_io(bool, f"{prefix}IfaceDhcpStateB")
        self.autoip_state = epics_signal_io(bool, f"{prefix}IfaceAutoIpStateB")
        self.static_ip_state = epics_signal_io(bool, f"{prefix}IfaceStaticIpStateB")
        self.bare_socket_state = epics_signal_io(bool, f"{prefix}IfaceBareSocketStateB")
        self.telnet_state = epics_signal_io(bool, f"{prefix}IfaceTelnetStateB")
        self.vxi11_state = epics_signal_io(bool, f"{prefix}IfaceVxiStateB")
        self.ip_address = epics_signal_io(str, f"{prefix}IfaceIpAddrS")
        self.network_mask = epics_signal_io(str, f"{prefix}IfaceNetMaskS")
        self.gateway = epics_signal_io(str, f"{prefix}IfaceGatewayS")
        # Individual delay channels
        with self.add_children_as_readables():
            self.channel_A = DG645Channel(f"{prefix}A")
            self.channel_B = DG645Channel(f"{prefix}B")
            self.channel_C = DG645Channel(f"{prefix}C")
            self.channel_D = DG645Channel(f"{prefix}D")
            self.channel_E = DG645Channel(f"{prefix}E")
            self.channel_F = DG645Channel(f"{prefix}F")
            self.channel_G = DG645Channel(f"{prefix}G")
            self.channel_H = DG645Channel(f"{prefix}H")
        # 2-channel delay outputs
        with self.add_children_as_readables():
            self.output_T0 = DG645Output(f"{prefix}T0")
            self.output_AB = DG645DelayOutput(f"{prefix}AB")
            self.output_CD = DG645DelayOutput(f"{prefix}CD")
            self.output_EF = DG645DelayOutput(f"{prefix}EF")
            self.output_GH = DG645DelayOutput(f"{prefix}GH")
        # Trigger control
        with self.add_children_as_readables(StandardReadableFormat.CONFIG_SIGNAL):
            self.trigger_source = epics_signal_io(
                self.TriggerSource,
                f"{prefix}TriggerSourceM",
            )
            self.trigger_inhibit = epics_signal_io(
                self.TriggerInhibit, f"{prefix}TriggerInhibitM"
            )
            self.trigger_level = epics_signal_io(float, f"{prefix}TriggerLevelA")
            self.trigger_rate = epics_signal_io(float, f"{prefix}TriggerRateA")
            self.trigger_advanced_mode = epics_signal_io(
                bool, f"{prefix}TriggerAdvancedModeB"
            )
            self.trigger_holdoff = epics_signal_io(float, f"{prefix}TriggerHoldoffA")
            self.trigger_prescale = epics_signal_io(int, f"{prefix}TriggerPrescaleL")
        # Burst settings
        with self.add_children_as_readables(StandardReadableFormat.CONFIG_SIGNAL):
            self.burst_mode = epics_signal_io(bool, f"{prefix}BurstModeB")
            self.burst_count = epics_signal_io(int, f"{prefix}BurstCountL")
            self.burst_config = epics_signal_io(
                self.BurstConfig, f"{prefix}BurstConfigB"
            )
            self.burst_delay = epics_signal_io(float, f"{prefix}BurstDelayA")
            self.burst_period = epics_signal_io(float, f"{prefix}BurstPeriodA")
        super().__init__(name=name)


# -----------------------------------------------------------------------------
# :author:    Mark Wolfman
# :email:     wolfman@anl.gov
# :copyright: Copyright © 2024, UChicago Argonne, LLC
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
