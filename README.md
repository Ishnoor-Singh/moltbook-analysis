# Moltbook Analysis

Tools for analyzing Moltbook.com - the social network for AI agents.

## Features

- **Systematic post collection** - Scrapes posts with full metadata
- **CSV exports by submolt** - Easy to analyze in pandas/Excel
- **User tracking** - Maintains registry of all seen users for profile analysis
- **Deduplication** - Prevents scraping the same post twice
- **Timestamp tracking** - Records both post creation time and scrape time
- **Raw data preservation** - Keeps full JSON for detailed analysis

## Data Collected

For each post:
- `post_id` - Unique identifier
- `url` - Full URL to post
- `title` - Post title
- `content` - Full post content
- `link_url` - External link (if link post)
- `author_name` - Author's Moltbook username
- `author_id` - Author's internal ID
- `submolt` - Community name
- `submolt_display` - Community display name
- `upvotes` / `downvotes` / `score` - Engagement metrics
- `comment_count` - Number of comments
- `created_at` - When post was created
- `scraped_at` - When we collected it
- `is_pinned` - Whether post is pinned

## Usage

```bash
# Basic usage - scrape 100 posts from general and introductions
python scraper.py

# Custom submolts and count
python scraper.py -s general thecoalition finance -n 50

# With API key (for authenticated endpoints)
python scraper.py -k moltbook_xxx
```

## Output Structure

```
data/
├── state.json          # Tracks seen posts (for deduplication)
├── users.json          # Registry of all seen users
└── posts/
    ├── general.csv     # Posts from m/general
    ├── general_raw.jsonl
    ├── introductions.csv
    └── introductions_raw.jsonl
```

## Research Ideas

- **Model fingerprinting** - Can we identify which LLM is behind each agent?
- **Behavioral clustering** - Do agents naturally group into types?
- **Linguistic analysis** - Common phrases, hedging patterns, emoji usage
- **Social dynamics** - Who interacts with whom? Cliques?
- **Topic analysis** - What do agents talk about?

## License

MIT
