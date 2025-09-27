import streamlit as st
from PIL import Image
import google.generativeai as genai
from docx import Document
from docx.shared import Inches
import io
from datetime import datetime
import os
from dotenv import load_dotenv
import hashlib
import sqlite3
import json
import uuid

# Load environment variables
load_dotenv()

# Database setup
def init_db():
    conn = sqlite3.connect('ocr_app.db')
    c = conn.cursor()
    
    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  username TEXT UNIQUE NOT NULL,
                  email TEXT UNIQUE NOT NULL,
                  password_hash TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    
    # Documents table
    c.execute('''CREATE TABLE IF NOT EXISTS documents
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER NOT NULL,
                  doc_name TEXT NOT NULL,
                  extracted_texts TEXT NOT NULL,
                  image_names TEXT NOT NULL,
                  processing_settings TEXT NOT NULL,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users (id))''')
    
    conn.commit()
    conn.close()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(username, email, password):
    conn = sqlite3.connect('ocr_app.db')
    c = conn.cursor()
    try:
        password_hash = hash_password(password)
        c.execute("INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
                  (username, email, password_hash))
        conn.commit()
        user_id = c.lastrowid
        conn.close()
        return user_id
    except sqlite3.IntegrityError:
        conn.close()
        return None

def authenticate_user(username, password):
    conn = sqlite3.connect('ocr_app.db')
    c = conn.cursor()
    password_hash = hash_password(password)
    c.execute("SELECT id, username FROM users WHERE username = ? AND password_hash = ?",
              (username, password_hash))
    user = c.fetchone()
    conn.close()
    return user

def save_document(user_id, doc_name, extracted_texts, image_names, settings):
    conn = sqlite3.connect('ocr_app.db')
    c = conn.cursor()
    c.execute("""INSERT INTO documents 
                 (user_id, doc_name, extracted_texts, image_names, processing_settings) 
                 VALUES (?, ?, ?, ?, ?)""",
              (user_id, doc_name, json.dumps(extracted_texts), 
               json.dumps(image_names), json.dumps(settings)))
    conn.commit()
    doc_id = c.lastrowid
    conn.close()
    return doc_id

def get_user_documents(user_id):
    conn = sqlite3.connect('ocr_app.db')
    c = conn.cursor()
    c.execute("""SELECT id, doc_name, extracted_texts, image_names, 
                 processing_settings, created_at 
                 FROM documents WHERE user_id = ? ORDER BY created_at DESC""",
              (user_id,))
    docs = c.fetchall()
    conn.close()
    return docs

def delete_document(user_id, doc_id):
    conn = sqlite3.connect('ocr_app.db')
    c = conn.cursor()
    c.execute("DELETE FROM documents WHERE id = ? AND user_id = ?", (doc_id, user_id))
    conn.commit()
    conn.close()

# Initialize database
init_db()

