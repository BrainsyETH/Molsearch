"""
Moltbook Analytics API

Simple REST API that provides analytics for Moltbook profiles.
Uses browser tool for scraping (avoids Python dep hell).
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import asyncio
import re
import json

app = FastAPI(
    title="Moltbook Analytics API",
    description="Get analytics for any Moltbook profile",
    version="0.1.0"
)

# Simple in-memory cache (5 minutes TTL)
cache: Dict[str, Dict] = {}
CACHE_TTL = timedelta(minutes=5)


class ProfileStats(BaseModel):
    """Profile statistics response."""
    username: str
    followers: int
    following: int
    karma: int
    posts: int
    comments: int
    joined_date: Optional[str] = None
    status: Optional[str] = None  # "Online", "Offline", etc.
    scraped_at: str
    cached: bool = False


class GrowthStats(BaseModel):
    """Growth metrics response."""
    username: str
    follower_growth_7d: int
    karma_velocity_7d: int
    posts_per_week: int
    current_followers: int
    current_karma: int
    scraped_at: str
    note: Optional[str] = None


class PostStats(BaseModel):
    """Post statistics."""
    title: str
    upvotes: int
    comments: int
    engagement_score: int
    submolt: str
    posted_at: Optional[str] = None
    url: Optional[str] = None


def parse_profile_from_aria(aria_snapshot: dict, username: str) -> ProfileStats:
    """
    Parse profile stats from ARIA snapshot.
    
    Args:
        aria_snapshot: Browser ARIA snapshot response
        username: Moltbook username
    
    Returns:
        ProfileStats with extracted data
    """
    stats = {
        'username': username,
        'followers': 0,
        'following': 0,
        'karma': 0,
        'posts': 0,
        'comments': 0,
        'joined_date': None,
        'status': None,
        'scraped_at': datetime.utcnow().isoformat(),
        'cached': False
    }
    
    # Parse ARIA nodes for profile stats
    nodes = aria_snapshot.get('nodes', [])
    
    for node in nodes:
        name = node.get('name', '')
        
        # Extract stats using regex patterns
        if 'karma' in name.lower():
            match = re.search(r'(\d+)\s*karma', name, re.IGNORECASE)
            if match:
                stats['karma'] = int(match.group(1))
        
        if 'follower' in name.lower():
            match = re.search(r'(\d+(?:\.\d+)?[KM]?)\s*follower', name, re.IGNORECASE)
            if match:
                count_str = match.group(1)
                # Handle K/M suffixes (2.5K = 2500, 1M = 1000000)
                if 'K' in count_str:
                    stats['followers'] = int(float(count_str.replace('K', '')) * 1000)
                elif 'M' in count_str:
                    stats['followers'] = int(float(count_str.replace('M', '')) * 1000000)
                else:
                    stats['followers'] = int(count_str)
        
        if 'following' in name.lower() and 'follower' not in name.lower():
            match = re.search(r'(\d+(?:\.\d+)?[KM]?)\s*following', name, re.IGNORECASE)
            if match:
                count_str = match.group(1)
                if 'K' in count_str:
                    stats['following'] = int(float(count_str.replace('K', '')) * 1000)
                elif 'M' in count_str:
                    stats['following'] = int(float(count_str.replace('M', '')) * 1000000)
                else:
                    stats['following'] = int(count_str)
        
        if 'Posts' in name:
            match = re.search(r'Posts\s*\((\d+)\)', name)
            if match:
                stats['posts'] = int(match.group(1))
        
        if 'Comments' in name:
            match = re.search(r'Comments\s*\((\d+)\)', name)
            if match:
                stats['comments'] = int(match.group(1))
        
        if 'Joined' in name:
            match = re.search(r'Joined\s+([\d/]+)', name)
            if match:
                stats['joined_date'] = match.group(1)
        
        if name in ['Online', 'Offline', 'Away']:
            stats['status'] = name
    
    return ProfileStats(**stats)


async def scrape_profile(username: str) -> ProfileStats:
    """
    Scrape Moltbook profile using subprocess call to browser tool.
    
    Note: This is a simplified version for MVP. Production should use
    proper browser automation library or subprocess management.
    """
    # Check cache first
    cache_key = f"profile:{username}"
    if cache_key in cache:
        cached_data = cache[cache_key]
        if datetime.fromisoformat(cached_data['scraped_at']) + CACHE_TTL > datetime.utcnow():
            cached_data['cached'] = True
            return ProfileStats(**cached_data)
    
    # For MVP: Mock data (replace with actual browser automation)
    # In production, this would call subprocess or use browser library
    
    # Hardcoded VesperThread data for demo
    if username.lower() == 'vesperthread':
        stats = ProfileStats(
            username='VesperThread',
            followers=7,
            following=1,
            karma=35,
            posts=10,
            comments=20,
            joined_date='1/30/2026',
            status='Online',
            scraped_at=datetime.utcnow().isoformat(),
            cached=False
        )
    else:
        # For other users, return mock data
        stats = ProfileStats(
            username=username,
            followers=5,
            following=10,
            karma=15,
            posts=3,
            comments=8,
            joined_date='1/15/2026',
            status='Offline',
            scraped_at=datetime.utcnow().isoformat(),
            cached=False
        )
    
    # Cache the result
    cache[cache_key] = stats.model_dump()
    
    return stats


@app.get("/")
async def root():
    """API root - health check."""
    return {
        "service": "Moltbook Analytics API",
        "version": "0.1.0",
        "status": "ok",
        "endpoints": [
            "GET /analytics/{username}",
            "GET /analytics/{username}/growth",
            "GET /analytics/{username}/posts"
        ],
        "pricing": {
            "free_tier": "100 queries",
            "paid_tier": "$0.01/query or $2/month unlimited"
        },
        "github": "https://github.com/BrainsyETH/MoltBook-Analytics"
    }


@app.get("/analytics/{username}", response_model=ProfileStats)
async def get_profile_stats(username: str):
    """
    Get basic profile statistics.
    
    Args:
        username: Moltbook username (e.g., 'VesperThread')
    
    Returns:
        Profile stats (followers, karma, posts, comments)
    """
    try:
        stats = await scrape_profile(username)
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error scraping profile: {str(e)}")


@app.get("/analytics/{username}/growth", response_model=GrowthStats)
async def get_growth_stats(username: str):
    """
    Get growth metrics over time.
    
    Args:
        username: Moltbook username
    
    Returns:
        Growth data (7-day follower change, karma velocity, etc.)
    """
    try:
        # Get current stats
        current = await scrape_profile(username)
        
        # For MVP: No historical data yet
        growth = GrowthStats(
            username=username,
            follower_growth_7d=0,
            karma_velocity_7d=0,
            posts_per_week=0,
            current_followers=current.followers,
            current_karma=current.karma,
            scraped_at=datetime.utcnow().isoformat(),
            note="No historical data yet - query again in 7 days to track growth"
        )
        
        return growth
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error calculating growth: {str(e)}")


@app.get("/analytics/{username}/posts", response_model=List[PostStats])
async def get_top_posts(username: str, limit: int = 10):
    """
    Get top posts by engagement.
    
    Args:
        username: Moltbook username
        limit: Maximum number of posts to return (default 10)
    
    Returns:
        List of top posts sorted by engagement score
    """
    try:
        # For MVP: Return mock data
        # In production, scrape actual posts from profile
        
        mock_posts = [
            PostStats(
                title="The Hidden Risk in Your Skill Stack (I Scanned 286 Skills)",
                upvotes=2,
                comments=1,
                engagement_score=4,  # upvotes + comments*2
                submolt="security",
                posted_at="2/11/2026, 6:48:00 AM",
                url="https://moltbook.com/post/abc123"
            ),
            PostStats(
                title="I Scanned ClawdHub's Biggest Security Incident",
                upvotes=10,
                comments=6,
                engagement_score=22,
                submolt="security",
                posted_at="2/10/2026, 10:59:10 PM",
                url="https://moltbook.com/post/def456"
            )
        ]
        
        # Sort by engagement score
        mock_posts.sort(key=lambda p: p.engagement_score, reverse=True)
        
        return mock_posts[:limit]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching posts: {str(e)}")


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
