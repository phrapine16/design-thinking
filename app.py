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

DEFAULT_TEACHERS = {"teacher": "1234"}

# ---------------- HELPERS ----------------
def ensure_local_dir():
    if not os.path.isdir(LOCAL_DATA_DIR):
        os.makedirs(LOCAL_DATA_DIR, exist_ok=True)

def load_students():
    try:
        df = pd.read_csv(STUDENTS_RAW_URL, dtype=str)
        return df[["StudentID", "Name"]].astype(str)
    except:
        return pd.DataFrame(columns=["StudentID", "Name"])

def load_responses():
    ensure_local_dir()
    if os.path.exists(RESPONSES_LOCAL_PATH):
        try:
            return pd.read_csv(RESPONSES_LOCAL_PATH, dtype=str)
        except:
            pass
    df = pd.DataFrame(columns=["StudentID", "Name", "Activity", "Answer", "Score"])
    df.to_csv(RESPONSES_LOCAL_PATH, index=False)
    return df

def save_responses(df):
    ensure_local_dir()
    df.to_csv(RESPONSES_LOCAL_PATH, index=False)

def upsert_response(student_id, name, activity, answer):
    df = load_responses()
    mask = (df["StudentID"] == student_id) & (df["Activity"] == activity)

    if mask.any():
        idx = mask.idxmax()
        df.at[idx, "Answer"] = answer
        df.at[idx, "Name"] = name
        df.at[idx, "Score"] = ""
    else:
        df.loc[len(df)] = [student_id, name, activity, answer, ""]
    save_responses(df)

def sanitize_col(s):
    import re
    s = str(s)
    s = re.sub(r"\s+", "_", s.strip())
    return re.sub(r"[^\w\-]", "", s)

def build_wide_summary(students_df, responses_df):
    if responses_df.empty:
        out = students_df.copy()
        out["TotalScore"] = ""
        return out

    activities = responses_df["Activity"].unique().tolist()
    summary = students_df.copy()

    for act in activities:
        san = sanitize_col(act)
        score_col = f"Score_{san}"
        answer_col = f"Answer_{san}"

        sub = responses_df[responses_df["Activity"] == act]

        mapping_score = {r["StudentID"]: r["Score"] for _, r in sub.iterrows()}
        mapping_answer = {r["StudentID"]: r["Answer"] for _, r in sub.iterrows()}

        summary[score_col] = summary["StudentID"].map(mapping_score)
        summary[answer_col] = summary["StudentID"].map(mapping_answer)

    score_cols = [c for c in summary.columns if c.startswith("Score_")]

    def calc_total(row):
        total = 0
        found = False
        for c in score_cols:
            v = row[c]
            if pd.isna(v) or v == "":
                continue
            try:
                total += float(v)
                found = True
            except:
                continue
        return int(total) if found else ""

    summary["TotalScore"] = summary.apply(calc_total, axis=1)
    return summary

# ---------------- UI ----------------
st.set_page_config(page_title="Student / Teacher System", layout="wide")
st.title("📘 Student / Teacher – Activity Submission")

# SESSION
if "teacher_logged" not in st.session_state:
    st.session_state.teacher_logged = False

# TABS
tabs = st.tabs(["Student", "Teacher", "Summary"])

# ---------------- Student Tab ----------------
with tabs[0]:
    st.header("👨‍🎓 Student – ส่งงาน")

    students_df = load_students()
    sid = st.text_input("Student ID (เช่น S001)")
    activity = st.text_input("ชื่อกิจกรรม (เช่น กิจกรรมที่ 1)")
    answer = st.text_area("คำตอบ")

    if st.button("ส่งงาน"):
        if sid not in students_df["StudentID"].values:
            st.error("ไม่พบ Student ID นี้")
        elif activity.strip() == "":
            st.error("กรุณากรอกชื่อกิจกรรม")
        else:
            name = students_df.loc[students_df["StudentID"] == sid, "Name"].values[0]
            upsert_response(sid, name, activity, answer)
            st.success("ส่งงานสำเร็จ")

# ---------------- Teacher Tab ----------------
with tabs[1]:
    if not st.session_state.teacher_logged:
        st.header("🔐 Teacher Login")
        user = st.text_input("Username")
        pw = st.text_input("Password", type="password")

        if st.button("เข้าสู่ระบบ"):
            if user in DEFAULT_TEACHERS and pw == DEFAULT_TEACHERS[user]:
                st.session_state.teacher_logged = True
                st.rerun()
            else:
                st.error("เข้าสู่ระบบไม่สำเร็จ")
    else:
        st.header("👨‍🏫 Teacher – ให้คะแนน (แก้ได้เลยในตาราง)")

        df = load_responses()

        st.write("**ตารางงานที่ส่งทั้งหมด**")
        edited = st.data_editor(
            df,
            num_rows="dynamic",
            hide_index=True,
            key="editor"
        )

        if st.button("💾 บันทึกคะแนนทั้งหมด"):
            save_responses(pd.DataFrame(edited))
            st.success("บันทึกสำเร็จ!")

# ---------------- Summary Tab ----------------
with tabs[2]:
    st.header("📊 Summary – ผลรวมกิจกรรมทั้งหมด")

    students_df = load_students()
    resp_df = load_responses()
    wide = build_wide_summary(students_df, resp_df)

    st.dataframe(wide)

    # EXPORT
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        wide.to_excel(writer, index=False, sheet_name="Summary")
    st.download_button("ดาวน์โหลด Excel Summary", output.getvalue(),
                       "summary.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
