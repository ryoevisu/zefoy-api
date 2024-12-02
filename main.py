from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
import re
import random
import string
import base64
import urllib.parse
import json
import time
from requests_toolbelt import MultipartEncoder
from PIL import Image
import pytesseract
import os

app = FastAPI(title="Zefoy API", description="API for TikTok view automation")

class VideoRequest(BaseModel):
    video_url: str

class ZefoyAPI:
    def __init__(self):
        self.cookies = {"Cookie": None}
        self.success = []
        self.failures = []

    def login(self):
        with requests.Session() as r:
            r.headers.update({
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36'
            })
            
            response = r.get('https://zefoy.com/')
            
            if 'Sorry, you have been blocked' in response.text:
                raise HTTPException(status_code=503, detail="Zefoy server is currently affected by cloudflare")
            
            captcha_image = re.search(r'src="(.*?)" onerror="errimg\(\)"', response.text).group(1).replace('amp;', '')
            form = re.search(r'type="text" name="(.*?)"', response.text).group(1)
            
            # Handle captcha solving (simplified for example)
            captcha_response = self.solve_captcha(r.get(f'https://zefoy.com{captcha_image}').content)
            
            login_data = {form: captcha_response}
            response = r.post('https://zefoy.com/', data=login_data)
            
            if 'placeholder="Enter Video URL"' in response.text:
                self.cookies["Cookie"] = "; ".join([f"{x}={y}" for x, y in r.cookies.get_dict().items()])
                return True
            return False

    def solve_captcha(self, image_data):
        # Implement captcha solving logic here
        # This is a simplified version
        with open('temp_captcha.png', 'wb') as f:
            f.write(image_data)
        image = Image.open('temp_captcha.png')
        text = pytesseract.image_to_string(image)
        os.remove('temp_captcha.png')
        return text.strip()

    def send_views(self, video_url):
        if not self.cookies["Cookie"]:
            if not self.login():
                raise HTTPException(status_code=401, detail="Failed to login to Zefoy")

        with requests.Session() as r:
            r.headers.update({
                'Cookie': self.cookies["Cookie"],
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            
            # Get video form
            response = r.get('https://zefoy.com/')
            video_form = re.search(r'name="(.*?)" placeholder="Enter Video URL"', response.text).group(1)
            post_action = re.findall(r'action="(.*?)">', response.text)[3]

            # Send view request
            boundary = '----WebKitFormBoundary' + ''.join(random.sample(string.ascii_letters + string.digits, 16))
            data = MultipartEncoder({video_form: video_url}, boundary=boundary)
            
            r.headers.update({'Content-Type': f'multipart/form-data; boundary={boundary}'})
            response = r.post(f'https://zefoy.com/{post_action}', data=data)
            
            result = self.decode_response(response.text)
            
            if 'Successfully' in result:
                views = re.search(r'Successfully (.*?) views sent.', result)
                return {
                    "success": True,
                    "message": result,
                    "views_sent": views.group(1) if views else "1000"
                }
            else:
                return {
                    "success": False,
                    "message": result
                }

    def decode_response(self, response):
        try:
            return base64.b64decode(urllib.parse.unquote(response[::-1])).decode()
        except:
            return response

zefoy_api = ZefoyAPI()

@app.post("/api/views")
async def send_views(request: VideoRequest):
    if not 'tiktok.com' in request.video_url:
        raise HTTPException(status_code=400, detail="Invalid TikTok URL")
    
    try:
        result = zefoy_api.send_views(request.video_url)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/status")
async def get_status():
    return {
        "status": "online",
        "logged_in": bool(zefoy_api.cookies["Cookie"])
  }
              
