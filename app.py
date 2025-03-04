from flask import Flask, render_template, jsonify, request, send_from_directory
import os
import pandas as pd
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.pool import QueuePool  # ✅ 添加这个导入

app = Flask(__name__)

# 读取数据库 URL（优先使用环境变量）
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://survey_db_1x37_user:u9FMPuqQDcZj0sgcjIvMixHtXF4lkUXE@dpg-cv3fuj5umphs73b9mbf0-a.oregon-postgres.render.com/survey_db_1x37")

# ✅ 强制启用 SSL 以防止 Render PostgreSQL 连接问题
if "sslmode" not in DATABASE_URL:
    DATABASE_URL += "?sslmode=require"

# ✅ SQLAlchemy 连接池优化配置
app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
    "poolclass": QueuePool,  # 使用 QueuePool 连接池
    "pool_size": 10,         # 允许最大 10 个连接
    "max_overflow": 5,       # 额外最多创建 5 个连接（超出 pool_size 时）
    "pool_timeout": 30,      # 30 秒超时（如果连接池已满）
    "pool_recycle": 1800,    # 30 分钟后自动回收连接，防止 Render 断开
    "pool_pre_ping": True    # 每次请求前检查连接是否可用
}

db = SQLAlchemy(app)

# 设置图片存放目录
FOLDER_A = "static/images/folder_A"
FOLDER_B = "static/images/folder_B"
EXCEL_FOLDER = "results"
os.makedirs(EXCEL_FOLDER, exist_ok=True)

# 每份问卷的题目数量（每 300 题一组）
QUESTIONS_PER_BATCH = 300

# 定义问卷数据库表
class SurveyResult(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50), nullable=False)
    batch_id = db.Column(db.Integer, nullable=False)
    image_name = db.Column(db.String(100), nullable=False)
    score = db.Column(db.Integer, nullable=False)

# 处理静态文件
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

@app.route("/api/images/<int:batch_id>")
def get_images(batch_id):
    """返回指定批次的 300 题"""
    images = get_image_pairs()
    total_batches = len(images) // QUESTIONS_PER_BATCH + (1 if len(images) % QUESTIONS_PER_BATCH else 0)

    if batch_id > total_batches or batch_id < 1:
        return jsonify({"error": "问卷编号超出范围", "total_batches": total_batches}), 400

    start_index = (batch_id - 1) * QUESTIONS_PER_BATCH
    end_index = start_index + QUESTIONS_PER_BATCH
    images_batch = images[start_index:end_index]

    return jsonify({"images": images_batch, "batch_id": batch_id})

@app.route("/api/submit", methods=["POST"])
def submit():
    """接收用户评分并保存到数据库和 Excel"""
    data = request.json
    user_id = data.get("user_id")
    batch_id = data.get("batch_id")
    answers = data.get("answers")

    # ✅ 存入数据库
    for image_name, score in answers.items():
        existing_entry = SurveyResult.query.filter_by(user_id=user_id, batch_id=batch_id, image_name=image_name).first()
        if existing_entry:
            existing_entry.score = score
        else:
            new_entry = SurveyResult(user_id=user_id, batch_id=batch_id, image_name=image_name, score=score)
            db.session.add(new_entry)
    db.session.commit()

    # ✅ 存入 Excel
    user_excel = os.path.join(EXCEL_FOLDER, f"{user_id}_batch_{batch_id}.xlsx")
    records = [{"image_name": img, "score": score} for img, score in answers.items()]
    df_new = pd.DataFrame(records)

    if os.path.exists(user_excel):
        df_old = pd.read_excel(user_excel, engine="openpyxl")
        df = pd.concat([df_old, df_new]).drop_duplicates(subset=["image_name"], keep="last")
    else:
        df = df_new

    df.to_excel(user_excel, index=False, engine="openpyxl")

    return jsonify({"status": "success", "message": "数据已保存！"})

@app.route("/api/load/<user_id>/<int:batch_id>")
def load(user_id, batch_id):
    """加载用户的历史答案"""
    user_excel = os.path.join(EXCEL_FOLDER, f"{user_id}_batch_{batch_id}.xlsx")
    if os.path.exists(user_excel):
        df = pd.read_excel(user_excel, engine="openpyxl")
        answers = dict(zip(df["image_name"], df["score"]))
        return jsonify({"answers": answers})
    return jsonify({"answers": {}})

# 🔹 初始化数据库（仅首次运行时执行）
with app.app_context():
    db.create_all()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5005))
    app.run(host="0.0.0.0", port=port)
