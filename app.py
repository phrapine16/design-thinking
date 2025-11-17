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
    if not os.path.isdir(LOCAL_DATA_DIR):
        try:
            os.makedirs(LOCAL_DATA_DIR, exist_ok=True)
        except:
            pass

def load_students():
    try:
        df = pd.read_csv(STUDENTS_RAW_URL, dtype=str)
        df = df[["StudentID", "Name"]]
        return df
    except Exception as e:
        st.error(f"โหลด students.csv ไม่ได้: {e}")
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
    
    if mask.any():  # ทับงาน
        idx = df[mask].index[0]
        df.at[idx, "Answer"] = answer
        df.at[idx, "Name"] = name
        df.at[idx, "Score"] = ""  # reset score
    else:  # เพิ่มงานใหม่
        new_row = {
            "StudentID": student_id,
            "Name": name,
            "Activity": activity,
            "Answer": answer,
            "Score": ""
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    save_responses(df)
    return True

def update_score(student_id, activity, score_value):
    df = load_responses()
    mask = (df["StudentID"] == student_id) & (df["Activity"] == activity)
    if mask.any():
        idx = df[mask].index[0]
        df.at[idx, "Score"] = score_value
        save_responses(df)
        return True
    return False


# ---------------- SUMMARY TABLE ----------------
def build_summary(students_df, responses_df):
    if responses_df.empty:
        summary = students_df.copy()
        summary["TotalScore"] = ""
        return summary

    summary = students_df.copy()
    activities = sorted(responses_df["Activity"].dropna().unique())

    for act in activities:
        col = act  # ใช้ชื่อ activity จริงเป็นชื่อคอลัมน์
        mapping = {
            row["StudentID"]: row["Score"]
            for _, row in responses_df[responses_df["Activity"] == act].iterrows()
        }
        summary[col] = summary["StudentID"].map(mapping)

    # รวมคะแนนทั้งหมด
    def calc_total(row):
        total = 0
        used = False
        for act in activities:
            v = row.get(act, "")
            if v not in ["", None, "nan", "None"]:
                try:
                    total += float(v)
                    used = True
                except:
                    pass
        return int(total) if used else ""

    summary["TotalScore"] = summary.apply(calc_total, axis=1)
    return summary



# ---------------- UI ----------------
st.set_page_config(page_title="Student/Teacher Activities", layout="wide")
st.title("📘 ระบบส่งงานตามกิจกรรม — Student / Teacher")

# session
if "teacher_logged" not in st.session_state:
    st.session_state.teacher_logged = False


# ---------------- Logout ----------------
if st.session_state.teacher_logged:
    if st.button("Logout"):
        st.session_state.teacher_logged = False
        st.rerun()


# ---------------- Tabs ----------------
if st.session_state.teacher_logged:
    tabs = st.tabs(["Student", "Teacher", "Summary"])
else:
    tabs = st.tabs(["Student", "Teacher Login"])


# ---------------- STUDENT TAB ----------------
with tabs[0]:
    st.header("👨‍🎓 Student — ส่งงานตามกิจกรรม")

    students_df = load_students()

    with st.form("student_form", clear_on_submit=True):
        sid = st.text_input("Student ID (เช่น S001)").strip()
        activity = st.text_input("ชื่อกิจกรรม").strip()
        answer = st.text_area("คำตอบ (Essay)")
        ok = st.form_submit_button("ส่งงาน")

    if ok:
        if sid == "" or activity == "":
            st.error("กรุณากรอก Student ID และชื่อกิจกรรม")
        elif sid not in students_df["StudentID"].values:
            st.error("ไม่พบ Student ID ในระบบ")
        else:
            name = students_df.loc[students_df["StudentID"] == sid, "Name"].values[0]
            upsert_response(sid, name, activity, answer)
            st.success("ส่งงานเรียบร้อย ✨")


# ---------------- TEACHER LOGIN ----------------
if not st.session_state.teacher_logged:
    with tabs[1]:
        st.header("🔐 Teacher Login")
        with st.form("login"):
            user = st.text_input("Username")
            pw = st.text_input("Password", type="password")
            ok = st.form_submit_button("เข้าสู่ระบบ")

        if ok:
            if user in DEFAULT_TEACHERS and pw == DEFAULT_TEACHERS[user]:
                st.session_state.teacher_logged = True
                st.rerun()
            else:
                st.error("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง")


# ---------------- TEACHER TAB ----------------
if st.session_state.teacher_logged:
    with tabs[1]:
        st.header("👨‍🏫 Teacher — ให้คะแนนงานกิจกรรม")

        students_df = load_students()
        resp_df = load_responses()

        st.subheader("📄 งานที่ส่งทั้งหมด")
        st.dataframe(resp_df, use_container_width=True)

        st.subheader("✏ ให้คะแนน")
        sid_list = students_df["StudentID"].tolist()
        selected_sid = st.selectbox("เลือกนักศึกษา", sid_list)

        sub = resp_df[resp_df["StudentID"] == selected_sid]

        if sub.empty:
            st.warning("ยังไม่มีงานที่ส่งสำหรับนักศึกษาคนนี้")
        else:
            act_list = sub["Activity"].tolist()
            selected_act = st.selectbox("เลือกกิจกรรม", act_list)

            row = sub[sub["Activity"] == selected_act].iloc[0]
            st.markdown("**คำตอบที่ส่ง:**")
            st.write(row["Answer"])

            new_score = st.text_input("คะแนน", value=str(row["Score"]))

            if st.button("บันทึกคะแนน"):
                update_score(selected_sid, selected_act, new_score)
                st.success("บันทึกคะแนนสำเร็จ")
                st.rerun()


# ---------------- SUMMARY TAB ----------------
if st.session_state.teacher_logged:
    with tabs[2]:
        st.header("📊 Summary — รวมคะแนนทุกกิจกรรม")

        students_df = load_students()
        resp_df = load_responses()
        summary = build_summary(students_df, resp_df)

        st.dataframe(summary, use_container_width=True)

        # export
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            summary.to_excel(writer, index=False, sheet_name="Summary")

        st.download_button(
            label="📥 ดาวน์โหลด Excel",
            data=buffer.getvalue(),
            file_name="summary.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
