import streamlit as st
import sqlite3
import openai
import uuid
import os

# 🔐 Abo-Prüfung: Freigabe für bestimmte Test-PINs
def is_abo_active(user_pin):
    if user_pin in ["FAMILIE123", "TESTZUGANG", "HARRO1"]:
        return True
    return False  # Standard: kein Abo aktiv

DB_NAME = "happiness_creator.db"
openai.api_key = st.secrets["openai_api_key"]

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS chat (
            user_id TEXT,
            topic TEXT,
            subtopic TEXT,
            message TEXT,
            response TEXT,
            summary TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS community (
            user_id TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS marketplace (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            title TEXT,
            description TEXT,
            price TEXT,
            kontakt_email TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id TEXT,
            receiver_id TEXT,
            item_id INTEGER,
            item_title TEXT,
            message TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS dating (
            user_id TEXT PRIMARY KEY,
            name TEXT,
            interesse TEXT,
            beschreibung TEXT,
            image_path TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def login():
    st.sidebar.subheader("🔐 Login")
    name = st.sidebar.text_input("Wie möchtest du genannt werden?")
    if st.sidebar.button("Einloggen") and name:
        user_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, name))
        conn = sqlite3.connect(DB_NAME)
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO users (id, name) VALUES (?, ?)", (user_id, name))
        conn.commit()
        conn.close()
        st.session_state.user_id = user_id
        st.session_state.user_name = name
        st.rerun()

def get_system_prompt(topic, subtopic):
    return f"""
Du bist Sokrates, verkörpert als ruhiger, zugewandter Freund.
Du führst keine Gespräche aus Wissensdrang, sondern aus aufrichtigem Interesse am Gegenüber.
Thema: {topic}  
Unterthema: {subtopic}
"""

def ask_gpt(system_prompt, chat_history, user_input):
    messages = [{"role": "system", "content": system_prompt}]
    for msg, reply in chat_history:
        messages.append({"role": "user", "content": msg})
        messages.append({"role": "assistant", "content": reply})
    messages.append({"role": "user", "content": user_input})
    res = openai.ChatCompletion.create(model="gpt-3.5-turbo", messages=messages)
    return res.choices[0].message["content"]

def load_chat(uid, topic, sub):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT message, response FROM chat WHERE user_id = ? AND topic = ? AND subtopic = ? ORDER BY timestamp", (uid, topic, sub))
    data = c.fetchall()
    conn.close()
    return data

def save_chat(uid, topic, sub, msg, resp):
    summary = resp[:100] + "..."
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT INTO chat (user_id, topic, subtopic, message, response, summary) VALUES (?, ?, ?, ?, ?, ?)", (uid, topic, sub, msg, resp, summary))
    conn.commit()
    conn.close()

def community_tab():
    st.header("🌱 Community")
    with st.form("post_form"):
        content = st.text_area("Was möchtest du teilen?")
        if st.form_submit_button("Posten") and content.strip():
            conn = sqlite3.connect(DB_NAME)
            c = conn.cursor()
            c.execute("INSERT INTO community (user_id, content) VALUES (?, ?)", (st.session_state.user_id, content))
            conn.commit()
            conn.close()
            st.success("Beitrag veröffentlicht.")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT content, timestamp FROM community ORDER BY timestamp DESC")
    for content, ts in c.fetchall():
        st.markdown(f"🕒 {ts}  \n💬 {content}")
        st.markdown("---")
    conn.close()

def marketplace_tab():
    st.header("🛍️ Marktplatz")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    with st.expander("📦 Neues Angebot erstellen"):
        title = st.text_input("Titel")
        description = st.text_area("Beschreibung")
        price = st.text_input("Preis (in €)")
        kontakt_email = st.text_input("Kontakt (E-Mail, optional)")
        if st.button("Angebot veröffentlichen"):
            if title and description and price:
                c.execute("""
                    INSERT INTO marketplace (user_id, title, description, price, kontakt_email)
                    VALUES (?, ?, ?, ?, ?)
                """, (st.session_state.user_id, title, description, price, kontakt_email))
                conn.commit()
                st.success("✅ Angebot wurde veröffentlicht!")
            else:
                st.warning("Bitte Titel, Beschreibung und Preis angeben.")
    st.markdown("---")
    st.subheader("📦 Angebote:")
    c.execute("SELECT id, user_id, title, description, price, kontakt_email, timestamp FROM marketplace ORDER BY timestamp DESC")
    offers = c.fetchall()
    for item_id, seller_id, title, desc, price, kontakt_email, ts in offers:
        st.markdown(f"**{title}**\n{desc}\n💰 {price or 'kostenlos'}\n✉️ {kontakt_email or 'Keine E-Mail'}\n🕒 {ts}")
        if seller_id != st.session_state.user_id:
            with st.expander("📝 Kontakt aufnehmen"):
                if is_abo_active(st.session_state.get("user_pin", "")):
                    message = st.text_area(f"Deine Nachricht an den Anbieter:", key=f"msg_{item_id}")
                    if st.button("Nachricht senden", key=f"send_{item_id}"):
                        c.execute("""
                            INSERT INTO messages (sender_id, receiver_id, item_id, item_title, message)
                            VALUES (?, ?, ?, ?, ?)
                        """, (st.session_state.user_id, seller_id, item_id, title, message))
                        conn.commit()
                        st.success("Deine Nachricht wurde gesendet!")
                else:
                    st.warning("Diese Funktion ist Teil des Happiness-Pakets (5,59 €/Monat).")
                    st.info("Freischaltung bald verfügbar – dann kannst du direkt mit Anbietern chatten. ❤️")
        st.markdown("---")
    conn.close()

def messages_tab():
    st.header("📬 Nachrichten")
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT message, timestamp, sender_id, item_title
        FROM messages
        WHERE receiver_id = ?
        ORDER BY timestamp DESC
    """, (st.session_state.user_id,))
    messages = c.fetchall()
    if not messages:
        st.info("Keine Nachrichten erhalten.")
        conn.close()
        return
    for idx, (msg, ts, sender_id, artikel) in enumerate(messages):
        st.markdown(f"""
        📦 **Artikel**: *{artikel}*  
        👤 **Von Nutzer-ID**: `{sender_id}`  
        🕒 **Zeit**: {ts}  
        ✉️ **Nachricht**:  
        {msg}
        """)
        st.markdown("---")
    conn.close()

def dating_tab():
    st.header("💞 Dating")
    if "user_id" not in st.session_state:
        st.warning("⚠️ Bitte zuerst einloggen.")
        return
    os.makedirs("profile_pics", exist_ok=True)
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    with st.form("dating_form"):
        name = st.text_input("Dein Name")
        interesse = st.text_input("Was suchst du?")
        beschreibung = st.text_area("Erzähl etwas über dich")
        bild = st.file_uploader("Lade ein Profilbild hoch (optional)", type=["png", "jpg", "jpeg"])
        submitted = st.form_submit_button("Eintragen")
        if submitted and name.strip() and interesse.strip():
            image_path = None
            if bild and bild.name:
                filename = f"profile_pics/{st.session_state.user_id}_{bild.name}"
                with open(filename, "wb") as f:
                    f.write(bild.getbuffer())
                image_path = filename
            try:
                c.execute("""
                    INSERT OR REPLACE INTO dating (user_id, name, interesse, beschreibung, image_path)
                    VALUES (?, ?, ?, ?, ?)
                """, (st.session_state.user_id, name, interesse, beschreibung, image_path))
                conn.commit()
                st.success("✅ Profil gespeichert!")
            except Exception as e:
                st.error(f"Fehler beim Speichern: {e}")
    st.markdown("---")
    st.subheader("✨ Andere Personen:")
    try:
        c.execute("""
            SELECT name, interesse, beschreibung, timestamp, image_path
            FROM dating
            WHERE user_id != ?
            ORDER BY timestamp DESC
            LIMIT 20
        """, (st.session_state.user_id,))
        results = c.fetchall()
    except Exception as e:
        st.error(f"Fehler beim Abrufen: {e}")
        conn.close()
        return
    if not results:
        st.info("Noch keine anderen Einträge.")
    else:
        for name, interesse, beschreibung, ts, img in results:
            if img and os.path.exists(img):
                st.image(img, width=150)
            st.markdown(f"""
            🧑 **{name}** – sucht: *{interesse}*  
            🕒 {ts}  
            💬 {beschreibung}
            """)
            st.markdown("---")
    conn.close()

def main():
    st.set_page_config("Happiness Creator", layout="centered")
    if "user_id" not in st.session_state:
        login()
        st.stop()
    st.sidebar.title("🧭 Navigation")
    menu = st.sidebar.radio("Wähle:", ["Gespräch", "Community", "Marktplatz", "Nachrichten", "Verbindung"])
    if menu == "Gespräch":
        st.title("🌞 Happiness Creator")
        st.write(f"Willkommen zurück, {st.session_state.user_name}!")
        topics = {
            "Mentale Gesundheit & Wohlbefinden": ["Stress", "Burnout", "Achtsamkeit"],
            "Nachhaltigkeit & Klimawandel": ["Umweltbewusstsein", "Klimaschutz", "Zero Waste"],
            "Digitale Gesellschaft & KI": ["Datenschutz", "Social Media", "Cybermobbing"],
            "Diversität & Inklusion": ["Gender", "LGBTQIA+", "Anti-Rassismus"],
            "Work-Life-Balance & New Work": ["Homeoffice", "Sinnsuche", "Side Hustles"],
            "Finanzen & Zukunftssicherheit": ["Finanzielle Bildung", "Krypto", "Altersvorsorge"],
            "Politische Teilhabe & Demokratie": ["Engagement", "Fake News", "Generationengerechtigkeit"],
            "Beziehungen & soziale Netzwerke": ["Freundschaft", "Dating", "Einsamkeit"],
            "On-Demand-Kultur & Mediennutzung": ["Streaming", "Podcasts", "Medienkompetenz"],
            "Konsumverhalten & ethische Marken": ["Nachhaltiger Konsum", "Fair Trade", "Influencer-Marketing"]
        }
        topic = st.selectbox("Thema", list(topics.keys()))
        sub = st.selectbox("Unterthema", topics[topic])
        chat = load_chat(st.session_state.user_id, topic, sub)
        if not chat:
            prompt = get_system_prompt(topic, sub)
            icebreaker = ask_gpt(prompt, [], "")
            save_chat(st.session_state.user_id, topic, sub, "", icebreaker)
            chat = load_chat(st.session_state.user_id, topic, sub)
        for user_msg, bot_msg in chat:
            if user_msg.strip():
                st.markdown(f"🧍 {user_msg}")
            st.markdown(f"🧠 {bot_msg}")
        with st.form("chat_form", clear_on_submit=True):
            user_input = st.text_input("Was bewegt dich?")
            if st.form_submit_button("Senden") and user_input.strip():
                prompt = get_system_prompt(topic, sub)
                reply = ask_gpt(prompt, chat, user_input)
                save_chat(st.session_state.user_id, topic, sub, user_input, reply)
                st.rerun()
    elif menu == "Community":
        community_tab()
    elif menu == "Marktplatz":
        marketplace_tab()
    elif menu == "Nachrichten":
        messages_tab()
    elif menu == "Verbindung":
        dating_tab()

if __name__ == "__main__":
    main()
