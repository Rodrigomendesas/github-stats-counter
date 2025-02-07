import requests
import json
import time
from datetime import datetime
    
def get_github_data(owner, repo, endpoint, start_date, end_date, token=None):
    """Fetch data from GitHub API with pagination and retry logic."""
    base_url = f'https://api.github.com/repos/{owner}/{repo}/{endpoint}'
    params = {
        'since': start_date.isoformat() + 'T00:00:00Z',
        'until': end_date.isoformat() + 'T23:59:59Z',
        'per_page': 100
    }
    headers = {}
    if token:
        headers['Authorization'] = f'token {token}'
    
    items = []
    page = 1
    while True:
        params['page'] = page
        response = requests.get(base_url, params=params, headers=headers)
        if response.status_code == 200:
            data = json.loads(response.text)
            items.extend(data)
            if len(data) < params['per_page']:
                break
            page += 1
        elif response.status_code == 403:
            print("Rate limit exceeded. Waiting 60 seconds...")
            time.sleep(60)
            continue
        else:
            print(f"API request failed: {response.status_code}")
            break
    return items

def get_commit_details(owner, repo, sha, token=None):
    """Fetch commit details to get additions/deletions."""
    url = f'https://api.github.com/repos/{owner}/{repo}/commits/{sha}'
    headers = {}
    if token:
        headers['Authorization'] = f'token {token}'
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        commit_data = response.json()
        additions = commit_data.get('stats', {}).get('additions', 0)
        deletions = commit_data.get('stats', {}).get('deletions', 0)
        return additions, deletions
    else:
        print(f"Failed to fetch commit details: {response.status_code}")
        return 0, 0

def get_user_stats_per_endpoint(owner, repo, endpoint, start_date, end_date, token=None):
    """Fetch and count user contributions from GitHub API."""
    items = get_github_data(owner, repo, endpoint, start_date, end_date, token)
    user_stats = {}
    
    for item in items:
        if endpoint == 'pulls':
            user_login = item.get('user', {}).get('login', 'unknown')
        elif endpoint == 'commits':
            user_login = item.get('author', {}).get('login', None)  # Correct extraction
            if not user_login:  # Handle cases where user is missing
                user_login = item.get('commit', {}).get('author', {}).get('name', 'unknown')
        
        if user_login not in user_stats:
            user_stats[user_login] = {'prs': 0, 'commits': 0, 'lines': 0}

        if endpoint == 'pulls':
            user_stats[user_login]['prs'] += 1
            # Fetch PR file details to get actual line changes
            pr_files_url = item.get('url') + '/files'  # API endpoint for PR files
            headers = {'Authorization': f'token {token}'} if token else {}
            pr_response = requests.get(pr_files_url, headers=headers)
            if pr_response.status_code == 200:
                pr_files = pr_response.json()
                user_stats[user_login]['lines'] += sum(f.get('changes', 0) for f in pr_files)
        
        elif endpoint == 'commits':
            # Extract user login (GitHub username) or fallback to author name
            user_login = item.get('author', {}).get('login')  # Try GitHub username

            if not user_login:  # If no GitHub login, fallback to commit author's name
                user_login = item.get('commit', {}).get('author', {}).get('name', 'unknown')

            # Ensure the user exists in stats dictionary
            if user_login not in user_stats:
                user_stats[user_login] = {'prs': 0, 'commits': 0, 'lines': 0}

            # Increment commit count for the user
            user_stats[user_login]['commits'] += 1

            # Fetch commit SHA (unique identifier)
            sha = item.get('sha')

            # Fetch additions & deletions stats from commit details
            additions, deletions = get_commit_details(owner, repo, sha, token)

            # Accumulate total lines changed
            user_stats[user_login]['lines'] += (additions + deletions)
    
    return user_stats


def main():
    url = input("Enter GitHub repository URL: ")
    start_date_str = input("Enter start date (YYYY-MM-DD): ")
    end_date_str = input("Enter end date (YYYY-MM-DD): ")
    token = input("Enter GitHub token (optional): ")

    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError:
        print("Invalid date format. Please use YYYY-MM-DD.")
        return
    
    owner, repo = url.strip().split('/')[-2:]
    
    # Initialize user statistics
    user_stats = {}
    
    # Fetch pull requests per user
    pr_stats = get_user_stats_per_endpoint(owner, repo, 'pulls', start_date, end_date, token)
    for user, stats in pr_stats.items():
        if user not in user_stats:
            user_stats[user] = {'prs': 0, 'commits': 0, 'lines': 0}
        user_stats[user]['prs'] = stats['prs']
        user_stats[user]['lines'] += stats['lines']
    
    # Fetch commits per user
    commit_stats = get_user_stats_per_endpoint(owner, repo, 'commits', start_date, end_date, token)
    for user, stats in commit_stats.items():
        if user not in user_stats:
            user_stats[user] = {'prs': 0, 'commits': 0, 'lines': 0}
        user_stats[user]['commits'] = stats['commits']
        user_stats[user]['lines'] += stats['lines']
    
    # Display user statistics
    if user_stats:
        print("\nContributor Statistics:")
        print("-" * 50)
        sorted_users = sorted(user_stats.items(), key=lambda x: (x[1]['prs'], x[1]['commits'], x[1]['lines']), reverse=True)
        for user, stats in sorted_users:
            prs = stats['prs']
            commits = stats['commits']
            lines = stats['lines']
            print(f"- {user}: {prs} pull requests, {commits} commits, {lines} lines of code changed")
    else:
        print("No contributions found between the specified dates.")

if __name__ == "__main__":
    main()
