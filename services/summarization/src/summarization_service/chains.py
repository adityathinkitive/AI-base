import asyncio
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from aibase.prompts import PromptRegistry
from aibase.providers.llm import LLMMessage, LLMPort

PROMPTS = PromptRegistry(Path(__file__).parent / "prompts")
NoteFormat = Literal["general", "soap"]
CHUNK_CHARS = 6000
MAX_PARALLEL = 4


class Summary(BaseModel):
    summary: str
    chunks: int
    prompts: list[str]


def split(text: str, size: int = CHUNK_CHARS) -> list[str]:
    paragraphs, chunks, current = text.split("\n"), [], ""
    for para in paragraphs:
        if current and len(current) + len(para) > size:
            chunks.append(current)
            current = ""
        current += para + "\n"
    if current.strip():
        chunks.append(current)
    return chunks


async def summarize(llm: LLMPort, text: str, note_format: NoteFormat = "general") -> Summary:
    chunks = split(text)
    gate = asyncio.Semaphore(MAX_PARALLEL)  # bound provider concurrency

    async def map_one(chunk: str) -> str:
        async with gate:
            prompt = PROMPTS.render("map", text=chunk)
            return (await llm.generate([LLMMessage(role="user", content=prompt.text)])).text

    partials = await asyncio.gather(*(map_one(c) for c in chunks))
    map_tag = PROMPTS.render("map", text="").tag
    if len(partials) == 1 and note_format == "general":
        return Summary(summary=partials[0], chunks=1, prompts=[map_tag])
    reduce_prompt = PROMPTS.render(
        "reduce", partials=partials, format=note_format, format_name=note_format.upper()
    )
    final = await llm.generate([LLMMessage(role="user", content=reduce_prompt.text)])
    return Summary(summary=final.text, chunks=len(chunks), prompts=[map_tag, reduce_prompt.tag])
