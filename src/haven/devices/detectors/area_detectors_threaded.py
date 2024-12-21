from ophyd import DetectorBase as OphydDetectorBase

from .flyer_threaded import FlyerMixin


class DetectorBase(FlyerMixin, OphydDetectorBase):

    _default_read_attrs = ()
    _default_configuration_attrs = ("cam", "hdf")

    def __init__(self, *args, description=None, **kwargs):
        super().__init__(*args, **kwargs)
        if description is None:
            description = self.name
        self.description = description

    @property
    def default_time_signal(self):
        return self.cam.acquire_time

    @property
    def drv(self):
        """Compatibility with ophyd-async devices.

        Ophyd-async area detectors define `drv` as a child device with
        signals for controlling the detector. Building interfaces
        around these devices is easier if they share common signal
        paths.

        """
        return self.cam
