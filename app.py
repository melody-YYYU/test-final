from flask import Flask, render_template, jsonify, request, send_from_directory
import os
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# 存放图片的目录
FOLDER_A = "static/images/folder_A"
FOLDER_B = "static/images/folder_B"
EXCEL_FOLDER = "results"  # 存放 Excel 文件
os.makedirs(EXCEL_FOLDER, exist_ok=True)

# 连接 Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name("google_credentials.json", scope)
client = gspread.authorize(creds)
sheet = client.open("SurveyResults").sheet1  # 选择工作表

@app.route("/api/submit", methods=["POST"])
def submit():
    data = request.json
    user_id = data.get("user_id")
    answers = data.get("answers")

    for image_name, score in answers.items():
        sheet.append_row([user_id, image_name, score])

    return jsonify({"status": "success", "message": "数据已保存到 Google Sheets！"})

# 每份问卷的题目数量（每 300 题一组）
QUESTIONS_PER_BATCH = 300

@app.route('/static/<path:filename>')
def serve_static(filename):
    """ 让 Flask 提供静态文件（Render & Railway 需要手动配置）"""
    return send_from_directory("static", filename)

def get_image_pairs():
    """获取两个文件夹中的图片对，并排序"""
    images_A = sorted([f for f in os.listdir(FOLDER_A) if f.endswith((".jpg", ".png", ".JPG"))])
    images_B = sorted([f for f in os.listdir(FOLDER_B) if f.endswith((".jpg", ".png", ".JPG"))])

    return [{"image_name": img_A, "img_A": f"/{FOLDER_A}/{img_A}", "img_B": f"/{FOLDER_B}/{img_B}"}
            for img_A, img_B in zip(images_A, images_B)]

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/images/<int:batch_id>")
def get_images(batch_id):
    """按问卷编号返回 300 题"""
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
    """接收用户评分并保存到 Excel"""
    data = request.json
    user_id = data.get("user_id")
    batch_id = data.get("batch_id")
    answers = data.get("answers")

    user_excel = os.path.join(EXCEL_FOLDER, f"{user_id}_batch_{batch_id}.xlsx")

    records = [{"image_name": img, "score": score} for img, score in answers.items()]
    df_new = pd.DataFrame(records)

    if os.path.exists(user_excel):
        df_old = pd.read_excel(user_excel, engine="openpyxl")
        df = pd.concat([df_old, df_new]).drop_duplicates(subset=["image_name"], keep="last")
    else:
        df = df_new

    df.to_excel(user_excel, index=False, engine="openpyxl")

    total_questions = len(get_image_pairs())
    all_completed = len(df) >= total_questions

    return jsonify({"status": "success", "message": "数据已保存！", "completed": all_completed})

@app.route("/api/load/<user_id>/<int:batch_id>")
def load(user_id, batch_id):
    """加载用户的历史答案"""
    user_excel = os.path.join(EXCEL_FOLDER, f"{user_id}_batch_{batch_id}.xlsx")
    if os.path.exists(user_excel):
        df = pd.read_excel(user_excel, engine="openpyxl")
        answers = dict(zip(df["image_name"], df["score"]))
        return jsonify({"answers": answers})
    return jsonify({"answers": {}})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5005))  # Railway 自动分配端口
    app.run(host="0.0.0.0", port=port)
