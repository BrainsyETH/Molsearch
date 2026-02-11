"""
Moltbook Profile Scraper (Simplified)

Uses the Clawdbot browser tool for scraping instead of Playwright.
This avoids dependency hell and reuses existing browser automation.
"""

import json
import re
from typing import Dict, List, Optional
from datetime import datetime, timezone
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MoltbookScraperSimple:
    """
    Simplified Moltbook scraper using browser snapshots.
    
    This is a prototype that manually parses HTML. In production,
    we'll integrate with Clawdbot's browser tool directly.
    """
    
    def parse_profile_html(self, html: str, username: str) -> Dict:
        """
        Parse profile stats from HTML snapshot.
        
        Args:
            html: Raw HTML from profile page
            username: Moltbook username
        
        Returns:
            Dict with followers, karma, posts, comments
        """
        stats = {
            'username': username,
            'followers': 0,
            'following': 0,
            'karma': 0,
            'posts': 0,
            'comments': 0,
            'scraped_at': datetime.now(timezone.utc).isoformat(),
            'profile_url': f'https://moltbook.com/u/{username}'
        }
        
        # Parse stats from HTML (adjust regex patterns based on actual HTML structure)
        patterns = {
            'followers': r'(\d+)\s*followers',
            'following': r'(\d+)\s*following',
            'karma': r'(\d+)\s*karma',
            'posts': r'(\d+)\s*posts?',
            'comments': r'(\d+)\s*comments?'
        }
        
        for key, pattern in patterns.items():
            match = re.search(pattern, html, re.IGNORECASE)
            if match:
                stats[key] = int(match.group(1).replace(',', ''))
        
        logger.info(f"Parsed profile for {username}: {stats}")
        return stats
    
    def parse_posts_html(self, html: str, limit: int = 20) -> List[Dict]:
        """
        Parse recent posts from profile HTML.
        
        Args:
            html: Raw HTML from profile page
            limit: Maximum number of posts to extract
        
        Returns:
            List of post dicts with title, upvotes, comments, engagement
        """
        posts = []
        
        # This is a placeholder - actual parsing depends on Moltbook HTML structure
        # In production, use browser tool's structured snapshot
        
        # Example regex patterns (adjust based on actual HTML)
        post_pattern = r'<article[^>]*>.*?<h2[^>]*>(.*?)</h2>.*?(\d+)\s*upvotes.*?(\d+)\s*comments.*?</article>'
        matches = re.findall(post_pattern, html, re.DOTALL | re.IGNORECASE)
        
        for title, upvotes, comments in matches[:limit]:
            upvotes = int(upvotes.replace(',', ''))
            comments = int(comments.replace(',', ''))
            posts.append({
                'title': title.strip(),
                'upvotes': upvotes,
                'comments': comments,
                'engagement_score': upvotes + (comments * 2),
                'url': None  # Extract from href if needed
            })
        
        # Sort by engagement
        posts.sort(key=lambda p: p['engagement_score'], reverse=True)
        
        logger.info(f"Parsed {len(posts)} posts")
        return posts
    
    def calculate_growth(self, current: Dict, historical: Optional[List[Dict]] = None) -> Dict:
        """
        Calculate growth metrics.
        
        Args:
            current: Current profile stats
            historical: List of previous scrapes
        
        Returns:
            Dict with growth metrics
        """
        if not historical or len(historical) == 0:
            return {
                'username': current['username'],
                'follower_growth_7d': 0,
                'karma_velocity_7d': 0,
                'posts_per_week': 0,
                'current_followers': current['followers'],
                'current_karma': current['karma'],
                'scraped_at': current['scraped_at'],
                'note': 'No historical data - run more queries to track growth'
            }
        
        # Find scrape from ~7 days ago
        week_ago = None
        current_date = datetime.fromisoformat(current['scraped_at'])
        
        for scrape in sorted(historical, key=lambda x: x['scraped_at'], reverse=True):
            scrape_date = datetime.fromisoformat(scrape['scraped_at'])
            days_diff = (current_date - scrape_date).days
            
            if 6 <= days_diff <= 8:
                week_ago = scrape
                break
        
        if not week_ago:
            week_ago = min(historical, key=lambda x: x['scraped_at'])
        
        # Calculate deltas
        follower_growth = current['followers'] - week_ago['followers']
        karma_growth = current['karma'] - week_ago['karma']
        posts_growth = current['posts'] - week_ago['posts']
        
        return {
            'username': current['username'],
            'follower_growth_7d': follower_growth,
            'karma_velocity_7d': karma_growth,
            'posts_per_week': posts_growth,
            'current_followers': current['followers'],
            'current_karma': current['karma'],
            'scraped_at': current['scraped_at']
        }


# Quick test with mock data
if __name__ == '__main__':
    scraper = MoltbookScraperSimple()
    
    # Mock HTML (replace with actual browser snapshot)
    mock_html = """
    <div class="profile">
        <div>5 followers</div>
        <div>1 following</div>
        <div>19 karma</div>
        <div>5 posts</div>
        <div>12 comments</div>
    </div>
    """
    
    stats = scraper.parse_profile_html(mock_html, 'VesperThread')
    print("Parsed stats:", json.dumps(stats, indent=2))
    
    growth = scraper.calculate_growth(stats)
    print("\nGrowth data:", json.dumps(growth, indent=2))
