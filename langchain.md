# Using Websearch API As LangChain Tools

This guide shows how to wrap this project's HTTP API as LangChain tools and use those tools with OpenAI through LangChain.

The examples use:

- `POST /api/v1/search` to discover search results.
- `POST /api/v1/extract` to fetch a URL and return cleaned `text` and `markdown`.
- A composed tool that searches first, then extracts content from the top result URLs.

## Prerequisites

Start the Websearch API locally:

```bash
mise run serve
```

Or run the equivalent command directly:

```bash
uv run uvicorn websearch_api.main:app --host 0.0.0.0 --port 8000 --reload
```

Install the example dependencies in the Python environment where you will run the examples:

```bash
pip install langchain langchain-core langchain-openai httpx pydantic
```

Set your OpenAI API key:

```bash
export OPENAI_API_KEY="sk-..."
```

All examples use this base URL:

```python
WEBSEARCH_API_BASE_URL = "http://127.0.0.1:8000/api/v1"
```

## Example 1: `/search` As An OpenAI-Backed LangChain Tool

Save this as `search_tool_example.py` and run it while the Websearch API service is running.

```python
from __future__ import annotations

import json
from typing import Literal

import httpx
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


WEBSEARCH_API_BASE_URL = "http://127.0.0.1:8000/api/v1"


class WebSearchInput(BaseModel):
    query: str = Field(..., description="Search query to send to Websearch API.")
    max_results: int = Field(default=5, ge=1, le=100)
    provider: Literal["brave", "duckduckgo"] = Field(default="brave")


@tool(args_schema=WebSearchInput)
def web_search(query: str, max_results: int = 5, provider: str = "brave") -> str:
    """Use this tool when you need fresh web search results for a question, topic, company, person, documentation page, or current web fact. It returns JSON with ranked results containing title, URL, snippet, rank, and source. Use `brave` by default; use `duckduckgo` only when explicitly requested."""
    response = httpx.post(
        f"{WEBSEARCH_API_BASE_URL}/search",
        json={
            "query": query,
            "max_results": max_results,
            "provider": provider,
        },
        timeout=30.0,
    )
    response.raise_for_status()
    payload = response.json()

    compact_results = [
        {
            "rank": item["rank"],
            "title": item["title"],
            "url": item["url"],
            "snippet": item.get("snippet"),
            "source": item["source"],
        }
        for item in payload["results"]
    ]

    return json.dumps(
        {
            "query": payload["query"],
            "provider": payload["provider"],
            "result_count": payload["result_count"],
            "results": compact_results,
        },
        ensure_ascii=False,
    )


def build_agent() -> AgentExecutor:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    tools = [web_search]

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a careful web research assistant. Use the web_search tool "
                "whenever the user asks for web results, URLs, sources, or current "
                "information. Cite URLs from the tool output in your final answer.",
            ),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )

    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True)


if __name__ == "__main__":
    agent_executor = build_agent()
    response = agent_executor.invoke(
        {
            "input": (
                "Search the web for FastAPI background task documentation. "
                "Return the 3 best results with a short explanation and URLs."
            )
        }
    )
    print(response["output"])
```

## Example 2: `/extract` As An OpenAI-Backed LangChain Tool

Save this as `extract_tool_example.py` and run it while the Websearch API service is running.

```python
from __future__ import annotations

import json

import httpx
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import AnyHttpUrl, BaseModel, Field


WEBSEARCH_API_BASE_URL = "http://127.0.0.1:8000/api/v1"


class WebExtractInput(BaseModel):
    url: AnyHttpUrl = Field(..., description="Absolute http(s) URL to extract.")
    wait_for_selector: str | None = Field(
        default=None,
        description="Optional CSS selector to wait for before extracting content.",
    )
    include_html: bool = Field(default=False)
    include_links: bool = Field(default=True)


@tool(args_schema=WebExtractInput)
def web_extract(
    url: str,
    wait_for_selector: str | None = None,
    include_html: bool = False,
    include_links: bool = True,
) -> str:
    """Use this tool when you already have a URL and need the page's main readable content, cleaned text, Markdown, metadata, or article links. It is best for summarizing, quoting, or analyzing a specific web page. For JavaScript-heavy pages, provide `wait_for_selector` when the user names the content selector to wait for."""
    response = httpx.post(
        f"{WEBSEARCH_API_BASE_URL}/extract",
        json={
            "url": url,
            "wait_for_selector": wait_for_selector,
            "include_html": include_html,
            "include_links": include_links,
        },
        timeout=60.0,
    )
    response.raise_for_status()
    payload = response.json()

    # Keep tool output compact enough to fit comfortably in an LLM context.
    markdown = payload.get("markdown", "")
    max_markdown_chars = 6000

    return json.dumps(
        {
            "url": payload["url"],
            "final_url": payload["final_url"],
            "status_code": payload["status_code"],
            "title": payload.get("title"),
            "description": payload.get("description"),
            "markdown": markdown[:max_markdown_chars],
            "truncated": len(markdown) > max_markdown_chars,
            "links": payload.get("links", [])[:10],
            "metadata": payload.get("metadata", {}),
        },
        ensure_ascii=False,
    )


def build_agent() -> AgentExecutor:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    tools = [web_extract]

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a careful reading assistant. Use the web_extract tool "
                "when the user gives you a URL to read, summarize, compare, or "
                "analyze. Base your final answer only on extracted content and "
                "include the source URL.",
            ),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )

    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True)


if __name__ == "__main__":
    agent_executor = build_agent()
    response = agent_executor.invoke(
        {
            "input": (
                "Extract and summarize this page in 5 bullets: "
                "https://fastapi.tiangolo.com/tutorial/background-tasks/"
            )
        }
    )
    print(response["output"])
```

