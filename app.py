from flask import Flask, request, jsonify
import requests
import ssl
import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from urllib3.util import ssl_
import urllib3
import time

app = Flask(__name__)

# === 보안 설정 (기존 동일) ===
class LegacySSLAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        context = ssl_.create_urllib3_context(ciphers='DEFAULT@SECLEVEL=1')
        context.check_hostname = False 
        context.verify_mode = ssl.CERT_NONE
        self.poolmanager = PoolManager(num_pools=connections, maxsize=maxsize, block=block, ssl_context=context)

def create_session():
    session = requests.Session()
    session.mount('https://', LegacySSLAdapter())
    return session

def get_soup(session, url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        response = session.get(url, headers=headers, timeout=5, verify=False)
        response.encoding = 'utf-8'
        return BeautifulSoup(response.text, 'html.parser')
    except:
        return None

# === ⭐️ [핵심] 2단계: 게시판 안으로 들어가서 키워드 찾기 ===
def deep_search(session, board_url, keyword):
    print(f"   👉 게시판 내부 진입: {board_url}")
    soup = get_soup(session, board_url)
    if not soup: return []

    results = []
    links = soup.find_all('a')
    
    for link in links:
        text = link.get_text().strip()
        href = link.get('href')
        
        if not text or not href: continue
        if 'javascript' in href or '#' == href: continue
        
        # 여기서 사용자의 키워드가 제목에 있는지 검사!
        if keyword in text:
            full_url = urljoin(board_url, href)
            results.append({"title": text, "link": full_url})
    
    return results

# === 메인 로직 ===
def get_notices(url, user_keyword):
    url = url.strip()
    if not url.startswith("http"): url = "https://" + url
    
    session = create_session()
    soup = get_soup(session, url)
    
    if not soup: return {"status": "error", "message": "접속 실패"}

    # 1. 메인 페이지 리다이렉트 처리 (쪽지 따라가기)
    meta_refresh = soup.find('meta', attrs={'http-equiv': re.compile(r'refresh', re.I)})
    if meta_refresh:
        content = meta_refresh.get('content', '')
        if 'url=' in content:
            new_path = content.split('url=')[-1].strip()
            url = urljoin(url, new_path)
            soup = get_soup(session, url)

    final_results = []
    seen_urls = set()