import streamlit as st
import pandas as pd
import os
import io

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
#   Add / Update Student Submission
# =========================

def add_or_update_response(student_id, activity, answer):
    df = load_responses()
    students = load_students()

    if student_id not in students["StudentID"].values:
        return False, "ไม่พบ StudentID ในระบบ"

    name = students.loc[students["StudentID"] == student_id, "Name"].iloc[0]

    # Check if activity exists → replace
    cond = (df["StudentID"] == student_id) & (df["Activity"] == activity)

    if cond.any():
        df.loc[cond, "Answer"] = answer
        df.loc[cond, "Status"] = "รอตรวจ"
        df.loc[cond, "Score"] = None
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
#   Update Score
# =========================

def update_score(student_id, activity, score):
    df = load_responses()
    cond = (df["StudentID"] == student_id) & (df["Activity"] == activity)

    if not cond.any():
        return False

    df.loc[cond, "Score"] = score
    df.loc[cond, "Status"] = "ตรวจแล้ว"
    save_responses(df)
    return True


# =========================
#   Build Summary Table
# =========================

def build_wide_summary(students_df, resp_df):
    if resp_df.empty:
        df = students_df.copy()
        df["TotalScore"] = 0
        return df

    # Pivot wide: Answer_กิจกรรม, Score_กิจกรรม, Status_กิจกรรม
    wide = pd.pivot_table(
        resp_df,
        index=["StudentID", "Name"],
        columns="Activity",
        values=["Answer", "Score", "Status"],
        aggfunc="first"
    )

    wide.columns = [f"{col[0]}_{col[1]}" for col in wide.columns]
    wide = wide.reset_index()

    # รวมคะแนนทั้งหมด
    score_cols = [c for c in wide.columns if c.startswith("Score_")]
    wide["TotalScore"] = wide[score_cols].apply(pd.to_numeric, errors="coerce").sum(axis=1)

    return wide


# =========================
#          UI
# =========================

st.set_page_config(page_title="Student/Teacher App", layout="wide")

if "teacher_logged" not in st.session_state:
    st.session_state.teacher_logged = False

tabs = st.tabs(["Student", "Teacher Login", "Summary"])


# =========================
#        STUDENT TAB
# =========================
with tabs[0]:
    st.header("👨‍🎓 Student — ส่งงาน Activity")

    student_id = st.text_input("Student ID เช่น S001")
    activity = st.text_input("ชื่อ Activity เช่น กิจกรรมที่ 1")
    answer = st.text_area("คำตอบ")

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
#      TEACHER LOGIN TAB
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
        st.header("👨‍🏫 Teacher — ตรวจงาน")

        students_df = load_students()
        resp_df = load_responses()

        # เลือกนักศึกษา
        student_list = students_df["StudentID"].tolist()
        selected_sid = st.selectbox("เลือก StudentID", student_list)

        stu_resp = resp_df[resp_df["StudentID"] == selected_sid]

        if stu_resp.empty:
            st.info("นักศึกษายังไม่ส่งงาน")
        else:
            act_list = stu_resp["Activity"].tolist()
            selected_act = st.selectbox("เลือกกิจกรรม", act_list)

            row = stu_resp[stu_resp["Activity"] == selected_act].iloc[0]

            st.markdown("### คำตอบ:")
            st.write(row["Answer"])

            score_input = st.text_input("ให้คะแนน", value=str(row.get("Score", "")))

            if st.button("บันทึกคะแนน"):
                ok = update_score(selected_sid, selected_act, score_input)
                if ok:
                    st.success("บันทึกคะแนนเรียบร้อย")
                    st.rerun()
                else:
                    st.error("บันทึกล้มเหลว")


# =========================
#        SUMMARY TAB
# =========================
with tabs[2]:
    st.header("📊 Summary — รวมผลทุกกิจกรรม")

    students_df = load_students()
    resp_df = load_responses()

    wide = build_wide_summary(students_df, resp_df)
    st.dataframe(wide, use_container_width=True)

    # Export Excel
    st.markdown("---")
    st.subheader("📥 ดาวน์โหลด Summary")

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        wide.to_excel(writer, index=False, sheet_name="Summary")

    st.download_button(
        "ดาวน์โหลดไฟล์ summary.xlsx",
        data=buffer.getvalue(),
        file_name="summary.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
