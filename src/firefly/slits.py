import haven
from firefly import display


class SlitsDisplay(display.FireflyDisplay):
    caqtdm_ui_file = "/APSshare/epics/synApps_6_2_1/support/optics-R2-13-5//opticsApp/op/ui/autoconvert/4slitGraphic.ui"
    
    def ui_filename(self):
        return "slits.ui"

    def launch_caqtdm(self):
        device = haven.registry.find(self.macros()["DEVICE"])
        P, SLIT = device.prefix.split(":")[0:2]
        H = device.h.prefix.split(":")[1]
        V = device.v.prefix.split(":")[1]
        caqtdm_macros = {
            "P": f"{P}:",
            "SLIT": SLIT,
            "H": H,
            "V": V,
        }
        super().launch_caqtdm(macros=caqtdm_macros)
    
