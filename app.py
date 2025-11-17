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

# simple teacher credentials (change if needed)
DEFAULT_TEACHERS = {"teacher": "1234"}

# ---------------- HELPERS ----------------
def ensure_local_dir():
    if not os.path.isdir(LOCAL_DATA_DIR):
        try:
            os.makedirs(LOCAL_DATA_DIR, exist_ok=True)
        except Exception:
            pass

def load_students():
    try:
        df = pd.read_csv(STUDENTS_RAW_URL, dtype=str)
        if "StudentID" not in df.columns or "Name" not in df.columns:
            st.error("ไฟล์ students.csv ต้องมีคอลัมน์ StudentID และ Name")
            return pd.DataFrame(columns=["StudentID","Name"])
        df = df[["StudentID","Name"]].astype(str)
        return df
    except Exception as e:
        st.error("ไม่สามารถโหลด students.csv จาก GitHub ได้: " + str(e))
        return pd.DataFrame(columns=["StudentID","Name"])

def load_responses():
    ensure_local_dir()
    if os.path.exists(RESPONSES_LOCAL_PATH):
        try:
            df = pd.read_csv(RESPONSES_LOCAL_PATH, dtype=str)
            return df
        except Exception:
            pass
    # create empty if missing or corrupted
    df = pd.DataFrame(columns=["StudentID","Name","Activity","Answer","Score","Status"])
    df.to_csv(RESPONSES_LOCAL_PATH, index=False)
    return df

def save_responses(df):
    ensure_local_dir()
    df.to_csv(RESPONSES_LOCAL_PATH, index=False)

