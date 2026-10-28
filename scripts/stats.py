"""Render the GitHub stats card shown in the profile README.

Run hourly by .github/workflows/stats.yml. Writes profile/stats-dark.svg,
profile/stats-light.svg and profile/stats.json. The files are only rewritten
when a number changes (or with --force), so quiet hours make no commit.

Usage: GITHUB_TOKEN=... python3 scripts/stats.py [--force]
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

USER = "EveningStudy"
NAME = "Wang Zixin"
OUT = Path(__file__).resolve().parent.parent / "profile"
API = "https://api.github.com"

QUERY = """
query($login: String!, $after: String) {
  user(login: $login) {
    pullRequests { totalCount }
    issues { totalCount }
    repositoriesContributedTo(contributionTypes: [COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]) { totalCount }
    repositories(first: 100, after: $after, ownerAffiliations: OWNER, isFork: false, privacy: PUBLIC) {
      nodes { stargazerCount }
      pageInfo { hasNextPage endCursor }
    }
  }
}
"""

# Octicons (MIT), same set the old github-readme-stats card used.
ICONS = {
    "star": "M8 .25a.75.75 0 01.673.418l1.882 3.815 4.21.612a.75.75 0 01.416 1.279l-3.046 2.97.719 4.192a.75.75 0 01-1.088.791L8 12.347l-3.766 1.98a.75.75 0 01-1.088-.79l.72-4.194L.818 6.374a.75.75 0 01.416-1.28l4.21-.611L7.327.668A.75.75 0 018 .25zm0 2.445L6.615 5.5a.75.75 0 01-.564.41l-3.097.45 2.24 2.184a.75.75 0 01.216.664l-.528 3.084 2.769-1.456a.75.75 0 01.698 0l2.77 1.456-.53-3.084a.75.75 0 01.216-.664l2.24-2.183-3.096-.45a.75.75 0 01-.564-.41L8 2.694v.001z",
    "commits": "M1.643 3.143L.427 1.927A.25.25 0 000 2.104V5.75c0 .138.112.25.25.25h3.646a.25.25 0 00.177-.427L2.715 4.215a6.5 6.5 0 11-1.18 4.458.75.75 0 10-1.493.154 8.001 8.001 0 101.6-5.684zM7.75 4a.75.75 0 01.75.75v2.992l2.028.812a.75.75 0 01-.557 1.392l-2.5-1A.75.75 0 017 8.25v-3.5A.75.75 0 017.75 4z",
    "prs": "M7.177 3.073L9.573.677A.25.25 0 0110 .854v4.792a.25.25 0 01-.427.177L7.177 3.427a.25.25 0 010-.354zM3.75 2.5a.75.75 0 100 1.5.75.75 0 000-1.5zm-2.25.75a2.25 2.25 0 113 2.122v5.256a2.251 2.251 0 11-1.5 0V5.372A2.25 2.25 0 011.5 3.25zM11 2.5h-1V4h1a1 1 0 011 1v5.628a2.251 2.251 0 101.5 0V5A2.5 2.5 0 0011 2.5zm1 10.25a.75.75 0 111.5 0 .75.75 0 01-1.5 0zM3.75 12a.75.75 0 100 1.5.75.75 0 000-1.5z",
    "issues": "M8 1.5a6.5 6.5 0 100 13 6.5 6.5 0 000-13zM0 8a8 8 0 1116 0A8 8 0 010 8zm9 3a1 1 0 11-2 0 1 1 0 012 0zm-.25-6.25a.75.75 0 00-1.5 0v3.5a.75.75 0 001.5 0v-3.5z",
    "contributed": "M2 2.5A2.5 2.5 0 014.5 0h8.75a.75.75 0 01.75.75v12.5a.75.75 0 01-.75.75h-2.5a.75.75 0 110-1.5h1.75v-2h-8a1 1 0 00-.714 1.7.75.75 0 01-1.072 1.05A2.495 2.495 0 012 11.5v-9zm10.5-1V9h-8c-.356 0-.694.074-1 .208V2.5a1 1 0 011-1h8zM5 12.25v3.25a.25.25 0 00.4.2l1.45-1.087a.25.25 0 01.3 0L8.6 15.7a.25.25 0 00.4-.2v-3.25a.25.25 0 00-.25-.25h-3.5a.25.25 0 00-.25.25z",
}

ROWS = [
    ("commits", "Total commits"),
    ("prs", "Pull requests"),
    ("issues", "Issues"),
    ("contributed", "Contributed to (last year)"),
]

THEMES = {
    "dark": {"accent": "#F778BA", "text": "#C9D1D9", "value": "#F0F6FC", "muted": "#8B949E"},
    "light": {"accent": "#BF3989", "text": "#434D58", "value": "#1F2328", "muted": "#6E7781"},
}


def call(path, body=None):
    req = urllib.request.Request(
        API + path,
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
            "Accept": "application/vnd.github+json",
            "User-Agent": USER + "-profile-stats",
        },
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.load(resp)
            break
        except urllib.error.URLError:
            if attempt == 2:
                raise
            time.sleep(5)
    if data.get("errors"):
        sys.exit("GitHub API error: " + json.dumps(data["errors"]))
    return data


def fetch():
    stars, after = 0, None
    while True:
        user = call("/graphql", {"query": QUERY, "variables": {"login": USER, "after": after}})["data"]["user"]
        repos = user["repositories"]
        stars += sum(r["stargazerCount"] for r in repos["nodes"])
        if not repos["pageInfo"]["hasNextPage"]:
            break
        after = repos["pageInfo"]["endCursor"]
    return {
        "stars": stars,
        "commits": call("/search/commits?per_page=1&q=author:" + USER)["total_count"],
        "prs": user["pullRequests"]["totalCount"],
        "issues": user["issues"]["totalCount"],
        "contributed": user["repositoriesContributedTo"]["totalCount"],
    }


def icon(key, x, y, color, size=16):
    scale = size / 16
    return (
        f'<g transform="translate({x} {y}) scale({scale:g})" fill="{color}">'
        f'<path fill-rule="evenodd" d="{ICONS[key]}"/></g>'
    )


def render(stats, updated, t):
    font = "'Segoe UI', Ubuntu, 'Helvetica Neue', Sans-Serif"
    rows = []
    for i, (key, label) in enumerate(ROWS):
        y = 74 + i * 27
        rows.append(
            icon(key, 25, y - 12, t["accent"])
            + f'<text x="52" y="{y}" fill="{t["text"]}" font-size="14" font-weight="600">{label}:</text>'
            + f'<text x="292" y="{y}" fill="{t["value"]}" font-size="14" font-weight="700" text-anchor="end">{stats[key]:,}</text>'
        )
    cx, cy = 384, 104
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="467" height="195" viewBox="0 0 467 195" role="img" aria-labelledby="title">
<title id="title">{NAME}'s GitHub Stats: {stats["stars"]:,} stars, {stats["commits"]:,} commits</title>
<g font-family="{font}">
<text x="25" y="38" fill="{t["accent"]}" font-size="18" font-weight="600">{NAME}'s GitHub Stats</text>
{''.join(rows)}
<circle cx="{cx}" cy="{cy}" r="46" fill="none" stroke="{t["accent"]}" stroke-width="5"/>
{icon("star", cx - 7, cy - 32, t["accent"], 14)}
<text x="{cx}" y="{cy + 10}" fill="{t["value"]}" font-size="26" font-weight="700" text-anchor="middle">{stats["stars"]:,}</text>
<text x="{cx}" y="{cy + 27}" fill="{t["muted"]}" font-size="11" font-weight="600" text-anchor="middle" letter-spacing="1">STARS</text>
<text x="25" y="180" fill="{t["muted"]}" font-size="11">Updated {updated} · refreshed hourly</text>
</g>
</svg>
"""


def main():
    force = "--force" in sys.argv
    state_file = OUT / "stats.json"
    old = json.loads(state_file.read_text()) if state_file.exists() else {}
    stats = fetch()
    if not force and old.get("stats") == stats:
        print("unchanged:", stats)
        return
    updated = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    OUT.mkdir(exist_ok=True)
    for name, theme in THEMES.items():
        (OUT / f"stats-{name}.svg").write_text(render(stats, updated, theme))
    state_file.write_text(json.dumps({"stats": stats, "updated": updated}, indent=2) + "\n")
    print("rendered:", stats)


if __name__ == "__main__":
    main()
