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

app = Flask(__name__)

# === 1. 보안 무시 어댑터 ===
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
        response = session.get(url, headers=headers, timeout=10, verify=False)
        response.encoding = 'utf-8'
        return BeautifulSoup(response.text, 'html.parser')
    except:
        return None

# === 2. 딥 서치 (게시판 내부 검색) ===
def deep_search(session, board_url, keyword):
    # print(f"👉 게시판 내부 진입: {board_url}") # 로그 확인용
    soup = get_soup(session, board_url)
    if not soup: return []

    results = []
    links = soup.find_all('a')
    
    for link in links:
        text = link.get_text().strip()
        href = link.get('href')
        
        if not text or not href: continue
        if 'javascript' in href or '#' == href: continue
        
        # 키워드가 제목에 포함되어 있으면 저장
        if keyword in text:
            full_url = urljoin(board_url, href)
            results.append({"title": text, "link": full_url})
    
    return results

# === 3. 메인 로직 ===
def get_notices(url, user_keyword):
    url = url.strip()
    if not url.startswith("http"): url = "https://" + url
    
    session = create_session()
    soup = get_soup(session, url)
    
    if not soup: return {"status": "error", "message": "접속 실패"}

    # 리다이렉트 처리
    meta_refresh = soup.find('meta', attrs={'http-equiv': re.compile(r'refresh', re.I)})
    if meta_refresh:
        content = meta_refresh.get('content', '')
        if 'url=' in content:
            new_path = content.split('url=')[-1].strip()
            url = urljoin(url, new_path)
            soup = get_soup(session, url)

    final_results = []
    seen_urls = set()
    links = soup.find_all('a')
    
    # (A) 키워드 없을 때: 그냥 게시판 목록만
    if not user_keyword:
        keywords = ['공지', 'Notice', 'news', '게시판']
        for link in links:
            text = link.get_text().strip()
            href = link.get('href')
            if not text or not href: continue
            for k in keywords:
                if k in text:
                    full_url = urljoin(url, href)
                    if full_url not in seen_urls:
                        final_results.append({"title": text, "link": full_url})
                        seen_urls.add(full_url)
                    break
        return {"status": "success", "data": final_results[:15]}

    # (B) 키워드 있을 때: 게시판 들어가서 찾기 (Deep Search)
    else:
        potential_boards = []
        board_keywords = ['공지', 'Notice', '소식', 'News', '게시판', '학사', '장학', '취업', '국제']
        
        for link in links:
            text = link.get_text().strip()
            href = link.get('href')
            if not text or not href: continue
            
            for bk in board_keywords:
                if bk in text:
                    full_url = urljoin(url, href)
                    if full_url not in seen_urls:
                        potential_boards.append(full_url)
                        seen_urls.add(full_url)
                    break
        
        # 발견된 게시판들 순회 (최대 5개)
        for board_url in potential_boards[:5]: 
            found_items = deep_search(session, board_url, user_keyword)
            for item in found_items:
                if item['link'] not in seen_urls:
                    final_results.append(item)
                    seen_urls.add(item['link'])
            
        if not final_results:
            return {"status": "success", "data": [], "message": "게시판 안에서도 키워드를 못 찾았습니다."}
            
        return {"status": "success", "data": final_results}

# === 4. 서버 경로 설정 (여기 중요!) ===

# 서버 상태 확인용 (브라우저로 접속하면 보임)
@app.route('/', methods=['GET'])
def home():
    return "서버가 정상 작동 중입니다! (V3 Update)"

# 아이폰 앱이 접속하는 경로
@app.route('/search', methods=['GET'])
def search_api():
    target_url = request.args.get('url')
    keyword = request.args.get('keyword')
    
    if not target_url:
        return jsonify({"status": "error", "message": "URL 필요"})
    
    result = get_notices(target_url, keyword)
    return jsonify(result)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001)