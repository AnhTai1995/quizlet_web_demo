# app.py (full file with home, project management and games)
from flask import Flask, render_template, request, redirect, url_for, session
import os
import csv
import random

app = Flask(__name__)
app.secret_key = 'quizlet-secret'
DATA_DIR = "data_text"

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def get_file_path(project):
    return os.path.join(DATA_DIR, f"{project}.csv")

def load_flashcards(project):
    path = get_file_path(project)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))

def save_flashcard(project, english, vietnamese):
    path = get_file_path(project)
    is_new = not os.path.exists(path)
    with open(path, "a", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["English", "Vietnamese"])
        writer.writerow([english, vietnamese])

def save_all_flashcards(project, flashcards):
    path = get_file_path(project)
    with open(path, "w", newline='', encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["English", "Vietnamese"])
        writer.writeheader()
        writer.writerows(flashcards)

@app.route("/")
def index():
    projects = [f[:-4] for f in os.listdir(DATA_DIR) if f.endswith(".csv")]
    return render_template("index.html", projects=projects)

@app.route("/create_project", methods=["POST"])
def create_project():
    name = request.form["project_name"].strip().replace(" ", "_")
    path = get_file_path(name)
    if not os.path.exists(path):
        with open(path, "w", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["English", "Vietnamese"])
    return redirect(url_for("index"))

@app.route("/project/<project>")
def project_view(project):
    flashcards = load_flashcards(project)
    return render_template("project.html", project=project, flashcards=flashcards)

@app.route("/add_flashcard/<project>", methods=["POST"])
def add_flashcard(project):
    english = request.form["english"].strip()
    vietnamese = request.form["vietnamese"].strip()
    save_flashcard(project, english, vietnamese)
    return redirect(url_for("project_view", project=project))

@app.route("/edit_flashcard/<project>/<int:index>", methods=["POST"])
def edit_flashcard(project, index):
    flashcards = load_flashcards(project)
    if 0 <= index < len(flashcards):
        flashcards[index]["English"] = request.form["english"].strip()
        flashcards[index]["Vietnamese"] = request.form["vietnamese"].strip()
        save_all_flashcards(project, flashcards)
    return redirect(url_for("project_view", project=project))

# ========== Game Routes ========== #

@app.route("/game/<project>")
def game_choice(project):
    return render_template("game_choice.html", project=project)

@app.route("/game/<project>/multiple/<lang>", methods=["GET", "POST"])
def game_multiple(project, lang):
    cards = load_flashcards(project)
    cards = [c for c in cards if c["English"] and c["Vietnamese"]]
    if len(cards) < 4:
        return "Cần ít nhất 4 flashcards để chơi."

    if "quiz" not in session:
        session["quiz"] = {
            "cards": random.sample(cards, len(cards)),
            "index": 0,
            "score": 0,
            "last_result": None,
            "last_answer": None
        }

    quiz = session["quiz"]
    index = quiz["index"]
    if index >= len(quiz["cards"]):
        result = {"score": quiz["score"], "total": len(quiz["cards"])}
        session.pop("quiz")
        return render_template("game_multiple_result.html", project=project, result=result)

    current = quiz["cards"][index]
    question = current["Vietnamese"] if lang == "vi" else current["English"]
    answer = current["English"] if lang == "vi" else current["Vietnamese"]
    pool = list({c["English"] if lang == "vi" else c["Vietnamese"] for c in cards if (c["English"] if lang == "vi" else c["Vietnamese"]) != answer})
    choices = random.sample(pool, min(3, len(pool))) + [answer]
    random.shuffle(choices)

    if request.method == "POST":
        user_answer = request.form.get("answer")
        is_correct = (user_answer == answer)
        if is_correct:
            quiz["score"] += 1
        quiz["last_result"] = is_correct
        quiz["last_answer"] = user_answer
        quiz["show_answer"] = True
        session["quiz"] = quiz
        return redirect(url_for("game_multiple", project=project, lang=lang))

    show_answer = quiz.pop("show_answer", False)
    last_result = quiz.get("last_result")
    last_answer = quiz.get("last_answer")
    if show_answer:
        quiz["index"] += 1
    session["quiz"] = quiz

    return render_template("game_multiple.html",
                           project=project,
                           lang=lang,
                           question=question,
                           answer=answer,
                           choices=choices,
                           show_answer=show_answer,
                           last_result=last_result,
                           last_answer=last_answer,
                           index=index + 1,
                           total=len(quiz["cards"]))
# Game Fill
@app.route("/game/<project>/fill/<lang>", methods=["GET", "POST"])
def game_fill(project, lang):
    cards = load_flashcards(project)
    cards = [c for c in cards if c["English"] and c["Vietnamese"]]
    if not cards:
        return "Không có flashcard hợp lệ để luyện tập."

    if "fill" not in session:
        session["fill"] = {"cards": random.sample(cards, len(cards)), "index": 0, "correct": 0, "show": False}

    quiz = session["fill"]
    idx = quiz["index"]
    total = len(quiz["cards"])

    # Khi hết flashcards
    if idx >= total:
        result_summary = {"correct": quiz["correct"], "total": total}
        session.pop("fill")
        return render_template("game_fill_result.html", project=project, result=result_summary)

    current = quiz["cards"][idx]
    question = current["Vietnamese"] if lang == "vi" else current["English"]
    answer = current["English"] if lang == "vi" else current["Vietnamese"]
    result = quiz.get("result") if quiz.get("show") else None

    if request.method == "POST":
        if request.form.get("action") == "next":
            quiz["index"] += 1
            quiz["show"] = False
            session["fill"] = quiz
            return redirect(url_for("game_fill", project=project, lang=lang))
        user_input = request.form.get("user_answer", "").strip().lower()
        is_correct = (user_input == answer.strip().lower())
        if is_correct:
            quiz["correct"] += 1
        quiz["result"] = (is_correct, answer)
        quiz["show"] = True
        session["fill"] = quiz
        return redirect(url_for("game_fill", project=project, lang=lang))

    return render_template("game_fill.html", project=project, lang=lang,
                           question=question, result=result,
                           index=idx+1, total=total)

@app.route("/game/<project>/flip")
def game_flip(project):
    cards = load_flashcards(project)
    cards = [c for c in cards if c["English"] and c["Vietnamese"]]

    if "flip_index" not in session:
        session["flip_cards"] = random.sample(cards, len(cards))
        session["flip_index"] = 0

    flip_cards = session["flip_cards"]
    index = session["flip_index"]
    current = flip_cards[index] if index < len(flip_cards) else None

    session["flip_index"] = index + 1 if index + 1 < len(flip_cards) else 0

    return render_template("game_flip.html", project=project, cards=[current] if current else [])

@app.route("/reset_fill")
def reset_fill():
    session.pop("fill_state", None)
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
