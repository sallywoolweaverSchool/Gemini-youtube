import google.generativeai as genai
import os
from dotenv import load_dotenv
import yt_dlp
import time
import re
import tkinter as tk
from tkinter import scrolledtext, messagebox
import threading

# Load environment variables
load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.getenv('API_KEY'))

# Create a GUI window
root = tk.Tk()
root.title("Video Downloader and Analyzer")

# Create a scrolled text widget to display logs
log_box = scrolledtext.ScrolledText(root, width=100, height=30, wrap=tk.WORD)
log_box.pack(padx=10, pady=10)

def log_update(message):
    """Update the log box in the GUI"""
    log_box.insert(tk.END, message + '\n')
    log_box.yview(tk.END)  # Scroll to the bottom
    log_box.update_idletasks()  # Ensure the GUI updates immediately

# Function to extract YouTube video ID from URL
def extract_youtube_id(youtube_url):
    """Extracts the YouTube video ID from a given URL."""
    match = re.search(r"(?:v=|\/)([A-Za-z0-9_-]{11})", youtube_url)
    if match:
        return match.group(1)
    else:
        return None

def download_video(video_url, output_filename="downloaded_video.mp4", update_status_func=None):
    """Download video and update the GUI with the download progress."""
    # Ensure that the downloaded file is deleted before download
    if os.path.exists(output_filename):
        log_update(f"Deleting existing video file: {output_filename}")
        os.remove(output_filename)

    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',  # Prioritize MP4
        'outtmpl': output_filename,  # Ensure file overwrites
        'quiet': False,  # Change to False to see more logs
        'progress_hooks': [lambda d: update_status_func(d)]  # Hook for progress updates
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_url, download=True)
            filename = ydl.prepare_filename(info_dict)
            log_update(f"Video downloaded: {info_dict.get('title')}")
            log_update(f"File saved as: {filename}")
            return filename, info_dict.get('duration')  # Return the video path and its duration
    except Exception as e:
        log_update(f"Error downloading video: {e}")
        return None, None

def update_status(d):
    """Handles progress updates."""
    status_message = ""
    if 'status' in d:
        status_message += f"Status: {d['status']} - "
    if 'filename' in d:
        status_message += f"Downloading: {d['filename']} - "
    if 'eta' in d:
        status_message += f"ETA: {d['eta']} seconds - "
    if 'downloaded_bytes' in d:
        status_message += f"Downloaded: {d['downloaded_bytes']} bytes"

    if status_message:
        log_update(status_message)

# Function to upload video to Gemini File API
def upload_video_to_gemini(video_file_path):
    """Upload video to Gemini and ensure it's ready for inference."""
    try:
        log_update(f"Uploading video file {video_file_path} to Gemini...")
        video_file = genai.upload_file(video_file_path)
        log_update(f"Completed upload: {video_file.uri}")

        while video_file.state.name != "ACTIVE":
            log_update('Processing video, please wait...')
            time.sleep(10)
            video_file = genai.get_file(video_file.name)

        if video_file.state.name == "FAILED":
            raise ValueError("File processing failed")
        
        log_update("File ready for analysis.")
        return video_file  # Return the URI of the uploaded video file

    except Exception as e:
        log_update(f"Error uploading video to Gemini: {e}")
        return None

# Function to analyze video with Gemini and return the response with the requested number of questions
def analyze_video_with_gemini(video_file_uri, prompt, num_questions):
    """Analyze video with Gemini and return the response with the requested number of questions."""
    try:
        log_update(f"Analyzing video with URI: {video_file_uri}")
        model = genai.GenerativeModel(model_name="gemini-1.5-pro")
        log_update("Making LLM inference request...")

        # Refined prompt to make sure we ask for the exact number of questions
        refined_prompt = (
            f"{prompt} Please make sure the quiz contains exactly {num_questions} multiple choice questions. "
            "Each question should be based entirely on the video content and should not include outside information. "
            "Provide the questions with timestamps in HH:MM:SS format."
        )

        response = model.generate_content([video_file_uri, refined_prompt], request_options={"timeout": 600})

        # Print the full response for debugging
        log_update("Raw API Response:")
        log_update(response.text)
        save_quiz_to_file(response.text)

    except Exception as e:
        log_update(f"An error occurred during Gemini API call: {e}")
        return None