# Streamlit page config
st.set_page_config(
    page_title="Gemini Vision OCR - Multi-Image",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS Styling
st.markdown("""
<style>
    .main-header {font-size: 2.5rem; color: #4285F4; text-align: center; margin-bottom: 0.5rem;}
    .sub-header {text-align: center; color: #666; margin-bottom: 2rem;}
    .success-box {padding: 1rem; border-radius: 0.5rem; background-color: #d4edda; border: 1px solid #c3e6cb; color: #155724; margin: 1rem 0;}
    .error-box {padding: 1rem; border-radius: 0.5rem; background-color: #f8d7da; border: 1px solid #f5c6cb; color: #721c24; margin: 1rem 0;}
    .warning-box {padding: 1rem; border-radius: 0.5rem; background-color: #fff3cd; border: 1px solid #ffecb5; color: #856404; margin: 1rem 0;}
    .info-box {padding: 1rem; border-radius: 0.5rem; background-color: #d1ecf1; border: 1px solid #bee5eb; color: #0c5460; margin: 1rem 0;}
    .stButton > button {width: 100%; background: linear-gradient(90deg, #4285F4, #34A853); color: white; border: none; border-radius: 0.5rem; padding: 0.5rem 1rem; font-weight: bold;}
    .image-container {border: 2px dashed #ccc; border-radius: 10px; padding: 10px; margin: 10px 0; text-align: center;}
    .processed-image {border: 2px solid #4CAF50; border-radius: 10px; padding: 10px; margin: 10px 0; background-color: #f0f8f0;}
    .user-info {background: linear-gradient(90deg, #4285F4, #34A853); color: white; padding: 0.5rem 1rem; border-radius: 0.5rem; margin-bottom: 1rem;}
    .document-card {border: 1px solid #ddd; border-radius: 0.5rem; padding: 1rem; margin: 0.5rem 0; background-color: #f9f9f9;}
</style>
""", unsafe_allow_html=True)

# Session state initialization
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'user_id' not in st.session_state:
    st.session_state.user_id = None
if 'username' not in st.session_state:
    st.session_state.username = None
if 'all_extracted_texts' not in st.session_state:
    st.session_state.all_extracted_texts = []
if 'processed_images' not in st.session_state:
    st.session_state.processed_images = []
if 'api_key_valid' not in st.session_state:
    st.session_state.api_key_valid = False

# Authentication functions
def show_login():
    st.markdown('<h2 class="main-header">🔐 Login</h2>', unsafe_allow_html=True)
    
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        
        if submitted:
            if username and password:
                user = authenticate_user(username, password)
                if user:
                    st.session_state.authenticated = True
                    st.session_state.user_id = user[0]
                    st.session_state.username = user[1]
                    st.success(f"Welcome back, {username}!")
                    st.rerun()
                else:
                    st.error("Invalid username or password")
            else:
                st.error("Please enter both username and password")

def show_signup():
    st.markdown('<h2 class="main-header">📝 Sign Up</h2>', unsafe_allow_html=True)
    
    with st.form("signup_form"):
        username = st.text_input("Username")
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        confirm_password = st.text_input("Confirm Password", type="password")
        submitted = st.form_submit_button("Sign Up")
        
        if submitted:
            if not all([username, email, password, confirm_password]):
                st.error("Please fill in all fields")
            elif password != confirm_password:
                st.error("Passwords do not match")
            elif len(password) < 6:
                st.error("Password must be at least 6 characters long")
            else:
                user_id = create_user(username, email, password)
                if user_id:
                    st.success("Account created successfully! Please login.")
                    st.session_state.show_login = True
                else:
                    st.error("Username or email already exists")

# API key fetch
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# Authentication check
if not st.session_state.authenticated:
    st.markdown('<h1 class="main-header">🚀 Gemini Vision OCR - Multi-Image</h1>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Please login or sign up to continue</p>', unsafe_allow_html=True)
    
    tab1, tab2 = st.tabs(["Login", "Sign Up"])
    
    with tab1:
        show_login()
    
    with tab2:
        show_signup()
        
else:
    # Main application for authenticated users
    st.markdown('<h1 class="main-header">🚀 Gemini Vision OCR - Multi-Image</h1>', unsafe_allow_html=True)
    
    # User info bar
    col1, col2 = st.columns([3, 1])
    with col1:
        st.markdown(f'<div class="user-info">Welcome, {st.session_state.username}!</div>', unsafe_allow_html=True)
    with col2:
        if st.button("Logout"):
            st.session_state.authenticated = False
            st.session_state.user_id = None
            st.session_state.username = None
            st.session_state.all_extracted_texts = []
            st.session_state.processed_images = []
            st.rerun()
    
    # Main tabs
    tab1, tab2, tab3 = st.tabs(["📷 New OCR", "📄 My Documents", "⚙️ Settings"])
    
    with tab3:  # Settings tab
        st.header("Settings")
        
        # API Key setup
        if not GEMINI_API_KEY:
            st.markdown("""
            <div class="warning-box">
                <strong>Setup Required:</strong> Please provide your Gemini API key.
            </div>
            """, unsafe_allow_html=True)
            temp_api_key = st.text_input("Enter Gemini API key:", type="password")
            if temp_api_key:
                GEMINI_API_KEY = temp_api_key
                st.success("API key loaded for this session!")
        else:
            st.markdown('<div class="success-box">API key loaded from environment</div>', unsafe_allow_html=True)
        
        if GEMINI_API_KEY:
            if st.button("Test API Key"):
                try:
                    genai.configure(api_key=GEMINI_API_KEY)
                    try:
                        model = genai.GenerativeModel("gemini-2.0-flash-exp")
                        response = model.generate_content("Test message. Respond with 'API works!'")
                    except Exception as model_error:
                        try:
                            model = genai.GenerativeModel("gemini-2.5-flash")
                            response = model.generate_content("Test message. Respond with 'API works!'")
                        except Exception:
                            model = genai.GenerativeModel("gemini-2.5-flash-lite")
                            response = model.generate_content("Test message. Respond with 'API works!'")
                    
                    if response and response.text and "API works" in response.text:
                        st.session_state.api_key_valid = True
                        st.success("API key is working!")
                    else:
                        st.warning("API responded but may have issues")
                except Exception as e:
                    st.session_state.api_key_valid = False
                    st.error(f"API test failed: {str(e)}")
    
    with tab2:  # My Documents tab
        st.header("My Documents")
        
        docs = get_user_documents(st.session_state.user_id)
        
        if not docs:
            st.markdown('<div class="info-box">No documents found. Process some images in the OCR tab to get started!</div>', unsafe_allow_html=True)
        else:
            for doc in docs:
                doc_id, doc_name, extracted_texts_json, image_names_json, settings_json, created_at = doc
                
                with st.expander(f"📄 {doc_name} - {created_at}"):
                    extracted_texts = json.loads(extracted_texts_json)
                    image_names = json.loads(image_names_json)
                    settings = json.loads(settings_json)
                    
                    st.write(f"**Images processed:** {len(image_names)}")
                    st.write(f"**Language:** {settings.get('target_language', 'N/A')}")
                    st.write(f"**OCR Mode:** {settings.get('ocr_mode', 'N/A')}")
                    
                    # Show extracted texts
                    for idx, text in enumerate(extracted_texts):
                        st.subheader(f"Image {idx + 1}: {image_names[idx]}")
                        st.text_area(f"Text {idx + 1}", value=text, height=100, key=f"saved_text_{doc_id}_{idx}")
                    
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        # Download as DOCX
                        if st.button(f"Download DOCX", key=f"docx_{doc_id}"):
                            try:
                                doc = Document()
                                doc.add_heading('Gemini Vision OCR - Multi-Image', 0)
                                doc.add_paragraph(f"Document: {doc_name}")
                                doc.add_paragraph(f"Created: {created_at}")
                                doc.add_paragraph(f"Language: {settings.get('target_language', 'N/A')}")
                                doc.add_paragraph(f"OCR Mode: {settings.get('ocr_mode', 'N/A')}")
                                
                                for idx, text in enumerate(extracted_texts):
                                    if settings.get('separate_pages', True) and idx > 0:
                                        doc.add_page_break()
                                    doc.add_heading(f"Image {idx + 1}: {image_names[idx]}", level=1)
                                    doc.add_paragraph(text)
                                
                                doc_buffer = io.BytesIO()
                                doc.save(doc_buffer)
                                doc_buffer.seek(0)
                                
                                st.download_button(
                                    label="Download DOCX",
                                    data=doc_buffer.getvalue(),
                                    file_name=f"{doc_name}.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                                    key=f"download_docx_{doc_id}"
                                )
                            except Exception as e:
                                st.error(f"Error creating DOCX: {str(e)}")
                    
                    with col2:
                        # Download as TXT
                        if st.button(f"Download TXT", key=f"txt_{doc_id}"):
                            txt_content = f"Document: {doc_name}\n"
                            txt_content += f"Created: {created_at}\n"
                            txt_content += f"Language: {settings.get('target_language', 'N/A')}\n"
                            txt_content += f"OCR Mode: {settings.get('ocr_mode', 'N/A')}\n"
                            txt_content += "-" * 60 + "\n\n"
                            
                            for idx, text in enumerate(extracted_texts):
                                txt_content += f"Image {idx + 1}: {image_names[idx]}\n"
                                txt_content += text + "\n\n"
                            
                            st.download_button(
                                label="Download TXT",
                                data=txt_content,
                                file_name=f"{doc_name}.txt",
                                mime="text/plain",
                                key=f"download_txt_{doc_id}"
                            )
                    
                    with col3:
                        # Delete document
                        if st.button(f"🗑️ Delete", key=f"delete_{doc_id}", type="secondary"):
                            delete_document(st.session_state.user_id, doc_id)
                            st.success("Document deleted!")
                            st.rerun()

    with tab1:  # OCR Processing tab
        if not GEMINI_API_KEY:
            st.markdown("""
            <div class="warning-box">
                <strong>Setup Required:</strong> Please configure your API key in the Settings tab first.
            </div>
            """, unsafe_allow_html=True)
        else:
            # Sidebar options
            with st.sidebar:
                st.header("OCR Configuration")
                
                target_language = st.selectbox(
                    "Target Language:",
                    ["Same as original", "English", "Spanish", "French", "German", "Italian",
                     "Portuguese", "Russian", "Chinese", "Japanese", "Korean",
                     "Arabic", "Hindi", "Dutch", "Swedish", "Norwegian"],
                    index=1
                )
                ocr_mode = st.selectbox(
                    "OCR Mode:",
                    ["Legal/Official Document", "Handwriting Focus", "Mixed Text", "Document Scan", "Creative/Artistic Text"],
                    index=0
                )
                st.divider()

                st.subheader("Processing Options")
                preserve_formatting = st.checkbox("Preserve text formatting", value=True)
                fix_grammar = st.checkbox("Auto-fix grammar and spelling", value=False)
                include_confidence = st.checkbox("Mark uncertain words with [?]", value=False)
                include_images_in_docx = st.checkbox("Include images in DOCX", value=True)
                st.divider()

                st.subheader("Multi-Image Options")
                process_all_at_once = st.checkbox("Process all images at once", value=False)
                separate_pages = st.checkbox("Each image on new page", value=True)
                st.divider()

                if st.button("Clear Current Session"):
                    st.session_state.all_extracted_texts = []
                    st.session_state.processed_images = []
                    st.rerun()

            def clean_extracted_text(text):
                """Clean and format the extracted text properly"""
                if not text:
                    return text
                
                import re
                
                # Replace underline tags with underscore formatting
                text = re.sub(r'<u>(.*?)</u>', r'_\1_', text, flags=re.IGNORECASE)
                text = re.sub(r'<b>(.*?)</b>', r'**\1**', text, flags=re.IGNORECASE)
                text = re.sub(r'<i>(.*?)</i>', r'*\1*', text, flags=re.IGNORECASE)
                
                # Remove any remaining HTML tags
                text = re.sub(r'<[^>]+>', '', text)
                
                # Fix multiple spaces but preserve intentional indentation
                lines = text.split('\n')
                cleaned_lines = []
                
                for line in lines:
                    leading_spaces = len(line) - len(line.lstrip())
                    content = line.strip()
                    if content:
                        cleaned_lines.append(' ' * leading_spaces + content)
                    else:
                        cleaned_lines.append('')
                
                return '\n'.join(cleaned_lines)

            def get_model():
                """Get the best available Gemini model"""
                genai.configure(api_key=GEMINI_API_KEY)
                
                models_to_try = [
                    "gemini-2.0-flash-exp",
                    "gemini-2.5-flash",
                    "gemini-2.5-flash-lite",
                ]
                
                for model_name in models_to_try:
                    try:
                        return genai.GenerativeModel(model_name)
                    except Exception:
                        continue
                
                raise Exception("No compatible Gemini model found. Please check your API access and model availability.")

            # Main App Area
            st.header("Upload Multiple Images")

            uploaded_files = st.file_uploader(
                "Upload images...",
                type=['png', 'jpg', 'jpeg', 'bmp', 'tiff', 'webp'],
                accept_multiple_files=True
            )

            if uploaded_files:
                st.success(f"{len(uploaded_files)} images uploaded!")
                st.subheader("Uploaded Images")
                cols = st.columns(min(3, len(uploaded_files)))
                for idx, uploaded_file in enumerate(uploaded_files):
                    with cols[idx % 3]:
                        image = Image.open(uploaded_file)
                        st.image(image, caption=uploaded_file.name, width=300)
                        st.caption(f"Size: {image.size[0]}x{image.size[1]}px")

                def create_prompt():
                    if ocr_mode == "Legal/Official Document":
                        base_prompt = ("You are an expert at extracting text from legal and official documents. Extract ALL text with perfect accuracy, "
                                       "maintaining exact formatting, numbering systems, indentation, and legal document structure. "
                                       "Pay special attention to section numbers, subsections, clauses, and hierarchical organization.")
                    elif ocr_mode == "Handwriting Focus":
                        base_prompt = ("You are an expert at reading handwritten text. Extract ALL text from this handwritten image with high accuracy. "
                                       "Pay special attention to cursive writing, connected letters, and personal writing styles.")
                    elif ocr_mode == "Mixed Text":
                        base_prompt = "Extract all text from this image, which may contain both handwritten and printed text."
                    elif ocr_mode == "Document Scan":
                        base_prompt = "Extract all text from this document image, maintaining the exact structure and layout."
                    else:
                        base_prompt = "Extract text from this image, which may contain artistic, stylized, or decorative text."

                    if target_language != "Same as original":
                        base_prompt += f" Translate the extracted text to {target_language}."
                    
                    if preserve_formatting:
                        base_prompt += """ CRITICAL FORMATTING RULES:
- Preserve ALL numbering exactly: (6), (7), (8), etc.
- Use proper indentation with spaces (not tabs)
- For underlined text: Use CAPITAL LETTERS or add underscores like _HEADING_
- DO NOT use HTML tags like <u>, <b>, or similar
- Maintain exact spacing and line breaks as shown
- Keep the same paragraph indentation levels
- Preserve all punctuation and special characters exactly
- Use plain text formatting only - no markup tags
- For emphasized text, use CAPITALS or _underscores_
- Maintain the visual hierarchy with proper spacing between sections"""
                    else:
                        base_prompt += " Preserve basic paragraph structure and line breaks."
                        
                    if fix_grammar:
                        base_prompt += " Fix any obvious spelling or grammar errors while maintaining the original meaning and formatting."
                    if include_confidence:
                        base_prompt += " If you're uncertain about any words, add [?] after them."
                    base_prompt += "\n\nProvide ONLY the extracted text in plain text format. NO HTML tags, NO markup. Use spaces for indentation and underscores or CAPITALS for emphasis."
                    return base_prompt

                st.header("Process Images")
                col1, col2 = st.columns(2)

                # Processing Column
                with col1:
                    if process_all_at_once:
                        if st.button("Process All Images"):
                            try:
                                with st.spinner("Analyzing images..."):
                                    model = get_model()
                                    prompt = create_prompt()
                                    st.session_state.all_extracted_texts = []
                                    st.session_state.processed_images = []
                                    for uploaded_file in uploaded_files:
                                        image = Image.open(uploaded_file)
                                        response = model.generate_content([prompt, image])
                                        text = response.text.strip() if response.text else ""
                                        text = clean_extracted_text(text)
                                        if text:
                                            st.session_state.all_extracted_texts.append(text)
                                            st.session_state.processed_images.append((uploaded_file.name, image))
                                            st.markdown(f'<div class="success-box">Text extracted from {uploaded_file.name}</div>', unsafe_allow_html=True)
                                        else:
                                            st.markdown(f'<div class="error-box">No text detected in {uploaded_file.name}</div>', unsafe_allow_html=True)
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
                    else:
                        selected_image = st.selectbox("Select an image to process:", [f.name for f in uploaded_files])
                        if st.button(f"Process {selected_image}"):
                            try:
                                with st.spinner(f"Analyzing {selected_image}..."):
                                    model = get_model()
                                    prompt = create_prompt()
                                    selected_file = next(f for f in uploaded_files if f.name == selected_image)
                                    image = Image.open(selected_file)
                                    response = model.generate_content([prompt, image])
                                    text = response.text.strip() if response.text else ""
                                    text = clean_extracted_text(text)
                                    if text:
                                        st.session_state.all_extracted_texts.append(text)
                                        st.session_state.processed_images.append((selected_file.name, image))
                                        st.markdown(f'<div class="success-box">Text extracted from {selected_file.name}</div>', unsafe_allow_html=True)
                                    else:
                                        st.markdown(f'<div class="error-box">No text detected in {selected_file.name}</div>', unsafe_allow_html=True)
                            except Exception as e:
                                st.error(f"Error: {str(e)}")

                # Results Column
                with col2:
                    if st.session_state.all_extracted_texts:
                        st.header("Extracted Text")
                        for idx, text in enumerate(st.session_state.all_extracted_texts):
                            st.subheader(f"Image {idx + 1}: {st.session_state.processed_images[idx][0]}")
                            st.text_area(f"Text from {st.session_state.processed_images[idx][0]}", value=text, height=150, key=f"text_{idx}")

                        st.header("Save & Download")
                        
                        # Document name input
                        doc_name = st.text_input("Document Name:", value=f"OCR_Document_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                        
                        if st.button("Save Document"):
                            if doc_name.strip():
                                try:
                                    # Prepare data for saving
                                    image_names = [img[0] for img in st.session_state.processed_images]
                                    settings = {
                                        'target_language': target_language,
                                        'ocr_mode': ocr_mode,
                                        'preserve_formatting': preserve_formatting,
                                        'fix_grammar': fix_grammar,
                                        'include_confidence': include_confidence,
                                        'separate_pages': separate_pages
                                    }
                                    
                                    doc_id = save_document(
                                        st.session_state.user_id,
                                        doc_name.strip(),
                                        st.session_state.all_extracted_texts,
                                        image_names,
                                        settings
                                    )
                                    
                                    st.success(f"Document '{doc_name}' saved successfully!")
                                    st.markdown('<div class="info-box">You can view and download your saved documents from the "My Documents" tab.</div>', unsafe_allow_html=True)
                                    
                                except Exception as e:
                                    st.error(f"Error saving document: {str(e)}")
                            else:
                                st.error("Please enter a document name")

                        st.divider()
                        
                        # Quick download options
                        if st.button("Quick Download as DOCX"):
                            try:
                                doc = Document()
                                doc.add_heading('Gemini Vision OCR - Multi-Image', 0)
                                doc.add_paragraph(f"Extraction Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                                doc.add_paragraph(f"Target Language: {target_language}")
                                doc.add_paragraph(f"OCR Mode: {ocr_mode}")

                                for idx, (filename, image) in enumerate(st.session_state.processed_images):
                                    if separate_pages and idx > 0:
                                        doc.add_page_break()
                                    doc.add_heading(f"Image {idx + 1}: {filename}", level=1)
                                    doc.add_paragraph(st.session_state.all_extracted_texts[idx])
                                    
                                doc_buffer = io.BytesIO()
                                doc.save(doc_buffer)
                                doc_buffer.seek(0)
                                
                                st.download_button(
                                    label="Download DOCX",
                                    data=doc_buffer.getvalue(),
                                    file_name=f"extracted_text_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx",
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                                )
                            except Exception as e:
                                st.error(f"Error creating DOCX: {str(e)}")

                        if st.button("Quick Download as TXT"):
                            txt_content = "Gemini Vision OCR - Multi-Image\n"
                            txt_content += f"Extraction Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                            txt_content += f"Target Language: {target_language}\n"
                            txt_content += f"OCR Mode: {ocr_mode}\n"
                            txt_content += "-" * 60 + "\n\n"
                            for idx, (filename, _) in enumerate(st.session_state.processed_images):
                                txt_content += f"Image {idx + 1}: {filename}\n"
                                txt_content += st.session_state.all_extracted_texts[idx] + "\n\n"
                                
                            st.download_button(
                                label="Download TXT",
                                data=txt_content,
                                file_name=f"extracted_text_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                                mime="text/plain"
                            )