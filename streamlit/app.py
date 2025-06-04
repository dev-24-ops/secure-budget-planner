import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import datetime, timedelta
import plotly.express as px
import json
from database import BudgetDatabase
from auth_manager import AuthManager

# Initialize authentication manager
auth = AuthManager()

# Initialize session state
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'token' not in st.session_state:
    st.session_state.token = None

# Set page configuration
st.set_page_config(
    page_title="Budget Planner",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

def login_page():
    st.title("Welcome to Budget Planner")
    
    tab1, tab2, tab3 = st.tabs(["Login", "Register", "Reset Password"])
    
    with tab1:
        st.subheader("Login")
        username = st.text_input("Username", key="login_username")
        password = st.text_input("Password", type="password", key="login_password")
        
        if st.button("Login"):
            success, result = auth.login(username, password)
            if success:
                st.session_state.authenticated = True
                st.session_state.token = result
                # Decode token to get user_id
                valid, payload = auth.verify_token(result)
                if valid:
                    st.session_state.user_id = payload['user_id']
                st.success("Login successful!")
                st.rerun()
            else:
                st.error(result)
    
    with tab2:
        st.subheader("Register")
        new_username = st.text_input("Username", key="reg_username")
        new_password = st.text_input("Password", type="password", key="reg_password")
        confirm_password = st.text_input("Confirm Password", type="password")
        email = st.text_input("Email")
        security_question = st.selectbox(
            "Security Question",
            ["What was your first pet's name?",
             "What city were you born in?",
             "What was your mother's maiden name?"]
        )
        security_answer = st.text_input("Security Answer")
        
        if st.button("Register"):
            if new_password != confirm_password:
                st.error("Passwords do not match!")
            elif len(new_password) < 8:
                st.error("Password must be at least 8 characters long!")
            else:
                if auth.create_user(new_username, new_password, email, 
                                  security_question, security_answer):
                    st.success("Registration successful! Please login.")
                else:
                    st.error("Username or email already exists!")
    
    with tab3:
        st.subheader("Reset Password")
        reset_username = st.text_input("Username", key="reset_username")
        security_answer = st.text_input("Security Answer", key="reset_security")
        new_password = st.text_input("New Password", type="password", key="new_password")
        confirm_new_password = st.text_input("Confirm New Password", type="password")
        
        if st.button("Reset Password"):
            if new_password != confirm_new_password:
                st.error("Passwords do not match!")
            elif len(new_password) < 8:
                st.error("Password must be at least 8 characters long!")
            else:
                if auth.reset_password(reset_username, security_answer, new_password):
                    st.success("Password reset successful! Please login.")
                else:
                    st.error("Invalid username or security answer!")

def main_app():
    # Initialize database with user_id
    db = BudgetDatabase(user_id=st.session_state.user_id)
    
    # Sidebar navigation
    st.sidebar.title("💰 Budget Planner")
    
    # Add logout button to sidebar
    if st.sidebar.button("Logout"):
        auth.logout(st.session_state.token)
        st.session_state.authenticated = False
        st.session_state.user_id = None
        st.session_state.token = None
        st.rerun()
    
    app_mode = st.sidebar.radio("Navigation", 
                               ["Overview", "Add Transaction", "Reports", "Backup & Restore"])

    # Main content
    if app_mode == "Overview":
        st.title("Welcome to Your Budget Planner")
        st.markdown("""
        ### Track Your Finances with the 50/30/20 Rule
        
        This budget planner helps you manage your money using the 50/30/20 rule:
        - 50% for **Needs** (essential expenses)
        - 30% for **Wants** (non-essential items)
        - 20% for **Savings** (future goals)
        """)

        # Display current salary and allocations
        current_salary = db.get_salary()
        if current_salary > 0:
            st.subheader("Your Current Budget Allocation")
            allocations = calculate_allocation(current_salary)
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Needs (50%)", f"${allocations['Needs']:,.2f}")
            with col2:
                st.metric("Wants (30%)", f"${allocations['Wants']:,.2f}")
            with col3:
                st.metric("Savings (20%)", f"${allocations['Savings']:,.2f}")

            # Show recent transactions
            st.subheader("Recent Transactions")
            recent_transactions = db.get_transactions()
            if recent_transactions:
                df = pd.DataFrame(recent_transactions)
                st.dataframe(
                    df[['date', 'amount', 'category', 'description']],
                    use_container_width=True
                )
            else:
                st.info("No transactions recorded yet.")

    elif app_mode == "Add Transaction":
        st.title("Add Transaction")
        
        # Salary input form
        with st.form("salary_form"):
            st.subheader("Update Monthly Salary")
            new_salary = st.number_input(
                "Monthly Salary",
                min_value=0.0,
                value=db.get_salary(),
                step=100.0,
                format="%.2f"
            )
            if st.form_submit_button("Update Salary"):
                db.update_salary(new_salary)
                st.success("Salary updated successfully!")
                
        # Transaction input form
        with st.form("transaction_form"):
            st.subheader("Add New Transaction")
            amount = st.number_input("Amount", min_value=0.0, step=1.0, format="%.2f")
            category = st.selectbox("Category", ["Needs", "Wants", "Savings"])
            description = st.text_input("Description")
            date = st.date_input("Date", value=datetime.today())
            
            if st.form_submit_button("Add Transaction"):
                db.add_transaction(date, amount, category, description)
                st.success("Transaction added successfully!")

    elif app_mode == "Reports":
        st.title("Budget Reports")
        
        report_period = st.selectbox("Select Report Period", ["Weekly", "Monthly", "Yearly"])
        start_date, end_date = get_date_range(report_period)
        
        transactions = db.get_transactions(start_date, end_date)
        
        if transactions:
            category_totals = db.get_category_totals(start_date, end_date)
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Spending Distribution")
                fig = px.pie(
                    values=list(category_totals.values()),
                    names=list(category_totals.keys()),
                    title=f"{report_period} Spending by Category"
                )
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                st.subheader("Budget vs. Actual")
                period_factor = 1
                if report_period == "Weekly":
                    period_factor = 7/30
                elif report_period == "Yearly":
                    period_factor = 12
                
                current_salary = db.get_salary()
                period_allocation = calculate_allocation(current_salary * period_factor)
                
                comparison_data = pd.DataFrame({
                    'Category': list(period_allocation.keys()),
                    'Allocated': list(period_allocation.values()),
                    'Spent': [
                        category_totals.get('Needs', 0),
                        category_totals.get('Wants', 0),
                        category_totals.get('Savings', 0)
                    ]
                })
                
                fig = px.bar(
                    comparison_data,
                    x='Category',
                    y=['Allocated', 'Spent'],
                    title=f"{report_period} Budget vs. Actual Spending",
                    barmode='group'
                )
                st.plotly_chart(fig, use_container_width=True)
            
            st.subheader("Transaction Details")
            df = pd.DataFrame(transactions)
            st.dataframe(
                df[['date', 'amount', 'category', 'description']].sort_values('date', ascending=False),
                use_container_width=True
            )
        else:
            st.info(f"No transactions found for the selected {report_period.lower()} period.")

    elif app_mode == "Backup & Restore":
        st.title("Backup & Restore")
        
        st.header("Create Backup")
        if st.button("Create New Backup"):
            backup_path = db.export_database()
            st.success(f"Backup created successfully at: {backup_path}")
        
        st.header("Restore from Backup")
        backups = db.list_backups()
        
        if backups:
            backup_options = {}
            for backup in backups:
                date_str = backup['created_at'].strftime('%Y-%m-%d')
                if date_str not in backup_options:
                    backup_options[date_str] = []
                backup_options[date_str].append(backup)
            
            selected_date = st.selectbox(
                "Select backup date",
                options=list(backup_options.keys()),
                format_func=lambda x: f"Backups from {x}"
            )
            
            if selected_date:
                day_backups = backup_options[selected_date]
                selected_backup = st.selectbox(
                    "Select specific backup",
                    options=day_backups,
                    format_func=lambda x: f"{x['filename']} ({x['created_at'].strftime('%H:%M:%S')})"
                )
                
                if selected_backup:
                    if st.button("Restore Selected Backup"):
                        if db.import_database(selected_backup['path']):
                            st.success("Backup restored successfully!")
                        else:
                            st.error("Error restoring backup")
        else:
            st.info("No backups available yet. Create a backup using the button above.")

def calculate_allocation(salary: float):
    """Calculate budget allocation based on 50/30/20 rule"""
    if salary < 0:
        raise ValueError("Salary must be non-negative")
    allocation = {
        "Needs": salary * 0.50,
        "Wants": salary * 0.30,
        "Savings": salary * 0.20
    }
    return allocation

def get_date_range(period: str):
    """Get date range based on selected period"""
    today = datetime.now()
    if period == "Weekly":
        start_date = today - timedelta(days=7)
    elif period == "Monthly":
        start_date = today - timedelta(days=30)
    else:  # Yearly
        start_date = today - timedelta(days=365)
    return start_date.date(), today.date()

# Main app logic
if not st.session_state.authenticated:
    login_page()
else:
    main_app()
