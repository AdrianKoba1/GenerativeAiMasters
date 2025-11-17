import streamlit as st
import logging
import pandas as pd
import sqlite3
import os
from utils import safe_agent


#logging the used functions and connecting the database
logging.basicConfig(level=logging.INFO)
DB_PATH = "data/sales_data.db"
TABLE = "sales_data"

#Load Data from SQLite for Metrics & Charts
@st.cache_data
def load_db_table(db_path, table_name):
    with sqlite3.connect(db_path) as con:
        return pd.read_sql_query(f"SELECT * FROM {table_name}", con)

if os.path.exists(DB_PATH):
    df = load_db_table(DB_PATH, TABLE)
else:
    st.error("Database file not found!")
    st.stop()


# Business Info UI
st.title("📊 Data Insights Dashboard")
st.write(f"**Rows:** {df.shape[0]}")
st.write(f"**Columns:** {', '.join(df.columns)}")
if "Total" in df.columns:
    st.write(f"**Total Sales:** {df['Total'].sum():,.2f}")
if "Region" in df.columns and "Total" in df.columns:
    st.line_chart(df.groupby("Region")["Total"].sum())
st.subheader("Sample Data")
st.dataframe(df.head(10))


# Agent Chat UI
st.subheader("💬 Agent Chat")
user_query = st.text_input("Ask a question (e.g. 'Show 5 customer names'):")

if user_query:
    response = safe_agent(user_query)
    st.write("**Agent:**", response)



