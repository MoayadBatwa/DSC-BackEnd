"""
DSC Backend - Check Followers

Checks if users who commented on DSC tweets are following the club account.

Features:
- Load commenters from previous extraction
- Check if each commenter follows @DSC_KAU
- Generate a report of followers and non-followers
"""

import requests
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
DSC_USERNAME = os.getenv("DSC_USERNAME", "DSC_KAU")

HEADERS = {
    "x-rapidapi-key": RAPIDAPI_KEY,
    "x-rapidapi-host": "twitter241.p.rapidapi.com"
}


def load_commenters_from_json(filename="dsc_comments.json"):
    """
    Load commenters from previously saved comments JSON file.
    Returns a list of unique commenter usernames.
    """
    if not os.path.exists(filename):
        print(f"File {filename} not found!")
        return []
    
    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    commenters = []
    # Handle dictionary structure (tweet_id: {tweet_text, comments})
    for tweet_data in data.values():
        for comment in tweet_data.get("comments", []):
            username = comment.get("username")
            if username and username not in commenters:
                commenters.append(username)
    
    print(f"Found {len(commenters)} unique commenters")
    return commenters


def get_user_id(username):
    """Get user ID from username."""
    url = "https://twitter241.p.rapidapi.com/user"
    params = {"username": username}
    
    response = requests.get(url, headers=HEADERS, params=params)
    
    if response.status_code == 200:
        data = response.json()
        result = data.get("result", {}).get("data", {}).get("user", {}).get("result", {})
        return result.get("rest_id")
    return None


def get_user_followers(user_id, cursor=None):
    """
    Get followers of a user account.
    Returns list of follower usernames.
    """
    url = "https://twitter241.p.rapidapi.com/followers"
    params = {"user": user_id, "count": "200"}
    if cursor:
        params["cursor"] = cursor
    
    response = requests.get(url, headers=HEADERS, params=params)
    
    if response.status_code == 200:
        data = response.json()
        
        followers = []
        next_cursor = data.get("cursor", {}).get("bottom")
        
        # Get timeline instructions
        result = data.get("result", {})
        timeline = result.get("timeline", {})
        instructions = timeline.get("instructions", [])
        
        for instruction in instructions:
            entries = instruction.get("entries", [])
            for entry in entries:
                content = entry.get("content", {})
                item_content = content.get("itemContent", {})
                user_results = item_content.get("user_results", {}).get("result", {})
                
                # Try to get screen_name from core first, then legacy
                core = user_results.get("core", {})
                legacy = user_results.get("legacy", {})
                
                screen_name = core.get("screen_name") or legacy.get("screen_name")
                if screen_name:
                    followers.append(screen_name.lower())
        
        return {"followers": followers, "cursor": next_cursor}
    else:
        print(f"Error fetching followers: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        return {"followers": [], "cursor": None}


def check_commenters_in_followers(commenters, target_user_id, fetch_all=True):
    """
    Check which commenters are in the target's followers list.
    
    Args:
        commenters: List of usernames to check
        target_user_id: The user ID of the target account
        fetch_all: If True, fetch ALL followers (no page limit)
    """
    print("Fetching ALL followers of target account...")
    
    all_followers = []
    cursor = None
    page = 1
    
    # Get ALL followers (no page limit when fetch_all=True)
    while True:
        print(f"  Fetching page {page}...", end=" ")
        result = get_user_followers(target_user_id, cursor)
        followers = result["followers"]
        
        if not followers:
            print("No more followers found.")
            break
            
        all_followers.extend(followers)
        print(f"Got {len(followers)} followers (Total: {len(all_followers)})")
        
        cursor = result["cursor"]
        if not cursor:
            print("  Reached end of followers list.")
            break
        page += 1
        
        # Only apply limit if fetch_all is False
        if not fetch_all and page > 10:
            print("  Reached page limit (10 pages)")
            break
    
    print(f"\n✅ Total followers fetched: {len(all_followers)}")
    
    # Check each commenter
    results = {"followers": [], "non_followers": []}
    
    for username in commenters:
        if username.lower() in all_followers:
            results["followers"].append(username)
        else:
            results["non_followers"].append(username)
    
    return results, all_followers


def check_all_commenters():
    """Main function - Check if all commenters follow the DSC account."""
    print(f"Loading commenters...")
    commenters = load_commenters_from_json()
    
    if not commenters:
        print("No commenters found! Run dsc_extract.py first.")
        return None
    
    print(f"Found commenters: {commenters}")
    
    print(f"\nGetting {DSC_USERNAME} user ID...")
    target_user_id = get_user_id(DSC_USERNAME)
    
    if not target_user_id:
        print(f"Could not find user ID for @{DSC_USERNAME}")
        return None
    
    print(f"Target user ID: {target_user_id}")
    print(f"\n" + "="*50)
    
    # Check by getting followers of target account
    check_results, all_followers = check_commenters_in_followers(commenters, target_user_id)
    
    results = {
        "target_account": DSC_USERNAME,
        "target_user_id": target_user_id,
        "total_commenters": len(commenters),
        "total_followers_checked": len(all_followers),
        "followers": check_results["followers"],
        "non_followers": check_results["non_followers"],
        "unknown": []
    }
    
    # Display results
    print("\n" + "="*50)
    print("CHECKING RESULTS")
    print("="*50)
    
    for username in commenters:
        if username in results["followers"]:
            print(f"  ✓ @{username} follows @{DSC_USERNAME}")
        else:
            print(f"  ✗ @{username} does NOT follow @{DSC_USERNAME}")
    
    # Summary
    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    print(f"Total commenters: {len(commenters)}")
    print(f"Followers: {len(results['followers'])}")
    print(f"Non-followers: {len(results['non_followers'])}")
    
    return results


def display_detailed_results(results):
    """Display detailed report of results."""
    if not results:
        return
    
    print("\n📋 DETAILED REPORT")
    print("="*50)
    
    if results["followers"]:
        print("\n✅ Commenters who follow @" + DSC_USERNAME + ":")
        for username in results["followers"]:
            print(f"   • @{username}")
    
    if results["non_followers"]:
        print("\n❌ Commenters who DON'T follow @" + DSC_USERNAME + ":")
        for username in results["non_followers"]:
            print(f"   • @{username}")
    
    if results["unknown"]:
        print("\n⚠️ Could not verify:")
        for item in results["unknown"]:
            print(f"   • @{item['username']} - {item['reason']}")


def save_results(results):
    """Save results to JSON file."""
    if not results:
        return
    
    with open("dsc_followers_check.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print("Results saved to dsc_followers_check.json")


def main():
    # Validate API key
    if not RAPIDAPI_KEY:
        raise ValueError("RAPIDAPI_KEY not found in .env file!")
    
    print(f"Configuration loaded. Target account: @{DSC_USERNAME}")
    
    # Run the check
    results = check_all_commenters()
    
    # Display detailed results
    display_detailed_results(results)
    
    # Save results
    save_results(results)


if __name__ == "__main__":
    main()
