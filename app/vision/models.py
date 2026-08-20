from typing import Any
from pydantic import BaseModel, Field


class UIElement(BaseModel):
    """Represents an individual visual or interactive element on screen."""
    type: str = Field(description="Type of UI element, e.g., button, text, input, window, menu, tab, icon")
    text: str | None = Field(default=None, description="Visible text or label of the element")
    x: int | None = Field(default=None, description="Estimated X coordinate (pixels)")
    y: int | None = Field(default=None, description="Estimated Y coordinate (pixels)")
    width: int | None = Field(default=None, description="Estimated width (pixels)")
    height: int | None = Field(default=None, description="Estimated height (pixels)")
    confidence: float | None = Field(default=None, description="Perception confidence 0.0-1.0")


class ScreenContext(BaseModel):
    """Structured perception data describing the active screen state."""
    timestamp: float = Field(description="Timestamp when screen was captured")
    screen_hash: str = Field(description="Perceptual/MD5 hash of the screen image")
    width: int = Field(description="Captured screen width")
    height: int = Field(description="Captured screen height")
    application: str = Field(default="Unknown", description="Primary active application detected")
    window_title: str = Field(default="Unknown", description="Title of the active window")
    summary: str = Field(description="Concise description of what is visible on screen")
    visible_text: list[str] = Field(default_factory=list, description="Key visible text phrases or paragraphs")
    elements: list[UIElement] = Field(default_factory=list, description="Key visual and interactive UI elements")

    def format_voice_summary(self, user_query: str = "") -> str:
        """Formats a natural, concise spoken summary for voice responses."""
        lower_q = user_query.lower()
        if "error" in lower_q:
            # Check if any visible text contains error keywords
            error_lines = [t for t in self.visible_text if any(k in t.lower() for k in ["error", "exception", "failed", "warning", "traceback"])]
            if error_lines:
                return f"I see an error on your screen: {error_lines[0]}."
            return f"I don't see any obvious errors displayed in {self.application}."

        if "app" in lower_q or "application" in lower_q or "window" in lower_q:
            return f"You currently have {self.application} open, with the window title '{self.window_title}'."

        if "text" in lower_q or "read" in lower_q:
            if self.visible_text:
                sample_text = " ".join(self.visible_text[:3])
                return f"On your screen in {self.application}, I can see: {sample_text}."
            return f"I can see {self.application}, but no clear readable text blocks were extracted."

        # Default general screen description
        return f"On your screen, {self.application} is active. {self.summary}"
