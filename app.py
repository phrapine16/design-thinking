# app.py (Store responses locally on Streamlit server; read students from public GitHub)
import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime

# ----------------- CONFIG (แก้ได้ตามต้องการ) -----------------
# Public GitHub repo ที่เก็บ students.csv (public raw URL จะถูกอ่านโดยตรง)
GITHUB_USER = "phrapine16"
GITHUB_REPO = "design-thinking"
GITHUB_BRANCH = "main"
STUDENTS_RAW_URL = f"https://raw.githubusercontent.com/{GITHUB_USER}/{GITHUB_REPO}/{GITHUB_BRANCH}/data/students.csv"

# Local path (บน Streamlit server) สำหรับเก็บ responses (ไม่ใช้ GitHub token)
LOCAL_DATA_DIR = "/mnt/data"
RESPONSES_LOCAL_PATH = os.path.join(LOCAL_DATA_DIR, "responses.csv")

# Default teacher credentials (ถ้าอยากเก็บใน Secrets ให้ใส่ st.secrets["teachers"])
DEFAULT_TEACHERS = {"teacher": "1234"}  # เปลี่ยนได้ตามต้องการ

# ----------------- Helpers -----------------
def ensure_local_dir():
    if not os.path.isdir(LOCAL_DATA_DIR):
        try:
            os.makedirs(LOCAL_DATA_DIR, exist_ok=True)
        except Exception:
            pass

def load_students():
    """Load students.csv from public GitHub raw URL. Return DataFrame."""
    try:
        df = pd.read_csv(STUDENTS_RAW_URL, dtype=str)
        # ensure columns StudentID, Name exist
        if "StudentID" not in df.columns or "Name" not in df.columns:
            st.warning("ไฟล์ students.csv ต้องมีคอลัมน์ StudentID และ Name")
        df = df[["StudentID", "Name"]].astype(str)
        return df
    except Exception as e:
        st.error("ไม่สามารถโหลด students.csv จาก GitHub ได้: " + str(e))
        return pd.DataFrame(columns=["StudentID", "Name"])

def load_responses():
    """Load local responses.csv (create empty if not exist)."""
    ensure_local_dir()
    if os.path.exists(RESPONSES_LOCAL_PATH):
        try:
            df = pd.read_csv(RESPONSES_LOCAL_PATH, dtype=str)
            return df
        except Exception:
            # corrupted file -> reset
            return pd.DataFrame(columns=["Timestamp","StudentID","Name","Answer","Score","Comment","Status"])
    else:
        # create empty
        df = pd.DataFrame(columns=["Timestamp","StudentID","Name","Answer","Score","Comment","Status"])
        df.to_csv(RESPONSES_LOCAL_PATH, index=False)
        return df

def save_responses(df):
    ensure_local_dir()
    df.to_csv(RESPONSES_LOCAL_PATH, index=False)

def append_response(row_dict):
    df = load_responses()
    df = pd.concat([df, pd.DataFrame([row_dict])], ignore_index=True)
    save_responses(df)
    return True

def update_response_by_timestamp(student_id, timestamp, updates: dict):
    df = load_responses()
    mask = (df["StudentID"].astype(str) == str(student_id)) & (df["Timestamp"].astype(str) == str(timestamp))
    if mask.any():
        idx = df[mask].index[0]
        for k, v in updates.items():
            df.at[idx, k] = v
        save_responses(df)
        return True
    return False

# ----------------- App UI -----------------
st.set_page_config(page_title="Student/Teacher (Local storage)", layout="wide")
st.title("📙 ระบบส่งงาน — เก็บ responses ไว้บน Streamlit (Local storage)")

# session state for teacher login
if "teacher_logged" not in st.session_state:
    st.session_state.teacher_logged = False
if "teacher_user" not in st.session_state:
    st.session_state.teacher_user = None

