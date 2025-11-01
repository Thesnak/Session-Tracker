import streamlit as st
import pandas as pd
from datetime import datetime, date
import json
import hashlib
import plotly.express as px
import plotly.graph_objects as go

# Page configuration
st.set_page_config(page_title="Session Tracker", page_icon="📚", layout="wide")

# File paths
USERS_FILE = 'users.json'
SESSIONS_FILE = 'sessions.json'


# Helper functions
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def load_users():
    try:
        with open(USERS_FILE, 'r') as f:
            st.text(f.readlines())
            return json.load(f)
    except FileNotFoundError:
        return {}


def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f)


def load_sessions():
    try:
        with open(SESSIONS_FILE, 'r') as f:
            data = json.load(f)
            return data.get(st.session_state.user_email, [])
    except FileNotFoundError:
        return []


def save_sessions():
    try:
        with open(SESSIONS_FILE, 'r') as f:
            all_data = json.load(f)
    except FileNotFoundError:
        all_data = {}

    all_data[st.session_state.user_email] = st.session_state.sessions

    with open(SESSIONS_FILE, 'w') as f:
        json.dump(all_data, f)


# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'user_email' not in st.session_state:
    st.session_state.user_email = None
if 'sessions' not in st.session_state:
    st.session_state.sessions = []

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
                users = load_users()
                if email in users and users[email] == hash_password(password):
                    st.session_state.logged_in = True
                    st.session_state.user_email = email
                    st.session_state.sessions = load_sessions()
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
                    users = load_users()
                    if new_email in users:
                        st.error("❌ Email already exists!")
                    else:
                        users[new_email] = hash_password(new_password)
                        save_users(users)
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

    with st.form("add_session"):
        academy = st.text_input("Academy/Institution*", placeholder="e.g., Tech Academy")
        group = st.text_input("Group/Course*", placeholder="e.g., AI Fundamentals - Group A")
        session_date = st.date_input("Date*", value=date.today())
        hours = st.number_input("Hours*", min_value=0.5, max_value=12.0, value=2.0, step=0.5)
        rate = st.number_input("Hourly Rate (EGP)*", min_value=0.0, value=200.0, step=50.0)
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
                st.session_state.sessions.append(session)
                save_sessions()
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

    tabs = st.tabs(["📊 Dashboard", "📈 Analytics", "📅 All Sessions", "📋 Monthly Report", "⚙️ Manage"])

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
                            st.session_state.sessions[index] = {
                                "academy": edit_academy,
                                "group": edit_group,
                                "date": edit_date.strftime("%Y-%m-%d"),
                                "hours": edit_hours,
                                "rate": edit_rate,
                                "amount": edit_hours * edit_rate,
                                "notes": edit_notes
                            }
                            save_sessions()
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
                st.session_state.sessions.pop(index)
                save_sessions()
                st.success("Deleted!")
                st.rerun()

        st.markdown("---")
        st.subheader("Clear All Data")
        st.warning("Deletes ALL sessions permanently!")

        if st.button("🗑️ Clear All Data", type="secondary"):
            st.session_state.sessions = []
            save_sessions()
            st.success("All cleared!")
            st.rerun()

st.markdown("---")
st.markdown("💡 **Cloud-enabled** • Data syncs automatically • Access from any device")