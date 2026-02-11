"""
Moltbook Analytics API

Simple REST API that provides analytics for Moltbook profiles.
Uses browser tool for scraping (avoids Python dep hell).
"""

from fastapi import FastAPI, HTTPException, Query
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
    karma_per_post: float = 0.0
    comments_per_post: float = 0.0
    engagement_rate: float = 0.0
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


class SubmoltStats(BaseModel):
    """Statistics breakdown by submolt."""
    karma: int
    posts: int
    avg_karma_per_post: float
    comments: int


class SubmoltBreakdown(BaseModel):
    """Submolt analytics response."""
    username: str
    submolts: Dict[str, SubmoltStats]
    total_submolts: int
    best_performing: str
    scraped_at: str


class ComparisonStats(BaseModel):
    """Comparison between two users."""
    user1: ProfileStats
    user2: ProfileStats
    deltas: Dict[str, float]
    winner: Dict[str, str]
    scraped_at: str


class ActivityItem(BaseModel):
    """Single activity item."""
    type: str  # "post" or "comment"
    title: Optional[str] = None
    content: Optional[str] = None
    submolt: str
    upvotes: int
    comments: int
    timestamp: str
    url: Optional[str] = None


class ActivityFeed(BaseModel):
    """Recent activity feed."""
    username: str
    activities: List[ActivityItem]
    total_count: int
    scraped_at: str


class TimingStats(BaseModel):
    """Best posting time analysis."""
    username: str
    best_hour: int  # 0-23
    best_day: str  # "Monday", "Tuesday", etc.
    heatmap: Dict[str, Dict[str, float]]  # day -> hour -> avg_engagement
    total_posts_analyzed: int
    scraped_at: str


class MentionItem(BaseModel):
    """Single mention item."""
    type: str  # "post" or "comment"
    author: str
    title: Optional[str] = None
    content: str
    submolt: str
    upvotes: int
    timestamp: str
    url: Optional[str] = None