# top bar logout
col_left, col_right = st.columns([3,1])
with col_right:
    if st.session_state.teacher_logged:
        if st.button("Logout"):
            st.session_state.teacher_logged = False
            st.session_state.teacher_user = None
            st.experimental_rerun()

# tabs
if st.session_state.teacher_logged:
    tabs = st.tabs(["Student", "Teacher", "Summary"])
else:
    tabs = st.tabs(["Student", "Teacher Login"])

# ---------- Student tab ----------
with tabs[0]:
    st.header("👨‍🎓 Student — ส่งแบบฝึกหัด (Essay)")
    st.info("ระบบจะตรวจ StudentID จาก students.csv บน GitHub (public). ถ้า StudentID ถูกต้อง จะบันทึกคำตอบลงบนเซิร์ฟเวอร์นี้")

    students_df = load_students()

    with st.form("student_form", clear_on_submit=True):
        sid = st.text_input("Student ID (เช่น S001)")
        if sid:
            sid = sid.strip()
        answer = st.text_area("คำตอบ (Essay / ข้อความยาว)")
        submitted = st.form_submit_button("ส่งงาน")

    if submitted:
        if sid is None or sid == "":
            st.error("กรุณากรอก Student ID")
        else:
            # check student exists
            if sid not in students_df["StudentID"].values:
                st.error("ไม่พบ Student ID นี้ใน students.csv (ตรวจสอบว่าพิมพ์ถูกหรือไม่)")
            else:
                name = students_df.loc[students_df["StudentID"] == sid, "Name"].values[0]
                ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                row = {
                    "Timestamp": ts,
                    "StudentID": sid,
                    "Name": name,
                    "Answer": answer,
                    "Score": "",
                    "Comment": "",
                    "Status": "รอตรวจ"
                }
                append_response(row)
                st.success("ส่งงานเรียบร้อยแล้ว ✅ (บันทึกลงเซิร์ฟเวอร์)")

