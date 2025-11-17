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
ARCHIVE_DIR = os.path.join(LOCAL_DATA_DIR, "archive")

DEFAULT_TEACHERS = {"teacher": "1234"}


# ---------------- HELPERS ----------------
def ensure_local_dir():
    os.makedirs(LOCAL_DATA_DIR, exist_ok=True)
    os.makedirs(ARCHIVE_DIR, exist_ok=True)


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


# ---------------- SUMMARY ----------------
def build_summary(students_df, responses_df):
    if responses_df.empty:
        summary = students_df.copy()
        summary["TotalScore"] = ""
        return summary

    summary = students_df.copy()
    activities = sorted(responses_df["Activity"].dropna().unique())

    for act in activities:
        mapping = {
            row["StudentID"]: row["Score"]
            for _, row in responses_df[responses_df["Activity"] == act].iterrows()
        }
        summary[act] = summary["StudentID"].map(mapping)

    def total(row):
        total_score = 0
        used = False
        for act in activities:
            v = row.get(act, "")
            if v in ["", None, "nan", "None"]:
                continue
            try:
                total_score += float(v)
                used = True
            except:
                pass

        if not used:
            return ""
        try:
            return int(total_score)
        except:
            return total_score

    summary["TotalScore"] = summary.apply(total, axis=1)
    return summary


# ---------------- UI ----------------
st.set_page_config(page_title="Student/Teacher Activities", layout="wide")

ensure_local_dir()

if "teacher_logged" not in st.session_state:
    st.session_state.teacher_logged = False


# logout
if st.session_state.teacher_logged:
    if st.button("Logout"):
        st.session_state.teacher_logged = False
        st.rerun()


# Tabs (เพิ่ม Archive)
if st.session_state.teacher_logged:
    tabs = st.tabs(["Student", "Teacher", "Summary", "Archive"])
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

        # =======================
        # ปุ่ม DELETE + POPUP
        # =======================
        if "confirm_delete" not in st.session_state:
            st.session_state.confirm_delete = False

        st.markdown("### 🗑️ ลบกิจกรรมเก่า (เก็บไฟล์ก่อนลบ)")

        # ปุ่มเริ่มการลบ (เปิด popup)
        if st.button("🗑️ Delete — เก็บกิจกรรมเก่าแล้วเริ่มใหม่"):
            st.session_state.confirm_delete = True
            st.rerun()

        # ถ้าอยู่ในสถานะยืนยัน → แสดง popup
        if st.session_state.confirm_delete:
            try:
                # popup modal
                with st.modal("⚠ ยืนยันการลบกิจกรรมเก่าทั้งหมด"):
                    st.write("ระบบจะเก็บไฟล์ responses.csv ปัจจุบันไว้ใน Archive และล้างข้อมูลทั้งหมดทันที")
                    st.write("ต้องการดำเนินการต่อหรือไม่?")

                    col1, col2 = st.columns(2)

                    with col1:
                        if st.button("✅ ยืนยันการลบ"):
                            import shutil
                            import datetime
                            
                            ensure_local_dir()
                            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                            archive_filename = f"responses_{ts}.csv"
                            archive_path = os.path.join(ARCHIVE_DIR, archive_filename)

                            # 1) เก็บ responses.csv เก่า
                            if os.path.exists(RESPONSES_LOCAL_PATH):
                                shutil.copy2(RESPONSES_LOCAL_PATH, archive_path)

                            # 2) ล้างข้อมูลสำหรับว่างใหม่
                            empty_df = pd.DataFrame(columns=["StudentID", "Name", "Activity", "Answer", "Score"])
                            save_responses(empty_df)

                            st.success(f"📦 เก็บกิจกรรมเก่าแล้ว: {archive_filename}")
                            st.success("🧹 ลบกิจกรรมเก่าเรียบร้อย! เริ่มใช้ใหม่ได้เลย")

                            st.session_state.confirm_delete = False
                            st.rerun()

                    with col2:
                        if st.button("❌ ยกเลิก"):
                            st.session_state.confirm_delete = False
                            st.rerun()

            except Exception:
                # fallback ถ้า Streamlit ไม่มี modal
                st.warning("ยืนยันการลบกิจกรรมเก่าทั้งหมด? การลบนี้ไม่สามารถย้อนกลับได้")
                col1, col2 = st.columns(2)

                with col1:
                    if st.button("Confirm Delete (fallback)"):
                        import shutil
                        import datetime
                        ensure_local_dir()

                        ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                        archive_filename = f"responses_{ts}.csv"
                        archive_path = os.path.join(ARCHIVE_DIR, archive_filename)

                        if os.path.exists(RESPONSES_LOCAL_PATH):
                            shutil.copy2(RESPONSES_LOCAL_PATH, archive_path)

                        empty_df = pd.DataFrame(columns=["StudentID", "Name", "Activity", "Answer", "Score"])
                        save_responses(empty_df)

                        st.success(f"📦 เก็บกิจกรรมเก่าแล้ว: {archive_filename}")
                        st.success("🧹 ลบกิจกรรมเก่าเรียบร้อย")

                        st.session_state.confirm_delete = False
                        st.rerun()

                with col2:
                    if st.button("Cancel (fallback)"):
                        st.session_state.confirm_delete = False
                        st.rerun()

        # =======================
        # ตารางแก้ไขคะแนน
        # =======================
        st.write("---")
        st.subheader("📄 แก้ไขคะแนนนักศึกษา")

        if resp.empty:
            st.info("ยังไม่มีงานที่ส่ง")
        else:
            edited = st.data_editor(
                resp,
                num_rows="dynamic",
                column_config={
                    "Score": st.column_config.TextColumn(
                        "Score",
                        help="พิมพ์คะแนนได้ทันที จะบันทึกอัตโนมัติ",
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
        st.dataframe(summary, use_container_width=True)

        st.markdown("---")
        st.subheader("⬇ ดาวน์โหลดรายงาน Excel")

        import io
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            summary.to_excel(writer, index=False, sheet_name="Summary")

        excel_data = output.getvalue()

        downloaded = st.download_button(
            label="📥 ดาวน์โหลดไฟล์ Summary.xlsx",
            data=excel_data,
            file_name="Summary_AllActivities.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        if downloaded:
            st.success("ดาวน์โหลดสำเร็จแล้ว ✓")


# ---------- ARCHIVE (หน้าใหม่) ----------
if st.session_state.teacher_logged:
    with tabs[3]:
        st.header("📦 Archive — ดาวน์โหลดกิจกรรมเก่าทั้งหมด")

        ensure_local_dir()
        archive_files = sorted(os.listdir(ARCHIVE_DIR))

        if not archive_files:
            st.info("ยังไม่มีไฟล์กิจกรรมเก่าที่ถูกเก็บไว้")
        else:
            st.write("รายการไฟล์กิจกรรมเก่าที่สำรองไว้:")

            for f in archive_files:
                file_path = os.path.join(ARCHIVE_DIR, f)

                with open(file_path, "rb") as file:
                    st.download_button(
                        label=f"📥 ดาวน์โหลด {f}",
                        data=file.read(),
                        file_name=f,
                        mime="text/csv",
                        key=f
                    )

            st.success("ดาวน์โหลดไฟล์เก่าได้ตามต้องการ ✓")
