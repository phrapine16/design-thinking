# app.py
import streamlit as st
import pandas as pd
import os
import io

# ---------------- CONFIG ----------------
GITHUB_USER = "phrapine16"
GITHUB_REPO = "design-thinking"
GITHUB_BRANCH = "main"
STUDENTS_RAW_URL = (
    f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}/data/students.csv"
)

LOCAL_DATA_DIR = "/tmp"
RESPONSES_LOCAL_PATH = os.path.join(LOCAL_DATA_DIR, "responses.csv")

# simple teacher credentials
DEFAULT_TEACHERS = {"teacher": "1234"}


# ---------------- HELPERS ----------------
def ensure_local_dir():
    if not os.path.isdir(LOCAL_DATA_DIR):
        os.makedirs(LOCAL_DATA_DIR, exist_ok=True)


def load_students():
    try:
        df = pd.read_csv(STUDENTS_RAW_URL, dtype=str)
        if "StudentID" not in df.columns or "Name" not in df.columns:
            st.error("ไฟล์ students.csv ต้องมีคอลัมน์ StudentID และ Name")
            return pd.DataFrame(columns=["StudentID", "Name"])
        return df[["StudentID", "Name"]].astype(str)
    except Exception as e:
        st.error("โหลด students.csv ไม่ได้: " + str(e))
        return pd.DataFrame(columns=["StudentID", "Name"])


def load_responses():
    ensure_local_dir()
    if os.path.exists(RESPONSES_LOCAL_PATH):
        try:
            df = pd.read_csv(RESPONSES_LOCAL_PATH, dtype=str)
            return df
        except Exception:
            pass

    df = pd.DataFrame(columns=["StudentID", "Name", "Activity", "Answer", "Score"])
    df.to_csv(RESPONSES_LOCAL_PATH, index=False)
    return df


def save_responses(df):
    ensure_local_dir()
    df.to_csv(RESPONSES_LOCAL_PATH, index=False)


