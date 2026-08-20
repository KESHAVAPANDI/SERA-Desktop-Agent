import re


class LocalIntentRouter:

    def detect(self, text: str):
        return self.route(text)

    def route(self, text: str):
        text = text.lower().strip()

        # Brightness
        match = re.search(
            r"(?:brightness|screen brightness)"
            r".*?(\d{1,3})\s*%?",
            text,
        )

        if match:

            value = int(
                match.group(1)
            )

            return {
                "tool": "set_brightness",
                "arguments": {
                    "brightness": value
                },
            }

        # Volume
        match = re.search(
            r"(?:volume|sound)"
            r".*?(\d{1,3})\s*%?",
            text,
        )

        if match:

            value = int(
                match.group(1)
            )

            return {
                "tool": "set_volume",
                "arguments": {
                    "volume": value
                },
            }

        # Mute
        if (
            "mute" in text
            and "unmute" not in text
        ):

            return {
                "tool": "mute",
                "arguments": {},
            }

        # Unmute
        if "unmute" in text:

            return {
                "tool": "unmute",
                "arguments": {},
            }

        return None