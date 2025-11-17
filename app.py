import streamlit as st
import pandas as pd
import os
import io

# ==========================
# CONFIG
# ==========================
GITHUB_USER = "phrapine16"
GITHUB_REPO = "design-thinking"
GITHUB_BRANCH = "main"
STUDENTS_RAW_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}/data/students.csv"

LOCAL_DATA_DIR = "/tmp"
RESPONSES_LOCAL_PATH = os.path.join(LOCAL_DATA_DIR, "responses.csv")

DEFAULT_TEACHERS = {"teacher": "1234"}   # simple login


# ==========================
# Helpers
# ==========================
def ensure_local_dir():
    if not os.path.isdir(LOCAL_DATA_DIR):
        os.makedirs(LOCAL_DATA_DIR, exist_ok=True)


def load_students():
    try:
        df = pd.read_csv(STUDENTS_RAW_URL, dtype=str)
        df = df[["StudentID", "Name"]]
        return df
    except:
        st.error("โหลดไฟล์ students.csv จาก GitHub ไม่ได้")
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
        idx = df[mask].index[0]
        df.at[idx, "Answer"] = answer
        df.at[idx, "Name"] = name
        df.at[idx, "Score"] = ""
    else:
        new_row = {
            "StudentID": student_id,
            "Name": name,
            "Activity": activity,
            "Answer": answer,
            "Score": ""
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    save_responses(df)


def update_score(student_id, activity, score_value):
    df = load_responses()
    mask = (df["StudentID"] == student_id) & (df["Activity"] == activity)
    if mask.any():
        idx = df[mask].index[0]
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


def build_wide_summary(students_df, responses_df):
    if responses_df.empty:
        out = students_df.copy()
        out["TotalScore"] = pd.NA
        return out

    activities = sorted(responses_df["Activity"].unique().tolist())
    wide = students_df.copy()

    for act in activities:
        san = sanitize_col(act)
        sub = responses_df[responses_df["Activity"] == act]

        ans_map = {row["StudentID"]: row["Answer"] for _, row in sub.iterrows()}
        score_map = {row["StudentID"]: row["Score"] for _, row in sub.iterrows()}

        wide[f"Answer_{san}"] = wide["StudentID"].map(ans_map)
        wide[f"Score_{san}"] = wide["StudentID"].map(score_map)

    score_cols = [c for c in wide.columns if c.startswith("Score_")]

    def sum_scores(row):
        total = 0
        have = False
        for c in score_cols:
            v = row.get(c, "")
            if v not in ("", None, "None"):
                try:
                    total += float(v)
                    have = True
                except:
                    pass
        return int(total) if have else ""

    wide["TotalScore"] = wide.apply(sum_scores, axis=1)
    return wide


# ==========================
# UI
# ==========================
st.set_page_config(page_title="Student/Teacher", layout="wide")
st.title("📘 ระบบส่งงานและให้คะแนน (Activity Based)")

if "teacher_logged" not in st.session_state:
    st.session_state.teacher_logged = False

# Logout button
if st.session_state.teacher_logged:
    if st.button("Logout"):
        st.session_state.teacher_logged = False
        st.rerun()

# Tabs
if st.session_state.teacher_logged:
    tabs = st.tabs(["Student", "Teacher", "Summary"])
else:
    tabs = st.tabs(["Student", "Teacher Login"])


# ==========================
# Student TAB
# ==========================
with tabs[0]:
    st.header("👨‍🎓 Student — ส่งงาน")
    st.info("พิมพ์ StudentID + ชื่อกิจกรรม + คำตอบ ถ้ากิจกรรมซ้ำจะทับงานเก่า")

    students_df = load_students()

    with st.form("student_form", clear_on_submit=True):
        sid = st.text_input("Student ID เช่น S001")
        activity = st.text_input("ชื่อกิจกรรม เช่น กิจกรรมที่ 1")
        answer = st.text_area("คำตอบ")
        ok = st.form_submit_button("ส่งงาน")

    if ok:
        if sid == "" or activity == "":
            st.error("กรุณากรอก StudentID และ ชื่อกิจกรรม")
        elif sid not in students_df["StudentID"].values:
            st.error("ไม่พบ StudentID ในรายชื่อ")
        else:
            name = students_df.loc[students_df["StudentID"] == sid, "Name"].values[0]
            upsert_response(sid, name, activity, answer)
            st.success("ส่งงานเรียบร้อย!")


# ==========================
# Teacher Login TAB
# ==========================
if not st.session_state.teacher_logged:
    with tabs[1]:
        st.header("🔐 Teacher Login")
        with st.form("login"):
            user = st.text_input("Username")
            pw = st.text_input("Password", type="password")
            login_btn = st.form_submit_button("เข้าสู่ระบบ")

        if login_btn:
            teachers = DEFAULT_TEACHERS.copy()
            if user in teachers and teachers[user] == pw:
                st.session_state.teacher_logged = True
                st.success("เข้าสู่ระบบสำเร็จ!")
                st.rerun()
            else:
                st.error("ข้อมูลเข้าสู่ระบบไม่ถูกต้อง")


# ==========================
# Teacher TAB
# ==========================
if st.session_state.teacher_logged:
    with tabs[1]:
        st.header("👨‍🏫 Teacher — ให้คะแนน")

        resp_df = load_responses()
        st.subheader("📄 งานที่ส่งทั้งหมด")
        st.dataframe(resp_df, use_container_width=True)

        if resp_df.empty:
            st.warning("ยังไม่มีการส่งงาน")
            st.stop()

        st.subheader("✏️ ให้คะแนน")
        sid_list = sorted(resp_df["StudentID"].unique().tolist())
        selected_sid = st.selectbox("เลือก Student ID", sid_list)

        sub = resp_df[resp_df["StudentID"] == selected_sid]

        if sub.empty:
            st.warning("นักศึกษาคนนี้ยังไม่ส่งงาน")
            st.stop()

        act_list = sorted(sub["Activity"].unique().tolist())
        selected_act = st.selectbox("เลือก Activity", act_list)

        selected_rows = sub[sub["Activity"] == selected_act]
        if selected_rows.empty:
            st.error("ไม่พบนักศึกษาส่งงาน Activity นี้")
            st.stop()

        row = selected_rows.iloc[0]

        st.markdown("### คำตอบ")
        st.write(row["Answer"])

        new_score = st.text_input("คะแนน", value=str(row.get("Score", "")))

        if st.button("บันทึกคะแนน"):
            if update_score(selected_sid, selected_act, new_score):
                st.success("บันทึกคะแนนแล้ว!")
                st.rerun()
            else:
                st.error("บันทึกคะแนนไม่สำเร็จ")


# ==========================
# Summary TAB
# ==========================
if st.session_state.teacher_logged:
    with tabs[2]:
        st.header("📊 Summary — สรุปคะแนนทั้งหมด")

        students_df = load_students()
        resp_df = load_responses()

        wide = build_wide_summary(students_df, resp_df)
        st.dataframe(wide, use_container_width=True)

        st.subheader("📥 ดาวน์โหลด Summary Excel")
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            wide.to_excel(writer, index=False, sheet_name="Summary")
        data = output.getvalue()

        st.download_button(
            "ดาวน์โหลด Excel",
            data,
            "summary.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
