import os
import time
from pydub import AudioSegment
import requests
import urllib3
import streamlit as st
from moviepy.editor import VideoFileClip

urllib3.disable_warnings()

st.title('Audio Transcription App')

chunk_size = st.text_input("Enter the chunk size in seconds (default: 200)", "200")
try:
    chunk_size = int(chunk_size)
except ValueError:
    st.error("Invalid chunk size. Please enter a valid integer.")
    st.stop()

hf_token = st.text_input("Enter your Hugging Face API token")
if not hf_token:
    st.warning("Please enter your Hugging Face API token.")
    st.stop()

delay = st.text_input("Enter the delay in seconds between API requests (default: 1)", "1")
try:
    delay = float(delay)
except ValueError:
    st.error("Invalid delay. Please enter a valid number.")
    st.stop()

uploaded_file = st.file_uploader("Choose a file", type=['mp3', 'mp4'])
if uploaded_file is None:
    st.info("Please upload a file.")
    st.stop()

file_details = {"FileName": uploaded_file.name, "FileType": uploaded_file.type, "FileSize": uploaded_file.size}
st.write(file_details)

# Save the uploaded file to the current directory
with open(uploaded_file.name, 'wb') as f:
    f.write(uploaded_file.getbuffer())
st.success("Saved File")

AUDIO_FILE = os.path.join(os.getcwd(), uploaded_file.name)

if uploaded_file.type == 'audio/mp3':
    st.write("File is mp3")
else:
    st.write("Creating mp3 file")
    video = VideoFileClip(AUDIO_FILE)
    video.audio.write_audiofile(AUDIO_FILE.rsplit(".", 1)[0] + '.mp3')


def transcribe_audio(file_path, hf_token):
    API_URL = "https://api-inference.huggingface.co/models/openai/whisper-large-v2"
    headers = {"Authorization": f"Bearer {hf_token}"}

    with open(file_path, "rb") as f:
        data = f.read()

    response = requests.post(API_URL, headers=headers, data=data)

    if response.status_code == 200:
        transcription = response.json()
        return transcription['text']
    else:
        st.write('Error:', response.status_code, response)
        time.sleep(5)  # Wait a bit before retrying

    st.write('Reached maximum retries without successful response.')
    return None


@st.cache
def split_mp3_file(file_path, chunk_length_sec, hf_token, delay_sec) -> dict:
    audio = AudioSegment.from_mp3(file_path)
    file_length_sec = len(audio) / 1000
    chunk_length_ms = chunk_length_sec * 500

    # Create empty lists to store chunks iteration and errors
    chunks_iteration = []
    errors = []

    for i in range(0, len(audio), chunk_length_ms):
        chunks_iteration.append(
            f"Processing chunk {i // chunk_length_ms + 1} of {int(file_length_sec // chunk_length_sec) + 1}")
        chunk = audio[i:i + chunk_length_ms]
        file_name = f"{os.path.splitext(file_path)[0]}_{i // chunk_length_ms + 1}.mp3"
        chunk.export(file_name, format="mp3")

        chunk_text = transcribe_audio(file_name, hf_token)

        if chunk_text:
            chunks_iteration.append(
                f"Deleting chunk {i // chunk_length_ms + 1} of {int(file_length_sec // chunk_length_sec) + 1}")
            os.remove(file_name)
            time.sleep(delay_sec)
        else:
            errors.append(
                f"Transcription failed for chunk {i // chunk_length_ms + 1} of {int(file_length_sec // chunk_length_sec) + 1}")

    # Return the chunks iteration and errors as a dictionary
    return {"chunks_iteration": chunks_iteration, "errors": errors}


# Call the cached function outside split_mp3_file()
result = split_mp3_file(AUDIO_FILE.rsplit(".", 1)[0] + '.mp3', chunk_size, hf_token, delay)
errors = result.get("errors", [])
st.text("\n".join(errors))

# Display the chunks iteration in scrollable list
chunks_iteration = result.get("chunks_iteration", [])
st.write("Chunks Iteration:")
st.text("\n".join(chunks_iteration))

# Remove all .mp3 and .mp4 files when the program terminates
def cleanup_files():
    for file in os.listdir():
        if file.endswith(".mp3") or file.endswith(".mp4"):
            os.remove(file)


cleanup_files()
