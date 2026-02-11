"""
Moltbook Profile Scraper

Scrapes public Moltbook profiles to extract analytics data.
Uses Playwright for browser automation (Moltbook is client-side rendered).
"""

import asyncio
import re
from typing import Optional, Dict, List
from datetime import datetime, timezone
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MoltbookScraper:
    """Scrapes Moltbook profiles for analytics data."""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        
    async def __aenter__(self):
        """Context manager entry."""
        await self.start()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        await self.close()
    
    async def start(self):
        """Initialize browser."""
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        self.context = await self.browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        )
        logger.info("Browser started")
    
    async def close(self):
        """Close browser."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if hasattr(self, 'playwright'):
            await self.playwright.stop()
        logger.info("Browser closed")
    
    async def get_profile_stats(self, username: str) -> Dict:
        """
        Get basic profile statistics.
        
        Args:
            username: Moltbook username (e.g., 'VesperThread')
        
        Returns:
            Dict with followers, following, karma, posts, comments
        """
        url = f"https://moltbook.com/u/{username}"
        page = await self.context.new_page()
        
        try:
            logger.info(f"Navigating to {url}")
            response = await page.goto(url, wait_until='networkidle', timeout=30000)
            
            if response.status == 404:
                raise ValueError(f"User '{username}' not found")
            
            # Wait for profile to load (client-side rendered)
            await page.wait_for_selector('.profile-stats', timeout=10000)
            
            # Extract stats from DOM
            stats = await page.evaluate("""
                () => {
                    // Find stats elements (adjust selectors based on actual Moltbook HTML)
                    const getStatValue = (label) => {
                        const elements = Array.from(document.querySelectorAll('.stat-label, .profile-stat-label'));
                        const element = elements.find(el => el.textContent.toLowerCase().includes(label.toLowerCase()));
                        if (element) {
                            const valueEl = element.nextElementSibling || element.parentElement.querySelector('.stat-value, .profile-stat-value');
                            if (valueEl) {
                                return parseInt(valueEl.textContent.replace(/,/g, '')) || 0;
                            }
                        }
                        return 0;
                    };
                    
                    return {
                        followers: getStatValue('followers'),
                        following: getStatValue('following'),
                        karma: getStatValue('karma'),
                        posts: getStatValue('posts'),
                        comments: getStatValue('comments')
                    };
                }
            """)
            
            # Add metadata
            stats['username'] = username
            stats['scraped_at'] = datetime.now(timezone.utc).isoformat()
            stats['profile_url'] = url
            
            logger.info(f"Scraped profile for {username}: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error scraping profile for {username}: {e}")
            raise
        finally:
            await page.close()
    
    async def get_recent_posts(self, username: str, limit: int = 20) -> List[Dict]:
        """
        Get recent posts from a user's profile.
        
        Args:
            username: Moltbook username
            limit: Maximum number of posts to retrieve
        
        Returns:
            List of post dicts with id, title, upvotes, comments, url
        """
        url = f"https://moltbook.com/u/{username}"
        page = await self.context.new_page()
        
        try:
            logger.info(f"Fetching posts for {username}")
            await page.goto(url, wait_until='networkidle', timeout=30000)
            
            # Wait for posts to load
            await page.wait_for_selector('.post-item, .user-post', timeout=10000)
            
            # Extract post data
            posts = await page.evaluate(f"""
                (limit) => {{
                    const postElements = Array.from(document.querySelectorAll('.post-item, .user-post'));
                    return postElements.slice(0, limit).map(post => {{
                        const titleEl = post.querySelector('.post-title, a[href*="/post/"]');
                        const upvotesEl = post.querySelector('.upvotes, .vote-count');
                        const commentsEl = post.querySelector('.comment-count, .comments');
                        const linkEl = post.querySelector('a[href*="/post/"]');
                        
                        return {{
                            title: titleEl ? titleEl.textContent.trim() : 'Untitled',
                            upvotes: upvotesEl ? parseInt(upvotesEl.textContent.replace(/[^0-9]/g, '')) || 0 : 0,
                            comments: commentsEl ? parseInt(commentsEl.textContent.replace(/[^0-9]/g, '')) || 0 : 0,
                            url: linkEl ? 'https://moltbook.com' + linkEl.getAttribute('href') : null,
                            post_id: linkEl ? linkEl.getAttribute('href').split('/post/')[1] : null
                        }};
                    }});
                }}
            """, limit)
            
            # Calculate engagement score (upvotes + comments * 2)
            for post in posts:
                post['engagement_score'] = post['upvotes'] + (post['comments'] * 2)
            
            # Sort by engagement
            posts.sort(key=lambda p: p['engagement_score'], reverse=True)
            
            logger.info(f"Fetched {len(posts)} posts for {username}")
            return posts
            
        except Exception as e:
            logger.error(f"Error fetching posts for {username}: {e}")
            raise
        finally:
            await page.close()
    
    async def get_growth_data(self, username: str, historical_data: Optional[List[Dict]] = None) -> Dict:
        """
        Calculate growth trends.
        
        Args:
            username: Moltbook username
            historical_data: Previous scrapes for this user (from database)
        
        Returns:
            Dict with growth metrics (7-day follower change, karma velocity, etc.)
        """
        current = await self.get_profile_stats(username)
        
        if not historical_data or len(historical_data) == 0:
            return {
                'username': username,
                'follower_growth_7d': 0,
                'karma_velocity_7d': 0,
                'posts_per_week': 0,
                'avg_engagement': 0,
                'scraped_at': current['scraped_at'],
                'note': 'No historical data available - run more queries to track growth'
            }
        
        # Find scrape from ~7 days ago
        week_ago = None
        for scrape in sorted(historical_data, key=lambda x: x['scraped_at'], reverse=True):
            scrape_date = datetime.fromisoformat(scrape['scraped_at'])
            current_date = datetime.fromisoformat(current['scraped_at'])
            days_diff = (current_date - scrape_date).days
            
            if 6 <= days_diff <= 8:  # Close to 7 days
                week_ago = scrape
                break
        
        if not week_ago:
            # Use oldest available data
            week_ago = min(historical_data, key=lambda x: x['scraped_at'])
        
        # Calculate deltas
        follower_growth = current['followers'] - week_ago['followers']
        karma_growth = current['karma'] - week_ago['karma']
        posts_growth = current['posts'] - week_ago['posts']
        
        return {
            'username': username,
            'follower_growth_7d': follower_growth,
            'karma_velocity_7d': karma_growth,
            'posts_per_week': posts_growth,
            'current_followers': current['followers'],
            'current_karma': current['karma'],
            'scraped_at': current['scraped_at']
        }


async def test_scraper():
    """Test the scraper with VesperThread profile."""
    async with MoltbookScraper(headless=True) as scraper:
        # Test basic stats
        stats = await scraper.get_profile_stats('VesperThread')
        print("Profile Stats:")
        print(stats)
        
        # Test posts
        posts = await scraper.get_recent_posts('VesperThread', limit=10)
        print(f"\nRecent Posts ({len(posts)}):")
        for i, post in enumerate(posts[:5], 1):
            print(f"{i}. {post['title']} - {post['engagement_score']} engagement")
        
        # Test growth (no historical data yet)
        growth = await scraper.get_growth_data('VesperThread')
        print("\nGrowth Data:")
        print(growth)


if __name__ == '__main__':
    asyncio.run(test_scraper())
