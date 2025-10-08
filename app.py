import streamlit as st
import sqlite3, uuid, time
from datetime import datetime
from urllib.parse import urlencode

DB_PATH = "shared_notes.db"

# --- DB setup ---
def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS notes (
        id TEXT PRIMARY KEY,
        title TEXT,
        content TEXT,
        updated_at REAL
    )""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS tokens (
        token TEXT PRIMARY KEY,
        note_id TEXT,
        created_at REAL,
        FOREIGN KEY(note_id) REFERENCES notes(id)
    )""")
    conn.commit()
    return conn

conn = init_db()

# --- Helpers ---
def save_note(note_id, title, content):
    now = time.time()
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO notes (id, title, content, updated_at)
        VALUES (?, ?, ?, ?)
    """, (note_id, title, content, now))
    conn.commit()

def get_note(note_id):
    c = conn.cursor()
    c.execute("SELECT id, title, content, updated_at FROM notes WHERE id = ?", (note_id,))
    row = c.fetchone()
    if not row:
        return None
    return {"id": row[0], "title": row[1], "content": row[2], "updated_at": row[3]}

def create_token(note_id):
    t = str(uuid.uuid4())[:8]
    now = time.time()
    c = conn.cursor()
    c.execute("INSERT INTO tokens (token, note_id, created_at) VALUES (?, ?, ?)", (t, note_id, now))
    conn.commit()
    return t

def get_tokens_for_note(note_id):
    c = conn.cursor()
    c.execute("SELECT token, created_at FROM tokens WHERE note_id = ?", (note_id,))
    return c.fetchall()

# --- Streamlit UI ---
st.set_page_config(page_title="Shared Notes", layout="wide")
st.title("📝 Shared Notes — Write & Share Instantly")

query = st.query_params
mode = query.get("view", "editor")
note_id_q = query.get("id", None)
token_q = query.get("token", None)

if mode == "viewer":
    # --- Viewer mode ---
    st.header("🔒 Note Viewer")
    if not note_id_q:
        st.error("Missing note ID. Example: ?view=viewer&id=NOTE_ID&token=TOKEN")
    else:
        note = get_note(note_id_q)
        if not note:
            st.error("Note not found.")
        else:
            tokens = [t for (t, _) in get_tokens_for_note(note_id_q)]
            if tokens and token_q not in tokens:
                st.error("Invalid or missing token.")
            else:
                st.subheader(note["title"] or "Untitled Note")
                last_updated = datetime.fromtimestamp(note["updated_at"]).strftime("%Y-%m-%d %H:%M:%S")
                st.caption(f"Last updated: {last_updated}")
                st.text_area("Note (read-only)", value=note["content"], height=400, disabled=True)
                st.info("Auto-refresh every few seconds to see updates (or click Refresh).")
                if st.button("🔄 Refresh"):
                    st.rerun()

else:
    # --- Editor mode ---
    st.header("✍️ Editor")
    col1, col2 = st.columns([2, 1])

    with col1:
        title = st.text_input("Title", value="")
        content = st.text_area("Write your note here:", height=300)

        if "editing_id" not in st.session_state:
            st.session_state.editing_id = note_id_q or str(uuid.uuid4())[:8]
        note_id = st.session_state.editing_id

        if st.button("💾 Save / Update"):
            save_note(note_id, title, content)
            st.success(f"Note saved successfully (ID: {note_id})")

    with col2:
        st.markdown("### 🔗 Share Links")
        st.write("Generate up to 3 unique share tokens.")

        if st.button("➕ Generate Share Token"):
            existing = get_tokens_for_note(note_id)
            if len(existing) >= 3:
                st.warning("Maximum 3 tokens already generated.")
            else:
                t = create_token(note_id)
                st.success(f"Token created: {t}")

        tokens = get_tokens_for_note(note_id)
        if tokens:
            st.markdown("**Share these links:**")
            base_url = "http://genonotes.streamlit.app"  # Change to your Streamlit Cloud URL after deployment
            for t, _ in tokens:
                params = {"view": "viewer", "id": note_id, "token": t}
                share_url = f"{base_url}/?{urlencode(params)}"
                st.code(share_url, language="text")
        else:
            st.info("No tokens yet. Generate one to share your note.")

    st.markdown("---")
    st.subheader("🪞 Preview")
    st.markdown(f"**{title or 'Untitled'}**")
    st.write(content or "_(empty note)_")

    st.info("""
    **How to share your note:**
    1. Save it.
    2. Click “Generate Share Token” (up to 3).
    3. Copy the share link and send it.
    4. Viewers can read it live via the viewer page.
    """)
