"""
Canvas to Reminders Sync Tool
-----------------------------

Syncs upcoming assignments from Canvas to Apple Reminders using the Canvas API and AppleScript.
Summarizes assignment descriptions using a local LLM (Ollama) and generates a study plan.

Built by Pratick for personal productivity and demo purposes.
"""

import os
import requests
import subprocess
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from collections import Counter
from dotenv import load_dotenv
import ollama

# Load environment variables (.env file)
def main():
    load_dotenv()
    API_TOKEN = os.getenv("CANVAS_API_TOKEN")
    CANVAS_DOMAIN = os.getenv("CANVAS_DOMAIN")

    if not API_TOKEN or not CANVAS_DOMAIN:
        print("❌ Missing Canvas API token or domain. Make sure you have a .env file or set environment variables.")
        exit(1)

    # Canvas API setup
    headers = {"Authorization": f"Bearer {API_TOKEN}"}
    base_url = f"https://{CANVAS_DOMAIN}/api/v1"
    now = datetime.now(timezone.utc)

    # Mapping from Canvas course names to Apple Reminders list names
    COURSE_TO_LIST = {
        "Design of Artificial Intelligence Products": "05-317",
        "Principles of Functional Programming": "15-150",
        "Ethics and Policy Issues in Computing": "17-200",
        "Business, Society and Ethics": "70-332"
    }

    # Setup summary and strategy cache
    CACHE_FILE = Path("cache/summaries.json")
    STRATEGY_CACHE_FILE = Path("cache/study_strategy.json")
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

    summary_cache = {}
    if CACHE_FILE.exists():
        with open(CACHE_FILE, "r") as f:
            summary_cache = json.load(f)

    strategy_cache = {}
    if STRATEGY_CACHE_FILE.exists():
        with open(STRATEGY_CACHE_FILE, "r") as f:
            strategy_cache = json.load(f)

    COMPLETION_CACHE_FILE = Path("cache/completion.json")
    completion_cache = set()
    if COMPLETION_CACHE_FILE.exists():
        with open(COMPLETION_CACHE_FILE, "r") as f:
            completion_cache = set(json.load(f))

    # Run AppleScript from Python
    def run_applescript(script: str):
        """Run an AppleScript command using osascript."""
        subprocess.run(["osascript", "-e", script])

    # Delete existing reminder (e.g. if assignment already submitted)
    def remove_existing_reminder(title: str, list_name: str):
        """Remove an existing reminder by title from the specified list."""
        script = f'''
        tell application "Reminders"
            set targetList to list "{list_name}"
            set matchingReminders to every reminder in targetList whose name is "{title}"
            repeat with r in matchingReminders
                set completed of r to true
            end repeat
        end tell
        '''
        run_applescript(script)

    # Create new reminder with title, due date, and optional notes
    def add_reminder(title: str, due_str: str, list_name: str, notes: str = ""):
        """Add a new reminder with a title, due date, and optional notes."""
        escaped_notes = notes.replace('"', '\\"')
        script = f'''
        tell application "Reminders"
            set targetList to list "{list_name}"
            set newReminder to make new reminder in targetList
            set name of newReminder to "{title}"
            set due date of newReminder to date "{due_str}"
            set body of newReminder to "{escaped_notes}"
        end tell
        '''
        run_applescript(script)

    # Use LLM to summarize assignment description in one short sentence
    def summarize_description(description: str, assignment_id: str) -> str:
        """Summarize the assignment description into a short sentence."""
        if assignment_id in summary_cache:
            return summary_cache[assignment_id]

        prompt = (
            "Summarize this assignment in one short sentence (max 20 words). "
            "Only return the summary — no intro or explanation.\n\n"
            f"{description.strip()}"
        )

        try:
            response = ollama.chat(model="mistral", messages=[
                {"role": "user", "content": prompt}
            ])
            full = response['message']['content'].strip()
            short = full.split(".")[0].strip()
            words = short.split()
            short = " ".join(words[:20]).strip()
            if short and not short.endswith("."):
                short += "."
            summary_cache[assignment_id] = short
            return short
        except Exception as e:
            print(f"❌ Error summarizing description for assignment {assignment_id}: {e}")
            return ""

    # Generate AI-powered, date-based weekly study plan
    def generate_study_strategy(assignments, avg_days, top_day, urgent_task):
        """Generate a study strategy based on upcoming assignments."""
        all_tasks = []
        for course, tasks in assignments.items():
            for title, due in tasks:
                all_tasks.append((title, course, due))

        all_tasks.sort(key=lambda x: datetime.strptime(x[2], "%m/%d/%Y"))
        task_list = "\n".join([f"- {t[0]} for {t[1]} (due {t[2]})" for t in all_tasks])
        total = len(all_tasks)
        top_course = max(assignments.items(), key=lambda x: len(x[1]))[0]

        today = datetime.now().astimezone()
        upcoming_days = [
            (today + timedelta(days=i)).strftime("%A, %B %d") for i in range(7)
        ]

        prompt = f"""
    You are helping a student plan their assignments across the next 7 days. Here are some stats:

    - {total} total assignments synced
    - Most assignments come from: {top_course}
    - Average days until due: {avg_days:.1f}
    - Most common due day: {top_day}

    Assignments (sorted by due date):
    {task_list}

    Suggest a day-by-day plan using these 7 calendar days:
    {', '.join(upcoming_days)}

    Be specific about which assignments to work on each day.
    Format it like:

    Monday, April 1: Start X, Continue Y  
    Tuesday, April 2: Finish X...

    Keep it brief but helpful — just 1–2 lines per day.
    """

        try:
            response = ollama.chat(model="mistral", messages=[
                {"role": "user", "content": prompt.strip()}
            ])
            return response['message']['content'].strip()
        except Exception as e:
            print(f"❌ Error generating study strategy: {e}")
            return None

    # Fetch favorite Canvas courses
    try:
        res = requests.get(f"{base_url}/users/self/favorites/courses", headers=headers)
        res.raise_for_status()
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to fetch favorite courses: {e}")
        exit()

    # Prepare sync tracking
    favorite_courses = res.json()
    total_added = 0
    added_by_course = {}
    all_due_dates = []
    weekday_counts = Counter()
    closest_assignment = None
    closest_days = float('inf')

    # Loop through each favorite course
    for course in favorite_courses:
        course_id = course.get("id")
        course_name = course.get("name", "Unnamed Course")
        reminder_list = COURSE_TO_LIST.get(course_name)

        if not course_id or not reminder_list:
            continue

        try:
            params = {
                "include[]": ["submission", "all_dates"],
                "per_page": 100
            }
            assignment_res = requests.get(f"{base_url}/courses/{course_id}/assignments", headers=headers, params=params)
            assignment_res.raise_for_status()
        except requests.exceptions.RequestException:
            continue

        assignments = assignment_res.json()
        if not assignments:
            continue

        # Sort assignments by due date
        assignments.sort(key=lambda a: a.get("due_at") or "")

        # Loop through assignments
        for index, assignment in enumerate(assignments, start=1):
            title = assignment.get("name", "No Title")
            due_at = assignment.get("due_at")
            assignment_id = str(assignment.get("id"))

            if assignment_id in completion_cache:
                continue

            submission = assignment.get("submission", {})
            submitted = submission.get("submitted_at") is not None

            if submitted or not due_at:
                continue

            try:
                due_date_utc = datetime.strptime(due_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                if due_date_utc <= now:
                    continue

                local_due = due_date_utc.astimezone()
                apple_due = local_due.strftime("%A, %B %d, %Y at %I:%M:%S %p")
                display_due = local_due.strftime("%m/%d/%Y")

                # Stats tracking
                all_due_dates.append(due_date_utc)
                weekday_counts[due_date_utc.strftime("%A")] += 1
                days_until = (due_date_utc - now).days
                if days_until < closest_days:
                    closest_days = days_until
                    closest_assignment = (title, course_name, due_date_utc.strftime("%m/%d/%Y"))

            except Exception:
                continue

            description = assignment.get("description", "")
            summary = summarize_description(description, assignment_id) if description else ""

            remove_existing_reminder(title, reminder_list)
            add_reminder(title, apple_due, reminder_list, notes=summary)

            # Track completion so we don't re-add completed reminders
            completion_cache.add(assignment_id)

            if course_name not in added_by_course:
                added_by_course[course_name] = []
            added_by_course[course_name].append((title, display_due))
            total_added += 1

    # Save summary cache to disk
    with open(CACHE_FILE, "w") as f:
        json.dump(summary_cache, f, indent=2)

    # Print sync summary
    print("\n🎯 Canvas → Reminders Sync Summary")
    print("-------------------------------------")
    if total_added == 0:
        print("✅ No new assignments to add. You're all caught up!")
    else:
        print(f"✅ {total_added} reminders added:\n")
        for course, assignments in added_by_course.items():
            print(f"📘 {course}:")
            for title, due in assignments:
                print(f"   • {title} (Due {due})")
    print("-------------------------------------\n")

    # Generate or reuse AI study plan
    if total_added > 0 and all_due_dates:
        avg_days = sum((d - now).days for d in all_due_dates) / len(all_due_dates)
        top_day = weekday_counts.most_common(1)[0][0]

        cache_key = "|".join(
            f"{title}-{due}" for course in added_by_course.values() for title, due in course
        )

        if cache_key in strategy_cache:
            suggestion = strategy_cache[cache_key]
        else:
            suggestion = generate_study_strategy(added_by_course, avg_days, top_day, closest_assignment)
            if suggestion:
                strategy_cache[cache_key] = suggestion
                with open(STRATEGY_CACHE_FILE, "w") as f:
                    json.dump(strategy_cache, f, indent=2)

        if suggestion:
            print("🧠 AI Study Suggestion")
            print("-------------------------------------")
            print(suggestion)
            print("-------------------------------------\n")

    # Save completion cache to disk
    with open(COMPLETION_CACHE_FILE, "w") as f:
        json.dump(list(completion_cache), f, indent=2)

if __name__ == "__main__":
    main()
