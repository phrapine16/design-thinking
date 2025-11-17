import streamlit as st
import pandas as pd
import os

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
    df.to_csv(RESPONSES_LOCAL_PATH, index=False)


def upsert_response(student_id, name, activity, answer):
    df = load_responses()
    mask = (df["StudentID"] == student_id) & (df["Activity"] == activity)

    if mask.any():
        idx = df[mask].index[0]
        df.at[idx, "Answer"] = answer
        df.at[idx, "Name"] = name
    else:
        df = pd.concat(
            [
                df,
                pd.DataFrame(
                    [
                        {
                            "StudentID": student_id,
                            "Name": name,
                            "Activity": activity,
                            "Answer": answer,
                            "Score": "",
                        }
                    ]
                ),
            ],
            ignore_index=True,
        )

    save_responses(df)


def sanitize(s):
    import re
    s = re.sub(r"\W+", "_", str(s))
    return s


def build_summary(students_df, responses_df):
    if responses_df.empty:
        summary = students_df.copy()
        summary["TotalScore"] = ""
        return summary

    summary = students_df.copy()
    activities = sorted(responses_df["Activity"].dropna().unique())

    # ใช้ชื่อ activity จริงเป็นชื่อคอลัมน์ใน summary
    for act in activities:
        col_score = act  # ใช้ชื่อกิจกรรมเป็นชื่อคอลัมน์
        mapping = {
            row["StudentID"]: row["Score"]
            for _, row in responses_df[responses_df["Activity"] == act].iterrows()
        }
        summary[col_score] = summary["StudentID"].map(mapping)

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

if "teacher_logged" not in st.session_state:
    st.session_state.teacher_logged = False


# logout
if st.session_state.teacher_logged:
    if st.button("Logout"):
        st.session_state.teacher_logged = False
        st.rerun()


# Tabs
if st.session_state.teacher_logged:
    tabs = st.tabs(["Student", "Teacher", "Summary"])
else:
    tabs = st.tabs(["Student", "Teacher Login"])


# ---------- STUDENT ----------
with tabs[0]:
    st.header("👨‍🎓 ส่งงานกิจกรรม")

    students = load_students()

    with st.form("student_form", clear_on_submit=True):
        sid = st.text_input("Student ID (เช่น S001)")
        act = st.text_input("ชื่อกิจกรรม")
        ans = st.text_area("คำตอบ (Essay)")
        submit = st.form_submit_button("ส่งงาน")

    if submit:
        if sid == "" or act == "" or sid not in students["StudentID"].values:
            st.error("กรุณากรอกข้อมูลให้ครบ และต้องมี StudentID ในระบบ")
        else:
            name = students.loc[students["StudentID"] == sid, "Name"].values[0]
            upsert_response(sid, name, act, ans)
            st.success("ส่งงานสำเร็จ!")


# ---------- TEACHER LOGIN ----------
if not st.session_state.teacher_logged:
    with tabs[1]:
        st.header("🔐 Teacher Login")

        with st.form("login"):
            user = st.text_input("Username")
            pw = st.text_input("Password", type="password")
            ok = st.form_submit_button("Login")

        if ok:
            if user in DEFAULT_TEACHERS and DEFAULT_TEACHERS[user] == pw:
                st.session_state.teacher_logged = True
                st.rerun()
            else:
                st.error("Incorrect username or password")


# ---------- TEACHER ----------
if st.session_state.teacher_logged:
    with tabs[1]:
        st.header("👨‍🏫 แก้ไขคะแนน (Auto-Save แบบ Excel)")

        resp = load_responses()

        if resp.empty:
            st.info("ยังไม่มีงานที่ส่ง")
        else:
            st.write("แก้ไขคะแนนได้ทันที ↓")

            edited = st.data_editor(
                resp,
                num_rows="dynamic",
                column_config={
                    "Score": st.column_config.TextColumn(
                        "Score",
                        help="พิมพ์คะแนนได้ทันที จะเซฟอัตโนมัติ",
                    )
                },
                disabled=["StudentID", "Name", "Activity", "Answer"],
            )

            if not edited.equals(resp):
                save_responses(edited)
                st.success("บันทึกข้อมูลอัตโนมัติแล้ว ✓")
                st.rerun()


# ---------- SUMMARY ----------
if st.session_state.teacher_logged:
    with tabs[2]:
        st.header("📊 Summary — รวมคะแนนทุกกิจกรรม")

        students = load_students()
        resp = load_responses()

        summary = build_summary(students, resp)
        st.dataframe(summary)
