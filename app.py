import streamlit as st
import pandas as pd
from datetime import datetime, date
import hashlib
import plotly.express as px
import plotly.graph_objects as go
import firebase_admin
from firebase_admin import credentials, firestore
import json

# Page configuration
st.set_page_config(page_title="Session Tracker", page_icon="📚", layout="wide")


# Initialize Firebase
@st.cache_resource
def init_firebase():
    try:
        # Check if already initialized
        firebase_admin.get_app()
    except ValueError:
        # Initialize with Streamlit secrets
        cred_dict = {
            "type": st.secrets["firebase"]["type"],
            "project_id": st.secrets["firebase"]["project_id"],
            "private_key_id": st.secrets["firebase"]["private_key_id"],
            "private_key": st.secrets["firebase"]["private_key"],
            "client_email": st.secrets["firebase"]["client_email"],
            "client_id": st.secrets["firebase"]["client_id"],
            "auth_uri": st.secrets["firebase"]["auth_uri"],
            "token_uri": st.secrets["firebase"]["token_uri"],
            "auth_provider_x509_cert_url": st.secrets["firebase"]["auth_provider_x509_cert_url"],
            "client_x509_cert_url": st.secrets["firebase"]["client_x509_cert_url"]
        }
        cred = credentials.Certificate(cred_dict)
        firebase_admin.initialize_app(cred)

    return firestore.client()


# Initialize Firestore
db = init_firebase()


# Helper functions
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def load_user(email):
    """Load user from Firestore"""
    user_ref = db.collection('users').document(email)
    user = user_ref.get()
    if user.exists:
        return user.to_dict()
    return None


def create_user(email, password):
    """Create new user in Firestore"""
    user_ref = db.collection('users').document(email)
    user_ref.set({
        'email': email,
        'password': hash_password(password),
        'created_at': firestore.SERVER_TIMESTAMP
    })


def load_sessions(email):
    """Load sessions from Firestore"""
    sessions_ref = db.collection('sessions').where('user_email', '==', email).stream()
    sessions = []
    for doc in sessions_ref:
        session_data = doc.to_dict()
        session_data['id'] = doc.id
        sessions.append(session_data)
    return sessions


def save_session(email, session_data):
    """Save a new session to Firestore"""
    session_data['user_email'] = email
    session_data['created_at'] = firestore.SERVER_TIMESTAMP
    db.collection('sessions').add(session_data)


def update_session(session_id, session_data):
    """Update existing session in Firestore"""
    db.collection('sessions').document(session_id).update(session_data)


def delete_session(session_id):
    """Delete session from Firestore"""
    db.collection('sessions').document(session_id).delete()


def delete_all_sessions(email):
    """Delete all sessions for a user"""
    sessions_ref = db.collection('sessions').where('user_email', '==', email).stream()
    for doc in sessions_ref:
        doc.reference.delete()


# Preferences functions
def load_preferences(email):
    """Load user preferences from Firestore"""
    pref_ref = db.collection('preferences').document(email)
    pref = pref_ref.get()
    if pref.exists:
        return pref.to_dict()
    return {'academies': [], 'groups': [], 'default_rate': 200.0}


def save_preferences(email, preferences):
    """Save user preferences to Firestore"""
    db.collection('preferences').document(email).set(preferences)


# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = None
if 'sessions' not in st.session_state:
    st.session_state.sessions = []
if 'preferences' not in st.session_state:
    st.session_state.preferences = {'academies': [], 'groups': [], 'default_rate': 200.0}

