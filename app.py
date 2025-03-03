from flask import Flask, render_template, jsonify, request
import random
import os
import pandas as pd

app = Flask(__name__)

# 存放图片的目录
FOLDER_A = "static/images/folder_A"
FOLDER_B = "static/images/folder_B"
EXCEL_FOLDER = "results"  # 存放 Excel 文件
os.makedirs(EXCEL_FOLDER, exist_ok=True)

def get_image_pairs():
    """获取两个文件夹中的图片对，并排序"""
    images_A = sorted([f for f in os.listdir(FOLDER_A) if f.endswith((".jpg", ".png", ".JPG"))])
    images_B = sorted([f for f in os.listdir(FOLDER_B) if f.endswith((".jpg", ".png", ".JPG"))])

    return [{"image_name": img_A, "img_A": f"/{FOLDER_A}/{img_A}", "img_B": f"/{FOLDER_B}/{img_B}"}
            for img_A, img_B in zip(images_A, images_B)]

'''def get_image_pairs():
    """获取两个文件夹中的图片对，并打乱顺序"""
    # 支持更多图片格式
    images_A = sorted([f for f in os.listdir(FOLDER_A) if f.lower().endswith((".jpg", ".jpeg", ".png", ".JPG"))])
    images_B = sorted([f for f in os.listdir(FOLDER_B) if f.lower().endswith((".jpg", ".jpeg", ".png", ".JPG"))])

    # 生成图片对
    image_pairs = [{"image_name": img_A, "img_A": f"/{FOLDER_A}/{img_A}", "img_B": f"/{FOLDER_B}/{img_B}"}
                   for img_A, img_B in zip(images_A, images_B)]

    # 打乱图片对的顺序
    random.shuffle(image_pairs)

    return image_pairs'''

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/images")
def get_images():
    """返回图片对列表"""
    images = get_image_pairs()
    return jsonify({"images": images})

@app.route("/api/submit", methods=["POST"])
def submit():
    """接收用户评分并保存到 Excel"""
    data = request.json
    user_id = data.get("user_id")
    answers = data.get("answers")

    user_excel = os.path.join(EXCEL_FOLDER, f"{user_id}.xlsx")

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

@app.route("/api/load/<user_id>")
def load(user_id):
    """加载用户的历史答案"""
    user_excel = os.path.join(EXCEL_FOLDER, f"{user_id}.xlsx")
    if os.path.exists(user_excel):
        df = pd.read_excel(user_excel, engine="openpyxl")
        answers = dict(zip(df["image_name"], df["score"]))
        return jsonify({"answers": answers})
    return jsonify({"answers": {}})

if __name__ == "__main__":
    app.run(debug=True, port=5001)