# app.py
import streamlit as st
import pandas as pd
import os
import io

# ---------------- CONFIG ----------------
GITHUB_USER = "phrapine16"
GITHUB_REPO = "design-thinking"
GITHUB_BRANCH = "main"
STUDENTS_RAW_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}/data/students.csv"

LOCAL_DATA_DIR = "/tmp"
RESPONSES_LOCAL_PATH = os.path.join(LOCAL_DATA_DIR, "responses.csv")

# simple teacher credentials
DEFAULT_TEACHERS = {"teacher": "1234"}

# ---------------- HELPERS ----------------
def ensure_local_dir():
    os.makedirs(LOCAL_DATA_DIR, exist_ok=True)

def load_students():
    try:
        df = pd.read_csv(STUDENTS_RAW_URL, dtype=str)
        df = df[["StudentID", "Name"]].astype(str)
        return df
    except:
        st.error("โหลด students.csv จาก GitHub ไม่สำเร็จ")
        return pd.DataFrame(columns=["StudentID","Name"])

def load_responses():
    """โหลด responses.csv และแก้ให้มีคอลัมน์ครบเสมอ"""
    ensure_local_dir()

    required_cols = ["StudentID", "Name", "Activity", "Answer", "Score", "Status"]

    if os.path.exists(RESPONSES_LOCAL_PATH):
        try:
            df = pd.read_csv(RESPONSES_LOCAL_PATH, dtype=str)

            # เติมคอลัมน์ที่หายไป
            for c in required_cols:
                if c not in df.columns:
                    df[c] = ""

            # เรียงคอลัมน์
            df = df[required_cols]

            return df
        except:
            pass

    # ถ้าไฟล์พังหรือไม่มี → สร้างใหม่
    df = pd.DataFrame(columns=required_cols)
    df.to_csv(RESPONSES_LOCAL_PATH, index=False)
    return df

def save_responses(df):
    ensure_local_dir()
    df.to_csv(RESPONSES_LOCAL_PATH, index=False)

def upsert_response(student_id, name, activity, answer):
    """ถ้ากิจกรรมซ้ำ → ทับ, ถ้าใหม่ → เพิ่ม"""
    df = load_responses()
    mask = (df["StudentID"] == student_id) & (df["Activity"] == activity)

    if mask.any():
        idx = df[mask].index[0]
        df.at[idx, "Name"] = name
        df.at[idx, "Answer"] = answer
        df.at[idx, "Score"] = ""
        df.at[idx, "Status"] = "รอตรวจ"
    else:
        df = pd.concat([
            df,
            pd.DataFrame([{
                "StudentID": student_id,
                "Name": name,
                "Activity": activity,
                "Answer": answer,
                "Score": "",
                "Status": "รอตรวจ"
            }])
        ], ignore_index=True)

    save_responses(df)

def update_score(student_id, activity, score_value):
    df = load_responses()
    mask = (df["StudentID"] == student_id) & (df["Activity"] == activity)

    if mask.any():
        idx = df[mask].index[0]
        df.at[idx, "Score"] = score_value
        df.at[idx, "Status"] = "ตรวจแล้ว"
        save_responses(df)
        return True
    return False

def sanitize(s):
    import re
    s = str(s).strip()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^\w\-]", "", s)
    return s