# Authentication UI
if not st.session_state.logged_in:
    st.title("📚 Session Tracker - Login")

    tab1, tab2 = st.tabs(["Login", "Sign Up"])

    with tab1:
        st.subheader("Login to Your Account")
        with st.form("login_form"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            login_btn = st.form_submit_button("Login", use_container_width=True)

            if login_btn:
                user = load_user(email)
                if user and user['password'] == hash_password(password):
                    st.session_state.logged_in = True
                    st.session_state.user_email = email
                    st.session_state.sessions = load_sessions(email)
                    st.session_state.preferences = load_preferences(email)
                    st.success("✅ Login successful!")
                    st.rerun()
                else:
                    st.error("❌ Invalid email or password!")

    with tab2:
        st.subheader("Create New Account")
        with st.form("signup_form"):
            new_email = st.text_input("Email")
            new_password = st.text_input("Password", type="password")
            confirm_password = st.text_input("Confirm Password", type="password")
            signup_btn = st.form_submit_button("Sign Up", use_container_width=True)

            if signup_btn:
                if not new_email or not new_password:
                    st.error("⚠️ Please fill in all fields!")
                elif new_password != confirm_password:
                    st.error("❌ Passwords don't match!")
                else:
                    existing_user = load_user(new_email)
                    if existing_user:
                        st.error("❌ Email already exists!")
                    else:
                        create_user(new_email, new_password)
                        st.success("✅ Account created! Please login.")

    st.stop()

# Main App (after login)
# Header with logout
col1, col2 = st.columns([6, 1])
with col1:
    st.title("📚 Session Tracker for Instructors")
with col2:
    if st.button("🚪 Logout"):
        st.session_state.logged_in = False
        st.session_state.user_email = None
        st.session_state.sessions = []
        st.rerun()

st.markdown(f"**User:** {st.session_state.user_email}")
st.markdown("---")

# Sidebar for adding new session
with st.sidebar:
    st.header("➕ Log New Session")

    # Get preferences
    prefs = st.session_state.preferences
    academy_list = prefs.get('academies', [])
    group_list = prefs.get('groups', [])
    default_rate = prefs.get('default_rate', 200.0)

    with st.form("add_session"):
        # Academy input with autocomplete
        if academy_list:
            academy_choice = st.selectbox("Academy*", ["Select..."] + academy_list + ["+ Add New"])
            if academy_choice == "+ Add New":
                academy = st.text_input("Enter new academy name*", placeholder="e.g., Tech Academy")
            elif academy_choice == "Select...":
                academy = ""
            else:
                academy = academy_choice
        else:
            academy = st.text_input("Academy/Institution*", placeholder="e.g., Tech Academy")

        # Group input with autocomplete
        if group_list:
            group_choice = st.selectbox("Group*", ["Select..."] + group_list + ["+ Add New"])
            if group_choice == "+ Add New":
                group = st.text_input("Enter new group name*", placeholder="e.g., AI Fundamentals - Group A")
            elif group_choice == "Select...":
                group = ""
            else:
                group = group_choice
        else:
            group = st.text_input("Group/Course*", placeholder="e.g., AI Fundamentals - Group A")

        session_date = st.date_input("Date*", value=date.today())
        hours = st.number_input("Hours*", min_value=0.5, max_value=12.0, value=2.0, step=0.5)
        rate = st.number_input("Hourly Rate (EGP)*", min_value=0.0, value=default_rate, step=50.0)
        notes = st.text_area("Notes (optional)", placeholder="Any additional details...")

        submitted = st.form_submit_button("💾 Save Session", use_container_width=True)

        if submitted:
            if academy and group:
                session = {
                    "academy": academy,
                    "group": group,
                    "date": session_date.strftime("%Y-%m-%d"),
                    "hours": hours,
                    "rate": rate,
                    "amount": hours * rate,
                    "notes": notes
                }
                save_session(st.session_state.user_email, session)
                st.session_state.sessions = load_sessions(st.session_state.user_email)
                st.success("✅ Session logged!")
                st.rerun()
            else:
                st.error("⚠️ Fill required fields!")

# Main content
if len(st.session_state.sessions) == 0:
    st.info("👈 Start by logging your first session using the sidebar!")
else:
    df = pd.DataFrame(st.session_state.sessions)
    df['date'] = pd.to_datetime(df['date'])

    tabs = st.tabs(["📊 Dashboard", "📈 Analytics", "📅 All Sessions", "📋 Monthly Report", "⚡ Bulk Insert", "⚙️ Manage",
                    "🎯 Preferences"])

    with tabs[0]:
        st.header("Dashboard Overview")

        current_month = datetime.now().month
        current_year = datetime.now().year
        current_month_data = df[(df['date'].dt.month == current_month) & (df['date'].dt.year == current_year)]

        # Metrics
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            total_hours = current_month_data['hours'].sum()
            st.metric("Total Hours (This Month)", f"{total_hours:.1f} hrs")

        with col2:
            total_amount = current_month_data['amount'].sum()
            st.metric("Expected Payment", f"{total_amount:,.0f} EGP")

        with col3:
            num_sessions = len(current_month_data)
            st.metric("Sessions This Month", num_sessions)

        with col4:
            num_academies = current_month_data['academy'].nunique()
            st.metric("Academies", num_academies)

        st.markdown("---")

        # Quick graphs
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("💰 Revenue by Academy (This Month)")
            if not current_month_data.empty:
                academy_revenue = current_month_data.groupby('academy')['amount'].sum().sort_values(ascending=True)
                fig = px.bar(academy_revenue, orientation='h',
                             labels={'value': 'Amount (EGP)', 'academy': 'Academy'},
                             color=academy_revenue.values,
                             color_continuous_scale='Blues')
                fig.update_layout(showlegend=False, height=300)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No data yet")

        with col2:
            st.subheader("⏰ Hours by Academy (This Month)")
            if not current_month_data.empty:
                academy_hours = current_month_data.groupby('academy')['hours'].sum()
                fig = px.pie(values=academy_hours.values, names=academy_hours.index,
                             hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu)
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("No data yet")

        st.markdown("---")

        # Breakdown table
        st.subheader("📍 Breakdown by Academy")
        academy_summary = current_month_data.groupby('academy').agg({
            'hours': 'sum',
            'amount': 'sum',
            'group': 'count'
        }).rename(columns={'group': 'sessions'}).sort_values('amount', ascending=False)

        if not academy_summary.empty:
            st.dataframe(academy_summary.style.format({
                'hours': '{:.1f} hrs',
                'amount': '{:,.0f} EGP',
                'sessions': '{:.0f}'
            }), use_container_width=True)

    with tabs[1]:
        st.header("📈 Analytics & Insights")

        # Time range selector
        col1, col2 = st.columns(2)
        with col1:
            months_back = st.slider("Show last N months", 1, 12, 6)

        cutoff_date = datetime.now() - pd.DateOffset(months=months_back)
        recent_data = df[df['date'] >= cutoff_date]

        # Monthly trends
        st.subheader("📊 Monthly Trends")
        monthly_stats = recent_data.groupby(recent_data['date'].dt.to_period('M')).agg({
            'hours': 'sum',
            'amount': 'sum',
            'academy': 'count'
        }).rename(columns={'academy': 'sessions'})
        monthly_stats.index = monthly_stats.index.astype(str)

        if not monthly_stats.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=monthly_stats.index, y=monthly_stats['amount'],
                                     name='Revenue (EGP)', mode='lines+markers',
                                     line=dict(color='#1f77b4', width=3)))
            fig.update_layout(title='Monthly Revenue Trend',
                              xaxis_title='Month', yaxis_title='Amount (EGP)',
                              height=350)
            st.plotly_chart(fig, use_container_width=True)

            col1, col2 = st.columns(2)
            with col1:
                fig2 = px.bar(monthly_stats, x=monthly_stats.index, y='hours',
                              labels={'x': 'Month', 'hours': 'Hours'},
                              title='Monthly Hours', color='hours',
                              color_continuous_scale='Greens')
                fig2.update_layout(height=300)
                st.plotly_chart(fig2, use_container_width=True)

            with col2:
                fig3 = px.bar(monthly_stats, x=monthly_stats.index, y='sessions',
                              labels={'x': 'Month', 'sessions': 'Sessions'},
                              title='Monthly Sessions Count', color='sessions',
                              color_continuous_scale='Oranges')
                fig3.update_layout(height=300)
                st.plotly_chart(fig3, use_container_width=True)

        st.markdown("---")

        # Academy comparison
        st.subheader("🏛️ Academy Performance Comparison")
        academy_stats = recent_data.groupby('academy').agg({
            'hours': 'sum',
            'amount': 'sum',
            'group': 'count'
        }).rename(columns={'group': 'sessions'}).sort_values('amount', ascending=False)

        if not academy_stats.empty:
            fig4 = go.Figure(data=[
                go.Bar(name='Hours', x=academy_stats.index, y=academy_stats['hours']),
                go.Bar(name='Sessions', x=academy_stats.index, y=academy_stats['sessions'])
            ])
            fig4.update_layout(barmode='group', title='Hours vs Sessions by Academy',
                               height=350)
            st.plotly_chart(fig4, use_container_width=True)

        st.markdown("---")

        # Hourly rate analysis
        st.subheader("💵 Hourly Rate Distribution")
        col1, col2 = st.columns(2)

        with col1:
            avg_rate_by_academy = recent_data.groupby('academy')['rate'].mean().sort_values(ascending=False)
            fig5 = px.bar(avg_rate_by_academy, orientation='h',
                          labels={'value': 'Avg Rate (EGP)', 'academy': 'Academy'},
                          title='Average Hourly Rate by Academy',
                          color=avg_rate_by_academy.values,
                          color_continuous_scale='Viridis')
            fig5.update_layout(showlegend=False, height=300)
            st.plotly_chart(fig5, use_container_width=True)

        with col2:
            fig6 = px.histogram(recent_data, x='rate', nbins=20,
                                title='Rate Distribution',
                                labels={'rate': 'Hourly Rate (EGP)', 'count': 'Frequency'},
                                color_discrete_sequence=['#ff7f0e'])
            fig6.update_layout(height=300)
            st.plotly_chart(fig6, use_container_width=True)

    with tabs[2]:
        st.header("All Sessions")

        # Filters
        col1, col2, col3 = st.columns(3)
        with col1:
            selected_academy = st.selectbox("Academy", ["All"] + sorted(df['academy'].unique().tolist()))
        with col2:
            selected_month = st.selectbox("Month", ["All"] + sorted(df['date'].dt.strftime('%Y-%m').unique().tolist(),
                                                                    reverse=True))
        with col3:
            selected_group = st.selectbox("Group", ["All"] + sorted(df['group'].unique().tolist()))

        # Apply filters
        filtered_df = df.copy()
        if selected_academy != "All":
            filtered_df = filtered_df[filtered_df['academy'] == selected_academy]
        if selected_month != "All":
            filtered_df = filtered_df[filtered_df['date'].dt.strftime('%Y-%m') == selected_month]
        if selected_group != "All":
            filtered_df = filtered_df[filtered_df['group'] == selected_group]

        # Display
        display_df = filtered_df[['date', 'academy', 'group', 'hours', 'rate', 'amount', 'notes']].sort_values('date',
                                                                                                               ascending=False)
        display_df['date'] = display_df['date'].dt.strftime('%Y-%m-%d')

        st.dataframe(display_df.style.format({
            'hours': '{:.1f}',
            'rate': '{:,.0f}',
            'amount': '{:,.0f}'
        }), use_container_width=True)

        # Summary
        st.markdown("---")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Sessions", len(filtered_df))
        with col2:
            st.metric("Total Hours", f"{filtered_df['hours'].sum():.1f}")
        with col3:
            st.metric("Total Amount", f"{filtered_df['amount'].sum():,.0f} EGP")

    with tabs[3]:
        st.header("Monthly Report Generator")

        available_months = sorted(df['date'].dt.strftime('%Y-%m').unique().tolist(), reverse=True)
        selected_report_month = st.selectbox("Select Month", available_months)

        if selected_report_month:
            report_data = df[df['date'].dt.strftime('%Y-%m') == selected_report_month]

            st.subheader(f"📅 Report for {selected_report_month}")

            for academy in report_data['academy'].unique():
                with st.expander(f"📍 {academy}", expanded=True):
                    academy_data = report_data[report_data['academy'] == academy]

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Sessions", len(academy_data))
                    with col2:
                        st.metric("Total Hours", f"{academy_data['hours'].sum():.1f}")
                    with col3:
                        st.metric("Amount Due", f"{academy_data['amount'].sum():,.0f} EGP")

                    session_details = academy_data[['date', 'group', 'hours', 'rate', 'amount']].copy()
                    session_details['date'] = session_details['date'].dt.strftime('%Y-%m-%d')
                    st.dataframe(session_details.style.format({
                        'hours': '{:.1f}',
                        'rate': '{:,.0f}',
                        'amount': '{:,.0f}'
                    }), use_container_width=True)

            st.markdown("---")
            st.subheader("📊 Month Total")
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Sessions", len(report_data))
            with col2:
                st.metric("Total Hours", f"{report_data['hours'].sum():.1f}")
            with col3:
                st.metric("Total Amount", f"{report_data['amount'].sum():,.0f} EGP")

    with tabs[4]:
        st.header("⚡ Bulk Insert Sessions")

        bulk_mode = st.radio("Choose bulk insert mode:",
                             ["Weekly Schedule", "Multiple Sessions", "Import from Text"])

        if bulk_mode == "Weekly Schedule":
            st.subheader("📅 Weekly Schedule Entry")
            st.info("Perfect for recurring weekly classes! Set up your schedule once and log all sessions.")

            with st.form("weekly_schedule"):
                col1, col2 = st.columns(2)

                with col1:
                    # Academy and Group selection
                    prefs = st.session_state.preferences
                    academy_list = prefs.get('academies', [])
                    group_list = prefs.get('groups', [])
                    default_rate = prefs.get('default_rate', 200.0)

                    if academy_list:
                        ws_academy = st.selectbox("Academy*", academy_list, key="ws_academy")
                    else:
                        ws_academy = st.text_input("Academy*", key="ws_academy")

                    if group_list:
                        ws_group = st.selectbox("Group*", group_list, key="ws_group")
                    else:
                        ws_group = st.text_input("Group*", key="ws_group")

                    ws_hours = st.number_input("Hours per session*", min_value=0.5, max_value=12.0, value=2.0, step=0.5)
                    ws_rate = st.number_input("Hourly Rate*", min_value=0.0, value=default_rate, step=50.0)

                with col2:
                    # Week range
                    st.markdown("**Select Week Range:**")
                    start_date = st.date_input("Start Date*", value=date.today())
                    num_weeks = st.number_input("Number of Weeks*", min_value=1, max_value=12, value=4)

                    # Days selection
                    st.markdown("**Select Days:**")
                    days_selected = []
                    col_a, col_b = st.columns(2)
                    with col_a:
                        if st.checkbox("Sunday"): days_selected.append(6)
                        if st.checkbox("Monday"): days_selected.append(0)
                        if st.checkbox("Tuesday"): days_selected.append(1)
                        if st.checkbox("Wednesday"): days_selected.append(2)
                    with col_b:
                        if st.checkbox("Thursday"): days_selected.append(3)
                        if st.checkbox("Friday"): days_selected.append(4)
                        if st.checkbox("Saturday"): days_selected.append(5)

                ws_notes = st.text_area("Notes (optional)", key="ws_notes")

                submit_weekly = st.form_submit_button("📅 Generate Sessions", use_container_width=True)

                if submit_weekly:
                    if ws_academy and ws_group and days_selected:
                        sessions_added = 0
                        current_date = start_date

                        for week in range(num_weeks):
                            for day_num in range(7):
                                check_date = current_date + pd.Timedelta(days=day_num + (week * 7))
                                if check_date.weekday() in days_selected:
                                    session = {
                                        "academy": ws_academy,
                                        "group": ws_group,
                                        "date": check_date.strftime("%Y-%m-%d"),
                                        "hours": ws_hours,
                                        "rate": ws_rate,
                                        "amount": ws_hours * ws_rate,
                                        "notes": ws_notes
                                    }
                                    save_session(st.session_state.user_email, session)
                                    sessions_added += 1

                        st.session_state.sessions = load_sessions(st.session_state.user_email)
                        st.success(f"✅ Added {sessions_added} sessions!")
                        st.rerun()
                    else:
                        st.error("⚠️ Fill all required fields and select at least one day!")

        elif bulk_mode == "Multiple Sessions":
            st.subheader("📝 Quick Multiple Sessions Entry")
            st.info("Add multiple sessions for the same date quickly!")

            with st.form("multiple_sessions"):
                col1, col2 = st.columns(2)

                with col1:
                    prefs = st.session_state.preferences
                    academy_list = prefs.get('academies', [])
                    group_list = prefs.get('groups', [])
                    default_rate = prefs.get('default_rate', 200.0)

                    ms_date = st.date_input("Date for all sessions*", value=date.today())
                    num_sessions = st.number_input("Number of sessions*", min_value=1, max_value=10, value=3)

                with col2:
                    st.write("")  # Spacing

                st.markdown("---")
                st.markdown("**Enter session details:**")

                sessions_data = []
                for i in range(int(num_sessions)):
                    with st.expander(f"Session {i + 1}", expanded=True):
                        col_a, col_b, col_c, col_d = st.columns(4)

                        with col_a:
                            if academy_list:
                                sess_academy = st.selectbox("Academy*", academy_list, key=f"ms_academy_{i}")
                            else:
                                sess_academy = st.text_input("Academy*", key=f"ms_academy_{i}")

                        with col_b:
                            if group_list:
                                sess_group = st.selectbox("Group*", group_list, key=f"ms_group_{i}")
                            else:
                                sess_group = st.text_input("Group*", key=f"ms_group_{i}")

                        with col_c:
                            sess_hours = st.number_input("Hours*", min_value=0.5, max_value=12.0,
                                                         value=2.0, step=0.5, key=f"ms_hours_{i}")

                        with col_d:
                            sess_rate = st.number_input("Rate*", min_value=0.0,
                                                        value=default_rate, step=50.0, key=f"ms_rate_{i}")

                        sessions_data.append({
                            'academy': sess_academy,
                            'group': sess_group,
                            'hours': sess_hours,
                            'rate': sess_rate
                        })

                submit_multiple = st.form_submit_button("💾 Save All Sessions", use_container_width=True)

                if submit_multiple:
                    valid_sessions = [s for s in sessions_data if s['academy'] and s['group']]

                    if valid_sessions:
                        for sess in valid_sessions:
                            session = {
                                "academy": sess['academy'],
                                "group": sess['group'],
                                "date": ms_date.strftime("%Y-%m-%d"),
                                "hours": sess['hours'],
                                "rate": sess['rate'],
                                "amount": sess['hours'] * sess['rate'],
                                "notes": ""
                            }
                            save_session(st.session_state.user_email, session)

                        st.session_state.sessions = load_sessions(st.session_state.user_email)
                        st.success(f"✅ Added {len(valid_sessions)} sessions!")
                        st.rerun()
                    else:
                        st.error("⚠️ Fill academy and group for at least one session!")

        else:  # Import from Text
            st.subheader("📋 Import from Text")
            st.info("Paste session data in this format (one per line):\nDate, Academy, Group, Hours, Rate")

            st.markdown("**Example:**")
            st.code("""2024-11-01, Tech Academy, AI Group A, 2, 250
2024-11-02, Data School, Python Basics, 3, 200
2024-11-03, Tech Academy, ML Advanced, 2.5, 300""")

            with st.form("import_text"):
                text_input = st.text_area("Paste your sessions here*", height=200,
                                          placeholder="2024-11-01, Tech Academy, AI Group A, 2, 250")

                submit_import = st.form_submit_button("📥 Import Sessions", use_container_width=True)

                if submit_import and text_input:
                    lines = text_input.strip().split('\n')
                    imported = 0
                    errors = []

                    for idx, line in enumerate(lines, 1):
                        try:
                            parts = [p.strip() for p in line.split(',')]
                            if len(parts) >= 5:
                                session = {
                                    "academy": parts[1],
                                    "group": parts[2],
                                    "date": pd.to_datetime(parts[0]).strftime("%Y-%m-%d"),
                                    "hours": float(parts[3]),
                                    "rate": float(parts[4]),
                                    "amount": float(parts[3]) * float(parts[4]),
                                    "notes": parts[5] if len(parts) > 5 else ""
                                }
                                save_session(st.session_state.user_email, session)
                                imported += 1
                            else:
                                errors.append(f"Line {idx}: Not enough fields")
                        except Exception as e:
                            errors.append(f"Line {idx}: {str(e)}")

                    st.session_state.sessions = load_sessions(st.session_state.user_email)

                    if imported > 0:
                        st.success(f"✅ Imported {imported} sessions!")
                    if errors:
                        st.warning("⚠️ Some lines had errors:\n" + "\n".join(errors[:5]))

                    if imported > 0:
                        st.rerun()

    with tabs[5]:
        st.header("Manage Sessions")

        st.warning("⚠️ Use carefully!")

        # Edit session
        st.subheader("✏️ Edit a Session")
        session_options = [f"{i}: {s['date']} - {s['academy']} - {s['group']} ({s['hours']}hrs)"
                           for i, s in enumerate(st.session_state.sessions)]

        if session_options:
            session_to_edit = st.selectbox("Select session to edit", session_options, key="edit_selector")

            if session_to_edit:
                index = int(session_to_edit.split(":")[0])
                session = st.session_state.sessions[index]

                with st.form("edit_session_form"):
                    st.markdown("**Edit Session Details:**")

                    col1, col2 = st.columns(2)
                    with col1:
                        edit_academy = st.text_input("Academy*", value=session['academy'])
                        edit_group = st.text_input("Group*", value=session['group'])
                        edit_date = st.date_input("Date*", value=pd.to_datetime(session['date']))

                    with col2:
                        edit_hours = st.number_input("Hours*", min_value=0.5, max_value=12.0,
                                                     value=float(session['hours']), step=0.5)
                        edit_rate = st.number_input("Hourly Rate (EGP)*", min_value=0.0,
                                                    value=float(session['rate']), step=50.0)
                        edit_notes = st.text_area("Notes", value=session.get('notes', ''))

                    col1, col2 = st.columns(2)
                    with col1:
                        save_btn = st.form_submit_button("💾 Save Changes", use_container_width=True)
                    with col2:
                        cancel_btn = st.form_submit_button("❌ Cancel", use_container_width=True)

                    if save_btn:
                        if edit_academy and edit_group:
                            updated_session = {
                                "academy": edit_academy,
                                "group": edit_group,
                                "date": edit_date.strftime("%Y-%m-%d"),
                                "hours": edit_hours,
                                "rate": edit_rate,
                                "amount": edit_hours * edit_rate,
                                "notes": edit_notes
                            }
                            update_session(session['id'], updated_session)
                            st.session_state.sessions = load_sessions(st.session_state.user_email)
                            st.success("✅ Session updated!")
                            st.rerun()
                        else:
                            st.error("⚠️ Fill required fields!")

        st.markdown("---")

        # Delete session
        st.subheader("🗑️ Delete a Session")
        session_options_delete = [f"{i}: {s['date']} - {s['academy']} - {s['group']} ({s['hours']}hrs)"
                                  for i, s in enumerate(st.session_state.sessions)]

        if session_options_delete:
            session_to_delete = st.selectbox("Select session to delete", session_options_delete, key="delete_selector")

            if st.button("🗑️ Delete Selected", type="secondary"):
                index = int(session_to_delete.split(":")[0])
                session_id = st.session_state.sessions[index]['id']
                delete_session(session_id)
                st.session_state.sessions = load_sessions(st.session_state.user_email)
                st.success("Deleted!")
                st.rerun()

        st.markdown("---")
        st.subheader("Clear All Data")
        st.warning("Deletes ALL sessions permanently!")

        if st.button("🗑️ Clear All Data", type="secondary"):
            delete_all_sessions(st.session_state.user_email)
            st.session_state.sessions = []
            st.success("All cleared!")
            st.rerun()

    with tabs[6]:
        st.header("🎯 Preferences & Settings")
        st.info("Set up your preferences for faster session entry!")

        # Load current preferences
        prefs = st.session_state.preferences

        # Academy Management
        st.subheader("🏛️ Academy List")
        st.markdown("Add academies you frequently work with:")

        col1, col2 = st.columns([3, 1])
        with col1:
            new_academy = st.text_input("Add new academy", placeholder="e.g., Tech Academy", key="new_academy_input")
        with col2:
            st.write("")
            st.write("")
            if st.button("➕ Add", key="add_academy_btn"):
                if new_academy and new_academy not in prefs.get('academies', []):
                    if 'academies' not in prefs:
                        prefs['academies'] = []
                    prefs['academies'].append(new_academy)
                    save_preferences(st.session_state.user_email, prefs)
                    st.session_state.preferences = prefs
                    st.success(f"Added: {new_academy}")
                    st.rerun()

        # Display current academies
        if prefs.get('academies'):
            st.markdown("**Your Academies:**")
            academies_to_remove = []
            for academy in prefs['academies']:
                col_a, col_b = st.columns([4, 1])
                with col_a:
                    st.text(f"• {academy}")
                with col_b:
                    if st.button("🗑️", key=f"remove_academy_{academy}"):
                        academies_to_remove.append(academy)

            if academies_to_remove:
                for academy in academies_to_remove:
                    prefs['academies'].remove(academy)
                save_preferences(st.session_state.user_email, prefs)
                st.session_state.preferences = prefs
                st.rerun()

        st.markdown("---")

        # Group Management
        st.subheader("👥 Group/Course List")
        st.markdown("Add groups or courses you teach:")

        col1, col2 = st.columns([3, 1])
        with col1:
            new_group = st.text_input("Add new group/course", placeholder="e.g., AI Fundamentals - Group A",
                                      key="new_group_input")
        with col2:
            st.write("")
            st.write("")
            if st.button("➕ Add", key="add_group_btn"):
                if new_group and new_group not in prefs.get('groups', []):
                    if 'groups' not in prefs:
                        prefs['groups'] = []
                    prefs['groups'].append(new_group)
                    save_preferences(st.session_state.user_email, prefs)
                    st.session_state.preferences = prefs
                    st.success(f"Added: {new_group}")
                    st.rerun()

        # Display current groups
        if prefs.get('groups'):
            st.markdown("**Your Groups:**")
            groups_to_remove = []
            for group in prefs['groups']:
                col_a, col_b = st.columns([4, 1])
                with col_a:
                    st.text(f"• {group}")
                with col_b:
                    if st.button("🗑️", key=f"remove_group_{group}"):
                        groups_to_remove.append(group)

            if groups_to_remove:
                for group in groups_to_remove:
                    prefs['groups'].remove(group)
                save_preferences(st.session_state.user_email, prefs)
                st.session_state.preferences = prefs
                st.rerun()

        st.markdown("---")

        # Default Rate
        st.subheader("💰 Default Hourly Rate")
        with st.form("default_rate_form"):
            default_rate = st.number_input("Default hourly rate (EGP)",
                                           min_value=0.0,
                                           value=prefs.get('default_rate', 200.0),
                                           step=50.0)

            if st.form_submit_button("💾 Save Default Rate", use_container_width=True):
                prefs['default_rate'] = default_rate
                save_preferences(st.session_state.user_email, prefs)
                st.session_state.preferences = prefs
                st.success("✅ Default rate updated!")
                st.rerun()

        st.markdown("---")

        # Auto-populate suggestions from existing data
        st.subheader("🔄 Auto-populate from Existing Data")
        if st.button("📊 Import Academies & Groups from Sessions", use_container_width=True):
            if st.session_state.sessions:
                df = pd.DataFrame(st.session_state.sessions)

                # Get unique academies and groups
                unique_academies = df['academy'].unique().tolist()
                unique_groups = df['group'].unique().tolist()

                # Add to preferences if not already there
                current_academies = prefs.get('academies', [])
                current_groups = prefs.get('groups', [])

                new_academies = [a for a in unique_academies if a not in current_academies]
                new_groups = [g for g in unique_groups if g not in current_groups]

                prefs['academies'] = current_academies + new_academies
                prefs['groups'] = current_groups + new_groups

                save_preferences(st.session_state.user_email, prefs)
                st.session_state.preferences = prefs

                st.success(f"✅ Added {len(new_academies)} academies and {len(new_groups)} groups!")
                st.rerun()
            else:
                st.info("No sessions found to import from.")

st.markdown("---")
st.markdown("☁️ **Firebase Cloud Storage** • Data syncs in real-time • Access from any device")