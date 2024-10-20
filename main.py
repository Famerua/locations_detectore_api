import cv2
import os
import base64
import requests
from fpdf import FPDF
import dotenv
import logging

logging.basicConfig(
    filename="info.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding='utf-8'
)

dotenv.load_dotenv()

FRAMES_DIR = "frames"
API_URL = "https://api.openai.com/v1/chat/completions"
API_KEY = os.getenv('token')
VIDEO_PATH = "dining.mp4"  
PDF_FILENAME = f"{VIDEO_PATH.split('.')[0]}.pdf"
TEXT_FILENAME = f"locations_{VIDEO_PATH.split('.')[0]}.txt"

#step 1 
def extract_frames(video_path, interval):
    '''convert video to frames with frequency = interval'''
    os.makedirs(FRAMES_DIR, exist_ok=True)
    vidcap = cv2.VideoCapture(video_path)
    fps = int(vidcap.get(cv2.CAP_PROP_FPS))
    frame_count = 0
    success, image = vidcap.read()

    while success:
        if frame_count % (fps * interval) == 0:
            frame_name = f"{FRAMES_DIR}/frame_{frame_count // (fps * interval)}.jpg"
            cv2.imwrite(frame_name, image)  
            logging.info(f"Кадр сохранен: {frame_name}")

        success, image = vidcap.read()
        frame_count += 1

    vidcap.release()


# Step 3
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def send_to_chatgpt(images, prompt):
    '''send request to ChatGPT'''
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encode_image(images[0])}"}}
                ]
            }
        ],
        "max_tokens": 300
    }
    if len(images) == 2:
        payload["messages"][0]["content"].append(
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encode_image(images[1])}"}}
        )
    response = requests.post(API_URL, headers=headers, json=payload)
    try:
        return response.json()["choices"][0]["message"]["content"]
    except:
        return 'err'
    
#step 2
def get_frame_location():
    '''preparation requests'''
    frames = sorted(os.listdir(FRAMES_DIR), key=lambda x: int(x.split('_')[1].split('.')[0]))
    logging.info(f"Всего кадров: {len(frames)}")
    locations = []

    for i in range(len(frames)):
        if i == 0:
            # First frame prompt
            prompt = "I sent you photo.I need you to say what location is in this photo in one word. For example, if it is a room in a house, then 'living room', 'bedroom', 'bathroom', etc. If outside, then 'street', 'road', 'porch', 'yard', etc."
            location = send_to_chatgpt([f'{FRAMES_DIR}/frame_0.jpg'], prompt)
        else:
            # Other frames prompt
            prompt = f"I'm sending you two photos. The first photo is the current frame, and the second photo is the previous frame. I also tell you that the location on the previous frame is {locations[-1]}. You must understand whether the photos are frames of the same scene and the same room. If so, then you must name the location of the current frame as the previous one. If not, then you must name the new location of the current frame.Give me answer location in one word. For example, if it is a room in a house, then 'living room', 'bedroom', 'bathroom', etc. If outside, then 'garage', 'yard', etc."
            location: str = send_to_chatgpt([f'{FRAMES_DIR}/frame_{i}.jpg', f'{FRAMES_DIR}/frame_{i-1}.jpg'], prompt)
        logging.info(f"frame_{i}: {location.lower()}")
        locations.append(location.lower())

    with open(TEXT_FILENAME, "w") as file:
        for i, location in enumerate(locations):
            file.write(f"frame_{i}: {location}\n")

# Step 4 
def combine_images_to_pdf():
    '''Combine all images into a PDF'''
    pdf = FPDF()
    frames = sorted(os.listdir(FRAMES_DIR), key=lambda x: int(x.split('_')[1].split('.')[0]))

    for frame in frames:
        frame_path = os.path.join(FRAMES_DIR, frame)
        pdf.add_page()
        pdf.image(frame_path, x=10, y=10, w=180)

    pdf.output(PDF_FILENAME)

# Step 5
def zip_images():
    '''zip frames'''
    import shutil
    shutil.make_archive(VIDEO_PATH.split('.')[0], 'zip', 'frames')
    shutil.rmtree(FRAMES_DIR)

# Step 6 
def send_zip_to_chatgpt():
    '''extra fun if short video'''
    with open(f'{VIDEO_PATH.split('.')[0]}.zip', "rb") as zip_file:
        zip_b64 = base64.b64encode(zip_file.read()).decode('utf-8')

    with open(TEXT_FILENAME) as f:
        locations = f.read()

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {API_KEY}"
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "user", "content": f"{locations}\n\nI am sending you a zip file containing photos. I am also sending you a list of locations for each photo. The name of the photo corresponds to the name of the line. For example, the file frame_1.jpg has a location after the words 'frame_1:'. I want you to compare all the photos and their locations. If the location is the same, but the names are different, then suggest me that I correct them in this format:frame_i, frame_j, your recommended name"},
            {"role": "user", "content": f"Zip file: {zip_b64}"}
        ]
    }
    response = requests.post(API_URL, headers=headers, json=payload)
    logging.info(response.json())
    return response.json()["choices"][0]["message"]["content"]

def main():
    extract_frames(VIDEO_PATH, interval=1)
    get_frame_location()
    combine_images_to_pdf()
    zip_images()
    try:
        logging.info(send_zip_to_chatgpt())
    except KeyError as err:
        logging.info(err)
        logging.info('Скорее всего превышаем лимиты по количеству токенов.')

if __name__ == "__main__":
    main()
