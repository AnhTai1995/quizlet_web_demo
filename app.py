from flask import Flask, render_template, request, redirect, url_for, session, send_file, flash
import os
import csv
import random
import zipfile
from io import BytesIO
from flask_session import Session

app = Flask(__name__)
app.secret_key = 'quizlet-secret'
app.config['SESSION_TYPE'] = 'filesystem'       # ✅ Requireds for session to work
app.config['TEMPLATES_AUTO_RELOAD'] = True      # Help reload template when edit HTML
Session(app)                                     # ✅ Requireds for session to work
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

def save_flashcard(project, english, vietnamese, explanation):
    path = get_file_path(project)
    is_new = not os.path.exists(path)
    with open(path, "a", newline='', encoding="utf-8") as f:
        writer = csv.writer(f)
        if is_new:
            writer.writerow(["English", "Vietnamese", "Explanation"])
        writer.writerow([english, vietnamese, explanation])

def save_all_flashcards(project, flashcards):
    path = get_file_path(project)
    with open(path, "w", newline='', encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["English", "Vietnamese", "Explanation"])
        writer.writeheader()
        writer.writerows(flashcards)

@app.route("/")
def index():
    projects = [f[:-4] for f in os.listdir(DATA_DIR) if f.endswith(".csv")]
    return render_template("index.html", projects=projects)

@app.route("/reset_fill")
def reset_fill():
    session.pop("fill", None)
    return redirect(url_for("index"))

@app.route("/export/<project>")
def export_csv(project):
    path = get_file_path(project)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    return "File not found", 404

@app.route("/delete_project/<project>", methods=["POST"])
def delete_project(project):
    path = get_file_path(project)
    if os.path.exists(path):
        os.remove(path)
    return redirect(url_for("index"))

@app.route("/create_project", methods=["POST"])
def create_project():
    name = request.form["project_name"].strip().replace(" ", "_")
    path = get_file_path(name)
    if not os.path.exists(path):
        with open(path, "w", newline='', encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["English", "Vietnamese", "Explanation"])
    return redirect(url_for("index"))

@app.route("/project/<project>")
def project_view(project):
    flashcards = load_flashcards(project)
    return render_template("project.html", project=project, flashcards=flashcards)

@app.route("/rename_project/<project>", methods=["POST"])
def rename_project(project):
    new_name = request.form.get("new_project_name", "").strip().replace(" ", "_")
    old_path = get_file_path(project)
    new_path = get_file_path(new_name)
    if os.path.exists(old_path) and new_name and not os.path.exists(new_path):
        os.rename(old_path, new_path)
        flash(f"Đã đổi tên project '{project}' thành '{new_name}'")
    else:
        flash("Không thể đổi tên project. Có thể tên đã tồn tại hoặc không hợp lệ.")
    return redirect(url_for("index"))

@app.route("/add_flashcard/<project>", methods=["POST"])
def add_flashcard(project):
    english = request.form["english"].strip()
    vietnamese = request.form["vietnamese"].strip()
    explanation = request.form.get("explanation", "").strip()
    save_flashcard(project, english, vietnamese, explanation)
    return redirect(url_for("project_view", project=project))

@app.route("/edit_flashcard/<project>/<int:index>", methods=["POST"])
def edit_flashcard(project, index):
    flashcards = load_flashcards(project)
    if 0 <= index < len(flashcards):
        flashcards[index]["English"] = request.form["english"].strip()
        flashcards[index]["Vietnamese"] = request.form["vietnamese"].strip()
        flashcards[index]["Explanation"] = request.form.get("explanation", "").strip()
        save_all_flashcards(project, flashcards)
    return redirect(url_for("project_view", project=project))

@app.route("/delete_flashcard/<project>/<int:index>", methods=["POST"])
def delete_flashcard(project, index):
    flashcards = load_flashcards(project)
    if 0 <= index < len(flashcards):
        flashcards.pop(index)
        save_all_flashcards(project, flashcards)
    return redirect(url_for("project_view", project=project))

