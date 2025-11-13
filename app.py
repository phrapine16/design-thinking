import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime

# -------------------------------------
# CONFIG
# -------------------------------------
SPREADSHEET_ID = "16t3Vc8DmnnMzrBqTQPXT4g_b96d9FEKwflQIxaLyZEw"
STUDENT_SHEET = "Student List"
RESPONSE_SHEET = "Response"

# -------------------------------------
# GOOGLE SHEET CONNECT
# -------------------------------------
def connect_sheet():
    scope = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)

    spreadsheet = client.open_by_key(SPREADSHEET_ID)

    student_ws = spreadsheet.worksheet(STUDENT_SHEET)      # แท็บรายชื่อนักศึกษา
    response_ws = spreadsheet.worksheet(RESPONSE_SHEET)    # แท็บส่งงาน

    return student_ws, response_ws


def sheet_to_df(ws):
    return pd.DataFrame(ws.get_all_records())

# -------------------------------------
# TEACHER LOGIN SYSTEM
# -------------------------------------
TEACHERS = {
    "teacher": "admin123",   # ตัวอย่าง
    "admin": "password"
}

if "teacher_logged_in" not in st.session_state:
    st.session_state.teacher_logged_in = False

def teacher_login_page():
    st.title("🔐 Teacher Login")

    username = st.text_input("Username")
    password = st.text_input("Password", type="password")

    if st.button("เข้าสู่ระบบ (Teacher)"):
        if username in TEACHERS and TEACHERS[username] == password:
            st.session_state.teacher_logged_in = True
            st.success("เข้าสู่ระบบสำเร็จ!")
            st.experimental_rerun()
        else:
            st.error("❌ Username หรือ Password ไม่ถูกต้อง")

# -------------------------------------
# START APP
# -------------------------------------
st.set_page_config(page_title="Design Thinking System", layout="wide")
st.title("📋 ระบบส่งงาน / ให้คะแนน / สรุปผล")

student_ws, response_ws = connect_sheet()

# LOGOUT BUTTON
if st.session_state.teacher_logged_in:
    if st.button("Logout (Teacher)"):
        st.session_state.teacher_logged_in = False
        st.experimental_rerun()

# -------------------------------------
# SHOW TABS BASED ON ROLE
# -------------------------------------
if st.session_state.teacher_logged_in:
    tabs = st.tabs(["Student", "Teacher", "Summary"])
else:
    tabs = st.tabs(["Student"])

# =====================================================
# STUDENT TAB
# =====================================================
with tabs[0]:
    st.header("👨‍🎓 Student — ส่งงาน")

    with st.form("student_form", clear_on_submit=True):
        emp_id = st.text_input("Student ID")
        name = st.text_input("ชื่อ - นามสกุล")
        ans1 = st.text_area("คำตอบข้อที่ 1")
        ans2 = st.text_area("คำตอบข้อที่ 2")
        submit = st.form_submit_button("ส่งงาน")

    if submit:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        response_ws.append_row([
            timestamp,
            emp_id,
            name,
            ans1,
            ans2,
            "",       # Score
            "",       # Comment
            "รอตรวจ"
        ])

        st.success("ส่งงานสำเร็จ ✔")

# =====================================================
# TEACHER TAB
# =====================================================
if st.session_state.teacher_logged_in:
    with tabs[1]:
        st.header("👨‍🏫 Teacher — ให้คะแนน")

        df_response = sheet_to_df(response_ws)

        if df_response.empty:
            st.warning("ยังไม่มีนักศึกษาส่งงาน")
        else:
            st.subheader("📄 ข้อมูลการส่งงานทั้งหมด")
            st.dataframe(df_response)

            student_list = df_response["StudentID"].unique()
            selected_id = st.selectbox("เลือก Student ID", student_list)

            stu_data = df_response[df_response["StudentID"] == selected_id]
            rec = stu_data.iloc[-1]  # งานล่าสุด

            st.write("### ✏️ คำตอบล่าสุด:")
            st.write("**คำตอบข้อ 1:**")
            st.write(rec["Answer1"])
            st.write("**คำตอบข้อ 2:**")
            st.write(rec["Answer2"])

            new_score = st.number_input("คะแนน (0 - 100)", 0, 100)
            new_comment = st.text_area("ความคิดเห็นเพิ่มเติม")

            if st.button("บันทึกคะแนน"):
                all_rows = response_ws.get_all_values()
                target_row = None

                for i, row in enumerate(all_rows):
                    if row[0] == rec["Timestamp"] and row[1] == rec["StudentID"]:
                        target_row = i + 1
                        break

                if target_row:
                    response_ws.update_cell(target_row, 6, str(new_score))
                    response_ws.update_cell(target_row, 7, new_comment)
                    response_ws.update_cell(target_row, 8, "ตรวจแล้ว")
                    st.success("บันทึกคะแนนสำเร็จ ✔")
                else:
                    st.error("ไม่พบข้อมูลใน Google Sheet")

# =====================================================
# SUMMARY TAB
# =====================================================
if st.session_state.teacher_logged_in:
    with tabs[2]:
        st.header("📊 Summary — สรุปผลทั้งหมด")

        df_students = sheet_to_df(student_ws)
        df_response = sheet_to_df(response_ws)

        if df_response.empty:
            st.warning("ยังไม่มีผู้ส่งงาน")
            st.stop()

        df_response["Score"] = pd.to_numeric(df_response["Score"], errors="coerce")

        df_latest = df_response.sort_values("Timestamp").groupby("StudentID").last().reset_index()

        summary = df_students.merge(df_latest, how="left", left_on="StudentID", right_on="StudentID")

        summary = summary.replace("", pd.NA)

        st.subheader("📄 ตารางสรุปผล")
        st.dataframe(summary)

        if summary["Score"].notna().any():
            st.subheader("📈 กราฟคะแนน")
            st.bar_chart(summary.set_index("StudentID")["Score"])
        else:
            st.info("ยังไม่มีคะแนนให้แสดง")
