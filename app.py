# app.py
import asyncio
import sys
import json
import os
from pathlib import Path
from datetime import datetime
import shutil
from fpdf import FPDF
from io import BytesIO
import html2text
import streamlit as st
import base64
from xhtml2pdf import pisa

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import streamlit as st
from agent import run_agent
from email_client import send_report_email, send_report_bulk, parse_recipients

# ============================================================================
# Configuration
# ============================================================================
REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)

PERSISTENT_STATE_FILE = Path("session_state.json")

# ============================================================================
# Persistent State Management
# ============================================================================
def load_persistent_state():
    """Load persistent state from JSON file."""
    if PERSISTENT_STATE_FILE.exists():
        try:
            with open(PERSISTENT_STATE_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_persistent_state(state_data):
    """Save state to JSON file."""
    try:
        with open(PERSISTENT_STATE_FILE, 'w') as f:
            json.dump(state_data, f, indent=2)
    except Exception as e:
        print(f"Failed to save state: {e}")

# ============================================================================
# Report Storage Functions
# ============================================================================
def save_report_to_disk(query: str, html_content: str):
    """Save report in multiple formats to dedicated folder."""
    # Create folder name
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    folder_name = f"{query[:50].replace(' ', '_')}_{timestamp}"
    report_folder = REPORTS_DIR / folder_name
    report_folder.mkdir(exist_ok=True)
    
    # Save HTML
    html_path = report_folder / "report.html"
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    # Save metadata
    metadata = {
        'query': query,
        'timestamp': timestamp,
        'date': datetime.now().isoformat(),
        'folder': str(report_folder)
    }
    metadata_path = report_folder / "metadata.json"
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    return str(report_folder)

def list_saved_reports():
    """List all saved reports with metadata."""
    reports = []
    for folder in REPORTS_DIR.iterdir():
        if folder.is_dir():
            metadata_file = folder / "metadata.json"
            if metadata_file.exists():
                try:
                    with open(metadata_file, 'r') as f:
                        metadata = json.load(f)
                        metadata['folder_name'] = folder.name
                        reports.append(metadata)
                except:
                    pass
    return sorted(reports, key=lambda x: x.get('timestamp', ''), reverse=True)

def delete_report(folder_name: str):
    """Delete a report folder."""
    folder_path = REPORTS_DIR / folder_name
    if folder_path.exists():
        shutil.rmtree(folder_path)
        return True
    return False

# ============================================================================
# Streamlit Configuration
# ============================================================================
st.set_page_config(
    page_title="AI Market Research Generator",
    page_icon="🔍",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# Initialize Session State with Persistent Storage
# ============================================================================
persistent_data = load_persistent_state()

if "report_html" not in st.session_state:
    st.session_state.report_html = None
if "query" not in st.session_state:
    st.session_state.query = ""
if "status_log" not in st.session_state:
    st.session_state.status_log = []
if "settings" not in st.session_state:
    st.session_state.settings = persistent_data.get('settings', {
        'max_search_results': 10,
        'scrape_timeout': 10,
        'search_timeout': 15,
        'polite_delay': 1.5,
        'temperature': 0.3,
    })
if "priority_websites" not in st.session_state:
    st.session_state.priority_websites = persistent_data.get('priority_websites', [])
if "enable_priority_websites" not in st.session_state:
    st.session_state.enable_priority_websites = persistent_data.get('enable_priority_websites', False)
if "query_cache" not in st.session_state:
    st.session_state.query_cache = persistent_data.get('query_cache', {})

# ============================================================================
# Sidebar Settings
# ============================================================================
with st.sidebar:
    st.header("⚙️ Settings")
    
    st.subheader("🔍 Search Configuration")
    
    # Get current values from session state
    current_settings = st.session_state.settings
    
    max_results = st.slider(
        "Max Search Results",
        min_value=3,
        max_value=100,
        value=current_settings['max_search_results'],
        key="slider_max_results",
        help="Number of URLs to search and scrape"
    )
    
    search_timeout = st.slider(
        "Search Timeout (seconds)",
        min_value=5,
        max_value=30,
        value=current_settings['search_timeout'],
        key="slider_search_timeout",
        help="Maximum time to wait for search results"
    )
    
    scrape_timeout = st.slider(
        "Scrape Timeout (seconds)",
        min_value=5,
        max_value=30,
        value=current_settings['scrape_timeout'],
        key="slider_scrape_timeout",
        help="Maximum time to wait per URL scrape"
    )
    
    polite_delay = st.slider(
        "Delay Between Requests (seconds)",
        min_value=0.5,
        max_value=5.0,
        value=current_settings['polite_delay'],
        step=0.5,
        key="slider_polite_delay",
        help="Polite crawling delay"
    )
    
    st.subheader("🤖 AI Configuration")
    temperature = st.slider(
        "AI Temperature",
        min_value=0.0,
        max_value=1.0,
        value=current_settings['temperature'],
        step=0.1,
        key="slider_temperature",
        help="Lower = factual, Higher = creative"
    )
    
    # Auto-update settings when sliders change
    st.session_state.settings = {
        'max_search_results': max_results,
        'scrape_timeout': scrape_timeout,
        'search_timeout': search_timeout,
        'polite_delay': polite_delay,
        'temperature': temperature,
    }
    
    if st.button("💾 Save Settings Permanently", use_container_width=True):
        save_persistent_state({
            'settings': st.session_state.settings,
            'priority_websites': st.session_state.priority_websites,
            'enable_priority_websites': st.session_state.enable_priority_websites,
            'query_cache': st.session_state.query_cache
        })
        st.success("✅ Settings saved permanently!")
    
    if st.button("🔄 Reset to Defaults", use_container_width=True):
        st.session_state.settings = {
            'max_search_results': 10,
            'scrape_timeout': 10,
            'search_timeout': 15,
            'polite_delay': 1.5,
            'temperature': 0.3,
        }
        st.rerun()
    
    st.markdown("---")
    
    # Priority Websites Configuration
    st.subheader("🎯 Priority Websites")
    
    enable_priority = st.checkbox(
        "Enable Priority Websites",
        value=st.session_state.enable_priority_websites,
        help="Force search on specific websites first"
    )
    st.session_state.enable_priority_websites = enable_priority
    
    if enable_priority:
        # Add website input
        new_website = st.text_input(
            "Add Website (e.g., timesofindia.com)",
            placeholder="example.com",
            key="new_priority_website"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("➕ Add", use_container_width=True):
                if new_website and new_website not in st.session_state.priority_websites:
                    st.session_state.priority_websites.append(new_website)
                    st.success(f"Added {new_website}")
        
        # Display current priority websites
        if st.session_state.priority_websites:
            st.markdown("**Current Priority Websites:**")
            for idx, website in enumerate(st.session_state.priority_websites):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.text(f"🌐 {website}")
                with col2:
                    if st.button("🗑️", key=f"delete_{idx}"):
                        st.session_state.priority_websites.pop(idx)
                        st.rerun()
        else:
            st.info("No priority websites added")
    
    st.markdown("---")
    st.markdown("### 📊 Cache Status")
    st.write(f"Cached Reports: {len(st.session_state.query_cache)}")
    if st.button("🗑️ Clear Cache", use_container_width=True):
        st.session_state.query_cache = {}
        st.success("Cache cleared!")

# ============================================================================
# Main UI
# ============================================================================
st.title("🔍 AI-Powered Market Research Report Generator")
st.markdown("Generate professional market research reports in minutes using AI-powered web research.")

# ============================================================================
# Tabs for different sections
# ============================================================================
tab1, tab2 = st.tabs(["📝 Generate Report", "📂 Saved Reports"])

# ============================================================================
# TAB 1: Report Generation
# ============================================================================
with tab1:
    st.markdown("### 🎯 Generate Market Research Report")
    
    query = st.text_area(
        "Enter Market Research Query",
        height=100,
        placeholder="E.g., Smart Rings Market India 2025, AI in Healthcare trends, Electric Vehicle adoption in Europe",
        value=st.session_state.query
    )
    
    col1, col2 = st.columns([2, 2])
    
    with col1:
        generate_btn = st.button("🚀 Generate Report", type="primary", use_container_width=True)
    
    with col2:
        use_cache = st.checkbox("Use cached result if available", value=True)
    
    # Report Generation Logic
    if generate_btn:
        if not query or len(query.strip()) < 5:
            st.error("⚠️ Please enter a valid query (at least 5 characters).")
        else:
            st.session_state.query = query
            
            if use_cache and query in st.session_state.query_cache:
                st.info("📦 Loading cached report...")
                st.session_state.report_html = st.session_state.query_cache[query]
                st.success("✅ Cached report loaded!")
            else:
                st.session_state.status_log = []
                
                with st.expander("🔄 Real-Time Agent Activity", expanded=True):
                    status_box = st.empty()
                    
                    def update_status(message: str):
                        st.session_state.status_log.append(message)
                        log_text = "\n".join(st.session_state.status_log[-25:])
                        status_box.code(log_text, language="text")
                    
                    try:
                        report_html = run_agent(
                            query,
                            settings=st.session_state.settings,
                            priority_websites=st.session_state.priority_websites if st.session_state.enable_priority_websites else [],
                            status_callback=update_status
                        )
                        st.session_state.report_html = report_html
                        st.session_state.query_cache[query] = report_html
                        
                        # Save report to disk
                        try:
                            folder_path = save_report_to_disk(query, report_html)
                            st.success(f"✅ Report generated and saved to: {folder_path}")
                        except Exception as e:
                            st.warning(f"⚠️ Report generated but save failed: {e}")
                        
                    except Exception as e:
                        st.error(f"❌ Failed to generate report: {str(e)}")
                        st.session_state.report_html = None
    
    # Display Report
    if st.session_state.get("report_html"):
        st.markdown("---")
        st.markdown("### 📄 Generated Market Research Report")
        
        st.components.v1.html(st.session_state.report_html, height=800, scrolling=True)
        
        # Email Section
        st.markdown("---")
        st.markdown("### 📧 Send Report via Email")
        
        recipient_input = st.text_area(
            "Recipient Email Address(es)",
            height=80,
            placeholder="recipient@example.com or multiple@example.com, another@example.com",
            help="Enter one or more email addresses separated by commas, semicolons, or newlines"
        )
        
        col1, col2 = st.columns([3, 1])
        
        with col1:
            if st.button("📧 Send Report via Email", use_container_width=True, type="primary"):
                if not recipient_input or not recipient_input.strip():
                    st.error("⚠️ Please enter at least one recipient email address.")
                else:
                    recipients = parse_recipients(recipient_input)
                    
                    if not recipients:
                        st.error("⚠️ No valid email addresses found.")
                    else:
                        try:
                            if len(recipients) == 1:
                                with st.spinner(f"📤 Sending to {recipients[0]}..."):
                                    if send_report_email(
                                        recipient_email=recipients[0],
                                        query=st.session_state.query,
                                        html_body=st.session_state.report_html
                                    ):
                                        st.success(f"✅ Sent to {recipients[0]}!")
                            else:
                                with st.spinner(f"📤 Sending to {len(recipients)} recipients..."):
                                    results = send_report_bulk(
                                        recipients=recipients,
                                        query=st.session_state.query,
                                        html_body=st.session_state.report_html
                                    )
                                    if results['success'] == results['total']:
                                        st.success(f"✅ Sent to all {results['total']} recipients!")
                                    else:
                                        st.warning(f"⚠️ Sent to {results['success']}/{results['total']}")
                        except Exception as e:
                            st.error(f"❌ Failed: {str(e)}")
        
        with col2:
                        # Convert HTML to plain text
            text = html2text.html2text(st.session_state.report_html)

            # Create PDF
            pdf = FPDF()
            pdf.set_auto_page_break(auto=True, margin=15)
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            # You can use built-in "Arial" variant that supports UTF-8 or add TTF font
            pdf.add_font("Times New Roman", "", "times.ttf", uni=True)
            pdf.set_font("Times New Roman", size=12)

            for line in text.split("\n"):
                pdf.multi_cell(0, 5, line)

                        
            # Save PDF to BytesIO
            pdf_bytes = BytesIO()
            pdf_bytes.write(pdf.output(dest='S').encode('latin1'))  # <-- get PDF as string, encode to bytes
            pdf_bytes.seek(0)

            # Streamlit download button
            st.download_button(
                label="💾 Download PDF",
                data=pdf_bytes,
                file_name=f"report_{st.session_state.query[:30].replace(' ', '_')}.pdf",
                mime="application/pdf",
                use_container_width=True
            )
            st.download_button(
                label="💾 Download",
                data=st.session_state.report_html,
                file_name=f"report_{st.session_state.query[:30].replace(' ', '_')}.html",
                mime="text/html",
                use_container_width=True
            )

# ============================================================================
# TAB 2: Saved Reports Management
# ============================================================================
with tab2:
    st.markdown("### 📂 Saved Reports")
    
    saved_reports = list_saved_reports()
    
    if not saved_reports:
        st.info("No saved reports found. Generate a report to see it here.")
    else:
        st.write(f"**Total Reports:** {len(saved_reports)}")
        
        for report in saved_reports:
            with st.expander(f"📄 {report['query'][:60]} - {report.get('date', 'Unknown')[:10]}"):
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                
                with col1:
                    st.write(f"**Query:** {report['query']}")
                    st.write(f"**Date:** {report.get('date', 'Unknown')}")
                    st.write(f"**Folder:** {report.get('folder_name', 'Unknown')}")
                
                with col2:
                    html_file = Path(report['folder']) / "report.html"
                    if html_file.exists():
                        with open(html_file, 'r', encoding='utf-8') as f:
                            html_content = f.read()
                        st.download_button(
                            "💾 HTML",
                            data=html_content,
                            file_name=f"{report['folder_name']}.html",
                            mime="text/html",
                            use_container_width=True
                        )
                
                # with col3:
                #     if st.button("👁️ View", key=f"view_{report['folder_name']}", use_container_width=True):
                #         pdf_file = Path(report['folder']) / "report.pdf"
                #         html_file = Path(report['folder']) / "report.html"

                #         # ✅ Generate PDF if not present
                #         if not pdf_file.exists() and html_file.exists():
                #             with open(html_file, "r", encoding="utf-8") as f:
                #                 html_content = f.read()

                #             pdf_bytes = BytesIO()
                #             pisa.CreatePDF(src=html_content, dest=pdf_bytes)
                #             pdf_bytes.seek(0)

                #             # Save the generated PDF
                #             with open(pdf_file, "wb") as f:
                #                 f.write(pdf_bytes.read())

                #         # ✅ Display the PDF (ensured it exists now)
                #         if pdf_file.exists():
                #             with open(pdf_file, "rb") as f:
                #                 pdf_bytes = f.read()

                #             st.session_state.report_pdf = pdf_bytes
                #             st.session_state.query = report["query"]

                #             b64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

                #             # ✅ Pop-out container with shadow & iframe viewer
                #             with st.container(border=True):
                #                 st.markdown(
                #                     f"""
                #                     <div style="
                #                         background-color: #f9f9f9;
                #                         border: 2px solid #ddd;
                #                         border-radius: 12px;
                #                         box-shadow: 0 0 15px rgba(0,0,0,0.15);
                #                         padding: 10px;
                #                         margin-top: 20px;
                #                         ">
                #                         <iframe
                #                             src="data:application/pdf;base64,{b64_pdf}"
                #                             width="100%"
                #                             height="800px"
                #                             style="border:none; border-radius: 8px;">
                #                         </iframe>
                #                     </div>
                #                     """,
                #                     unsafe_allow_html=True,
                #                 )

                #         else:
                #             st.warning("⚠️ No report found to display or generate.")
                with col3:
                    if st.button("👁️ View", key=f"view_{report['folder_name']}", use_container_width=True):
                        pdf_file = Path(report['folder']) / "report.pdf"
                        html_file = Path(report['folder']) / "report.html"

                        # ✅ Generate PDF if missing
                        if not pdf_file.exists() and html_file.exists():
                            with open(html_file, "r", encoding="utf-8") as f:
                                html_content = f.read()

                            pdf_bytes = BytesIO()
                            pisa.CreatePDF(src=html_content, dest=pdf_bytes)
                            pdf_bytes.seek(0)

                            with open(pdf_file, "wb") as f:
                                f.write(pdf_bytes.read())

                        # ✅ Load PDF and show modal
                        if pdf_file.exists():
                            with open(pdf_file, "rb") as f:
                                pdf_bytes = f.read()
                            # ✅ Rename logically (in memory)
                            folder_name = Path(report["folder"]).name
                            renamed_pdf = BytesIO(pdf_bytes)
                            renamed_pdf.name = f"{folder_name}.pdf"
                            b64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

                            # Store modal state
                            st.session_state["show_modal"] = True
                            st.session_state["pdf_data"] = b64_pdf

                # ===========================
                # ✅ Modal PDF viewer section
                # ===========================
                    if st.session_state.get("show_modal", False):
                        b64_pdf = st.session_state["pdf_data"]

                        # Inject CSS + HTML for fullscreen overlay
                        st.markdown(
                            f"""
                            <style>
                            .modal-overlay {{
                                position: fixed;
                                top: 0; left: 0;
                                width: 100vw; height: 100vh;
                                background-color: rgba(0,0,0,0.75);
                                display: flex; justify-content: center; align-items: center;
                                z-index: 9999;
                            }}
                            .modal-content {{
                                position: relative;
                                width: 85%;
                                height: 90%;
                                background-color: white;
                                border-radius: 12px;
                                box-shadow: 0 0 25px rgba(0,0,0,0.5);
                                overflow: hidden;
                            }}
                            .close-btn {{
                                position: absolute;
                                top: 10px;
                                right: 15px;
                                background: #ff5555;
                                color: white;
                                border: none;
                                font-size: 22px;
                                font-weight: bold;
                                border-radius: 50%;
                                width: 35px; height: 35px;
                                cursor: pointer;
                                z-index: 10000;
                            }}
                            </style>

                            <div class="modal-overlay">
                                <div class="modal-content">
                                    <button class="close-btn" onclick="window.parent.postMessage('close_modal', '*')">✖</button>
                                    <iframe src="data:application/pdf;base64,{b64_pdf}" 
                                            width="100%" height="100%" 
                                            style="border:none;">
                                    </iframe>
                                </div>
                            </div>

                            <script>
                            window.addEventListener('message', (event) => {{
                                if (event.data === 'close_modal') {{
                                    window.parent.location.reload();
                                }}
                            }});
                            </script>
                            """,
                            unsafe_allow_html=True,
                        )

                            
                
                with col4:
                    if st.button("🗑️ Delete", key=f"delete_{report['folder_name']}", use_container_width=True):
                        if delete_report(report['folder_name']):
                            st.success("Deleted!")
                            st.rerun()

# ============================================================================
# Footer
# ============================================================================
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: gray; font-size: 12px;'>
    Powered by AI Market Research Agent | Persistent Storage Enabled | 
    Reports auto-saved in dedicated folders
    </div>
    """,
    unsafe_allow_html=True
)
