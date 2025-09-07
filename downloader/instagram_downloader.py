import requests
from bs4 import BeautifulSoup
import os

def download_instagram_image(url, download_folder):
    headers = {"User-Agent": "Mozilla/5.0"}
    res = requests.get(url, headers=headers)
    soup = BeautifulSoup(res.text, "html.parser")
    meta_tag = soup.find("meta", property="og:image")
    if meta_tag:
        img_url = meta_tag["content"]
        img_res = requests.get(img_url)
        file_name = os.path.join(download_folder, img_url.split("/")[-1])
        with open(file_name, "wb") as f:
            f.write(img_res.content)
        return file_name
    return None
