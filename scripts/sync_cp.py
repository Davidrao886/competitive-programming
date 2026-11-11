import os
import json
import re
import requests

CF_HANDLE = os.environ.get("CF_HANDLE")
LC_USERNAME = os.environ.get("LC_USERNAME")
SYNCED_FILE = "synced.json"

def clean_slug(text):
    text = re.sub(r'[^a-zA-Z0-9_\s-]', '', text)
    return text.strip().replace(" ", "_")

def load_synced():
    if os.path.exists(SYNCED_FILE):
        with open(SYNCED_FILE, "r") as f:
            return json.load(f)
    return {"codeforces": [], "leetcode": []}

def save_synced(synced_data):
    with open(SYNCED_FILE, "w") as f:
        json.dump({
            "codeforces": sorted(list(set(synced_data["codeforces"]))),
            "leetcode": sorted(list(set(synced_data["leetcode"])))
        }, f, indent=2)

# --- Codeforces Engine ---
def sync_codeforces(synced_ids):
    if not CF_HANDLE:
        print("[CF] No CF_HANDLE configured. Skipping Codeforces.")
        return 0

    print(f"[CF] Fetching Codeforces submissions for: {CF_HANDLE}")
    url = f"https://codeforces.com/api/user.status?handle={CF_HANDLE}&from=1&count=50"
    try:
        res = requests.get(url).json()
    except Exception as e:
        print(f"[CF] Network error: {e}")
        return 0

    if res.get("status") != "OK":
        print(f"[CF] API Error: {res.get('comment')}")
        return 0

    new_count = 0
    accepted = [s for s in res["result"] if s.get("verdict") == "OK" and "contestId" in s["problem"]]

    for sub in reversed(accepted):
        sub_id = sub["id"]
        if sub_id in synced_ids:
            continue

        problem = sub["problem"]
        cid, idx = problem["contestId"], problem["index"]
        name = problem["name"]
        rating = problem.get("rating", 0)
        tags = ", ".join(problem.get("tags", []))

        tier = "Unrated" if not rating else f"{(rating // 200) * 200}-{(rating // 200) * 200 + 199}"
        folder = f"Codeforces/{tier}/{cid}{idx}_{clean_slug(name)}"
        os.makedirs(folder, exist_ok=True)

        with open(os.path.join(folder, "README.md"), "w") as f:
            f.write(f"# [{cid}{idx}] {name}\n\n")
            f.write(f"- **URL:** https://codeforces.com/contest/{cid}/problem/{idx}\n")
            f.write(f"- **Difficulty Rating:** {rating if rating else 'N/A'}\n")
            f.write(f"- **Tags:** `{tags}`\n")
            f.write(f"- **Submission ID:** {sub_id}\n")

        sol_file = os.path.join(folder, "solution.cpp")
        if not os.path.exists(sol_file):
            with open(sol_file, "w") as f:
                f.write(f"// Codeforces Solution: {cid}{idx} - {name}\n")
                f.write(f"// Submission ID: {sub_id}\n\n")

        synced_ids.append(sub_id)
        new_count += 1

    print(f"[CF] Synced {new_count} new problem(s).")
    return new_count

# --- LeetCode Engine ---
def sync_leetcode(synced_slugs):
    if not LC_USERNAME:
        print("[LC] No LC_USERNAME configured. Skipping LeetCode.")
        return 0

    print(f"[LC] Fetching LeetCode recent ACs for: {LC_USERNAME}")
    url = "https://leetcode.com/graphql"
    query = """
    query getRecentAcSubmissions($username: String!) {
        recentAcSubmissionList(username: $username, limit: 30) {
            id
            title
            titleSlug
            timestamp
        }
    }
    """
    payload = {"query": query, "variables": {"username": LC_USERNAME}}
    headers = {"Content-Type": "application/json", "Referer": "https://leetcode.com"}

    try:
        res = requests.post(url, json=payload, headers=headers).json()
    except Exception as e:
        print(f"[LC] Network error: {e}")
        return 0

    submissions = res.get("data", {}).get("recentAcSubmissionList", [])
    if not submissions:
        print("[LC] No submissions found or profile is private.")
        return 0

    detail_query = """
    query getQuestionDetails($titleSlug: String!) {
        question(titleSlug: $titleSlug) {
            questionId
            difficulty
            topicTags { name }
        }
    }
    """
    new_count = 0

    for sub in reversed(submissions):
        slug = sub["titleSlug"]
        if slug in synced_slugs:
            continue

        try:
            q_res = requests.post(
                url, 
                json={"query": detail_query, "variables": {"titleSlug": slug}},
                headers=headers
            ).json()
            q_data = q_res.get("data", {}).get("question", {})
        except Exception:
            q_data = {}

        qid = q_data.get("questionId", "0000").zfill(4)
        difficulty = q_data.get("difficulty", "General")
        tags = ", ".join([t["name"] for t in q_data.get("topicTags", [])])
        title = sub["title"]

        folder = f"LeetCode/{difficulty}/{qid}_{clean_slug(title)}"
        os.makedirs(folder, exist_ok=True)

        with open(os.path.join(folder, "README.md"), "w") as f:
            f.write(f"# {qid}. {title}\n\n")
            f.write(f"- **URL:** https://leetcode.com/problems/{slug}/\n")
            f.write(f"- **Difficulty:** {difficulty}\n")
            f.write(f"- **Tags:** `{tags}`\n")
            f.write(f"- **Last Solved:** {sub['timestamp']}\n")

        sol_file = os.path.join(folder, "solution.cpp")
        if not os.path.exists(sol_file):
            with open(sol_file, "w") as f:
                f.write(f"// LeetCode: {qid}. {title}\n\n")

        synced_slugs.append(slug)
        new_count += 1

    print(f"[LC] Synced {new_count} new problem(s).")
    return new_count

def main():
    synced = load_synced()
    cf_new = sync_codeforces(synced["codeforces"])
    lc_new = sync_leetcode(synced["leetcode"])
    if cf_new > 0 or lc_new > 0:
        save_synced(synced)
    print("Execution complete.")

if __name__ == "__main__":
    main()