@app.route("/game/<project>")
def game_choice(project):
    session.pop("quiz", None) # reset game multiple
    session.pop("fill", None) # reset game fill
    # reset flip session
    session.pop(f"flip_cards_{project}", None)
    session.pop(f"flip_index_{project}", None)
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
            "show_result": False,
            "result": None,
            "choices": []
        }

    quiz = session["quiz"]
    index = quiz["index"]
    total = len(quiz["cards"])

    if index >= total:
        result = {"score": quiz["score"], "total": total}
        session.pop("quiz", None)
        session.pop("current_answer", None)
        return render_template("game_multiple_result.html", project=project, result=result)

    current = quiz["cards"][index]
    question = current["Vietnamese"] if lang == "vi" else current["English"]
    answer = current["English"] if lang == "vi" else current["Vietnamese"]

    if request.method == "POST":
        if request.form.get("answer"):
            user_answer = request.form.get("answer")
            is_correct = (user_answer == answer)
            if is_correct:
                quiz["score"] += 1
            quiz["result"] = {
                "is_correct": is_correct,
                "correct_answer": answer,
                "user_answer": user_answer
            }
            quiz["show_result"] = True
            quiz["choices"] = quiz.get("choices", [])
            session["quiz"] = quiz
            session["current_answer"] = answer
            return redirect(url_for("game_multiple", project=project, lang=lang))
        elif request.form.get("action") == "next":
            quiz["index"] += 1
            quiz["show_result"] = False
            quiz["result"] = None
            quiz["choices"] = []
            session["quiz"] = quiz
            return redirect(url_for("game_multiple", project=project, lang=lang))

    if quiz["show_result"]:
        choices = quiz.get("choices", [])
    else:
        pool = [c["English"] if lang == "vi" else c["Vietnamese"]
                for c in cards if (c["English"] if lang == "vi" else c["Vietnamese"]) != answer]
        choices = random.sample(pool, min(3, len(pool))) + [answer]
        random.shuffle(choices)
        quiz["choices"] = choices
        session["quiz"] = quiz
        session["current_answer"] = answer

    return render_template("game_multiple.html",
                           project=project,
                           lang=lang,
                           question=question,
                           choices=choices,
                           result=quiz["result"],
                           index=index + 1,
                           total=total)

@app.route("/game/<project>/fill/<lang>", methods=["GET", "POST"])
def game_fill(project, lang):
    cards = load_flashcards(project)
    cards = [c for c in cards if c["English"] and c["Vietnamese"]]
    if not cards:
        return "Không có flashcard hợp lệ để luyện tập."

    if "fill" not in session:
        session["fill"] = {
            "cards": random.sample(cards, len(cards)),
            "index": 0,
            "correct": 0,
            "show_result": False,
            "result": None
        }

    quiz = session["fill"]
    idx = quiz["index"]
    total = len(quiz["cards"])

    if idx >= total:
        result_summary = {"correct": quiz["correct"], "total": total}
        session.pop("fill", None)
        return render_template("game_fill_result.html", project=project, result=result_summary)

    current = quiz["cards"][idx]
    question = current["Vietnamese"] if lang == "vi" else current["English"]
    answer = current["English"] if lang == "vi" else current["Vietnamese"]

    if request.method == "POST":
        if request.form.get("action") == "next":
            quiz["index"] += 1
            quiz["show_result"] = False
            quiz["result"] = None
            session["fill"] = quiz
            return redirect(url_for("game_fill", project=project, lang=lang))
        user_input = request.form.get("user_answer", "").strip().lower()
        is_correct = (user_input == answer.strip().lower())
        if is_correct:
            quiz["correct"] += 1
        quiz["result"] = (is_correct, answer)
        quiz["show_result"] = True
        session["fill"] = quiz
        return redirect(url_for("game_fill", project=project, lang=lang))

    result = quiz.get("result") if quiz.get("show_result") else None

    return render_template("game_fill.html",
                           project=project,
                           lang=lang,
                           question=question,
                           result=result,
                           index=idx + 1,
                           total=total)

@app.route("/game/<project>/flip")
def game_flip(project):
    cards = load_flashcards(project)
    cards = [c for c in cards if c["English"] and c["Vietnamese"]]
    if not cards:
        flash("Không có flashcard hợp lệ để lật.")
        return redirect(url_for("project_view", project=project))

    flip_key = f"flip_cards_{project}"
    flip_idx_key = f"flip_index_{project}"

    if flip_key not in session or not session.get(flip_key):
        session[flip_key] = random.sample(cards, len(cards))
        session[flip_idx_key] = 0

    flip_cards = session[flip_key]
    idx = session[flip_idx_key]
    current = flip_cards[idx] if idx < len(flip_cards) else None
    session[flip_idx_key] = idx + 1 if idx + 1 < len(flip_cards) else 0

    return render_template("game_flip.html",
                           project=project,
                           cards=[current] if current else [],
                           index=idx + 1,  # to display 1-based index
                           total=len(flip_cards))

@app.route("/export_all")
def export_all():
    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w') as zf:
        for filename in os.listdir(DATA_DIR):
            if filename.endswith(".csv"):
                path = os.path.join(DATA_DIR, filename)
                zf.write(path, arcname=filename)
    memory_file.seek(0)
    return send_file(memory_file, download_name="flashcards_backup.zip", as_attachment=True)

@app.route("/import", methods=["POST"])
def import_zip():
    uploaded_file = request.files.get("zip_file")
    if not uploaded_file or not uploaded_file.filename.endswith(".zip"):
        flash("Vui lòng tải lên tệp .zip hợp lệ")
        return redirect(url_for("index"))

    try:
        with zipfile.ZipFile(uploaded_file) as zf:
            for filename in zf.namelist():
                print(f"📦 Importing file: {filename}")
                if not filename.endswith(".csv"):
                    continue
                content = zf.read(filename).decode("utf-8")
                with open(os.path.join(DATA_DIR, filename), "w", encoding="utf-8") as f:
                    f.write(content)
        flash("✅ Đã import thành công")
    except Exception as e:
        flash(f"❌ Lỗi khi import: {str(e)}")
    
    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(debug=True)
