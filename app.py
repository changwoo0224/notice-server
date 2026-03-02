from flask import Flask, request, jsonify
import requests
import ssl
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from urllib3.util import ssl_
import urllib3
import time

app = Flask(__name__)

# === 1. 보안 무시 어댑터 ===
class LegacySSLAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        context = ssl_.create_urllib3_context(ciphers='DEFAULT@SECLEVEL=1')
        context.check_hostname = False 
        context.verify_mode = ssl.CERT_NONE
        self.poolmanager = PoolManager(num_pools=connections, maxsize=maxsize, block=block, ssl_context=context)

def get_soup(url):
    try:
        session = requests.Session()
        session.mount('https://', LegacySSLAdapter())
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        }
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        # 타임아웃을 5초로 설정 (여러 페이지 돌려면 빨라야 함)
        response = session.get(url, headers=headers, timeout=5, verify=False)
        response.encoding = 'utf-8' 
        return BeautifulSoup(response.text, 'html.parser'), response.status_code, len(response.text)
    except Exception as e:
        print(f"Error: {e}")
        return None, 500, 0

# === 2. 페이지 자동 넘김 크롤러 (핵심 기능) ===
def scrape_with_pagination(base_url, keyword, max_pages=100):
    base_url = base_url.strip()
    if not base_url.startswith("http"): base_url = "https://" + base_url
    
    print(f"🚀 [자동화 시작] '{keyword}' 검색 시작 (최대 {max_pages}페이지 탐색)")
    
    all_results = []
    seen_links = set()
    prev_page_size = 0 # 페이지가 끝났는지 확인용
    
    # 1페이지부터 max_pages까지 반복
    for page in range(1, max_pages + 1):
        # URL 만들기 (이미 파라미터가 있으면 &pageIndex=, 없으면 ?pageIndex=)
        # 전북대 등 대부분의 공공 사이트는 'pageIndex' 또는 'page'를 씁니다.
        if "pageIndex=" in base_url or "page=" in base_url:
            # 이미 페이지 정보가 있으면 그건 1페이지로 간주하고 첫 턴만 돔 (복잡해짐 방지)
            current_url = base_url 
        else:
            separator = "&" if "?" in base_url else "?"
            # 전북대 표준 파라미터인 pageIndex를 우선 사용
            current_url = f"{base_url}{separator}pageIndex={page}"
            
        print(f"   Reading Page {page}: {current_url}")
        
        soup, status, content_size = get_soup(current_url)
        
        if not soup or status != 200:
            print("   -> 접속 실패 또는 끝")
            break
            
        # (옵션) 이전 페이지와 내용 길이가 똑같으면 '마지막 페이지'라고 판단하고 종료
        if page > 1 and abs(content_size - prev_page_size) < 50:
            print("   -> 페이지 내용이 변하지 않음. 마지막 페이지 도달.")
            break
        prev_page_size = content_size

        # 링크 수집
        links = soup.find_all('a')
        found_on_this_page = 0
        
        for link in links:
            text = link.get_text().strip()
            href = link.get('href')
            
            if not text or not href: continue
            if 'javascript' in href or '#' in href: continue
            
            # 키워드 검사 (공백 무시)
            clean_text = text.replace(" ", "")
            clean_keyword = keyword.replace(" ", "") if keyword else ""
            
            if (keyword and clean_keyword in clean_text) or (not keyword and len(text) > 5):
                # URL 합치기
                if not href.startswith("http"):
                    base_root = "/".join(base_url.split('/')[:3])
                    if href.startswith("/"):
                        full_url = base_root + href
                    else:
                        # 현재 경로 기준 합치기
                        path_url = base_url.split('?')[0] # 쿼리 떼고
                        path_url = "/".join(path_url.split('/')[:-1])
                        full_url = path_url + "/" + href
                else:
                    full_url = href

                if full_url not in seen_links:
                    all_results.append({"title": f"[{page}p] {text}", "link": full_url})
                    seen_links.add(full_url)
                    found_on_this_page += 1
        
        print(f"   -> {found_on_this_page}개 발견")
        
        # 만약 사용자가 URL에 이미 page를 넣었으면 1번만 돌고 종료
        if current_url == base_url:
            break
            
        # 너무 빨리 긁으면 차단당하니까 0.5초 휴식
        time.sleep(0.5)

    return all_results

# === 서버 경로 ===
@app.route('/', methods=['GET'])
def home():
    return "V8: Auto-Pagination Walker (페이지 자동 넘김 모드)"

@app.route('/search', methods=['GET'])
def search_api():
    target_url = request.args.get('url')
    keyword = request.args.get('keyword')
    
    if not target_url:
        return jsonify({"status": "error", "message": "URL 필요"})
    
    # 페이지 자동 넘김 크롤러 실행
    results = scrape_with_pagination(target_url, keyword, max_pages=100) # 5페이지까지 뒤짐
    
    if not results:
        return jsonify({"status": "success", "data": [], "message": "100페이지까지 뒤져봤지만 글이 없습니다."})
        
    return jsonify({"status": "success", "data": results})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001)