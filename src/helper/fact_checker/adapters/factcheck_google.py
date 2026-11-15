import json
import urllib.parse
import urllib.request

from fact_checker.core.flags import PublishedCheck

URL = "https://factchecktools.googleapis.com/v1alpha1/claims:search"


class GoogleFactCheck:
    """Published fact-checks (ClaimReview) through the Google Fact Check Tools API."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str, language: str = "es") -> list[PublishedCheck]:
        params = urllib.parse.urlencode({"query": query, "languageCode": language, "pageSize": 5})
        req = urllib.request.Request(f"{URL}?{params}", headers={"X-goog-api-key": self.api_key})
        with urllib.request.urlopen(req, timeout=20) as res:
            data = json.load(res)
        return [
            PublishedCheck(claim=c.get("text", ""), claimant=c.get("claimant", ""),
                           publisher=r.get("publisher", {}).get("name", ""), site=r.get("publisher", {}).get("site", ""),
                           url=r.get("url", ""), rating=r.get("textualRating", ""), review_date=r.get("reviewDate", "")[:10])
            for c in data.get("claims", []) for r in c.get("claimReview", [])
        ]