def build_summary(students_df, responses_df):
    """สร้างตารางสรุปแบบกว้าง (wide)"""
    if responses_df.empty:
        out = students_df.copy()
        out["Summary_TotalScore"] = pd.NA
        out["Summary_Completed"] = 0
        out["Summary_Status"] = "ยังไม่ส่ง"
        return out

    activities = responses_df["Activity"].unique().tolist()

    summary = students_df.copy()

    for act in activities:
        san = sanitize(act)
        answer_col = f"Answer_{san}"
        score_col = f"Score_{san}"
        status_col = f"Status_{san}"

        sub = responses_df[responses_df["Activity"] == act]

        map_answer = dict(zip(sub["StudentID"], sub["Answer"]))
        map_score  = dict(zip(sub["StudentID"], sub["Score"]))
        map_status = dict(zip(sub["StudentID"], sub["Status"]))

        summary[answer_col] = summary["StudentID"].map(map_answer)
        summary[score_col]  = summary["StudentID"].map(map_score)
        summary[status_col] = summary["StudentID"].map(map_status)

    # ---- TotalScore ----
    score_cols = [c for c in summary.columns if c.startswith("Score_")]

    def total(row):
        s = 0
        found = False
        for c in score_cols:
            v = row[c]
            if v not in [None, "", "nan", "None"] and pd.notna(v):
                try:
                    s += float(v)
                    found = True
                except:
                    pass
        return int(s) if found else pd.NA

    summary["Summary_TotalScore"] = summary.apply(total, axis=1)

    # ---- Completed Count ----
    status_cols = [c for c in summary.columns if c.startswith("Status_")]

    def count_done(row):
        return sum(
            1 for c in status_cols
            if str(row[c]).strip() not in ["", "ยังไม่ส่ง", "None", "nan"]
        )

    summary["Summary_Completed"] = summary.apply(count_done, axis=1)
    summary["Summary_Status"] = summary["Summary_Completed"].apply(
        lambda x: "ยังไม่ส่ง" if x == 0 else "มีผลการตรวจ"
    )

    return summary


# ---------------- UI ----------------
st.set_page_config(page_title="Student Activity System", layout="wide")
st.title("📘 ระบบส่งงานตามกิจกรรม — Student / Teacher")

if "teacher_logged" not in st.session_state:
    st.session_state.teacher_logged = False

# Tabs
tabs = st.tabs(["Student", "Teacher", "Summary"])

# -------- Student Tab --------
with tabs[0]:
    st.header("👨‍🎓 Student — ส่งงาน")
    st.info("กรอก Student ID, ชื่อกิจกรรม และคำตอบ หากส่งกิจกรรมเดิมจะทับงานเดิม")

    students_df = load_students()

    with st.form("student_form", clear_on_submit=True):
        sid = st.text_input("Student ID (เช่น S001)").strip()
        activity = st.text_input("ชื่อกิจกรรม (เช่น กิจกรรมที่ 1)").strip()
        answer = st.text_area("คำตอบ (Essay)")
        ok = st.form_submit_button("ส่งงาน")

    if ok:
        if sid == "" or activity == "":
            st.error("กรุณากรอกข้อมูลให้ครบ")
        elif sid not in students_df["StudentID"].values:
            st.error("ไม่พบ Student ID นี้ในระบบ")
        else:
            name = students_df.loc[students_df["StudentID"] == sid, "Name"].values[0]
            upsert_response(sid, name, activity, answer)
            st.success("ส่งงานสำเร็จ!")

# -------- Teacher Tab --------
with tabs[1]:
    st.header("👨‍🏫 Teacher — ให้คะแนน")
    students_df = load_students()
    resp_df = load_responses()

    st.subheader("📄 งานที่ส่งทั้งหมด")
    st.dataframe(resp_df, use_container_width=True)

    st.subheader("ให้คะแนน")
    sid_list = students_df["StudentID"].tolist()
    sid = st.selectbox("เลือก StudentID", sid_list)

    sub = resp_df[resp_df["StudentID"] == sid]

    if sub.empty:
        st.warning("ยังไม่มีงานส่ง")
    else:
        activity_list = sub["Activity"].tolist()
        act = st.selectbox("เลือกกิจกรรม", activity_list)

        row = sub[sub["Activity"] == act].iloc[0]
        st.write("**คำตอบ:**")
        st.info(row["Answer"])

        new_score = st.text_input("คะแนน", value=row["Score"])
        if st.button("บันทึกคะแนน"):
            update_score(sid, act, new_score)
            st.success("บันทึกคะแนนแล้ว")

# -------- Summary Tab --------
with tabs[2]:
    st.header("📊 Summary")
    students_df = load_students()
    resp_df = load_responses()

    summary = build_summary(students_df, resp_df)

    st.subheader("📌 ตารางสรุป")
    st.dataframe(summary, use_container_width=True)

    # Export Excel
    st.subheader("📤 Download Excel")
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        summary.to_excel(writer, index=False, sheet_name="Summary")
    st.download_button(
        "ดาวน์โหลด Summary.xlsx",
        data=output.getvalue(),
        file_name="summary.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
