import streamlit as st
import pandas as pd
import os
import json
from google import genai
from google.genai import types

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="Interactive Dutch Tutor", page_icon="🇳🇱")
st.title("🇳🇱 Interactive Dutch Exam App")

# --- SECURE API KEY LOADING WITH SAFE LOCAL FALLBACK ---
api_key = ""
try:
    if "GEMINI_API_KEY" in st.secrets:
        api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    pass

if not api_key:
    api_key = st.sidebar.text_input("Gemini API Key", type="password")

# Auto-load CSV if present in the folder, otherwise show uploader
default_csv = "dutch_vocab.csv"
if os.path.exists(default_csv):
    df = pd.read_csv(default_csv)
    st.sidebar.success(f"Loaded '{default_csv}' automatically!")
else:
    uploaded_file = st.sidebar.file_uploader("Upload Dutch CSV", type=["csv"])
    if uploaded_file:
        df = pd.read_csv(uploaded_file)
    else:
        df = None

# --- SESSION STATE INITIALIZATION ---
if "exam_data" not in st.session_state:
    st.session_state.exam_data = None
if "submitted" not in st.session_state:
    st.session_state.submitted = False

# --- MAIN APP LOGIC ---
if api_key and df is not None:
    num_questions = st.sidebar.slider("Number of Questions", 3, 10, 5)

    if st.button("Generate New Exam") or st.session_state.exam_data is None:
        sampled_df = df.sample(n=min(num_questions, len(df)))
        vocab_string = sampled_df.to_string(index=False)

        client = genai.Client(api_key=api_key)

        prompt = f"""
        You are a Dutch language teacher. Create an exam with {num_questions} multiple-choice questions based ONLY on these word pairs:
        {vocab_string}

        Return ONLY a valid JSON object with a key "questions" containing a list of objects. Each object must have:
        - "id": integer starting from 1
        - "question": string (the exam question testing Dutch translation or meaning)
        - "options": list of 4 possible string options (one correct answer, three plausible distractors)
        - "correct_answer": string (the exact matching string from options)
        - "explanation": string (brief grammar explanation or note about de/het)
        """

        with st.spinner("Gemini is building your interactive exam..."):
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

    # --- RENDER INTERACTIVE EXAM UI ---
    if st.session_state.exam_data:
        st.markdown("---")
        st.markdown("### 📝 Exam Time")

        questions = st.session_state.exam_data.get("questions", [])
        user_answers = {}

        for idx, q in enumerate(questions):
            st.markdown(f"**Question {idx + 1}:** {q['question']}")
            user_answers[idx] = st.radio(
                f"Choose option for Q{idx + 1}",
                options=q["options"],
                key=f"q_{idx}",
                index=None
            )
            st.markdown("")

        if not st.session_state.submitted:
            if st.button("Submit Exam"):
                if None in user_answers.values():
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
                user_ans = user_answers.get(idx)
                correct_ans = q["correct_answer"]

                if user_ans == correct_ans:
                    score += 1
                    st.success(f"**Question {idx + 1}: Correct!** (Your answer: {user_ans})")
                else:
                    st.error(f"**Question {idx + 1}: Incorrect.** (Your answer: {user_ans} | Correct answer: {correct_ans})")

                st.info(f"💡 *Teacher's Note:* {q['explanation']}")

            st.metric(label="Final Score", value=f"{score} / {total}")

            if st.button("Take Another Exam"):
                st.session_state.exam_data = None
                st.session_state.submitted = False
                st.rerun()

else:
    st.info("👈 Please enter your API key in the sidebar and ensure your vocabulary sheet is saved as **`dutch_vocab.csv`** in the app folder!")
