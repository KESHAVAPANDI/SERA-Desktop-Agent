import asyncio
from app.core.runtime import SERARuntime


class SERA:
    """SERA Voice Assistant entrypoint facade."""

    def __init__(self, config_path: str | None = None):
        self.runtime = SERARuntime(config_path=config_path)

    @property
    def state(self):
        return self.runtime.state

    @property
    def events(self):
        return self.runtime.events

    @property
    def tools(self):
        return self.runtime.tools

    @property
    def router(self):
        return self.runtime.router

    @property
    def agent(self):
        return self.runtime.agent

    async def process(self, text: str) -> str:
        """Processes a single text turn."""
        return await self.runtime.process_text(text)

    async def run(self) -> None:
        """Runs the voice loop."""
        await self.runtime.run()