# Function to run the main video download, upload, and analysis process in a separate thread
def run_video_analysis(video_url, num_questions):
    video_file_path, video_duration = download_video(video_url, update_status_func=update_status)

    # Check if the video is less than 59 minutes
    if video_duration and video_duration > 3540:  # 59 minutes in seconds
        log_update("Error: Video is too long (greater than 59 minutes). Please choose a shorter video.")
        return

    if video_file_path:
        log_update(f"Downloaded video at {video_file_path}")
        video_uri = upload_video_to_gemini(video_file_path)
        print("testing link",video_uri)
        if video_uri:
            prompt = (
                f"Summarize the entire video, and create a quiz with exactly {num_questions} multiple choice questions. "
                "The questions should be based entirely on the content of the video and should not include outside information. "
                "Each question should be distinct, based on key moments, facts, and events from the video, and include timestamps "
                "in the format HH:MM:SS for each question. "
                "Ensure the quiz covers the video in chronological order, starting with the introduction and moving through key "
                "scenes and actions until the conclusion. Provide an answer key as well, listing the timestamp for each answer. Questions should be evenly spread out throughout the entire video (ie don't just ask all questions in the first few minutes). There should be questions covering the beginning, middle, and end of the video"
            )
            video_analysis_response = analyze_video_with_gemini(video_uri, prompt, num_questions)
            print(video_analysis_response)
            if video_analysis_response:
                log_update("Video Analysis Response:")
                log_update(video_analysis_response)
                save_quiz_to_file(video_analysis_response)  # Save the quiz to a .txt or .doc file
            else:
                log_update("Failed to analyze video.")
        else:
            log_update("Failed to upload video to Gemini.")
    else:
        log_update("Failed to download video.")

def save_quiz_to_file(quiz_content):
    """Save the quiz content to a text file or Word document."""
    file_choice = messagebox.askquestion("Save Quiz", "Do you want to save the quiz as a .txt file? Click no to save as a .doc", icon='question')
    
    if file_choice == 'yes':
        with open("quiz.txt", "w") as f:
            f.write(quiz_content)
        log_update("Quiz saved as quiz.txt")
    else:
        # Option to save as a Word document (optional)
        from docx import Document
        doc = Document()
        doc.add_paragraph(quiz_content)
        doc.save("quiz.docx")
        log_update("Quiz saved as quiz.docx")

# Function to start the video download and analysis
def start_analysis():
    video_url = url_entry.get()  # Get the URL from the input field
    if not video_url:
        log_update("Please enter a valid YouTube URL.")
        return

    try:
        num_questions = int(num_questions_entry.get())
    except ValueError:
        log_update("Please enter a valid number of questions.")
        return

    log_update("Validating URL...")
    # Run the video download and analysis in a separate thread to keep the GUI responsive
    threading.Thread(target=run_video_analysis, args=(video_url, num_questions)).start()

# Create an input field for the URL
url_entry = tk.Entry(root, width=100)
url_entry.pack(padx=10, pady=5)

# Create an input field for the number of questions
num_questions_label = tk.Label(root, text="Number of Questions:")
num_questions_label.pack(padx=10, pady=5)
num_questions_entry = tk.Entry(root, width=10)
num_questions_entry.pack(padx=10, pady=5)

# Create a button to start the process
start_button = tk.Button(root, text="Start Analysis", command=start_analysis)
start_button.pack(padx=10, pady=10)

# Start the GUI event loop
root.mainloop()
