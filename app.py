import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime

# ================================================================
# CONFIG
# ================================================================

# Public GitHub repo ที่เก็บ students.csv แบบ Raw
GITHUB_USER = "phrapine16"
GITHUB_REPO = "design-thinking"
GITHUB_BRANCH = "main"

STUDENTS_RAW_URL = (
    f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}/data/students.csv"
)

# Local path บน Streamlit (ใช้ /tmp เพราะเขียนได้ 100%)
LOCAL_DATA_DIR = "/tmp"
RESPONSES_LOCAL_PATH = os.path.join(LOCAL_DATA_DIR, "responses.csv")

# Teacher Login แบบง่าย
DEFAULT_TEACHERS = {"teacher": "1234"}  # เปลี่ยนได้ตามต้องการ


# ================================================================
# Helper Functions
# ================================================================

def ensure_local_dir():
    """Ensure that /tmp exists."""
    if not os.path.isdir(LOCAL_DATA_DIR):
        try:
            os.makedirs(LOCAL_DATA_DIR, exist_ok=True)
        except Exception:
            pass


def load_students():
    """Load students.csv จาก GitHub RAW URL."""
    try:
        df = pd.read_csv(STUDENTS_RAW_URL, dtype=str)
        if "StudentID" not in df.columns or "Name" not in df.columns:
            st.error("❌ students.csv ต้องมีคอลัมน์ StudentID และ Name")
        df = df[["StudentID", "Name"]].astype(str)
        return df
    except Exception as e:
        st.error("ไม่สามารถโหลด students.csv จาก GitHub ได้: " + str(e))
        return pd.DataFrame(columns=["StudentID", "Name"])


def load_responses():
    """Load หรือสร้าง responses.csv ใน /tmp"""
    ensure_local_dir()

    if os.path.exists(RESPONSES_LOCAL_PATH):
        try:
            df = pd.read_csv(RESPONSES_LOCAL_PATH, dtype=str)
            return df
        except Exception:
            pass

    # ถ้าไม่มีไฟล์ หรือมีปัญหา → สร้างไฟล์ใหม่
    df = pd.DataFrame(columns=[
        "Timestamp", "StudentID", "Name", "Answer",
        "Score", "Comment", "Status"
    ])
    df.to_csv(RESPONSES_LOCAL_PATH, index=False)
    return df


def save_responses(df):
    """บันทึก responses.csv กลับไปที่ /tmp"""
    ensure_local_dir()
    df.to_csv(RESPONSES_LOCAL_PATH, index=False)


def append_response(row_dict):
    """เพิ่มแถวใหม่ลง responses.csv"""
    df = load_responses()
    df = pd.concat([df, pd.DataFrame([row_dict])], ignore_index=True)
    save_responses(df)
    return True


def update_response_by_timestamp(student_id, timestamp, updates):
    df = load_responses()
    mask = (
        (df["StudentID"].astype(str) == str(student_id)) &
        (df["Timestamp"].astype(str) == str(timestamp))
    )
    if mask.any():
        idx = df[mask].index[0]
        for k, v in updates.items():
            df.at[idx, k] = v
        save_responses(df)
        return True
    return False


# ================================================================
# Streamlit UI
# ================================================================

st.set_page_config(page_title="Student/Teacher System", layout="wide")
st.title("📘 ระบบส่งงาน / ให้คะแนน / สรุปผล (เก็บข้อมูลบน Streamlit Server)")

# Session State
if "teacher_logged" not in st.session_state:
    st.session_state.teacher_logged = False
if "teacher_user" not in st.session_state:
    st.session_state.teacher_user = None

# Logout Button
col1, col2 = st.columns([3, 1])
with col2:
    if st.session_state.teacher_logged:
        if st.button("Logout"):
            st.session_state.teacher_logged = False
            st.session_state.teacher_user = None
            st.rerun()   # <<<<<< แก้แล้ว


# Tabs
if st.session_state.teacher_logged:
    tabs = st.tabs(["Student", "Teacher", "Summary"])
else:
    tabs = st.tabs(["Student", "Teacher Login"])


# ================================================================
# Student TAB
# ================================================================

