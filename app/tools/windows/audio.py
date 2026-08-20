from pycaw.pycaw import (
    AudioUtilities,
    IAudioEndpointVolume,
)
from comtypes import CLSCTX_ALL

from app.tools.base import Tool


def get_volume_interface():

    devices = AudioUtilities.GetSpeakers()

    if hasattr(devices, "EndpointVolume"):
        return devices.EndpointVolume

    interface = devices.Activate(
        IAudioEndpointVolume._iid_,
        CLSCTX_ALL,
        None,
    )

    return interface


class GetVolumeTool(Tool):

    @property
    def name(self):
        return "get_volume"

    @property
    def description(self):
        return "Get the current Windows speaker volume."

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self):

        volume = get_volume_interface()

        level = volume.GetMasterVolumeLevelScalar()

        muted = volume.GetMute()

        return {
            "success": True,
            "volume": round(level * 100),
            "muted": bool(muted),
        }


class SetVolumeTool(Tool):

    @property
    def name(self):
        return "set_volume"

    @property
    def description(self):
        return (
            "Set the Windows speaker volume "
            "between 0 and 100 percent."
        )

    @property
    def parameters(self):

        return {
            "type": "object",
            "properties": {
                "volume": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": (
                        "Volume percentage."
                    ),
                }
            },
            "required": ["volume"],
        }

    async def execute(
        self,
        volume: int,
    ):

        volume = max(
            0,
            min(100, int(volume)),
        )

        interface = get_volume_interface()

        interface.SetMasterVolumeLevelScalar(
            volume / 100,
            None,
        )

        return {
            "success": True,
            "volume": volume,
        }


class MuteTool(Tool):

    @property
    def name(self):
        return "mute"

    @property
    def description(self):
        return "Mute the Windows speaker output."

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self):

        interface = get_volume_interface()

        interface.SetMute(1, None)

        return {
            "success": True,
            "muted": True,
        }


class UnmuteTool(Tool):

    @property
    def name(self):
        return "unmute"

    @property
    def description(self):
        return "Unmute the Windows speaker output."

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self):

        interface = get_volume_interface()

        interface.SetMute(0, None)

        return {
            "success": True,
            "muted": False,
        }