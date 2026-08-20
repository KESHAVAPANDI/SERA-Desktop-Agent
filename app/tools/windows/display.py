import screen_brightness_control as sbc

from app.tools.base import Tool


class GetBrightnessTool(Tool):

    @property
    def name(self):
        return "get_brightness"

    @property
    def description(self):
        return "Get the current display brightness."

    @property
    def parameters(self):
        return {
            "type": "object",
            "properties": {},
        }

    async def execute(self):

        values = sbc.get_brightness()

        if not values:

            return {
                "success": False,
                "error": "Brightness unavailable.",
            }

        return {
            "success": True,
            "brightness": values[0],
        }


class SetBrightnessTool(Tool):

    @property
    def name(self):
        return "set_brightness"

    @property
    def description(self):
        return (
            "Set the display brightness "
            "between 0 and 100 percent."
        )

    @property
    def parameters(self):

        return {
            "type": "object",
            "properties": {
                "brightness": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": (
                        "Brightness percentage."
                    ),
                }
            },
            "required": ["brightness"],
        }

    async def execute(
        self,
        brightness: int,
    ):

        brightness = max(
            0,
            min(100, int(brightness)),
        )

        sbc.set_brightness(
            brightness
        )

        return {
            "success": True,
            "brightness": brightness,
        }