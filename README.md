# Canvas to Apple Reminders Sync

🎓 Sync all your upcoming Canvas assignments directly into Apple Reminders — organized by course, with due dates and AI-generated summaries.

## 🚀 Features

- ✅ Pulls your upcoming assignments from Canvas using their API
- 🧠 Summarizes assignment descriptions with a local LLM (Ollama)
- 📅 Adds reminders in macOS Reminders, organized by course
- 📊 Creates an AI-powered, date-based weekly study plan
- 💾 Caches summaries + strategy for speed and efficiency
- 🔒 Keeps your API token secure in a `.env` file

## 📂 Project Structure

```
canvasToReminders/
├── main.py                # The main script
├── .env                   # Your secrets (ignored from Git)
├── example.env            # Sample environment config
├── requirements.txt       # Python dependencies
├── .gitignore             # Files to exclude from Git
└── cache/                 # LLM summary + strategy cache
```

## ⚙️ Setup Instructions

1. **Clone the repo**

```bash
git clone git@github.com:yourusername/canvas-to-reminders.git
cd canvas-to-reminders
```

2. **Create your `.env` file**

```bash
cp example.env .env
# Then open `.env` and paste your Canvas API token and domain
```

3. **Create and activate a virtual environment**

```bash
python3 -m venv venv
source venv/bin/activate
```

4. **Install dependencies**

```bash
pip install -r requirements.txt
```

5. **Run the script**

```bash
python3 main.py
```

Your assignments will be added to Reminders, and an AI-generated study plan will be printed in your terminal.

---

## 🤖 Local LLM: Ollama

This script uses a local AI model via [Ollama](https://ollama.com) to summarize assignments and generate a study strategy.

To install:

```bash
brew install ollama
ollama run mistral
```

---

## 🧠 Sample Output

```bash
🎯 Canvas → Reminders Sync Summary
✅ 7 reminders added:
📘 Ethics and Policy Issues in Computing:
   • Week 11 Reflection (Due 04/01/2025 23:59)
...

🧠 AI Study Suggestion
Monday, April 1: Start Reflection, review Functional HW
Tuesday, April 2: Finish Reflection, work on BSE write-up
...
```

---

## 🔒 Security Note

Make sure to never commit your `.env` file. It's excluded by `.gitignore` automatically.

---

## 📬 Questions?

Reach out at [pkafley@andrew.cmu.edu] or file an issue on GitHub.