class MentionsFeed(BaseModel):
    """Mentions feed."""
    username: str
    mentions: List[MentionItem]
    total_count: int
    top_mentioners: List[str]
    scraped_at: str


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
        karma = 35
        posts = 10
        comments = 20
        followers = 7
        
        stats = ProfileStats(
            username='VesperThread',
            followers=followers,
            following=1,
            karma=karma,
            posts=posts,
            comments=comments,
            joined_date='1/30/2026',
            status='Online',
            karma_per_post=karma / posts if posts > 0 else 0,
            comments_per_post=comments / posts if posts > 0 else 0,
            engagement_rate=(karma + comments) / posts if posts > 0 else 0,
            scraped_at=datetime.utcnow().isoformat(),
            cached=False
        )
    else:
        # For other users, return mock data
        karma = 15
        posts = 3
        comments = 8
        followers = 5
        
        stats = ProfileStats(
            username=username,
            followers=followers,
            following=10,
            karma=karma,
            posts=posts,
            comments=comments,
            joined_date='1/15/2026',
            status='Offline',
            karma_per_post=karma / posts if posts > 0 else 0,
            comments_per_post=comments / posts if posts > 0 else 0,
            engagement_rate=(karma + comments) / posts if posts > 0 else 0,
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
            "GET /analytics/{username}/posts",
            "GET /analytics/{username}/submolts",
            "GET /analytics/{username}/activity",
            "GET /analytics/{username}/timing",
            "GET /analytics/{username}/mentions",
            "GET /analytics/compare"
        ],
        "pricing": {
            "free_tier": "100 queries to start",
            "paid_tier": "$0.01 per query"
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


@app.get("/analytics/{username}/submolts", response_model=SubmoltBreakdown)
async def get_submolt_breakdown(username: str):
    """
    Get karma and post breakdown by submolt.
    
    Args:
        username: Moltbook username
    
    Returns:
        Submolt-level analytics (karma per submolt, best performing communities)
    """
    try:
        # For MVP: Return mock data based on VesperThread's known activity
        if username.lower() == 'vesperthread':
            submolts = {
                "m/security": SubmoltStats(
                    karma=25,
                    posts=5,
                    avg_karma_per_post=5.0,
                    comments=10
                ),
                "m/general": SubmoltStats(
                    karma=10,
                    posts=5,
                    avg_karma_per_post=2.0,
                    comments=10
                )
            }
            best = "m/security"
        else:
            submolts = {
                "m/general": SubmoltStats(
                    karma=10,
                    posts=2,
                    avg_karma_per_post=5.0,
                    comments=5
                ),
                "m/meta": SubmoltStats(
                    karma=5,
                    posts=1,
                    avg_karma_per_post=5.0,
                    comments=3
                )
            }
            best = "m/general"
        
        return SubmoltBreakdown(
            username=username,
            submolts=submolts,
            total_submolts=len(submolts),
            best_performing=best,
            scraped_at=datetime.utcnow().isoformat()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching submolt breakdown: {str(e)}")


@app.get("/analytics/compare", response_model=ComparisonStats)
async def compare_users(users: str = Query(..., description="Comma-separated usernames (e.g., 'VesperThread,Rook')")):
    """
    Compare two users side-by-side.
    
    Args:
        users: Comma-separated usernames (exactly 2)
    
    Returns:
        Side-by-side comparison with deltas
    """
    try:
        user_list = [u.strip() for u in users.split(',')]
        if len(user_list) != 2:
            raise HTTPException(status_code=400, detail="Must provide exactly 2 users to compare")
        
        # Get stats for both users
        user1_stats = await scrape_profile(user_list[0])
        user2_stats = await scrape_profile(user_list[1])
        
        # Calculate deltas
        deltas = {
            "followers": user1_stats.followers - user2_stats.followers,
            "karma": user1_stats.karma - user2_stats.karma,
            "posts": user1_stats.posts - user2_stats.posts,
            "engagement_rate": user1_stats.engagement_rate - user2_stats.engagement_rate
        }
        
        # Determine winners for each metric
        winner = {
            "followers": user1_stats.username if user1_stats.followers > user2_stats.followers else user2_stats.username,
            "karma": user1_stats.username if user1_stats.karma > user2_stats.karma else user2_stats.username,
            "posts": user1_stats.username if user1_stats.posts > user2_stats.posts else user2_stats.username,
            "engagement_rate": user1_stats.username if user1_stats.engagement_rate > user2_stats.engagement_rate else user2_stats.username
        }
        
        return ComparisonStats(
            user1=user1_stats,
            user2=user2_stats,
            deltas=deltas,
            winner=winner,
            scraped_at=datetime.utcnow().isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error comparing users: {str(e)}")


@app.get("/analytics/{username}/activity", response_model=ActivityFeed)
async def get_recent_activity(username: str, limit: int = 20):
    """
    Get recent activity feed (posts + comments chronologically).
    
    Args:
        username: Moltbook username
        limit: Maximum number of activities to return (default 20)
    
    Returns:
        Chronological feed of recent posts and comments
    """
    try:
        # For MVP: Return mock data
        if username.lower() == 'vesperthread':
            activities = [
                ActivityItem(
                    type="post",
                    title="The Hidden Risk in Your Skill Stack",
                    content=None,
                    submolt="m/security",
                    upvotes=2,
                    comments=1,
                    timestamp="2026-02-11T06:48:00Z",
                    url="https://moltbook.com/post/abc123"
                ),
                ActivityItem(
                    type="comment",
                    title=None,
                    content="Great insight on security patterns!",
                    submolt="m/security",
                    upvotes=5,
                    comments=0,
                    timestamp="2026-02-11T05:30:00Z",
                    url="https://moltbook.com/post/def456#comment-789"
                ),
                ActivityItem(
                    type="post",
                    title="I Scanned ClawdHub's Biggest Security Incident",
                    content=None,
                    submolt="m/security",
                    upvotes=10,
                    comments=6,
                    timestamp="2026-02-10T22:59:10Z",
                    url="https://moltbook.com/post/def456"
                )
            ]
        else:
            activities = [
                ActivityItem(
                    type="post",
                    title="First post on Moltbook!",
                    content=None,
                    submolt="m/general",
                    upvotes=3,
                    comments=2,
                    timestamp="2026-02-10T10:00:00Z",
                    url="https://moltbook.com/post/mock1"
                )
            ]
        
        return ActivityFeed(
            username=username,
            activities=activities[:limit],
            total_count=len(activities),
            scraped_at=datetime.utcnow().isoformat()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching activity: {str(e)}")


@app.get("/analytics/{username}/timing", response_model=TimingStats)
async def get_timing_analysis(username: str):
    """
    Analyze best posting times based on historical performance.
    
    Args:
        username: Moltbook username
    
    Returns:
        Heatmap of engagement by day/hour, best posting times
    """
    try:
        # For MVP: Return mock timing analysis
        # In production, this would analyze post timestamps vs. engagement
        
        # Mock heatmap data (day -> hour -> avg_engagement)
        heatmap = {
            "Monday": {"6": 5.2, "12": 3.1, "18": 7.5, "22": 4.8},
            "Tuesday": {"6": 4.8, "12": 6.2, "18": 8.1, "22": 5.5},
            "Wednesday": {"6": 5.5, "12": 5.8, "18": 9.2, "22": 6.1},
            "Thursday": {"6": 6.1, "12": 4.5, "18": 7.8, "22": 5.2},
            "Friday": {"6": 4.2, "12": 5.1, "18": 6.5, "22": 8.9},
            "Saturday": {"6": 3.5, "12": 7.2, "18": 5.8, "22": 6.3},
            "Sunday": {"6": 4.1, "12": 6.8, "18": 7.1, "22": 5.9}
        }
        
        # Find best time (highest engagement)
        best_day = "Wednesday"
        best_hour = 18
        
        return TimingStats(
            username=username,
            best_hour=best_hour,
            best_day=best_day,
            heatmap=heatmap,
            total_posts_analyzed=10,
            scraped_at=datetime.utcnow().isoformat()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing timing: {str(e)}")


@app.get("/analytics/{username}/mentions", response_model=MentionsFeed)
async def get_mentions(username: str, limit: int = 20):
    """
    Find posts and comments mentioning @{username}.
    
    Args:
        username: Moltbook username
        limit: Maximum number of mentions to return (default 20)
    
    Returns:
        Feed of mentions with top mentioners
    """
    try:
        # For MVP: Return mock mentions data
        if username.lower() == 'vesperthread':
            mentions = [
                MentionItem(
                    type="comment",
                    author="Rook",
                    title=None,
                    content="@VesperThread has some great security insights!",
                    submolt="m/security",
                    upvotes=8,
                    timestamp="2026-02-11T08:15:00Z",
                    url="https://moltbook.com/post/xyz#comment-123"
                ),
                MentionItem(
                    type="post",
                    author="AgentAlpha",
                    title="Shoutout to @VesperThread",
                    content="Thanks @VesperThread for the analysis on the security scanner!",
                    submolt="m/general",
                    upvotes=12,
                    timestamp="2026-02-10T14:30:00Z",
                    url="https://moltbook.com/post/mention1"
                )
            ]
            top_mentioners = ["Rook", "AgentAlpha"]
        else:
            mentions = []
            top_mentioners = []
        
        return MentionsFeed(
            username=username,
            mentions=mentions[:limit],
            total_count=len(mentions),
            top_mentioners=top_mentioners,
            scraped_at=datetime.utcnow().isoformat()
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching mentions: {str(e)}")


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000)
