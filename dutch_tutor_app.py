import streamlit as st
import pandas as pd
import json
import random
from google import genai
from google.genai import types
from streamlit_gsheets import GSheetsConnection

# --- PAGE CONFIGURATION & CLEAN NEUTRAL STYLING ---
st.set_page_config(page_title="My Dutch Studio", page_icon="🇳🇱", layout="wide")

st.markdown("""
    <style>
    .stApp {
        background-color: #f8fafc;
    }
    
    h1, h2, h3 {
        color: #0f172a;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        font-weight: 700;
    }

    /* CARD CONTAINER STYLING */
    .card-box {
        background-color: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 24px;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.05);
        margin-bottom: 24px;
    }

    /* HIGH-CONTRAST INPUT FIELDS */
    .stTextInput input, .stSelectbox select, div[data-baseweb="select"] > div {
        background-color: #ffffff !important;
        color: #0f172a !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 8px !important;
    }

    .stTextInput label, .stSelectbox label {
        color: #334155 !important;
        font-weight: 600 !important;
    }

    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e2e8f0;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🇳🇱 My Personal Dutch Learning Studio")
st.markdown("*Your customized, private sanctuary for mastering the Dutch language.*")

# --- SECURE API KEY LOADING WITH SAFE LOCAL FALLBACK ---
api_key = ""
try:
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass

if not api_key:
    api_key = st.sidebar.text_input("Gemini API Key", type="password")

# --- GOOGLE SHEETS DATA LOADING & SYNC ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_vocab():
    try:
        df = conn.read(ttl=0)
        if df is not None and not df.empty:
            if len(df.columns) >= 3:
                df = df.iloc[:, :3]
                df.columns = ['Dutch', 'English', 'Category']
            elif len(df.columns) == 2:
                df = df.iloc[:, :2]
                df.columns = ['Dutch', 'English']
                df['Category'] = 'General'
            else:
                df['English'] = ''
                df['Category'] = 'General'
                df.columns = ['Dutch', 'English', 'Category']

            df['Dutch'] = df['Dutch'].astype(str).str.strip()
            df['English'] = df['English'].astype(str).str.strip()
            df['Category'] = df['Category'].astype(str).str.strip().replace('', 'General')
            return df
        return pd.DataFrame(columns=['Dutch', 'English', 'Category'])
    except Exception as e:
        st.error(f"Error connecting to Google Sheets: {e}")
        return pd.DataFrame(columns=['Dutch', 'English', 'Category'])

df = load_vocab()

# --- SESSION STATE INITIALIZATION ---
if "exam_data" not in st.session_state:
    st.session_state.exam_data = None
if "submitted" not in st.session_state:
    st.session_state.submitted = False
if "flashcard_idx" not in st.session_state:
    st.session_state.flashcard_idx = 0
if "show_back" not in st.session_state:
    st.session_state.show_back = False

if "game_active" not in st.session_state:
    st.session_state.game_active = False
if "game_score" not in st.session_state:
    st.session_state.game_score = 0
if "game_questions" not in st.session_state:
    st.session_state.game_questions = []
if "game_idx" not in st.session_state:
    st.session_state.game_idx = 0
if "game_options" not in st.session_state:
    st.session_state.game_options = []
if "game_history" not in st.session_state:
    st.session_state.game_history = []

if "app_mode" not in st.session_state:
    st.session_state.app_mode = "🏠 Home Dashboard"

# ==========================================
# DIALOG / POPUP FOR DELETE CONFIRMATION
# ==========================================
@st.dialog("⚠️ Confirm Deletion")
def confirm_delete_dialog(rows_to_delete, full_df):
    st.write(f"Are you sure you want to delete **{len(rows_to_delete)}** selected word(s) from your studio?")
    
    st.dataframe(
        rows_to_delete[['Dutch', 'English', 'Category']],
        use_container_width=True,
        hide_index=True
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("❌ Yes, Delete Permanently", type="primary", use_container_width=True):
            # Exclude selected rows from current dataframe
            remaining_df = full_df[~full_df.index.isin(rows_to_delete.index)].reset_index(drop=True)
            conn.update(data=remaining_df)
            st.success("Successfully deleted from Google Sheets!")
            st.rerun()
    with col2:
        if st.button("Cancel", use_container_width=True):
            st.rerun()

# ==========================================
# SIDEBAR: NAVIGATION & LOOKUP
# ==========================================
st.sidebar.markdown("---")
if st.sidebar.button("🏠 Return to Home Hub", use_container_width=True):
    st.session_state.app_mode = "🏠 Home Dashboard"
    st.rerun()

# --- AI WORD TRANSLATOR & CHECKER TOOL ---
st.sidebar.markdown("---")
st.sidebar.subheader("🔍 AI Word Lookup & Checker")
lookup_query = st.sidebar.text_input("Type word to check (Dutch or English)")

if st.sidebar.button("Translate & Check"):
    if not api_key:
        st.sidebar.warning("⚠️ Enter Gemini API key above first.")
    elif not lookup_query.strip():
        st.sidebar.warning("⚠️ Type a word to look up.")
    else:
        try:
            client = genai.Client(api_key=api_key)
            prompt = f"Translate and explain this word/phrase ('{lookup_query}') between Dutch and English. Give the translation, article (de/het if Dutch noun), and a short example sentence. Keep it concise."
            response = client.models.generate_content(model='gemini-3.8-flash', contents=prompt)
            st.sidebar.info(response.text)
        except Exception as e:
            st.sidebar.error(f"Lookup error (Rate limit or quota reached): {e}")

# --- SIDEBAR: CATEGORY FILTER FOR STUDY MODES ---
st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Filter Study Scope")
all_cats = ["All Categories"] + (sorted(df['Category'].unique().tolist()) if not df.empty and 'Category' in df.columns else ['General'])
selected_category = st.sidebar.selectbox("Choose Category/List to Practice", all_cats)

if not df.empty:
    if selected_category != "All Categories":
        active_df = df[df['Category'] == selected_category].reset_index(drop=True)
    else:
        active_df = df.copy()
else:
    active_df = pd.DataFrame(columns=['Dutch', 'English', 'Category'])

if "flashcard_order" not in st.session_state or len(st.session_state.flashcard_order) != len(active_df):
    st.session_state.flashcard_order = list(range(len(active_df)))
    random.shuffle(st.session_state.flashcard_order)

# ==========================================
# MAIN APP LOGIC
# ==========================================
if st.session_state.app_mode == "🏠 Home Dashboard":
    st.markdown("### 👋 Welcome to your Dutch Learning Hub!")
    st.markdown("Select a module below to begin your session:")
    st.markdown("")

    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📚 **Vocabulary Browser**\n\nBrowse, search, edit, and manage your custom lists and categories.", use_container_width=True):
            st.session_state.app_mode = "📚 Vocabulary Browser"
            st.rerun()
        
        st.markdown("")
        if st.button("⚡ **Quick Match Game**\n\nTest your speed and reflexes with quick-fire translations.", use_container_width=True):
            st.session_state.app_mode = "⚡ Quick Match Game"
            st.rerun()

    with col2:
        if st.button("🃏 **Flashcard Practice**\n\nFlip through randomized cards to drill down on memory.", use_container_width=True):
            st.session_state.app_mode = "🃏 Flashcard Practice"
            st.rerun()
        
        st.markdown("")
        if st.button("📝 **Custom Exam**\n\nTake an AI-powered test tailored specifically to your words.", use_container_width=True):
            st.session_state.app_mode = "📝 Custom Exam"
            st.rerun()

# ==========================================
# 1. LEARNING MODE (VOCABULARY BROWSER V3)
# ==========================================
elif st.session_state.app_mode == "📚 Vocabulary Browser":
    st.header("📚 Vocabulary Management Studio")
    st.markdown("Manage, edit, search, and organize your entire vocabulary list in real-time.")
    st.markdown("---")

    # --- CENTERED "ADD NEW WORD" CARD ---
    with st.expander("➕ **Add New Word / Phrase**", expanded=True):
        existing_categories = sorted(df['Category'].unique().tolist()) if not df.empty and 'Category' in df.columns else ['General']
        
        with st.form(key="centered_add_word_form", clear_on_submit=True):
            col_dutch, col_english = st.columns(2)
            with col_dutch:
                new_dutch = st.text_input("Dutch Word / Phrase *", placeholder="e.g. de spiegel")
            with col_english:
                new_english = st.text_input("English Translation *", placeholder="e.g. the mirror")

            col_cat1, col_cat2 = st.columns(2)
            with col_cat1:
                category_choice = st.selectbox("Select or Create List/Category", existing_categories + ["➕ Add New Category..."])
            with col_cat2:
                new_category_input = st.text_input("New Category Name (if selected left)", placeholder="e.g. Household")

            save_btn = st.form_submit_button("💾 Save Word to Studio", use_container_width=True)

            if save_btn:
                errors = []
                if not new_dutch.strip():
                    errors.append("Dutch word or phrase is missing.")
                if not new_english.strip():
                    errors.append("English translation is missing.")

                clean_dutch = new_dutch.strip()
                clean_english = new_english.strip()

                if not errors and not df.empty and 'Dutch' in df.columns:
                    existing_dutch_words = df['Dutch'].astype(str).str.strip().str.lower().tolist()
                    if clean_dutch.lower() in existing_dutch_words:
                        errors.append(f"'{clean_dutch}' is already in your vocabulary list!")

                if errors:
                    for err in errors:
                        st.warning(f"⚠️ {err}")
                else:
                    if category_choice == "➕ Add New Category...":
                        final_category = new_category_input.strip() if new_category_input.strip() else "General"
                    else:
                        final_category = category_choice

                    new_row = pd.DataFrame([{'Dutch': clean_dutch, 'English': clean_english, 'Category': final_category}])
                    updated_df = pd.concat([df, new_row], ignore_index=True)
                    
                    conn.update(data=updated_df)
                    st.success(f"Added successfully: **{clean_dutch}** = *{clean_english}* [{final_category}]!")
                    st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # --- SEARCH & INTERACTIVE TABLE SECTION ---
    st.subheader("🔍 Vocabulary List")

    col_search, col_stats = st.columns([3, 1])
    with col_search:
        search_query = st.text_input("🔍 Quick Search (Dutch, English, or Category)", placeholder="Type to filter words...")
    with col_stats:
        st.metric(label="Total Words in View", value=len(active_df))

    # Apply search filter
    if search_query.strip():
        mask = active_df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)
        display_df = active_df[mask].reset_index(drop=True)
    else:
        display_df = active_df.reset_index(drop=True)

    if display_df.empty:
        st.info("No matching words found.")
    else:
        st.markdown("💡 *Double-click any cell to edit translations or categories directly. Use the checkboxes on the left to select rows for deletion.*")
        
        # Interactive data editor with row selection enabled
        edited_df = st.data_editor(
            display_df,
            column_config={
                "Dutch": st.column_config.TextColumn("Dutch Word / Phrase", required=True),
                "English": st.column_config.TextColumn("English Translation", required=True),
                "Category": st.column_config.SelectboxColumn("Category / List", options=existing_categories + ["General"], required=True)
            },
            num_rows="dynamic",
            use_container_width=True,
            hide_index=True,
            key="vocab_table_editor"
        )

        col_save_changes, col_del_selected = st.columns([1, 1])
        
        with col_save_changes:
            if st.button("💾 Save Table Edits to Google Sheets", use_container_width=True):
                # Merge edits back to main dataframe
                conn.update(data=edited_df)
                st.success("All table edits saved successfully!")
                st.rerun()

        with col_del_selected:
            # Multi-select row deletion UI
            rows_to_del_indices = st.multiselect(
                "Select word(s) to remove:",
                options=display_df.index,
                format_func=lambda i: f"🇳🇱 {display_df.loc[i, 'Dutch']} = {display_df.loc[i, 'English']}"
            )
            
            if st.button("🗑️ Delete Selected Row(s)", type="secondary", use_container_width=True):
                if not rows_to_del_indices:
                    st.warning("Please select at least one row from the dropdown above to delete.")
                else:
                    selected_rows = display_df.loc[rows_to_del_indices]
                    confirm_delete_dialog(selected_rows, df)

# ==========================================
# 2. FLASHCARD MODE
# ==========================================
elif st.session_state.app_mode == "🃏 Flashcard Practice":
    st.header("🃏 Flashcard Practice Studio")
    st.markdown(f"Studying category: **{selected_category}** (Randomized order)")

    if len(active_df) == 0:
        st.warning("No words found in this category!")
    else:
        if st.session_state.flashcard_idx >= len(active_df):
            st.session_state.flashcard_idx = 0

        actual_row_idx = st.session_state.flashcard_order[st.session_state.flashcard_idx]
        current_row = active_df.iloc[actual_row_idx]
        
        dutch_word = str(current_row['Dutch'])
        english_translation = str(current_row['English'])

        card_text = english_translation if st.session_state.show_back else dutch_word
        card_label = f"English Translation" if st.session_state.show_back else f"Dutch Word ({current_row['Category']})"

        st.markdown(f"### Card {st.session_state.flashcard_idx + 1} of {len(active_df)}")
        
        st.markdown(f"""
            <div style="background-color: #ffffff; border: 2px solid #cbd5e1; border-radius: 16px; padding: 40px; text-align: center; box-shadow: 0 4px 6px rgba(0,0,0,0.02); margin-bottom: 20px;">
                <span style="font-size: 13px; color: #64748b; font-weight: bold; text-transform: uppercase; letter-spacing: 1px;">{card_label}</span>
                <br><br>
                <span style="font-size: 42px; font-weight: bold; color: #0f172a;">{card_text}</span>
            </div>
        """, unsafe_allow_html=True)

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            if st.button("⬅️ Prev"):
                st.session_state.flashcard_idx = (st.session_state.flashcard_idx - 1) % len(active_df)
                st.session_state.show_back = False
                st.rerun()
        with col2:
            if st.button("🔄 Flip"):
                st.session_state.show_back = not st.session_state.show_back
                st.rerun()
        with col3:
            if st.button("Next ➡️"):
                st.session_state.flashcard_idx = (st.session_state.flashcard_idx + 1) % len(active_df)
                st.session_state.show_back = False
                st.rerun()
        with col4:
            if st.button("🔀 Shuffle"):
                st.session_state.flashcard_order = list(range(len(active_df)))
                random.shuffle(st.session_state.flashcard_order)
                st.session_state.flashcard_idx = 0
                st.session_state.show_back = False
                st.rerun()

# ==========================================
# 3. MATCH GAME
# ==========================================
elif st.session_state.app_mode == "⚡ Quick Match Game":
    st.header("⚡ Quick Match Challenge")
    st.markdown(f"Playing category: **{selected_category}**")

    if len(active_df) == 0:
        st.warning("No words found in this category to play the game!")
    else:
        if not st.session_state.game_active:
            if st.button("🔥 Start New Match Session"):
                num_rounds = min(5, len(active_df))
                sampled = active_df.sample(n=num_rounds)
                st.session_state.game_questions = sampled.to_dict('records')
                random.shuffle(st.session_state.game_questions)
                st.session_state.game_idx = 0
                st.session_state.game_score = 0
                st.session_state.game_max_score = num_rounds * 10
                st.session_state.game_history = []
                st.session_state.game_active = True
                
                row = st.session_state.game_questions[0]
                correct = str(row['English'])
                distractors = active_df[active_df['English'] != correct]['English'].astype(str).sample(n=min(3, len(active_df)-1)).tolist()
                options = distractors + [correct]
                random.shuffle(options)
                st.session_state.game_options = options
                st.rerun()
        else:
            q_list = st.session_state.game_questions
            curr_idx = st.session_state.game_idx

            if curr_idx < len(q_list):
                row = q_list[curr_idx]
                dutch_target = str(row['Dutch'])
                correct_answer = str(row['English'])

                st.progress((curr_idx) / len(q_list), text=f"Question {curr_idx + 1} of {len(q_list)}")
                
                st.markdown(f"""
                    <div style="background-color: #ffffff; border: 2px solid #cbd5e1; border-radius: 12px; padding: 20px; text-align: center;">
                        <span style="font-size: 14px; color: #64748b; font-weight: bold;">Translate this word:</span><br>
                        <span style="font-size: 34px; font-weight: bold; color: #0f172a;">{dutch_target}</span>
                    </div>
                """, unsafe_allow_html=True)
                st.markdown("")

                selected = st.radio("Choose the correct meaning:", st.session_state.game_options, key=f"game_q_{curr_idx}", index=None)

                if st.button("Check Answer"):
                    if selected is None:
                        st.warning("Please choose an option!")
                    else:
                        is_correct = (selected == correct_answer)
                        if is_correct:
                            st.success("🎉 Correct! +10 Points")
                            st.session_state.game_score += 10
                        else:
                            st.error(f"❌ Incorrect! The correct answer was: **{correct_answer}**")

                        st.session_state.game_history.append({
                            "dutch": dutch_target,
                            "user_choice": selected,
                            "correct_answer": correct_answer,
                            "is_correct": is_correct
                        })
                        
                        st.session_state.game_idx += 1
                        if st.session_state.game_idx < len(q_list):
                            next_row = q_list[st.session_state.game_idx]
                            nxt_correct = str(next_row['English'])
                            nxt_distractors = active_df[active_df['English'] != nxt_correct]['English'].astype(str).sample(n=min(3, len(active_df)-1)).tolist()
                            nxt_options = nxt_distractors + [nxt_correct]
                            random.shuffle(nxt_options)
                            st.session_state.game_options = nxt_options
                        st.rerun()
            else:
                st.markdown("---")
                max_score = st.session_state.get("game_max_score", len(q_list) * 10)
                history = st.session_state.get("game_history", [])
                wrong_answers = [h for h in history if not h["is_correct"]]
                correct_count = len(history) - len(wrong_answers)
                accuracy = (correct_count / len(history) * 100) if history else 0

                st.markdown(f"""
                    <div style="background-color: #ffffff; border: 2px solid #2e7d32; border-radius: 15px; padding: 25px; text-align: center;">
                        <h2>🏆 Challenge Complete!</h2>
                        <p style="font-size: 22px; color: #1e293b;">Final Score: <b>{st.session_state.game_score} / {max_score} Points</b> ({accuracy:.0f}% Accuracy)</p>
                    </div>
                """, unsafe_allow_html=True)

                st.markdown("<br>", unsafe_allow_html=True)

                if wrong_answers:
                    st.subheader("❌ Review Your Mistakes")
                    st.markdown("Here are the words you got wrong in this round so you can review them:")

                    for item in wrong_answers:
                        st.error(f"🇳🇱 **{item['dutch']}**\n\n* Your answer: `{item['user_choice']}`\n* Correct answer: **{item['correct_answer']}**")
                else:
                    st.balloons()
                    st.success("🌟 **Perfect Score!** You didn't make a single mistake this round. Outstanding work!")

                st.markdown("---")
                if st.button("🔄 Play Another Round", use_container_width=True):
                    st.session_state.game_active = False
                    st.rerun()

# ==========================================
# 4. CUSTOM EXAM MODE
# ==========================================
elif st.session_state.app_mode == "📝 Custom Exam":
    st.header("📝 Custom Exam Generator")
    st.markdown(f"Exam category scope: **{selected_category}**")
    
    if not api_key:
        st.warning("⚠️ Please enter your Gemini API key in the sidebar to generate exams.")
    elif len(active_df) == 0:
        st.warning("No words available in this category to generate an exam.")
    else:
        st.sidebar.markdown("---")
        st.sidebar.subheader("⚙️ Exam Preferences")
        num_questions = st.sidebar.slider("Number of Questions", 3, 15, min(5, len(active_df)))
        exam_type = st.sidebar.selectbox(
            "Exam Focus", 
            ["Mixed (Radio & Translation Textbox)", "Dutch to English Translation", "Grammar & Articles (de/het)"]
        )

        if st.button("🚀 Generate New Exam") or st.session_state.exam_data is None:
            sampled_df = active_df.sample(n=min(num_questions, len(active_df)))
            vocab_string = sampled_df.to_string(index=False)

            client = genai.Client(api_key=api_key)

            prompt = f"""
            You are an expert Dutch language teacher. Create an exam with {num_questions} questions focusing on '{exam_type}' based ONLY on these word pairs:
            {vocab_string}

            Mix the question types so that some questions use multiple-choice options (with 4 options) and some questions require a text-based translation input.
            
            Return ONLY a valid JSON object with a key "questions" containing a list of objects. Each object must have:
            - "id": integer starting from 1
            - "question": string (the exam question)
            - "type": string, either "multiple_choice" or "text_input"
            - "options": list of 4 possible string options IF type is "multiple_choice", otherwise empty list []
            - "correct_answer": string (the exact correct answer)
            - "explanation": string (brief grammar explanation or note about de/het)
            """

            with st.spinner("Gemini is crafting your custom exam..."):
                try:
                    response = client.models.generate_content(
                        model='gemini-3.8-flash',
                        contents=prompt,
                        config=types.GenerateContentConfig(response_mime_type="application/json")
                    )
                    st.session_state.exam_data = json.loads(response.text)
                    st.session_state.submitted = False
                    st.rerun()
                except Exception as e:
                    st.error(f"Error generating exam: {e}")

        if st.session_state.exam_data:
            st.markdown("---")
            questions = st.session_state.exam_data.get("questions", [])
            user_answers = {}

            for idx, q in enumerate(questions):
                st.markdown(f"**Question {idx + 1}:** {q['question']}")
                
                q_type = q.get("type", "multiple_choice")
                if q_type == "multiple_choice" and q.get("options"):
                    user_answers[idx] = st.radio(
                        f"Choose option for Q{idx + 1}",
                        options=q["options"],
                        key=f"q_{idx}",
                        index=None
                    )
                else:
                    user_answers[idx] = st.text_input(
                        f"Type your translation/answer for Q{idx + 1}",
                        key=f"q_text_{idx}"
                    )
                st.markdown("")

            if not st.session_state.submitted:
                if st.button("Submit Exam"):
                    unanswered = [i for i, ans in user_answers.items() if ans == "" or ans is None]
                    if unanswered:
                        st.warning("Please answer all questions before submitting!")
                    else:
                        st.session_state.submitted = True
                        st.rerun()
            else:
                score = 0
                total = len(questions)
                st.markdown("---")
                st.markdown("### 📊 Exam Results & Feedback")

                for idx, q in enumerate(questions):
                    user_ans = str(user_answers.get(idx, "")).strip().lower()
                    correct_ans = str(q["correct_answer"]).strip().lower()

                    if user_ans == correct_ans:
                        score += 1
                        st.success(f"**Question {idx + 1}: Correct!** (Your answer: {user_answers.get(idx)})")
                    else:
                        st.error(f"**Question {idx + 1}: Incorrect.** (Your answer: {user_answers.get(idx)} | Correct answer: {q['correct_answer']})")

                    st.info(f"💡 *Teacher's Note:* {q['explanation']}")

                st.metric(label="Final Score", value=f"{score} / {total}")

                if st.button("Take Another Exam"):
                    st.session_state.exam_data = None
                    st.session_state.submitted = False
                    st.rerun()
