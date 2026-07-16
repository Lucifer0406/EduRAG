import os
import json
import requests
import pandas as pd
import joblib
import numpy as np
import faiss
from utils.config import OLLAMA_URL,TOP_K,EMBEDDING_MODEL


def get_embedding(text_list):
    try:
        r = requests.post(
            f"{OLLAMA_URL}/embed", 
            json={
                "model": EMBEDDING_MODEL, 
                "input": text_list
            }
        )
        r.raise_for_status()
        return r.json()['embeddings']
    except Exception as e:
        print(f"Embedding error: {e}")
        return None
    
def rebuild_faiss_index(base_data_dir="data"):
    prep_dir = os.path.join(base_data_dir,"preprocessed")
    vs_dir = os.path.join(base_data_dir,"vector_store")
    os.makedirs(vs_dir,exist_ok=True)

    my_dict = []
    chunk_id = 0

    if not os.path.exists(prep_dir):return False

    for json_file in os.listdir(prep_dir):
        if not json_file.endswith(".json"):continue
        with open(os.path.join(prep_dir,json_file),encoding="utf-8") as f:
            content = json.load(f)

        embeddings = get_embedding([c['text'] for c in content['chunks']])
        if not embeddings: continue

        for i,chunk in enumerate(content['chunks']):
            chunk['chunk_id'] = chunk_id
            chunk['embedding'] = embeddings[i]
            chunk_id+=1
            my_dict.append(chunk)

    if not my_dict : return False

    df = pd.DataFrame.from_records(my_dict)
    raw_embeddings = np.vstack(df['embedding']).astype("float32")
    faiss.normalize_L2(raw_embeddings)

    index = faiss.IndexFlatIP(raw_embeddings.shape[1])
    index.add(raw_embeddings)

    faiss.write_index(index,os.path.join(vs_dir,"my_faiss.index"))
    df_metadata = df.drop(columns=['embedding'])
    joblib.dump(df_metadata,os.path.join(vs_dir,"metadata.joblib"))
    
    return True
    

def query_vector_store(incoming_query,top_results=TOP_K,base_data_dir="data"):
    vs_dir = os.path.join(base_data_dir, "vector_store")
    idx_path = os.path.join(vs_dir, "my_faiss.index")
    meta_path = os.path.join(vs_dir, "metadata.joblib")

    if not (os.path.exists(idx_path)) or not (os.path.exists(meta_path)): return None

    df = joblib.load(meta_path)
    index = faiss.read_index(idx_path)

    query_emb = np.asarray(get_embedding([incoming_query]), dtype=np.float32)
    faiss.normalize_L2(query_emb)

    distances,max_index = index.search(query_emb,top_results)
    return df.loc[max_index.flatten()]