from firefly.slits import SlitsDisplay

# from haven.instrument import mirrors


class KBMirrorsDisplay(SlitsDisplay):
    @property
    def caqtdm_ui_file(self):
        # Go up the class list until we find a class that is recognized
        if self.device.horiz.bendable or self.device.vert.bendable:
            ui_file = "/net/s25data/xorApps/ui/KB_mirrors_and_benders.ui"
        else:
            ui_file = "/net/s25data/xorApps/ui/KB_mirrors.ui"
        return ui_file

    def ui_filename(self):
        return "kb_mirrors.ui"

    def customize_ui(self):
        # Enable/disable bender controls
        horiz = self.device.horiz
        self.ui.horizontal_upstream_display.setEnabled(horiz.bendable)
        self.ui.horizontal_downstream_display.setEnabled(horiz.bendable)
        vert = self.device.vert
        self.ui.vertical_upstream_display.setEnabled(vert.bendable)
        self.ui.vertical_downstream_display.setEnabled(vert.bendable)

    def launch_caqtdm(self):
        # Sort out the prefix from the slit designator
        prefix = self.device.prefix.strip(":")
        pieces = prefix.split(":")
        # Build the macros for the caQtDM panels
        P = ":".join(pieces[:-1])
        P = f"{P}:"
        KB = pieces[-1]
        KBH = self.device.horiz.prefix.replace(P, "").strip(":")
        KBV = self.device.vert.prefix.replace(P, "").strip(":")

        def suffix(signal):
            return signal.prefix.split(":")[-1]

        caqtdm_macros = {
            "P": f"{P}",
            "PM": P,
            "KB": KB,
            "KBH": KBH,
            "KBV": KBV,
            # Macros for the real motors
            "KBHUS": suffix(self.device.horiz.upstream),
            "KBHDS": suffix(self.device.horiz.downstream),
            "KBVUS": suffix(self.device.vert.upstream),
            "KBVDS": suffix(self.device.vert.downstream),
            # Macros for the transform records
            "KB1": KBH.replace(":", ""),
            "KB2": KBV.replace(":", ""),
        }
        # Macros for each mirror's bender motors
        horiz = self.device.horiz
        if horiz.bendable:
            caqtdm_macros.update(
                {
                    "HBUS": suffix(horiz.bender_upstream),
                    "HBDS": suffix(horiz.bender_downstream),
                }
            )
        vert = self.device.vert
        if vert.bendable:
            caqtdm_macros.update(
                {
                    "VBUS": suffix(vert.bender_upstream),
                    "VBDS": suffix(vert.bender_downstream),
                }
            )
        # Launch the caQtDM panel
        super(SlitsDisplay, self).launch_caqtdm(macros=caqtdm_macros)


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