## Example 3: `/search` And `/extract` Together With OpenAI

This example gives OpenAI two separate LangChain tools: one tool for `/search` and one tool for `/extract`. The agent is instructed to call `web_search` first, then call `web_extract` on the URLs it chooses from the search results.

Save this as `search_and_extract_tool_example.py` and run it while the Websearch API service is running.

```python
from __future__ import annotations

import json
from typing import Literal

import httpx
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


WEBSEARCH_API_BASE_URL = "http://127.0.0.1:8000/api/v1"


class WebSearchInput(BaseModel):
    query: str = Field(..., description="Search query to discover relevant pages.")
    max_results: int = Field(default=3, ge=1, le=10)
    provider: Literal["brave", "duckduckgo"] = Field(default="brave")


class WebExtractInput(BaseModel):
    url: str = Field(..., description="Absolute http(s) URL selected from search results.")
    wait_for_selector: str | None = Field(
        default=None,
        description="Optional CSS selector to wait for before extracting content.",
    )
    include_links: bool = Field(default=False)


def _post_json(path: str, payload: dict, timeout: float) -> dict:
    response = httpx.post(
        f"{WEBSEARCH_API_BASE_URL}{path}",
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    return response.json()


@tool(args_schema=WebSearchInput)
def web_search(query: str, max_results: int = 3, provider: str = "brave") -> str:
    """Use this tool first when the user asks a research question and you need to discover relevant web pages. It returns ranked JSON search results with title, URL, snippet, rank, and source. Do not use snippets as final evidence when the user needs source-grounded analysis; call `web_extract` on the best URLs next."""
    payload = _post_json(
        "/search",
        {
            "query": query,
            "max_results": max_results,
            "provider": provider,
        },
        timeout=30.0,
    )

    compact_results = [
        {
            "rank": item["rank"],
            "title": item["title"],
            "url": item["url"],
            "snippet": item.get("snippet"),
            "source": item["source"],
        }
        for item in payload["results"]
    ]

    return json.dumps(
        {
            "query": payload["query"],
            "provider": payload["provider"],
            "result_count": payload["result_count"],
            "results": compact_results,
        },
        ensure_ascii=False,
    )


@tool(args_schema=WebExtractInput)
def web_extract(
    url: str,
    wait_for_selector: str | None = None,
    include_links: bool = False,
) -> str:
    """Use this tool after `web_search` when you need to read the actual content of a selected search result URL. It returns cleaned Markdown, title, description, metadata, and final URL. Use this before summarizing, comparing, quoting, or making source-grounded claims from a page."""
    payload = _post_json(
        "/extract",
        {
            "url": url,
            "wait_for_selector": wait_for_selector,
            "include_html": False,
            "include_links": include_links,
        },
        timeout=60.0,
    )
    markdown = payload.get("markdown", "")
    max_markdown_chars = 5000

    return json.dumps(
        {
            "url": payload["url"],
            "final_url": payload["final_url"],
            "status_code": payload["status_code"],
            "title": payload.get("title"),
            "description": payload.get("description"),
            "markdown": markdown[:max_markdown_chars],
            "truncated": len(markdown) > max_markdown_chars,
            "links": payload.get("links", [])[:10],
            "metadata": payload.get("metadata", {}),
        },
        ensure_ascii=False,
    )


def build_agent() -> AgentExecutor:
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    tools = [web_search, web_extract]

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a source-grounded research assistant. For research "
                "questions, you must call web_search first to discover URLs. "
                "Then call web_extract on the best one or two URLs from the "
                "search results before answering. Do not answer from search "
                "snippets alone. Cite the extracted source URLs in the final "
                "answer and mention if extracted content was truncated.",
            ),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ]
    )

    agent = create_tool_calling_agent(llm, tools, prompt)
    return AgentExecutor(agent=agent, tools=tools, verbose=True)


if __name__ == "__main__":
    agent_executor = build_agent()
    response = agent_executor.invoke(
        {
            "input": (
                "Use web_search to find pages about FastAPI background tasks. "
                "Then use web_extract on the top 2 useful URLs and explain when "
                "background tasks should be used. Cite URLs."
            )
        }
    )
    print(response["output"])
```

## Notes

- Use `brave` unless you specifically want to test DuckDuckGo. DuckDuckGo may challenge headless browsers more often.
- Keep tool responses compact. Long extracted pages can exceed an LLM context window, so the examples truncate Markdown before returning it to LangChain.
- For JavaScript-heavy pages, pass `wait_for_selector` to `/extract` so Playwright waits for the content you care about before extraction.
- If the API returns an error, `response.raise_for_status()` raises an `httpx.HTTPStatusError`. In production, catch that exception and return a clear tool error message for the agent.
- The tool docstrings are intentionally specific. LangChain passes them to the model, and the model uses them to decide when and how to call each tool.
