from bluesky import RunEngine as BlueskyRunEngine
import databroker

from ._iconfig import load_config


class RunEngine(BlueskyRunEngine):
    def __init__(self, *args, connect_databroker=True, **kwargs):
        super().__init__(*args, **kwargs)
        if connect_databroker:
            catalog_name = load_config()["database"]["databroker"]["catalog"]
            catalog = databroker.catalog[catalog_name]
            self.subscribe(catalog.v1.insert)
