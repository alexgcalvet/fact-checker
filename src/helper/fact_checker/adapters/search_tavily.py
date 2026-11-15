import json
import urllib.request


class Tavily:
    """The Tavily search API: the results of a web search, for a model that cannot search by itself."""

    def __init__(self, key: str, base_url: str = "https://api.tavily.com", timeout: int = 60):
        self.key, self.base_url, self.timeout = key, base_url, timeout

    def search(self, query: str) -> list[dict]:
        """The top 5 results: `title`, `url`, `content` (a snippet) and `published_date` (null when unknown)."""
        body = {"query": query, "search_depth": "basic", "max_results": 5, "include_published_date": True}
        request = urllib.request.Request(f"{self.base_url}/search", data=json.dumps(body).encode(), headers={
            "Authorization": f"Bearer {self.key}", "Content-Type": "application/json"})
        with urllib.request.urlopen(request, timeout=self.timeout) as r:
            return json.load(r)["results"]
