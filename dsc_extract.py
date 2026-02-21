"""
DSC Twitter Data Extraction

Extracts tweets and comments from the Data Science Club Twitter account.

Output Files:
- dsc_tweets.json - Tweet data (text, likes, retweets, views, etc.)
- dsc_comments.json - Comments on each tweet

Requirements:
1. Account on RapidAPI (https://rapidapi.com/)
2. Subscription to Twitter241 API
"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ==========================================
TWEET_COUNT = 40  # Number of tweets to extract
# ==========================================

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
DSC_USERNAME = os.getenv("DSC_USERNAME", "DSC_KAU")

HEADERS = {
    "x-rapidapi-key": RAPIDAPI_KEY,
    "x-rapidapi-host": "twitter241.p.rapidapi.com"
}


def get_user_id(username: str) -> str:
    """Get user ID from username"""
    url = "https://twitter241.p.rapidapi.com/user"
    response = requests.get(url, headers=HEADERS, params={"username": username})
    
    if response.status_code != 200:
        print(f"❌ Error: {response.status_code}")
        return None
    
    data = response.json()
    
    if 'result' in data and 'data' in data['result']:
        return data['result']['data']['user']['result']['rest_id']
    elif 'data' in data:
        return data['data']['user']['result']['rest_id']
    
    return None


def get_tweets(user_id: str, count: int) -> list:
    """Get tweets with full engagement metrics (with pagination support)"""
    url = "https://twitter241.p.rapidapi.com/user-tweets"
    tweets = []
    cursor = None
    
    while len(tweets) < count:
        params = {"user": user_id, "count": "40"}
        if cursor:
            params["cursor"] = cursor
        
        response = requests.get(url, headers=HEADERS, params=params)
        
        if response.status_code != 200:
            print(f"❌ Error: {response.status_code}")
            break
        
        data = response.json()
        
        # Extract instructions
        instructions = data.get('result', {}).get('timeline', {}).get('instructions', [])
        if not instructions:
            instructions = data.get('data', {}).get('user', {}).get('result', {}).get('timeline_v2', {}).get('timeline', {}).get('instructions', [])
        
        # Find entries and cursor
        entries = []
        next_cursor = None
        
        for instruction in instructions:
            if 'entries' in instruction:
                entries = instruction['entries']
                break
            elif instruction.get('type') == 'TimelineAddEntries':
                entries = instruction.get('entries', [])
                break
        
        if not entries:
            break
        
        tweets_added = 0
        for entry in entries:
            entry_id = entry.get('entryId', '')
            
            # Look for cursor for pagination
            if 'cursor-bottom' in entry_id.lower():
                cursor_content = entry.get('content', {})
                next_cursor = cursor_content.get('value') or cursor_content.get('itemContent', {}).get('value')
                continue
            
            if 'tweet' not in entry_id.lower():
                continue
            
            try:
                content = entry.get('content', {})
                item_content = content.get('itemContent', {})
                tweet_results = item_content.get('tweet_results', {})
                result = tweet_results.get('result', {})
                
                if result.get('__typename') == 'TweetWithVisibilityResults':
                    result = result.get('tweet', {})
                
                legacy = result.get('legacy', {})
                if not legacy:
                    continue
                
                tweet = {
                    'id': legacy.get('id_str', ''),
                    'text': legacy.get('full_text', ''),
                    'date': legacy.get('created_at', ''),
                    'likes': legacy.get('favorite_count', 0),
                    'retweets': legacy.get('retweet_count', 0),
                    'replies': legacy.get('reply_count', 0),
                    'quotes': legacy.get('quote_count', 0),
                    'bookmarks': legacy.get('bookmark_count', 0),
                    'views': int(result.get('views', {}).get('count', 0) or 0)
                }
                
                # Avoid duplicates
                if tweet['id'] and tweet['id'] not in [t['id'] for t in tweets]:
                    tweets.append(tweet)
                    tweets_added += 1
                    
                    if len(tweets) >= count:
                        break
                
            except Exception:
                continue
        
        # Check if we should continue pagination
        if not next_cursor or tweets_added == 0:
            break
        
        cursor = next_cursor
        print(f"   📄 Fetched {len(tweets)} tweets so far...")
    
    return tweets[:count]


def get_tweet_comments(tweet_id: str, max_comments: int = 20) -> list:
    """Get comments on a specific tweet"""
    url = "https://twitter241.p.rapidapi.com/tweet"
    response = requests.get(url, headers=HEADERS, params={"pid": tweet_id})
    
    if response.status_code != 200:
        return []
    
    data = response.json()
    comments = []
    
    try:
        conversation = data.get('data', {}).get('threaded_conversation_with_injections_v2', {})
        instructions = conversation.get('instructions', [])
        
        entries = []
        for instruction in instructions:
            if instruction.get('type') == 'TimelineAddEntries':
                entries = instruction.get('entries', [])
                break
        
        for entry in entries:
            entry_id = entry.get('entryId', '')
            
            if 'conversationthread' in entry_id.lower():
                items = entry.get('content', {}).get('items', [])
                
                for item in items:
                    try:
                        item_content = item.get('item', {}).get('itemContent', {})
                        tweet_results = item_content.get('tweet_results', {})
                        result = tweet_results.get('result', {})
                        
                        if result.get('__typename') == 'TweetWithVisibilityResults':
                            result = result.get('tweet', {})
                        
                        legacy = result.get('legacy', {})
                        core = result.get('core', {}).get('user_results', {}).get('result', {})
                        user_legacy = core.get('legacy', {})
                        
                        if legacy and legacy.get('id_str') != tweet_id:
                            comment_text = legacy.get('full_text', '')
                            if comment_text:
                                comments.append({
                                    'comment_id': legacy.get('id_str', ''),
                                    'text': comment_text,
                                    'username': user_legacy.get('screen_name', 'Unknown'),
                                    'name': user_legacy.get('name', 'Unknown'),
                                    'likes': legacy.get('favorite_count', 0),
                                    'date': legacy.get('created_at', '')
                                })
                                
                                if len(comments) >= max_comments:
                                    break
                    except:
                        continue
                        
    except Exception:
        pass
    
    return comments


def search_replies(username: str, tweet_ids: list) -> dict:
    """Search for additional replies using search endpoint"""
    url = "https://twitter241.p.rapidapi.com/search-v2"
    response = requests.get(url, headers=HEADERS, params={"query": f"to:{username}", "count": "100", "type": "Latest"})
    
    if response.status_code != 200:
        return {}
    
    data = response.json()
    replies = {tid: [] for tid in tweet_ids}
    
    try:
        instructions = data.get('result', {}).get('timeline', {}).get('instructions', [])
        
        entries = []
        for instruction in instructions:
            if instruction.get('type') == 'TimelineAddEntries':
                entries = instruction.get('entries', [])
                break
        
        for entry in entries:
            if 'tweet' not in entry.get('entryId', '').lower():
                continue
            
            try:
                content = entry.get('content', {})
                item_content = content.get('itemContent', {})
                tweet_results = item_content.get('tweet_results', {})
                result = tweet_results.get('result', {})
                
                if result.get('__typename') == 'TweetWithVisibilityResults':
                    result = result.get('tweet', {})
                
                legacy = result.get('legacy', {})
                core = result.get('core', {}).get('user_results', {}).get('result', {})
                user_legacy = core.get('legacy', {})
                
                in_reply_to = legacy.get('in_reply_to_status_id_str', '')
                
                if in_reply_to in tweet_ids:
                    replies[in_reply_to].append({
                        'comment_id': legacy.get('id_str', ''),
                        'text': legacy.get('full_text', ''),
                        'username': user_legacy.get('screen_name', 'Unknown'),
                        'name': user_legacy.get('name', 'Unknown'),
                        'likes': legacy.get('favorite_count', 0),
                        'date': legacy.get('created_at', '')
                    })
                    
            except:
                continue
                
    except:
        pass
    
    return replies


def main():
    # Validate API key
    if not RAPIDAPI_KEY:
        print("❌ Error: RAPIDAPI_KEY not found in .env file!")
        return
    
    print(f"✅ API Key loaded successfully")
    print(f"✅ Username: @{DSC_USERNAME}")
    print(f"✅ Tweet count: {TWEET_COUNT}")
    
    print(f"\n🔍 Extracting data for @{DSC_USERNAME}...")
    print(f"📊 Tweet count: {TWEET_COUNT}")
    print("=" * 50)
    
    # Step 1: Get user ID
    print("\n🔄 Getting user ID...")
    user_id = get_user_id(DSC_USERNAME)
    
    if not user_id:
        print("❌ Could not find user")
        return
    
    print(f"✅ User ID: {user_id}")
    
    # Step 2: Get tweets
    print(f"\n🔄 Fetching {TWEET_COUNT} tweets...")
    tweets = get_tweets(user_id, TWEET_COUNT)
    
    if not tweets:
        print("❌ No tweets found")
        return
    
    print(f"✅ Found {len(tweets)} tweets")
    
    # Display tweets
    print("\n" + "=" * 50)
    print("📝 TWEETS:")
    print("=" * 50)
    
    for i, tweet in enumerate(tweets, 1):
        text = tweet['text'][:60] + "..." if len(tweet['text']) > 60 else tweet['text']
        print(f"\n{i}. {text}")
        print(f"   ❤️ {tweet['likes']} | 🔄 {tweet['retweets']} | 💬 {tweet['replies']} | 👁️ {tweet['views']:,}")
    
    # Step 3: Get comments for each tweet
    print("\n" + "=" * 50)
    print("💬 EXTRACTING COMMENTS...")
    print("=" * 50)
    
    tweet_ids = [t['id'] for t in tweets]
    all_comments = {}
    
    for i, tweet in enumerate(tweets, 1):
        print(f"\n🔄 Tweet {i}/{len(tweets)}...")
        comments = get_tweet_comments(tweet['id'])
        all_comments[tweet['id']] = {
            'tweet_text': tweet['text'],
            'comments': comments
        }
        print(f"   ✅ Found {len(comments)} comments")
    
    # Step 4: Search for additional replies
    print("\n🔄 Searching for additional replies...")
    search_results = search_replies(DSC_USERNAME, tweet_ids)
    
    for tweet_id, replies in search_results.items():
        if tweet_id in all_comments:
            existing_ids = [c['comment_id'] for c in all_comments[tweet_id]['comments']]
            for reply in replies:
                if reply['comment_id'] not in existing_ids:
                    all_comments[tweet_id]['comments'].append(reply)
    
    # Summary
    total_comments = sum(len(data['comments']) for data in all_comments.values())
    print(f"\n✅ Total comments extracted: {total_comments}")
    
    # Save to JSON files
    print("\n" + "=" * 50)
    print("💾 SAVING DATA...")
    print("=" * 50)
    
    # Save tweets (without id field for cleaner output)
    tweets_output = []
    for t in tweets:
        tweets_output.append({
            'text': t['text'],
            'date': t['date'],
            'likes': t['likes'],
            'retweets': t['retweets'],
            'replies': t['replies'],
            'quotes': t['quotes'],
            'bookmarks': t['bookmarks'],
            'views': t['views']
        })
    
    with open('dsc_tweets.json', 'w', encoding='utf-8') as f:
        json.dump(tweets_output, f, ensure_ascii=False, indent=2)
    print(f"✅ Saved {len(tweets_output)} tweets to: dsc_tweets.json")
    
    with open('dsc_comments.json', 'w', encoding='utf-8') as f:
        json.dump(all_comments, f, ensure_ascii=False, indent=2)
    print(f"✅ Saved {total_comments} comments to: dsc_comments.json")
    
    print("\n" + "=" * 50)
    print("✅ DONE!")
    print("=" * 50)


if __name__ == "__main__":
    main()