def upsert_response(student_id, name, activity, answer):
    """
    If an entry with same StudentID+Activity exists -> overwrite Answer, Score reset, Status to 'รอตรวจ'
    Else -> append new row.
    """
    df = load_responses()
    mask = (df["StudentID"].astype(str) == str(student_id)) & (df["Activity"].astype(str) == str(activity))
    if mask.any():
        idx = df[mask].index[0]
        df.at[idx, "Answer"] = answer
        df.at[idx, "Name"] = name
        df.at[idx, "Score"] = ""   # reset score on resubmit
        df.at[idx, "Status"] = "รอตรวจ"
    else:
        new_row = {
            "StudentID": student_id,
            "Name": name,
            "Activity": activity,
            "Answer": answer,
            "Score": "",
            "Status": "รอตรวจ"
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
    save_responses(df)
    return True

def update_score(student_id, activity, score_value, status="ตรวจแล้ว"):
    df = load_responses()
    mask = (df["StudentID"].astype(str) == str(student_id)) & (df["Activity"].astype(str) == str(activity))
    if mask.any():
        idx = df[mask].index[0]
        df.at[idx, "Score"] = str(score_value)
        df.at[idx, "Status"] = status
        save_responses(df)
        return True
    return False

def sanitize_col(s):
    # create safe column name
    import re
    s = str(s)
    s = re.sub(r"\s+", "_", s.strip())
    s = re.sub(r"[^\w\-]", "", s)
    return s

def build_wide_summary(students_df, responses_df):
    """
    Build a wide table:
    For each Activity occurrence for each student, create columns:
      Answer_{n}_{ActivitySanitized}, Score_{n}_{ActivitySanitized}, Status_{n}_{ActivitySanitized}
    The order of activities follows sorted unique activities across responses (stable).
    Rightmost columns: Summary_TotalScore, Summary_Status (e.g., if any checked?), Summary_CompletedCount
    """
    # ensure responses_df as expected
    if responses_df.empty:
        # create blank wide with students only
        out = students_df.copy()
        out["Summary_TotalScore"] = pd.NA
        out["Summary_CompletedCount"] = 0
        out["Summary_Status"] = "ยังไม่ส่ง"
        return out

    # get list of unique activities across all responses, sorted
    activities = responses_df["Activity"].astype(str).unique().tolist()

    # start with students
    summary = students_df.copy()

    # for each activity, we will try to find for each student the single row (since we upsert, one per student+activity)
    for act in activities:
        san = sanitize_col(act)
        answer_col = f"Answer_{san}"
        score_col = f"Score_{san}"
        status_col = f"Status_{san}"
        # prepare a mapping student->value
        sub = responses_df[responses_df["Activity"].astype(str) == str(act)][["StudentID","Answer","Score","Status"]]
        # set default NaN
        mapping_answer = {row["StudentID"]: row["Answer"] for _, row in sub.iterrows()}
        mapping_score = {row["StudentID"]: row["Score"] for _, row in sub.iterrows()}
        mapping_status = {row["StudentID"]: row["Status"] for _, row in sub.iterrows()}
        summary[answer_col] = summary["StudentID"].map(mapping_answer)
        summary[score_col] = summary["StudentID"].map(mapping_score)
        summary[status_col] = summary["StudentID"].map(mapping_status)

    # compute Summary_TotalScore (sum numeric scores across Score_* columns)
    score_cols = [c for c in summary.columns if c.startswith("Score_")]
    def sum_scores(row):
        total = 0.0
        any_num = False
        for c in score_cols:
            v = row.get(c, None)
            try:
                if pd.isna(v) or v == "" or str(v).lower() in ("none","nan"):
                    continue
                num = float(str(v))
                total += num
                any_num = True
            except Exception:
                # non-numeric score -> ignore for sum
                continue
        if any_num:
            # return integer if whole
            if total.is_integer():
                return int(total)
            return total
        return pd.NA

    summary["Summary_TotalScore"] = summary.apply(sum_scores, axis=1)

    # Summary_CompletedCount: count activities with non-empty status != ยังไม่ส่ง
    status_cols = [c for c in summary.columns if c.startswith("Status_")]
    def count_completed(row):
        cnt = 0
        for c in status_cols:
            v = row.get(c, None)
            if pd.isna(v):
                continue
            if str(v).strip() != "" and str(v).strip() != "ยังไม่ส่ง":
                cnt += 1
        return cnt
    summary["Summary_CompletedCount"] = summary.apply(count_completed, axis=1)

    # Summary_Status: simple rule
    def summary_status(row):
        if row["Summary_CompletedCount"] == 0:
            return "ยังไม่ส่ง"
        return "มีผลการตรวจ"
    summary["Summary_Status"] = summary.apply(summary_status, axis=1)

    return summary

# ---------------- UI ----------------
st.set_page_config(page_title="Student/Teacher (Activity)", layout="wide")
st.title("📘 ระบบส่งงานตามกิจกรรม — Student / Teacher")

# session
if "teacher_logged" not in st.session_state:
    st.session_state.teacher_logged = False
if "teacher_user" not in st.session_state:
    st.session_state.teacher_user = None

# logout
colL, colR = st.columns([3,1])
with colR:
    if st.session_state.teacher_logged:
        if st.button("Logout"):
            st.session_state.teacher_logged = False
            st.session_state.teacher_user = None
            st.rerun()

# tabs
if st.session_state.teacher_logged:
    tabs = st.tabs(["Student", "Teacher", "Summary"])
else:
    tabs = st.tabs(["Student", "Teacher Login"])

# ---------- Student tab ----------
with tabs[0]:
    st.header("👨‍🎓 Student — ส่งงานตามกิจกรรม")
    st.info("กรอก Student ID, ชื่อกิจกรรม, และคำตอบ (Essay). ถ้าส่งกิจกรรมเดิม จะทับงานเก่า")

    students_df = load_students()
    if students_df.empty:
        st.warning("ยังไม่มีรายชื่อนักศึกษา: ตรวจ students.csv")
    with st.form("student_form", clear_on_submit=True):
        sid = st.text_input("Student ID (เช่น S001)").strip()
        activity = st.text_input("ชื่อกิจกรรม (เช่น กิจกรรมที่ 1)").strip()
        answer = st.text_area("คำตอบ (Essay)")
        submit_btn = st.form_submit_button("ส่งงาน")

    if submit_btn:
        if sid == "" or activity == "":
            st.error("กรุณากรอก Student ID และ ชื่อกิจกรรม")
        elif sid not in students_df["StudentID"].values:
            st.error("ไม่พบ Student ID นี้ใน students.csv")
        else:
            name = students_df.loc[students_df["StudentID"] == sid, "Name"].values[0]
            upsert_response(sid, name, activity, answer)
            st.success("ส่งงานเรียบร้อย (เก็บ/ทับตาม Activity)")

# ---------- Teacher login ----------
if not st.session_state.teacher_logged:
    with tabs[1]:
        st.header("🔐 Teacher Login")
        with st.form("login"):
            user = st.text_input("Username")
            pw = st.text_input("Password", type="password")
            ok = st.form_submit_button("เข้าสู่ระบบ")
        if ok:
            teachers = DEFAULT_TEACHERS.copy()
            try:
                if "teachers" in st.secrets:
                    teachers = dict(st.secrets["teachers"])
            except Exception:
                pass
            if user in teachers and teachers[user] == pw:
                st.session_state.teacher_logged = True
                st.session_state.teacher_user = user
                st.rerun()
            else:
                st.error("Username หรือ Password ไม่ถูกต้อง")

# ---------- Teacher tab ----------
if st.session_state.teacher_logged:
    with tabs[1]:
        st.header("👨‍🏫 Teacher — ให้คะแนนตามกิจกรรม")
        students_df = load_students()
        resp_df = load_responses()
        st.subheader("รายการการส่งงาน (ทั้งหมด)")
        st.dataframe(resp_df)

        st.subheader("ให้คะแนน: เลือกนักศึกษา และกิจกรรม")
        sid_options = students_df["StudentID"].tolist()
        selected_sid = st.selectbox("เลือก StudentID", sid_options)

        # activities submitted by this student
        sub_all = resp_df[resp_df["StudentID"].astype(str) == str(selected_sid)]
        if sub_all.empty:
            st.warning("นักศึกษายังไม่ส่งงานใดๆ")
        else:
            activity_list = sub_all["Activity"].astype(str).tolist()
            selected_activity = st.selectbox("เลือก Activity", activity_list)
            # get the row
            row = sub_all[sub_all["Activity"] == selected_activity].iloc[0]
            st.markdown("**คำตอบ:**")
            st.write(row["Answer"])

            score_val = st.text_input("คะแนน (พิมพ์เป็นตัวเลขหรือข้อความได้)", value=str(row.get("Score","")))
            if st.button("บันทึกคะแนน"):
                update_ok = update_score(selected_sid, selected_activity, score_val, status="ตรวจแล้ว")
                if update_ok:
                    st.success("บันทึกคะแนนเรียบร้อย")
                else:
                    st.error("บันทึกไม่สำเร็จ")

# ---------- Summary tab ----------
if st.session_state.teacher_logged:
    with tabs[2]:
        st.header("📊 Summary — แสดงทุกกิจกรรมแบบขยายไปทางขวา และสรุปผลรวมคะแนน")
        students_df = load_students()
        resp_df = load_responses()

        wide = build_wide_summary(students_df, resp_df)

        st.subheader("ตารางสรุป (Activity เป็นคอลัมน์ด้านขวา)")
        st.dataframe(wide)

        # Basic overall stats
        if "Summary_TotalScore" in wide.columns and wide["Summary_TotalScore"].notna().any():
            st.write("จำนวนที่มีคะแนนเชิงตัวเลข:", int(wide["Summary_TotalScore"].count()))
            try:
                st.write("ผลรวมคะแนนทั้งหมดของกลุ่ม (รวมทุกคน):", float(wide["Summary_TotalScore"].dropna().astype(float).sum()))
            except Exception:
                pass

        # Export Excel
        st.markdown("---")
        st.subheader("Export")
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            wide.to_excel(writer, index=False, sheet_name="Summary")
        data = output.getvalue()

        st.download_button("ดาวน์โหลด Excel (.xlsx)", data=data,
                           file_name="summary_all_activities.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.markdown("---")
st.write("Note: ระบบเก็บ responses ในเครื่องเซิร์ฟเวอร์ของ Streamlit (/tmp). ถ้าต้องการเก็บถาวร ให้ดาวน์โหลดไฟล์ Excel แล้วอัปโหลดเก็บในที่เก็บของคุณ")
