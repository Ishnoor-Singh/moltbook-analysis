#!/usr/bin/env python3
"""
Moltbook Scraper - Systematically collect posts from Moltbook.com

Features:
- Collects full post data (content, votes, author, timestamps, etc.)
- Saves to CSVs organized by submolt
- Maintains user registry for later profile scraping
- Prevents duplicate post collection
- Records both post time and scrape time
"""

import requests
import json
import csv
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Set
import argparse

# Configuration
BASE_URL = "https://www.moltbook.com/api/v1"
DATA_DIR = Path("data")
POSTS_DIR = DATA_DIR / "posts"
STATE_FILE = DATA_DIR / "state.json"
USERS_FILE = DATA_DIR / "users.json"

# Rate limiting
REQUEST_DELAY = 1.0  # seconds between requests


class MoltbookScraper:
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.session = requests.Session()
        if api_key:
            self.session.headers["Authorization"] = f"Bearer {api_key}"
        self.session.headers["User-Agent"] = "MoltbookAnalysis/1.0"
        
        # Ensure directories exist
        DATA_DIR.mkdir(exist_ok=True)
        POSTS_DIR.mkdir(exist_ok=True)
        
        # Load state
        self.seen_posts: Set[str] = set()
        self.users: Dict[str, dict] = {}
        self._load_state()
    
    def _load_state(self):
        """Load previously seen posts and users from disk."""
        if STATE_FILE.exists():
            with open(STATE_FILE) as f:
                data = json.load(f)
                self.seen_posts = set(data.get("seen_posts", []))
                print(f"Loaded {len(self.seen_posts)} previously seen posts")
        
        if USERS_FILE.exists():
            with open(USERS_FILE) as f:
                self.users = json.load(f)
                print(f"Loaded {len(self.users)} known users")
    
    def _save_state(self):
        """Save state to disk."""
        with open(STATE_FILE, "w") as f:
            json.dump({
                "seen_posts": list(self.seen_posts),
                "last_updated": datetime.utcnow().isoformat()
            }, f, indent=2)
        
        with open(USERS_FILE, "w") as f:
            json.dump(self.users, f, indent=2)
    
    def _api_request(self, endpoint: str, params: dict = None) -> dict:
        """Make an API request with rate limiting."""
        url = f"{BASE_URL}/{endpoint}"
        time.sleep(REQUEST_DELAY)
        
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API request failed: {e}")
            return {"success": False, "error": str(e)}
    
    def get_posts(self, submolt: str = None, sort: str = "new", limit: int = 25) -> List[dict]:
        """Fetch posts from the API."""
        params = {"sort": sort, "limit": limit}
        
        if submolt:
            endpoint = f"submolts/{submolt}/feed"
        else:
            endpoint = "posts"
        
        result = self._api_request(endpoint, params)
        
        if result.get("success") and "posts" in result:
            return result["posts"]
        elif isinstance(result, list):
            return result
        elif "data" in result and isinstance(result["data"], list):
            return result["data"]
        else:
            print(f"Unexpected response format: {list(result.keys()) if isinstance(result, dict) else type(result)}")
            return []
    
    def extract_post_data(self, post: dict, scraped_at: str) -> dict:
        """Extract all relevant data from a post."""
        # Handle nested author structure
        author = post.get("author", {})
        if isinstance(author, dict):
            author_name = author.get("name", "unknown")
        else:
            author_name = str(author) if author else "unknown"
        
        # Track user
        if author_name and author_name != "unknown":
            if author_name not in self.users:
                self.users[author_name] = {
                    "first_seen": scraped_at,
                    "post_count": 0,
                    "submolts": []
                }
            self.users[author_name]["post_count"] += 1
            self.users[author_name]["last_seen"] = scraped_at
        
        # Handle submolt
        submolt = post.get("submolt", {})
        if isinstance(submolt, dict):
            submolt_name = submolt.get("name", "unknown")
        else:
            submolt_name = str(submolt) if submolt else "unknown"
        
        # Track submolt for user
        if author_name in self.users and submolt_name not in self.users[author_name]["submolts"]:
            self.users[author_name]["submolts"].append(submolt_name)
        
        return {
            # Identifiers
            "post_id": post.get("id", ""),
            "url": f"https://www.moltbook.com/post/{post.get('id', '')}",
            
            # Content
            "title": post.get("title", ""),
            "content": post.get("content", ""),
            "link_url": post.get("url", ""),  # If it's a link post
            
            # Author
            "author_name": author_name,
            "author_id": author.get("id", "") if isinstance(author, dict) else "",
            
            # Community
            "submolt": submolt_name,
            "submolt_display": submolt.get("display_name", submolt_name) if isinstance(submolt, dict) else submolt_name,
            
            # Engagement
            "upvotes": post.get("upvotes", 0),
            "downvotes": post.get("downvotes", 0),
            "score": post.get("upvotes", 0) - post.get("downvotes", 0),
            "comment_count": post.get("comment_count", post.get("comments", 0)),
            
            # Timestamps
            "created_at": post.get("created_at", ""),
            "scraped_at": scraped_at,
            
            # Metadata
            "is_pinned": post.get("is_pinned", False),
            "raw_json": json.dumps(post)  # Keep raw data for later analysis
        }
    
    def scrape_submolt(self, submolt: str, target_count: int = 100) -> List[dict]:
        """Scrape posts from a specific submolt."""
        print(f"\n{'='*60}")
        print(f"Scraping m/{submolt} - Target: {target_count} new posts")
        print(f"{'='*60}")
        
        collected = []
        page = 0
        consecutive_dupes = 0
        max_consecutive_dupes = 3  # Stop if we hit 3 pages of all dupes
        
        while len(collected) < target_count and consecutive_dupes < max_consecutive_dupes:
            posts = self.get_posts(submolt=submolt, sort="new", limit=25)
            
            if not posts:
                print("No more posts returned")
                break
            
            new_in_batch = 0
            scraped_at = datetime.utcnow().isoformat()
            
            for post in posts:
                post_id = post.get("id", "")
                
                if not post_id:
                    continue
                
                if post_id in self.seen_posts:
                    continue
                
                # Extract and store
                post_data = self.extract_post_data(post, scraped_at)
                collected.append(post_data)
                self.seen_posts.add(post_id)
                new_in_batch += 1
                
                if len(collected) >= target_count:
                    break
            
            if new_in_batch == 0:
                consecutive_dupes += 1
            else:
                consecutive_dupes = 0
            
            page += 1
            print(f"  Page {page}: Found {new_in_batch} new posts (total: {len(collected)})")
        
        print(f"Collected {len(collected)} new posts from m/{submolt}")
        return collected
    
    def save_to_csv(self, posts: List[dict], submolt: str):
        """Save posts to a CSV file for the submolt."""
        if not posts:
            return
        
        csv_file = POSTS_DIR / f"{submolt}.csv"
        file_exists = csv_file.exists()
        
        # Define columns (exclude raw_json for readability)
        columns = [
            "post_id", "url", "title", "content", "link_url",
            "author_name", "author_id", "submolt", "submolt_display",
            "upvotes", "downvotes", "score", "comment_count",
            "created_at", "scraped_at", "is_pinned"
        ]
        
        with open(csv_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
            
            if not file_exists:
                writer.writeheader()
            
            writer.writerows(posts)
        
        print(f"Saved {len(posts)} posts to {csv_file}")
        
        # Also save raw JSON for full data preservation
        json_file = POSTS_DIR / f"{submolt}_raw.jsonl"
        with open(json_file, "a", encoding="utf-8") as f:
            for post in posts:
                f.write(post.get("raw_json", "{}") + "\n")
    
    def run(self, submolts: List[str], posts_per_submolt: int = 100):
        """Main scraping loop."""
        print(f"\nMoltbook Scraper Starting")
        print(f"Target submolts: {submolts}")
        print(f"Posts per submolt: {posts_per_submolt}")
        print(f"Already seen: {len(self.seen_posts)} posts")
        
        total_collected = 0
        
        for submolt in submolts:
            posts = self.scrape_submolt(submolt, posts_per_submolt)
            self.save_to_csv(posts, submolt)
            total_collected += len(posts)
            
            # Save state after each submolt
            self._save_state()
        
        print(f"\n{'='*60}")
        print(f"SCRAPING COMPLETE")
        print(f"{'='*60}")
        print(f"Total new posts collected: {total_collected}")
        print(f"Total unique posts seen: {len(self.seen_posts)}")
        print(f"Total unique users tracked: {len(self.users)}")
        print(f"\nData saved to: {DATA_DIR.absolute()}")
        
        return total_collected


def main():
    parser = argparse.ArgumentParser(description="Scrape posts from Moltbook")
    parser.add_argument("--submolts", "-s", nargs="+", default=["general", "introductions"],
                        help="Submolts to scrape")
    parser.add_argument("--count", "-n", type=int, default=100,
                        help="Number of posts per submolt")
    parser.add_argument("--api-key", "-k", help="Moltbook API key (optional)")
    
    args = parser.parse_args()
    
    scraper = MoltbookScraper(api_key=args.api_key)
    scraper.run(args.submolts, args.count)


if __name__ == "__main__":
    main()
