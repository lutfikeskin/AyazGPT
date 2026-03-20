import streamlit as st

st.set_page_config(page_title="MyMind - Personal AI", layout="wide", page_icon="🧠")

# Define pages relative to ui/ folder (since it runs from root usually or ui/)
# If run with 'streamlit run ui/app.py', paths are relative to ui/ or absolute.
# The user suggests "pages/investment.py" which implies execution from ui/ or handled by streamlit.
home_page = st.Page("pages/home.py", title="Home", icon="🏠", default=True)
investment_page = st.Page("pages/investment.py", title="Investment", icon="📈")

pg = st.navigation([home_page, investment_page])
pg.run()
