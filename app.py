from flask import Flask, render_template, jsonify, request, send_from_directory
import os
import pandas as pd
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.pool import QueuePool

app = Flask(__name__)

# 读取数据库 URL（优先使用环境变量）
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://survey_db_1x37_user:u9FMPuqQDcZj0sgcjIvMixHtXF4lkUXE@dpg-cv3fuj5umphs73b9mbf0-a.oregon-postgres.render.com/survey_db_1x37")

if "sslmode" not in DATABASE_URL:
    DATABASE_URL += "?sslmode=require"

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "poolclass": QueuePool,
    "pool_size": 10,
    "max_overflow": 5,
    "pool_timeout": 30,
    "pool_recycle": 1800,
    "pool_pre_ping": True
}

db = SQLAlchemy(app)

# 设置图片存放目录
FOLDER_A = "static/images/folder_A"
FOLDER_B = "static/images/folder_B"
EXCEL_FOLDER = "results"
os.makedirs(EXCEL_FOLDER, exist_ok=True)

# ✅ 每份问卷的题目数量（每 300 题一组），每页 20 题
QUESTIONS_PER_BATCH = 300
QUESTIONS_PER_PAGE = 20

# 数据库表
class SurveyResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), nullable=False)
    batch_id = db.Column(db.Integer, nullable=False)
    image_name = db.Column(db.String(100), nullable=False)
    score = db.Column(db.Integer, nullable=False)

@app.route('/static/<path:filename>')
def serve_static(filename):
    return send_from_directory("static", filename)

def get_image_pairs():
    """获取图片对，并排序"""
    images_A = sorted([f for f in os.listdir(FOLDER_A) if f.endswith((".jpg", ".png", ".JPG"))])
    images_B = sorted([f for f in os.listdir(FOLDER_B) if f.endswith((".jpg", ".png", ".JPG"))])
    return [{"image_name": img_A, "img_A": f"/{FOLDER_A}/{img_A}", "img_B": f"/{FOLDER_B}/{img_B}"}
            for img_A, img_B in zip(images_A, images_B)]

@app.route("/")
def index():
    return render_template("index.html")

# ✅ 按批次 & 分页返回问卷数据
@app.route("/api/images/<int:batch_id>/<int:page>")
def get_images(batch_id, page):
    """返回指定批次的 20 题（分页）"""
    images = get_image_pairs()
    total_batches = len(images) // QUESTIONS_PER_BATCH + (1 if len(images) % QUESTIONS_PER_BATCH else 0)

    if not images:
        return jsonify({"error": "没有找到可用的图片数据，请检查文件夹路径"}), 404

    total_batches = len(images) // QUESTIONS_PER_BATCH + (1 if len(images) % QUESTIONS_PER_BATCH else 0)

    if batch_id > total_batches or batch_id < 1:
        return jsonify({"error": "问卷编号超出范围", "total_batches": total_batches}), 400

    start_index = (batch_id - 1) * QUESTIONS_PER_BATCH
    end_index = start_index + QUESTIONS_PER_BATCH
    images_batch = images[start_index:end_index]

    total_pages = len(images_batch) // QUESTIONS_PER_PAGE + (1 if len(images_batch) % QUESTIONS_PER_PAGE else 0)

    if page > total_pages or page < 1:
        return jsonify({"error": "页码超出范围", "total_pages": total_pages}), 400

    page_start = (page - 1) * QUESTIONS_PER_PAGE
    page_end = page_start + QUESTIONS_PER_PAGE
    images_page = images_batch[page_start:page_end]

    return jsonify({"images": images_page, "batch_id": batch_id, "page": page, "total_pages": total_pages})

@app.route("/api/submit", methods=["POST"])
def submit():
    """保存当前页的问卷答案"""
    data = request.json
    user_id = data.get("user_id")
    batch_id = data.get("batch_id")
    answers = data.get("answers")

    for image_name, score in answers.items():
        existing_entry = SurveyResult.query.filter_by(user_id=user_id, batch_id=batch_id, image_name=image_name).first()
        if existing_entry:
            existing_entry.score = score
        else:
            new_entry = SurveyResult(user_id=user_id, batch_id=batch_id, image_name=image_name, score=score)
            db.session.add(new_entry)
    db.session.commit()

    return jsonify({"status": "success", "message": "数据已保存！"})

@app.route("/api/load/<user_id>/<int:batch_id>")
def load(user_id, batch_id):
    """加载用户已填的答案"""
    results = SurveyResult.query.filter_by(user_id=user_id, batch_id=batch_id).all()
    answers = {entry.image_name: entry.score for entry in results}
    return jsonify({"answers": answers})

with app.app_context():
    db.create_all()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5005))
    app.run(host="0.0.0.0", port=port)
