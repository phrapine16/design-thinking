import streamlit as st
import pandas as pd
import os
import io
from datetime import datetime

DATA_DIR = "data"
STUDENTS_FILE = f"{DATA_DIR}/students.csv"
RESP_FILE = f"{DATA_DIR}/responses.csv"


# =========================
#   Load / Save functions
# =========================

def load_students():
    if not os.path.exists(STUDENTS_FILE):
        return pd.DataFrame(columns=["StudentID", "Name"])
    return pd.read_csv(STUDENTS_FILE)


def load_responses():
    if not os.path.exists(RESP_FILE):
        return pd.DataFrame(columns=["StudentID", "Name", "Activity", "Answer", "Score", "Status"])
    return pd.read_csv(RESP_FILE)


def save_responses(df):
    df.to_csv(RESP_FILE, index=False)


# =========================
#   Add or update activity
# =========================

def add_or_update_response(student_id, activity, answer):
    df = load_responses()
    students = load_students()

    if student_id not in students["StudentID"].values:
        return False, "ไม่พบรหัสนักศึกษาในระบบ"

    name = students.loc[students["StudentID"] == student_id, "Name"].iloc[0]

    # ถ้ามี Activity เดิม → ทับ
    exists = df[(df["StudentID"] == student_id) & (df["Activity"] == activity)]

    if not exists.empty:
        df.loc[(df["StudentID"] == student_id) & (df["Activity"] == activity), "Answer"] = answer
        df.loc[(df["StudentID"] == student_id) & (df["Activity"] == activity), "Status"] = "รอตรวจ"
    else:
        new_row = pd.DataFrame([{
            "StudentID": student_id,
            "Name": name,
            "Activity": activity,
            "Answer": answer,
            "Score": None,
            "Status": "รอตรวจ"
        }])
        df = pd.concat([df, new_row], ignore_index=True)

    save_responses(df)
    return True, "ส่งงานสำเร็จ"


# =========================
#     Update Score
# =========================

def update_score(student_id, activity, score, status="ตรวจแล้ว"):
    df = load_responses()
    cond = (df["StudentID"] == student_id) & (df["Activity"] == activity)

    if df[cond].empty:
        return False

    df.loc[cond, "Score"] = score
    df.loc[cond, "Status"] = status

    save_responses(df)
    return True


# =========================
#   Build Wide Summary
# =========================

def build_wide_summary(students_df, resp_df):
    if resp_df.empty:
        df = students_df.copy()
        df["TotalScore"] = 0
        return df

    wide = pd.pivot_table(
        resp_df,
        index=["StudentID", "Name"],
        columns="Activity",
        values=["Answer", "Score", "Status"],
        aggfunc="first"
    )

    wide.columns = [f"{c[1]}_{c[0]}" for c in wide.columns]
    wide = wide.reset_index()

    # ผลรวมคะแนนทั้งหมดของทุก Activity
    score_cols = [col for col in wide.columns if col.endswith("_Score")]
    wide["TotalScore"] = wide[score_cols].apply(pd.to_numeric, errors="coerce").sum(axis=1)

    return wide


# =========================
#      Streamlit UI
# =========================

st.set_page_config(page_title="Student/Teacher App", layout="wide")

if "teacher_logged" not in st.session_state:
    st.session_state.teacher_logged = False

tabs = st.tabs(["Student", "Teacher Login / Teacher"])


# =========================
#        STUDENT TAB
# =========================
with tabs[0]:
    st.header("👨‍🎓 Student — ส่งงาน (Essay)")

    st.info("พิมพ์รหัสนักศึกษา เลือกกิจกรรม และส่งคำตอบ")

    student_id = st.text_input("Student ID (เช่น S001)")
    activity = st.text_input("ชื่อกิจกรรม (Activity) เช่น 'กิจกรรมที่ 1'")
    answer = st.text_area("คำตอบ (Essay)", height=200)

    if st.button("ส่งงาน"):
        if student_id.strip() == "" or activity.strip() == "" or answer.strip() == "":
            st.error("กรุณากรอกข้อมูลให้ครบ")
        else:
            ok, msg = add_or_update_response(student_id.strip(), activity.strip(), answer.strip())
            if ok:
                st.success(msg)
            else:
                st.error(msg)


# =========================
#    TEACHER LOGIN → MAIN
# =========================
with tabs[1]:
    if not st.session_state.teacher_logged:

        st.header("🔐 Teacher Login")
        u = st.text_input("Username")
        p = st.text_input("Password", type="password")

        if st.button("เข้าสู่ระบบ"):
            if u == "teacher" and p == "1234":
                st.session_state.teacher_logged = True
                st.rerun()
            else:
                st.error("ล็อกอินไม่ถูกต้อง")

    else:
        st.header("👨‍🏫 Teacher — ตรวจงาน + Summary")

        students_df = load_students()
        resp_df = load_responses()

        # -------------------------
        # SUMMARY TABLE
        # -------------------------
        st.subheader("📊 Summary — รวมผลทุกกิจกรรม")
        wide = build_wide_summary(students_df, resp_df)
        st.dataframe(wide, use_container_width=True)

        st.markdown("---")

        # -------------------------
        # SCORE SECTION
        # -------------------------
        st.subheader("✏️ ให้คะแนนจาก Summary")

        sid_list = students_df["StudentID"].tolist()
        selected_sid = st.selectbox("เลือก StudentID", sid_list)

        stu_resp = resp_df[resp_df["StudentID"] == selected_sid]

        if stu_resp.empty:
            st.info("นักศึกษายังไม่ส่งงาน")
        else:
            act_list = stu_resp["Activity"].tolist()
            selected_act = st.selectbox("เลือกกิจกรรม (Activity)", act_list)

            row = stu_resp[stu_resp["Activity"] == selected_act].iloc[0]

            st.markdown("### คำตอบที่ส่ง")
            st.write(row["Answer"])

            score_input = st.text_input("ให้คะแนน", value=str(row.get("Score", "")))

            if st.button("บันทึกคะแนน"):
                ok = update_score(selected_sid, selected_act, score_input)
                if ok:
                    st.success("บันทึกคะแนนแล้ว")
                    st.rerun()
                else:
                    st.error("เกิดข้อผิดพลาด")

        st.markdown("---")

        # -------------------------
        # DOWNLOAD EXCEL
        # -------------------------
        st.subheader("📥 ดาวน์โหลด Summary (Excel)")

        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            wide.to_excel(writer, index=False, sheet_name="Summary")
        data = buffer.getvalue()

        st.download_button(
            "ดาวน์โหลดไฟล์ Summary.xlsx",
            data=data,
            file_name="summary.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