with tabs[0]:
    st.header("👨‍🎓 Student — ส่งงาน (Essay)")
    st.info("พิมพ์รหัสนักศึกษา และส่งคำตอบแบบยาว")

    students_df = load_students()

    with st.form("student_form", clear_on_submit=True):
        sid = st.text_input("Student ID (เช่น S001)").strip()
        answer = st.text_area("คำตอบ (Essay)")
        submit_btn = st.form_submit_button("ส่งงาน")

    if submit_btn:
        if sid == "":
            st.error("กรุณากรอก Student ID")
        elif sid not in students_df["StudentID"].values:
            st.error("ไม่พบ Student ID นี้ในระบบ")
        else:
            name = students_df.loc[students_df["StudentID"] == sid, "Name"].values[0]
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_row = {
                "Timestamp": ts,
                "StudentID": sid,
                "Name": name,
                "Answer": answer,
                "Score": "",
                "Comment": "",
                "Status": "รอตรวจ"
            }
            append_response(new_row)
            st.success("ส่งงานเรียบร้อยแล้ว 🎉")


# ================================================================
# Teacher Login TAB
# ================================================================

if not st.session_state.teacher_logged:
    with tabs[1]:
        st.header("🔐 Teacher Login")
        with st.form("login_form"):
            user = st.text_input("Username")
            pwd = st.text_input("Password", type="password")
            login_btn = st.form_submit_button("เข้าสู่ระบบ")

        if login_btn:
            if user in DEFAULT_TEACHERS and DEFAULT_TEACHERS[user] == pwd:
                st.session_state.teacher_logged = True
                st.session_state.teacher_user = user
                st.rerun()  # <<<<<< แก้แล้ว
            else:
                st.error("Username หรือ Password ผิด")


# ================================================================
# Teacher TAB (หลัง Login)
# ================================================================

if st.session_state.teacher_logged:
    with tabs[1]:
        st.header("👨‍🏫 Teacher — ให้คะแนน")

        students_df = load_students()
        resp_df = load_responses()

        st.subheader("📄 งานที่ส่งล่าสุด")
        st.dataframe(resp_df)

        st.subheader("🔎 เลือกนักศึกษา")
        sid_list = students_df["StudentID"].tolist()
        selected_sid = st.selectbox("StudentID", sid_list)

        # หา Submission ล่าสุดของนักศึกษาคนนี้
        sub = resp_df[resp_df["StudentID"] == selected_sid]

        if sub.empty:
            st.warning("นักศึกษายังไม่ส่งงาน")
        else:
            last = sub.iloc[-1]
            st.write(f"⏱ ส่งล่าสุด: {last['Timestamp']}")
            st.write(f"👤 ชื่อ: {last['Name']}")
            st.markdown("### 📝 คำตอบ:")
            st.info(last["Answer"])

            score = st.text_input("คะแนน", value=last.get("Score", ""))
            comment = st.text_area("ความคิดเห็น", value=last.get("Comment", ""))

            if st.button("บันทึกคะแนน"):
                ok = update_response_by_timestamp(
                    selected_sid,
                    last["Timestamp"],
                    {
                        "Score": score,
                        "Comment": comment,
                        "Status": "ตรวจแล้ว"
                    }
                )
                if ok:
                    st.success("บันทึกคะแนนแล้ว ✓")
                else:
                    st.error("ไม่สามารถบันทึกได้")


# ================================================================
# Summary TAB
# ================================================================

if st.session_state.teacher_logged:
    with tabs[2]:
        st.header("📊 Summary — รายงานทั้งหมด")

        students_df = load_students()
        resp_df = load_responses()

        # หา submission ล่าสุดของแต่ละคน
        if not resp_df.empty:
            resp_df["Timestamp"] = resp_df["Timestamp"].astype(str)
            latest = resp_df.sort_values("Timestamp").groupby("StudentID", as_index=False).last()
        else:
            latest = pd.DataFrame(columns=["StudentID"])

        # Merge กับรายชื่อนักศึกษา (แสดงทุกคน)
        summary = students_df.merge(
            latest[["StudentID","Score","Comment","Status","Timestamp"]],
            on="StudentID",
            how="left"
        )

        summary["Status"] = summary["Status"].fillna("ยังไม่ส่ง")

        st.subheader("📄 ตารางสรุป")
        st.dataframe(summary)

        # Export Excel
        st.subheader("⬇ Export Excel")
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            summary.to_excel(writer, index=False, sheet_name="Summary")

        st.download_button(
            label="ดาวน์โหลด Excel",
            data=buffer.getvalue(),
            file_name="summary.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
