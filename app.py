import streamlit as st
import os
import requests
from utils.processor import process_video_pipeline
from utils.database import rebuild_faiss_index,query_vector_store
from utils.config import OLLAMA_URL,LLM_MODEL

st.set_page_config(page_title="EduRAG - AI Assistant", page_icon="🎓", layout='wide')
st.title("🎓 EduRAG: Local Video Learning Assistant")

#initialising session states for chat history
if "messages" not in st.session_state:
    st.session_state.messages=[]

#sidebar for precessing video uploads
with st.sidebar:
    st.header("Upload System Database")
    uploaded_files = st.file_uploader("Upload video lectures", type=["mp4", "mkv", "avi", "webm"], accept_multiple_files=True)

    db_action = st.radio(
        "Database Update Strategy:",
        options = ['Append to Existing Database','Wipe and Start Fresh'],
        index = 0
    )

    if st.button("Build/Update RAG Knowledge Base"):
        if uploaded_files:
            upload_dir = "data/uploads"

            import shutil

            if db_action == "Wipe and Start Fresh":
                st.info("Wiping Old Data to create a Fresh Database!")
                for folder in ["data/uploads", "data/audios", "data/jsons", "data/preprocessed", "data/vector_store"]:
                    if os.path.exists(folder):
                        shutil.rmtree(folder)
                st.session_state.messages = []
            else:
                st.info("Appending new Files to Existing Database!")

            os.makedirs(upload_dir, exist_ok=True)

            progress_bar = st.progress(0)
            for idx,file in enumerate(uploaded_files):
                st.info(f"Processing:{file.name}")
                filepath = os.path.join(upload_dir,file.name)
                with open(filepath,"wb") as f:
                    f.write(file.getbuffer())

                #run modular code elements
                process_video_pipeline(filepath)
                progress_bar.progress(int(((idx+1)/len(uploaded_files))*100))
            
            st.info("Generating Vector Embeddings And FAISS Indexes...")
            success = rebuild_faiss_index()
            if success:
                st.success("Database fully active and index built!")
        else:
            st.warning("Please drag video files into the uploader area first.")

#main window
st.subheader("Chat with your Video Repository")

#render previous text history (built-in ,streamlit)
for message in st.session_state.messages:
    with st.chat_message(message['role']):
        st.markdown(message['content'])

#handling user query
if incoming_query := st.chat_input("Ask Away Nerd:"):
    #display human text block
    with st.chat_message('user'):
        st.markdown(incoming_query)
    st.session_state.messages.append({
        'role':'user',
        'content':incoming_query
    })

    #query database
    retrieved_df = query_vector_store(incoming_query)

    if retrieved_df is None or retrieved_df.empty:
        bot_response = "Database context empty. Please upload lecture videos via the side menu to begin."
    else:
        #build prompt
        context_str = retrieved_df[['source','start','end','text']].to_json(orient="records",indent=2)
        prompt = f"""
You are EduRAG, an AI teaching assistant.

Use ONLY the retrieved transcript chunks below to answer the user's question.

Retrieved Context:
{context_str}

-----------------------------------------

User Question:
{incoming_query}

Instructions:

- Answer only using the information provided in the retrieved transcript chunks.
- If the answer exists, explain it naturally and clearly.
- Mention the source video and relevant timestamps whenever possible.
- If the information comes from multiple videos, combine it into one coherent answer.
- If the retrieved context is insufficient, say that there is not enough information in the available videos.
- If the question is unrelated to the uploaded videos, politely explain that you can only answer questions based on the uploaded educational content.
- Never invent facts that are not present in the retrieved context.
"""
        # Generate response using Llama 3.2 on Ollama
        with st.spinner("Analyzing data vectors..."):
            try:
                r = requests.post(
                    f"{OLLAMA_URL}/generate", 
                    json={
                        "model": LLM_MODEL, 
                        "prompt": prompt, 
                        "stream": False
                    }
                )
                r.raise_for_status()
                bot_response = r.json()['response']
            except Exception as e:
                bot_response = f"Failed connecting to local inference node: {e}"

    # Render bot response to page frame
    with st.chat_message("assistant"):
        st.markdown(bot_response)
    st.session_state.messages.append({"role": "assistant", "content": bot_response})
