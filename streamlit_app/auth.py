import streamlit as st

USERS = {
    "admin": {"password": "admin123", "role": "ADMIN"},
    "analyst": {"password": "analyst123", "role": "ANALYST"},
}

def login():
    username = st.sidebar.text_input("User")
    password = st.sidebar.text_input("Password", type="password")

    if st.sidebar.button("Login"):
        if username in USERS and USERS[username]["password"] == password:
            st.session_state.user = username
            st.session_state.role = USERS[username]["role"]
            st.sidebar.success(f"Logged in as {username}")
        else:
            st.sidebar.error("Invalid credentials")