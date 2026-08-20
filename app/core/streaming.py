import re
from typing import AsyncIterator, Iterator


class SentenceBuffer:
    """Buffers streamed tokens from an LLM and emits natural, speakable sentences or phrases.

    Avoids micro-fragmentation by enforcing minimum phrase length before splitting on boundaries.
    """

    def __init__(self, min_words: int = 4, max_buffer_chars: int = 250):
        self.min_words = min_words
        self.max_buffer_chars = max_buffer_chars
        self._buffer = ""
        # Strong sentence terminators
        self._strong_term_re = re.compile(r'([.!?\n]+(?:\s+|$))')
        # Secondary clause terminators (used when buffer has accumulated enough words)
        self._clause_term_re = re.compile(r'([;:]+(?:\s+|$)|,\s+)')

    def add_token(self, token: str) -> list[str]:
        """Adds a token to the buffer and returns any completed sentences/phrases."""
        if not token:
            return []

        self._buffer += token
        ready_sentences = []

        while True:
            sentence = self._extract_next_sentence()
            if sentence:
                ready_sentences.append(sentence)
            else:
                break

        return ready_sentences

    def flush(self) -> list[str]:
        """Flushes and returns any remaining text in the buffer."""
        remaining = self._buffer.strip()
        self._buffer = ""
        if remaining:
            return [remaining]
        return []

    def _extract_next_sentence(self) -> str | None:
        # 1. Look for strong terminators (. ! ? \n)
        match = self._strong_term_re.search(self._buffer)
        if match:
            idx = match.end()
            candidate = self._buffer[:idx].strip()
            # Ensure candidate has enough words or looks like a full short sentence
            words = candidate.split()
            if len(words) >= self.min_words or (len(words) >= 1 and any(candidate.endswith(p) for p in [".", "!", "?"])):
                self._buffer = self._buffer[idx:].lstrip()
                return candidate

        # 2. Look for clause terminators if buffer is getting long
        words_in_buf = self._buffer.split()
        if len(words_in_buf) >= self.min_words * 2 or len(self._buffer) >= self.max_buffer_chars:
            clause_match = self._clause_term_re.search(self._buffer)
            if clause_match:
                idx = clause_match.end()
                candidate = self._buffer[:idx].strip()
                self._buffer = self._buffer[idx:].lstrip()
                return candidate

        return None


async def stream_sentences(
    token_stream: AsyncIterator[str],
    min_words: int = 4,
    max_buffer_chars: int = 250,
) -> AsyncIterator[str]:
    """Async generator consuming an async token stream and yielding complete sentences."""
    buffer = SentenceBuffer(min_words=min_words, max_buffer_chars=max_buffer_chars)
    async for token in token_stream:
        sentences = buffer.add_token(token)
        for s in sentences:
            if s.strip():
                yield s.strip()

    for s in buffer.flush():
        if s.strip():
            yield s.strip()
