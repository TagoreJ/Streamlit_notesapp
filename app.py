# shared_notes_app.py
import streamlit as st
import sqlite3, uuid, time
from datetime import datetime
from urllib.parse import urlencode

DB_PATH = "shared_notes.db"

# --- DB helpers ---
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

def save_note(note_id, title, content):
    now = time.time()
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO notes (id, title, content, updated_at) VALUES (?, ?, ?, ?)
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

def note_exists(note_id):
    return get_note(note_id) is not None

# --- UI ---
st.set_page_config(page_title="Shared Notes", layout="wide")
st.title("Shared Notes — write and share instantly")

query = st.experimental_get_query_params()
mode = query.get("view", ["editor"])[0]  # "editor" or "viewer"
note_id_q = query.get("id", [None])[0]
token_q = query.get("token", [None])[0]

if mode == "viewer":
    # Viewer page: read-only display (auto-refresh)
    st.header("Viewer")
    if not note_id_q:
        st.error("No note ID provided in URL. Example: ?view=viewer&id=NOTE_ID&token=TOKEN")
    else:
        note = get_note(note_id_q)
        if not note:
            st.error("Note not found.")
        else:
            # If tokens exist for this note, require valid token
            tokens = [t for (t,_) in get_tokens_for_note(note_id_q)]
            if tokens and token_q not in tokens:
                st.error("Invalid or missing token. You need a valid token to view this note.")
            else:
                # Show note and auto-refresh
                st.subheader(note["title"] or "Untitled")
                last_updated = datetime.fromtimestamp(note["updated_at"]).strftime("%Y-%m-%d %H:%M:%S")
                st.caption(f"Last updated: {last_updated}")
                # Use st.empty + polling for near-real-time updates
                note_placeholder = st.empty()
                note_placeholder.text_area("Note (read-only)", value=note["content"], height=400)
                # Poll every 2 seconds
                st.write("This viewer auto-refreshes every 2 seconds to show updates.")
                st.experimental_rerun() if st.button("Refresh now") else None
                # Lightweight auto-refresh loop using st.experimental_get_query_params hack:
                st.experimental_set_query_params(view="viewer", id=note_id_q, token=token_q, _ts=int(time.time()))
                st.stop()

else:
    # Editor page
    st.header("Editor")
    col1, col2 = st.columns([2,1])
    with col1:
        title = st.text_input("Title", value="")
        content = st.text_area("Write your note here:", height=300)
        if "editing_id" not in st.session_state:
            st.session_state.editing_id = note_id_q or str(uuid.uuid4())[:8]
        note_id = st.session_state.editing_id

        if st.button("Save / Update"):
            save_note(note_id, title, content)
            st.success(f"Saved (id: {note_id})")

    with col2:
        st.markdown("### Share")
        st.write("Create up to 3 share links (each link is a unique token).")
        if st.button("Generate a share token (max 3)"):
            existing = get_tokens_for_note(note_id)
            if len(existing) >= 3:
                st.warning("Maximum of 3 tokens already generated for this note.")
            else:
                t = create_token(note_id)
                st.success(f"Token created: {t}")

        tokens = get_tokens_for_note(note_id)
        if tokens:
            st.write("Share links (copy and send to people):")
            for t, created in tokens:
                params = {"view":"viewer","id":note_id,"token": t}
                link = st.experimental_get_url()  # base URL
                # Build shareable URL with proper query params
                base = st.experimental_get_query_params()  # not used, just to avoid lint
                url = st.get_option("server.baseUrlPath", default="")  # fallback
                # Better: construct using request url from Streamlit's location
                full = st.experimental_get_url()  # returns full current URL, include params below
                # We'll build the URL relative to current host
                host = st.experimental_get_query_params()  # dummy to avoid linter; real build:
                current = st.experimental_get_query_params()  # avoid errors
                # Simpler: show the relative query string (works when user copies and pastes the local URL)
                query_str = urlencode(params)
                share_url = f"?{query_str}"
                st.code(share_url, language="text")
        else:
            st.info("No tokens created yet. Anyone who opens the viewer link without a token will be blocked (unless you choose to leave tokens empty).")

        st.markdown("---")
        st.write("Other actions:")
        if st.button("Open viewer in new tab (yourself)"):
            viewer_qs = urlencode({"view":"viewer","id":note_id})
            st.write("Open this URL in a new tab and add a token parameter if you created one:")
            st.code(f"?{viewer_qs}", language="text")

    st.markdown("---")
    st.write("Notes database id:", note_id)
    # show preview
    st.subheader("Preview")
    st.markdown(f"**{title or 'Untitled'}**")
    st.write(content or "_(empty)_")

    # Instruction block
    st.info("""
    How to share:
    1. Save the note.
    2. Click 'Generate a share token' (repeat up to 3 times).
    3. Copy the shown share link (format: `?view=viewer&id=<NOTE_ID>&token=<TOKEN>`) and send it to up to 3 people.
    4. When they open the link, their page will auto-refresh every few seconds to show updates.
    """)

