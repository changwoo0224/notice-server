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

# === 1. 보안 무시 어댑터 (한국 사이트 접속 필수템) ===
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
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        response = session.get(url, headers=headers, timeout=8, verify=False)
        response.encoding = 'utf-8' # 한글 깨짐 방지
        return BeautifulSoup(response.text, 'html.parser')
    except:
        return None

# === 2. 범용 검색 로직 ===
def get_notices(url, user_keyword):
    url = url.strip()
    if not url.startswith("http"): url = "https://" + url
    
    session = create_session()
    print(f"🔍 [진입] {url} 분석 시작...")
    
    soup = get_soup(session, url)
    if not soup: return {"status": "error", "message": "사이트 접속 실패"}

    # (1) 메인 리다이렉트 처리 (쪽지 따라가기)
    meta_refresh = soup.find('meta', attrs={'http-equiv': re.compile(r'refresh', re.I)})
    if meta_refresh:
        content = meta_refresh.get('content', '')
        if 'url=' in content:
            new_path = content.split('url=')[-1].strip()
            url = urljoin(url, new_path)
            print(f"   👉 자동 이동됨: {url}")
            soup = get_soup(session, url)

    final_results = []
    seen_urls = set()
    
    # 만약 사용자가 키워드 없이 URL만 줬다면? -> 모든 링크 수집 (단순 모드)
    if not user_keyword:
        links = soup.find_all('a')
        board_keywords = ['공지', 'Notice', '소식', 'News', '게시판', '알림']
        for link in links:
            text = link.get_text().strip()
            href = link.get('href')
            if not text or not href: continue
            
            # 공지사항스러운 링크만 15개 수집
            for bk in board_keywords:
                if bk in text:
                    full_url = urljoin(url, href)
                    if full_url not in seen_urls:
                        final_results.append({"title": text, "link": full_url})
                        seen_urls.add(full_url)
                    break
        return {"status": "success", "data": final_results[:15]}

    # ==========================================
    # ⭐️ [핵심] 키워드가 있을 때 (스마트 검색 모드)
    # ==========================================
    
    # 전략 A: "현재 페이지"에 바로 키워드 글이 있는지 확인
    # (사용자가 '공지사항 게시판 주소'를 직접 넣었을 때 작동)
    links = soup.find_all('a')
    for link in links:
        text = link.get_text().strip()
        href = link.get('href')
        if not text or not href: continue
        if 'javascript' in href or '#' == href: continue

        if user_keyword in text:
            full_url = urljoin(url, href)
            if full_url not in seen_urls:
                final_results.append({"title": text, "link": full_url})
                seen_urls.add(full_url)
    
    # 전략 B: 현재 페이지에 글이 별로 없으면, "게시판 목록"을 찾아 들어감
    # (사용자가 '메인 홈페이지 주소'를 넣었을 때 작동)
    if len(final_results) < 3: 
        print("   👉 현재 페이지에서 결과 부족. 하위 게시판 탐색 시작...")
        
        potential_boards = []
        # '더보기', '+', 'Notice' 같은 게시판 입구 단어들
        board_cues = ['공지', 'Notice', '소식', 'News', '게시판', '학사', '장학', '채용', 'More', '더보기', '+']
        
        for link in links:
            text = link.get_text().strip()
            href = link.get('href')
            if not text or not href: continue
            
            # 이미 찾은 글은 게시판 아님
            full_url = urljoin(url, href)
            if full_url in seen_urls: continue

            for cue in board_cues:
                if cue in text or cue.upper() in text.upper():
                    if full_url not in potential_boards:
                        potential_boards.append(full_url)
                    break
        
        # 찾은 게시판들(최대 5개)을 하나씩 들어가서 털어옴
        for board_url in potential_boards[:5]:
            print(f"      Run: 하위 게시판 진입 -> {board_url}")
            sub_soup = get_soup(session, board_url)
            if not sub_soup: continue
            
            sub_links = sub_soup.find_all('a')
            for sub_link in sub_links:
                s_text = sub_link.get_text().strip()
                s_href = sub_link.get('href')
                if not s_text or not s_href: continue
                
                if user_keyword in s_text:
                    s_full_url = urljoin(board_url, s_href)
                    if s_full_url not in seen_urls:
                        final_results.append({"title": s_text, "link": s_full_url})
                        seen_urls.add(s_full_url)

    return {"status": "success", "data": final_results[:20]}

# === 서버 경로 ===
@app.route('/', methods=['GET'])
def home():
    return "🌐 범용 검색 서버 가동 중 (V5: General AI Mode)"

@app.route('/search', methods=['GET'])
def search_api():
    target_url = request.args.get('url')
    keyword = request.args.get('keyword')
    if not target_url: return jsonify({"status": "error", "message": "URL 필요"})
    
    result = get_notices(target_url, keyword)
    return jsonify(result)

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001)