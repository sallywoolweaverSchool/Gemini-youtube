import google.generativeai as genai
import os
from dotenv import load_dotenv
import yt_dlp
import time
import re

# Load environment variables
load_dotenv()

# Configure Gemini API
genai.configure(api_key=os.getenv('API_KEY'))

# Function to extract YouTube video ID from URL
def extract_youtube_id(youtube_url):
    """Extracts the YouTube video ID from a given URL."""
    match = re.search(r"(?:v=|\/)([A-Za-z0-9_-]{11})", youtube_url)  # Regular expression to extract ID
    if match:
        return match.group(1)
    else:
        return None

def download_video(video_url, output_filename="downloaded_video.mp4"):
    # Ensure that the downloaded file is deleted before download
    if os.path.exists(output_filename):
        print(f"Deleting existing video file: {output_filename}")
        os.remove(output_filename)

    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',  # Prioritize MP4
        'outtmpl': output_filename,  # Ensure file overwrites
        'quiet': False,  # Change to False to see more logs
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(video_url, download=True)
            print(f"Video downloaded: {info_dict.get('title')}")
            filename = ydl.prepare_filename(info_dict)
            print(f"File saved as: {filename}")
            return filename
    except Exception as e:
        print(f"Error downloading video: {e}")
        return None

# Function to upload video to Gemini File API
def upload_video_to_gemini(video_file_path):
    try:
        print(f"Uploading video file {video_file_path} to Gemini...")
        video_file = genai.upload_file(video_file_path)
        print(f"Completed upload: {video_file.uri}")

        # Ensure the file is ready for inference (ACTIVE state)
        while video_file.state.name != "ACTIVE":
            print('.', end='')  # Show progress while checking
            time.sleep(10)
            video_file = genai.get_file(video_file.name)

        if video_file.state.name == "FAILED":
            raise ValueError("File processing failed")
        
        # Get file metadata to verify
        print("File Metadata:", video_file)
        print(f"File Name: {video_file.name}")
        print(f"File URI: {video_file.uri}")
        
        return video_file  # Return the URI of the uploaded video file

    except Exception as e:
        print(f"Error uploading video to Gemini: {e}")
        return None

# Function to analyze video with Gemini
def analyze_video_with_gemini(video_file_uri, prompt):
    try:
        print(f"Analyzing video with URI: {video_file_uri}")
        print(f"File name: {video_file_uri.name}")

        model = genai.GenerativeModel(model_name="gemini-1.5-pro")
        print("Making LLM inference request...")
        response = model.generate_content([video_file_uri, prompt], request_options={"timeout": 600})
        return response.text
    except Exception as e:
        print(f"An error occurred during Gemini API call: {e}")
        return None


# Main flow
video_url = "https://www.youtube.com/watch?v=OGR9vTOgRJ4"  # Test with a valid video URL
video_file_path = download_video(video_url)

if video_file_path:
    print(f"Downloaded video at {video_file_path}")
    video_uri = upload_video_to_gemini(video_file_path)
    if video_uri:
        prompt = "Summarize this entire video. Include specific examples from the video. Then create a quiz with answer key based on the information in the video."
        video_analysis_response = analyze_video_with_gemini(video_uri, prompt)

        if video_analysis_response:
            print("Video Analysis Response:")
            print(video_analysis_response)
        else:
            print("Failed to analyze video.")
    else:
        print("Failed to upload video to Gemini.")
else:
    print("Failed to download video.")
