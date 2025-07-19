import streamlit as st
import pandas as pd
import datetime
from pymongo import MongoClient
import altair as alt
import base64 # Import the base64 library

# --- Page Configuration ---
st.set_page_config(
    page_title="Weekly  Timetable",
    page_icon="🗓️",
    layout="wide"
)

# --- Function to set background image ---
@st.cache_data
def get_img_as_base64(file):
    """Reads an image file and returns its base64 encoded version."""
    try:
        with open(file, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    except FileNotFoundError:
        st.error(f"Background image file not found. Make sure 'bg.jpg' is in the same folder as your script.")
        return None

# Use the function to get the encoded image
# Ensure you have an image named 'bg.jpg' in your project folder
def get_base64(image_path):
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()

background_path = "bg2.jpg"
img_base64 = get_base64(background_path)

st.markdown(f"""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Gaegu:wght@400;700&display=swap');

     .stApp {{
            background: url("data:image/jpg;base64,{img_base64}") no-repeat center center fixed;
            background-size: cover;
        }}
    
    ::-webkit-scrollbar {{ width: 10px; }}
    ::-webkit-scrollbar-track {{ background: rgba(255, 255, 255, 0.2); }}
    ::-webkit-scrollbar-thumb {{
        background: linear-gradient(135deg, #ee9ca7, #a6c1ee);
        border-radius: 10px;
    }}

    body, .stDataFrame td, .stDataFrame th, .task-text, .stSelectbox {{
        font-family: 'Gaegu', cursive;
    }}
    h1, h2 {{
        font-weight: 700;
        color: #FFFFFF;
        text-shadow: 0px 3px 6px rgba(0, 0, 0, 0.5);
    }}
    
    .stDataFrame, .checklist-container, div[data-testid="stMetric"] {{
        background-color: #FFFFFF;
        border-radius: 20px;
        border: 1px solid rgba(255, 255, 255, 0.5);
        box-shadow: 0 8px 25px rgba(162, 128, 185, 0.4);
        padding: 25px;
        transition: all 0.3s ease;
    }}

    .checklist-container:hover {{
        transform: translateY(-5px);
        box-shadow: 0 12px 30px rgba(162, 128, 185, 0.5);
    }}
    
    .stDataFrame th, .stDataFrame td, .task-text, h3 {{
        color: #3b3041;
        font-size: 1.9rem;
        font-weight: 700;
    }}
    .checklist-header {{
        font-size: 1.7rem;
        font-weight: 700;
        color: #6a447d;
    }}

    .stDataFrame > div > div > div > div > div[data-testid="stDataFrameResizableHandle"] {{
        background-color: #fcecf2;
        color: #6a447d;
        border-bottom: 2px solid #f5b9d3;
    }}

    .stSelectbox div[data-baseweb="select"] > div {{
        background-color: #fcecf2;
        border-radius: 15px;
        border: 2px solid #f5b9d3;
        color: #3b3041;
        font-weight: 700;
    }}
    .stSelectbox div[data-baseweb="select"] > div:hover {{
        border-color: #a6c1ee;
    }}

    div[data-testid="stMetricLabel"] {{
        font-family: 'Gaegu', cursive;
        font-weight: 700;
        color: #6a447d;
    }}
    div[data-testid="stMetricValue"] {{
        font-family: 'Gaegu', cursive;
        font-weight: 700;
        font-size: 2.5rem;
        color: #3b3041;
    }}
</style>
""", unsafe_allow_html=True)



# --- (The rest of your Python code remains exactly the same) ---
# --- MongoDB Connection, Database Helpers, Analytics Functions, Main App layout ---

# --- MongoDB Connection (Hardcoded) ---
client = MongoClient(
    'mongodb+srv://soumyadeepdas2511:dxRsCQDq7YQSc1vh@cluster0.zmm4k.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0'
)

# --- Database Helper Functions ---
def get_or_create_log(date_str, tasks_for_day):
    db = client["task_tracker"]
    collection = db["daily_logs"]
    log = collection.find_one({"_id": date_str})

    if log is None:
        st.toast(f"Creating new log for {date_str}...")
        new_log_tasks = [
            {"name": task, "bby_status": "Not Done", "bbu_status": "Not Done"}
            for task in tasks_for_day if task not in ['—', 'BREAK']
        ]
        new_log = {"_id": date_str, "tasks": new_log_tasks}
        collection.insert_one(new_log)
        return new_log
    return log

def update_task_status(date_str, task_name, person):
    key = f"{person}_{task_name}"
    new_status = st.session_state[key]
    
    db = client["task_tracker"]
    collection = db["daily_logs"]
    
    collection.update_one(
        {"_id": date_str, "tasks.name": task_name},
        {"$set": {f"tasks.$.{person}_status": new_status}}
    )
    st.toast(f"Set '{task_name}' to '{new_status}' for {person.upper()}!", icon="👍")

# --- Analytics Functions ---
@st.cache_data(ttl=600)
def get_available_months(_collection):
    pipeline = [
        {"$project": {"month": {"$substrCP": [{"$toString": "$_id"}, 0, 7]}}},
        {"$match": {"month": {"$regex": r"^\d{4}-\d{2}$"}}},
        {"$group": {"_id": "$month"}},
        {"$sort": {"_id": -1}}
    ]
    return [doc["_id"] for doc in _collection.aggregate(pipeline)]

@st.cache_data(ttl=600)
def get_monthly_task_completions(_collection, selected_month):
    pipeline = [
        {"$match": {"_id": {"$regex": f"^{selected_month}"}}},
        {"$unwind": "$tasks"},
        {"$group": {
            "_id": "$tasks.name",
            "BBY Completions": {"$sum": {"$cond": [{"$eq": ["$tasks.bby_status", "Done"]}, 1, 0]}},
            "BBU Completions": {"$sum": {"$cond": [{"$eq": ["$tasks.bbu_status", "Done"]}, 1, 0]}}
        }},
        {"$sort": {"_id": 1}}
    ]
    return list(_collection.aggregate(pipeline))

@st.cache_data(ttl=600)
def get_daily_progress_data(_collection, selected_month):
    pipeline = [
        {"$match": {"_id": {"$regex": f"^{selected_month}"}}},
        {"$unwind": "$tasks"},
        {"$group": {
            "_id": {"$substrCP": ["$_id", 8, 2]},
            "BBY": {"$sum": {"$cond": [{"$eq": ["$tasks.bby_status", "Done"]}, 1, 0]}},
            "BBU": {"$sum": {"$cond": [{"$eq": ["$tasks.bbu_status", "Done"]}, 1, 0]}}
        }},
        {"$sort": {"_id": 1}}
    ]
    return list(_collection.aggregate(pipeline))

# --- Main App ---
st.title("🗓️  Weekly Timetable")

# --- Timetable Data and Display ---
timetable_data = {
    'Monday': ['DSA', 'React Js', 'Aptitude', 'Projects', 'LEET', 'GYM'],
    'Tuesday': ['DAA', 'React Js', 'Aptitude', 'Projects', 'LEET', 'GYM'],
    'Wednesday': ['DBMS', 'React Js', 'Aptitude', 'Projects', 'LEET', 'BREAK'],
    'Thursday': ['DSA', 'BREAK', 'BREAK', 'DN/NPN', 'LEET', 'GYM'],
    'Friday': ['DAA', 'BREAK', 'BREAK', 'DN/NPN', 'LEET', 'GYM'],
    'Saturday': ['DBMS', 'React Js', 'Aptitude', 'Projects', 'LEET', 'BREAK'],
}
index_labels = [
    '📚 5 videos/day', '💻 Programming Language', '🧠 1 chapter/day',
    '🚀 Internship / Projects', '☕ JAVA/DBMS', '💪 IMP'
]
df = pd.DataFrame(timetable_data, index=index_labels)
def style_special_cells(val):
    if val == 'BREAK': return 'background-color: #FEF08A; color: #713F12;'
    elif val == '—': return 'background-color: #E5E7EB; color: #4B5563;'
    return ''
st.dataframe(df.style.applymap(style_special_cells), use_container_width=True)


# --- Interactive Checklist Section ---
st.header("🎯 Today's Focus")

today_name = datetime.datetime.now().strftime('%A')
today_str = datetime.date.today().isoformat()

if client and today_name in timetable_data:
    tasks_today_all = timetable_data[today_name]
    log_data = get_or_create_log(today_str, tasks_today_all)
    status_map = {task['name']: task for task in log_data.get('tasks', [])}

    #st.markdown('<div class="checklist-container">', unsafe_allow_html=True)
    header_cols = st.columns((4, 2, 2))
    header_cols[0].markdown("<p class='checklist-header'>Task</p>", unsafe_allow_html=True)
    header_cols[1].markdown("<p class='checklist-header'>BBY</p>", unsafe_allow_html=True)
    header_cols[2].markdown("<p class='checklist-header'>BBU</p>", unsafe_allow_html=True)
    
    status_options = ["Not Done", "Doing", "Done"]

    for task in tasks_today_all:
        if task in ['—', 'BREAK']:
            continue
        
        task_status = status_map.get(task, {"bby_status": "Not Done", "bbu_status": "Not Done"})
        
        task_cols = st.columns((4, 2, 2))
        task_cols[0].markdown(f"<div class='task-text'>{task}</div>", unsafe_allow_html=True)
        
        # BBY Dropdown
        bby_saved_status = task_status.get('bby_status', 'Not Done')
        try:
            bby_default_index = status_options.index(bby_saved_status)
        except ValueError:
            bby_default_index = 0
        
        task_cols[1].selectbox(
            label=f"BBY_{task}", options=status_options, index=bby_default_index,
            key=f"bby_{task}", on_change=update_task_status,
            kwargs=dict(date_str=today_str, task_name=task, person="bby"),
            label_visibility="collapsed"
        )
        
        # BBU Dropdown
        bbu_saved_status = task_status.get('bbu_status', 'Not Done')
        try:
            bbu_default_index = status_options.index(bbu_saved_status)
        except ValueError:
            bbu_default_index = 0
            
        task_cols[2].selectbox(
            label=f"BBU_{task}", options=status_options, index=bbu_default_index,
            key=f"bbu_{task}", on_change=update_task_status,
            kwargs=dict(date_str=today_str, task_name=task, person="bbu"),
            label_visibility="collapsed"
        )
        
    st.markdown('</div>', unsafe_allow_html=True)

elif today_name == "Sunday":
    st.success("🎉 It's Sunday! A day for rest. No tasks scheduled.")


# --- Analytics & Progress Section ---
st.markdown("---")
st.header("📊 Analytics & Progress")

if client:
    db = client["task_tracker"]
    collection = db["daily_logs"]
    
    available_months = get_available_months(collection)

    if not available_months:
        st.info("No data available yet. Complete some tasks to see your progress!")
    else:
        # --- Month Selector ---
        selected_month = st.selectbox("Select a month to view analytics:", options=available_months)
        
        # --- Get Data for Selected Month ---
        monthly_task_data = get_monthly_task_completions(collection, selected_month)
        daily_progress_data = get_daily_progress_data(collection, selected_month)

        if not monthly_task_data:
            st.warning(f"No tasks were marked as 'Done' in {selected_month}.")
        else:
            # --- Overall & Per-Task Tables (Now Filtered by Month) ---
            st.subheader(f"Monthly Summary for {selected_month}")
            
            analytics_df = pd.DataFrame(monthly_task_data).rename(columns={"_id": "Task"}).set_index("Task")
            
            bby_total = analytics_df["BBY Completions"].sum()
            bbu_total = analytics_df["BBU Completions"].sum()
            col1, col2 = st.columns(2)
            col1.metric("BBY's Total Tasks Done", f"{int(bby_total)}")
            col2.metric("BBU's Total Tasks Done", f"{int(bbu_total)}")
            
            st.dataframe(analytics_df, use_container_width=True)

            # --- Altair Line Chart for Monthly Progress ---
            st.subheader(f"Cumulative Progress in {selected_month}")
            if daily_progress_data:
                progress_df = pd.DataFrame(daily_progress_data).rename(columns={"_id": "Day"}).set_index("Day").sort_index()
                
                if not progress_df.empty:
                    progress_df.index = progress_df.index.astype(int)
                    year, month = map(int, selected_month.split('-'))
                    days_in_month = pd.Period(selected_month).days_in_month
                    full_day_index = pd.Index(range(1, days_in_month + 1), name="Day")
                    progress_df = progress_df.reindex(full_day_index, fill_value=0)

                cumulative_df = progress_df.cumsum()

                # Reshape data from wide to long format for Altair
                chart_data = cumulative_df.reset_index().melt('Day', var_name='Person', value_name='Tasks Done')

                # Create the Altair chart
                chart = alt.Chart(chart_data).mark_line().encode(
                    x=alt.X('Day', title='Day of the Month'),
                    y=alt.Y('Tasks Done', title='Cumulative Tasks Done'),
                    color=alt.Color('Person', title='Person', scale=alt.Scale(scheme='category10')), # Assigns different colors
                    tooltip=['Day', 'Person', 'Tasks Done']
                ).interactive()

                st.altair_chart(chart, use_container_width=True)
            else:
                st.info("No tasks marked 'Done' to show progress chart.")
