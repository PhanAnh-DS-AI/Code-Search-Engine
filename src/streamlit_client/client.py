import streamlit as st

# Set page config for the entire app
st.set_page_config(page_title="Code Semantic Search", layout="wide")
# Main content (only shown on default page)
st.title("_Semantic Search_ is :blue[cool] :sunglasses:")
st.markdown("Search engine for Github Repositories")

# Define pages
main_page = st.Page("page/main_page.py", title= "Mainpage", icon=":material/home:")
search_page = st.Page("page/search_page.py", title="Search", icon=":material/search:")
recommendation_page = st.Page("page/recommendation_page.py", title="Recommendation", icon=":material/recommend:", default=False)

# Sidebar
# st.header("Navigation")
page = st.navigation({
    "Mainpage": [main_page],
    "Tools": [search_page, recommendation_page]
})

if __name__ == "__main__":
    page.run()

