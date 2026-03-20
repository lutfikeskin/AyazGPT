import streamlit as st
import requests

st.title("MyMind Dashboard")
st.write("Welcome to your personal AI assistant. Use the sidebar to navigate between modules.")

try:
    response = requests.get("http://127.0.0.1:8000/health")
    if response.status_code == 200:
        st.success("Backend is reachable")
        st.json(response.json())
    else:
        st.error(f"Backend returned status {response.status_code}")
except Exception as e:
    st.error(f"Failed to connect to backend: {e}")