# ---------- อัปเดตหรือเพิ่มงาน ----------
def upsert_response(student_id, name, activity, answer):
    df = load_responses()

    # ป้องกัน mismatch columns
    for col in ["StudentID", "Name", "Activity", "Answer", "Score"]:
        if col not in df.columns:
            df[col] = ""

    mask = (df["StudentID"] == student_id) & (df["Activity"] == activity)

    if mask.any():  
        idx = mask.idxmax()
        df.at[idx, "Answer"] = answer
        df.at[idx, "Name"] = name
        df.at[idx, "Score"] = ""   # reset score เมื่อส่งใหม่
    else:
        new_row = {
            "StudentID": student_id,
            "Name": name,
            "Activity": activity,
            "Answer": answer,
            "Score": "",
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    save_responses(df)


# ---------- อัปเดตคะแนน ----------
def update_score(student_id, activity, score_value):
    df = load_responses()
    mask = (df["StudentID"] == student_id) & (df["Activity"] == activity)

    if mask.any():
        idx = mask.idxmax()
        df.at[idx, "Score"] = str(score_value)
        save_responses(df)
        return True
    return False


def sanitize_col(s):
    import re

    s = str(s)
    s = re.sub(r"\s+", "_", s.strip())
    s = re.sub(r"[^\w\-]", "", s)
    return s


# ---------------- SUMMARY ----------------
def build_wide_summary(students_df, responses_df):
    if responses_df.empty:
        out = students_df.copy()
        out["TotalScore"] = ""
        return out

    activities = sorted(responses_df["Activity"].astype(str).unique())

    summary = students_df.copy()

    for act in activities:
        san = sanitize_col(act)

        ans_col = f"Answer_{san}"
        score_col = f"Score_{san}"

        sub = responses_df[responses_df["Activity"] == act]

        summary[ans_col] = summary["StudentID"].map(
            sub.set_index("StudentID")["Answer"]
        )
        summary[score_col] = summary["StudentID"].map(
            sub.set_index("StudentID")["Score"]
        )

    score_cols = [c for c in summary.columns if c.startswith("Score_")]

    def calc_total(row):
        total = 0
        found = False
        for c in score_cols:
            v = row.get(c, "")
            try:
                if v != "" and pd.notna(v):
                    total += float(v)
                    found = True
            except:
                pass
        return int(total) if found else ""

    summary["TotalScore"] = summary.apply(calc_total, axis=1)

    return summary


# ---------------- UI ----------------
st.set_page_config(page_title="Student / Teacher Activities", layout="wide")
st.title("📘 ระบบส่งงาน และให้คะแนนตามกิจกรรม")

# session
if "teacher_logged" not in st.session_state:
    st.session_state.teacher_logged = False
if "teacher_user" not in st.session_state:
    st.session_state.teacher_user = None

# logout
colL, colR = st.columns([3, 1])
with colR:
    if st.session_state.teacher_logged and st.button("Logout"):
        st.session_state.teacher_logged = False
        st.rerun()


# Tabs
if st.session_state.teacher_logged:
    tabs = st.tabs(["Student", "Teacher", "Summary"])
else:
    tabs = st.tabs(["Student", "Teacher Login"])


# ---------------- Student ----------------
with tabs[0]:
    st.header("👨‍🎓 ส่งงานนักศึกษา")
    st.info("กรอก Student ID, ชื่อกิจกรรม, คำตอบ (Essay). ส่งซ้ำจะทับงานเดิม")

    students_df = load_students()

    with st.form("student_form", clear_on_submit=True):
        sid = st.text_input("Student ID (เช่น S001)").strip()
        activity = st.text_input("ชื่อกิจกรรม").strip()
        answer = st.text_area("คำตอบ (Essay)")
        btn = st.form_submit_button("ส่งงาน")

    if btn:
        if sid == "" or activity == "":
            st.error("กรุณากรอก Student ID และ Activity")
        elif sid not in students_df["StudentID"].values:
            st.error("ไม่พบนักศึกษาในไฟล์ students.csv")
        else:
            name = students_df.loc[students_df["StudentID"] == sid, "Name"].values[0]
            upsert_response(sid, name, activity, answer)
            st.success("ส่งงานสำเร็จ!")


# ---------------- Teacher Login ----------------
if not st.session_state.teacher_logged:
    with tabs[1]:
        st.header("🔐 Teacher Login")
        with st.form("login"):
            user = st.text_input("Username")
            pw = st.text_input("Password", type="password")
            ok = st.form_submit_button("เข้าสู่ระบบ")

        if ok:
            teachers = DEFAULT_TEACHERS
            if user in teachers and teachers[user] == pw:
                st.session_state.teacher_logged = True
                st.session_state.teacher_user = user
                st.rerun()
            else:
                st.error("Username หรือ Password ไม่ถูกต้อง")


# ---------------- Teacher ----------------
if st.session_state.teacher_logged:
    with tabs[1]:
        st.header("👨‍🏫 ให้คะแนน")

        resp_df = load_responses()
        st.subheader("งานที่ส่งทั้งหมด")
        st.dataframe(resp_df, use_container_width=True)

        st.subheader("ให้คะแนน")
        sid_list = resp_df["StudentID"].unique().tolist()
        selected_sid = st.selectbox("เลือก Student ID", sid_list)

        sub = resp_df[resp_df["StudentID"] == selected_sid]

        if not sub.empty:
            act_list = sub["Activity"].tolist()
            selected_act = st.selectbox("เลือก Activity", act_list)

            row = sub[sub["Activity"] == selected_act].iloc[0]
            st.markdown("### คำตอบที่ส่งมา")
            st.write(row["Answer"])

            new_score = st.text_input("คะแนน", value=str(row.get("Score", "")))

            if st.button("บันทึกคะแนน"):
                update_score(selected_sid, selected_act, new_score)
                st.success("อัปเดตคะแนนแล้ว")
                st.rerun()


# ---------------- Summary ----------------
if st.session_state.teacher_logged:
    with tabs[2]:
        st.header("📊 Summary — สรุปคะแนนทุกกิจกรรม")

        students_df = load_students()
        resp_df = load_responses()

        wide = build_wide_summary(students_df, resp_df)
        st.dataframe(wide, use_container_width=True)

        st.markdown("---")
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            wide.to_excel(writer, index=False, sheet_name="Summary")
        st.download_button(
            "ดาวน์โหลด Summary (Excel)",
            output.getvalue(),
            file_name="summary.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