# ---------- Teacher Login ----------
if not st.session_state.teacher_logged:
    with tabs[1]:
        st.header("🔐 Teacher Login")
        st.write("ล็อกอินด้วยบัญชีครู (default: teacher / 1234). ถ้าต้องการแก้ ให้ใส่ในโค้ดหราผ่าน st.secrets['teachers'].")
        with st.form("login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            login = st.form_submit_button("เข้าสู่ระบบ")
        if login:
            # get teacher dict: secret override possible
            teachers = DEFAULT_TEACHERS.copy()
            try:
                if "teachers" in st.secrets:
                    # secret should be a dict of username:password
                    teachers = dict(st.secrets["teachers"])
            except Exception:
                pass
            if username in teachers and teachers[username] == password:
                st.session_state.teacher_logged = True
                st.session_state.teacher_user = username
                st.success("เข้าสู่ระบบสำเร็จ")
                st.experimental_rerun()
            else:
                st.error("Username หรือ Password ไม่ถูกต้อง")

# ---------- Teacher tab (logged) ----------
if st.session_state.teacher_logged:
    with tabs[1]:
        st.header("👨‍🏫 Teacher — ดูการส่งงานและให้คะแนน")
        students_df = load_students()
        resp_df = load_responses()

        if resp_df.empty:
            st.info("ยังไม่มีการส่งงาน")
        else:
            st.subheader("รายการการส่งงาน (ล่าสุดด้านล่าง)")
            # show last 200 submissions
            try:
                st.dataframe(resp_df.tail(200))
            except Exception:
                st.write(resp_df.tail(200))

            # Choose student to grade (based on students list)
            # Provide list of StudentIDs existing in students.csv for teacher convenience
            student_ids_all = students_df["StudentID"].tolist()
            selected_sid = st.selectbox("เลือก StudentID (จาก students.csv)", options=student_ids_all)

            # show latest submission for selected student (if any)
            sel_rows = resp_df[resp_df["StudentID"].astype(str) == str(selected_sid)]
            if sel_rows.empty:
                st.warning("นักศึกษายังไม่ส่งงานครั้งใด ๆ")
            else:
                last_rec = sel_rows.iloc[-1]
                st.write("**ล่าสุดส่งเมื่อ:**", last_rec["Timestamp"])
                st.write("**ชื่อ:**", last_rec["Name"])
                st.write("**คำตอบ:**")
                st.write(last_rec["Answer"])

                # grading inputs
                st.markdown("### ให้คะแนน / ความเห็น")
                score_input = st.text_input("คะแนน (พิมพ์ค่าได้ตามต้องการ เช่น 85 หรือ A หรือ ข้อความ)", value=str(last_rec.get("Score", "")))
                comment_input = st.text_area("ความคิดเห็น", value=str(last_rec.get("Comment", "")))

                if st.button("บันทึกคะแนนและสถานะ"):
                    updated = update_response_by_timestamp(selected_sid, last_rec["Timestamp"], {
                        "Score": score_input,
                        "Comment": comment_input,
                        "Status": "ตรวจแล้ว"
                    })
                    if updated:
                        st.success("บันทึกคะแนนเรียบร้อย")
                    else:
                        st.error("ไม่สามารถอัปเดตแถวได้ (อาจมีการเปลี่ยนแปลงไฟล์)")

# ---------- Summary (Teacher only) ----------
if st.session_state.teacher_logged:
    with tabs[2]:
        st.header("📊 Summary — สรุปผลทั้งหมด และ Export")
        students_df = load_students()
        resp_df = load_responses()

        if not resp_df.empty:
            # convert Timestamp to str and sort then take latest per student
            resp_df["Timestamp"] = resp_df["Timestamp"].astype(str)
            latest = resp_df.sort_values("Timestamp").groupby("StudentID", as_index=False).last()
        else:
            latest = pd.DataFrame(columns=["StudentID","Score","Comment","Status","Timestamp","Name"])

        summary = students_df.merge(
            latest[["StudentID","Score","Comment","Status","Timestamp"]],
            how="left",
            on="StudentID"
        )
        summary["Status"] = summary["Status"].fillna("ยังไม่ส่ง")
        # convert Score to numeric where possible, otherwise keep as text
        try:
            summary["Score_numeric"] = pd.to_numeric(summary["Score"], errors="coerce")
        except Exception:
            summary["Score_numeric"] = pd.Series([None]*len(summary))

        st.subheader("ตารางสรุป (รายชื่อนักศึกษาทั้งหมด)")
        st.dataframe(summary.drop(columns=["Score_numeric"]))

        # Basic stats (only count numeric scores)
        if summary["Score_numeric"].notna().any():
            st.write("จำนวนที่มีคะแนน:", int(summary["Score_numeric"].count()))
            st.write("คะแนนเฉลี่ย:", float(summary["Score_numeric"].mean()))
            st.bar_chart(summary.set_index("StudentID")["Score_numeric"])
        else:
            st.info("ยังไม่มีคะแนนเชิงตัวเลขให้แสดงสถิติ")

        # Export Excel
        st.markdown("---")
        st.subheader("Export Excel")
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            summary.to_excel(writer, index=False, sheet_name="Summary")
        out_bytes = output.getvalue()

        st.download_button(
            label="ดาวน์โหลด Excel (.xlsx)",
            data=out_bytes,
            file_name=f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

# ---------------- Footer / Notes ----------------
st.markdown("---")
st.write("Note: ระบบเก็บ responses ลงบนเซิร์ฟเวอร์ Streamlit (`/mnt/data/responses.csv`) — หากต้องการเก็บถาวรหรือแชร์ผล ให้ดาวน์โหลดไฟล์ Excel แล้วนำไปเก็บต่อบนเครื่องหรือ GitHub.")
st.write("If you want to enable writing back to GitHub later, we can change to use GitHub API with a token stored in Streamlit Secrets.")
