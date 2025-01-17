from os.path import sep as PathSep
import os
from typing import Optional

debug = True

EMBEDDING_MODEL = "thenlper/gte-small"
EMBEDDING_DIM = 384
EMBEDDING_MODEL_ARGS = model_kwargs = {"device": "cuda"}

DATA_PATH = os.getcwd() + PathSep + "data"
DB_FAISS_PATH = "chatbot/vectorstore/db_faiss"

MODEL_PATH = os.getcwd() + PathSep + "chatbot/models/zephyr-7b-beta.Q4_K_M.gguf"
MODEL_NAME = MODEL_PATH.partition(".")[0].partition(PathSep)[-1]
# MODEL_KWARGS = {"max_new_tokens": 1024, "temperature": 0.8}

SIMILARITY_SEARCH_KWARGS = {"similarity_top_k": 3}
SIMILARITY_SEARCH_THRESHOLD = 0.33

instruct_prompt_template = """Below is an instruction that describes a task, paired with an input that provides further context. Write a response that appropriately completes the request. 

### Instruction:
{instruction}

### Input: 
{input}

### Response:

"""


# library commons
def get_subjects_from_dirs(data_path=DATA_PATH):
    subjects = {walk: walk for walk in next(os.walk(data_path))[1]}
    return subjects


def get_subject_data_path(subject_str: str) -> Optional[str]:
    if subject_str in subjects.keys():
        subpath = DATA_PATH + PathSep + subjects[subject_str]
        if os.path.exists(subpath):
            return subpath
    return None


subjects = get_subjects_from_dirs()


if __name__ == "__main__":
    print(MODEL_PATH)
