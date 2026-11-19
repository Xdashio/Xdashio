"""Minimal GitHub GraphQL client (standard library only)."""
import json
import os
import sys
import urllib.request

ENDPOINT = "https://api.github.com/graphql"


def token_from_env() -> str:
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is not set")
    return token


def graphql(query: str, variables: dict, token: str) -> dict:
    body = json.dumps({"query": query, "variables": variables}).encode()
    req = urllib.request.Request(
        ENDPOINT, data=body,
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "xdashio-profile-builder"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        raise RuntimeError(f"GitHub API error: {payload['errors']}")
    return payload["data"]
