import os
from flask import Flask, request, jsonify
import requests
import ssl
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from urllib3.util import ssl_
import urllib3
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

app = Flask(__name__)

# === 1. 보안 설정 ===
class LegacySSLAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        context = ssl_.create_urllib3_context(ciphers='DEFAULT@SECLEVEL=1')
        context.check_hostname = False 
        context.verify_mode = ssl.CERT_NONE
        self.poolmanager = PoolManager(num_pools=connections, maxsize=maxsize, block=block, ssl_context=context)

def get_soup(url, params=None):
    try:
        session = requests.Session()
        session.mount('https://', LegacySSLAdapter())
        headers = {'User-Agent': 'Mozilla/5.0'}
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # 타임아웃 5초
        response = session.get(url, headers=headers, params=params, timeout=5, verify=False)
        response.encoding = 'utf-8' 
        return BeautifulSoup(response.text, 'html.parser'), response.url
    except Exception as e:
        print(f"Error: {e}")
        return None, ""

# === 2. V16: 파라미터 보존 + 조건 검색 ===
def search_jbnu_logic(target_url, keyword):
    if not target_url.startswith("http"): target_url = "https://" + target_url
    
    # URL 분해
    parsed = urlparse(target_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    
    # 기존 파라미터 가져오기 (menu=2377 등을 살리기 위함)
    current_params = parse_qs(parsed.query)
    clean_params = {k: v[0] for k, v in current_params.items()}
    
    # ⭐️ 핵심: 전북대 검색 조건 강제 주입
    clean_params['searchKeyword'] = keyword
    clean_params['searchCondition'] = '0' # 0=제목, 1=내용
    
    # 접속!
    soup, final_url = get_soup(base_url, params=clean_params)
    print(f"👉 접속 시도 URL: {final_url}") 

    if not soup: return []

    results = []
    seen_links = set()
    links = soup.find_all('a')
    
    for link in links:
        text = link.get_text().strip()
        href = link.get('href')
        
        if not text or not href: continue
        if 'javascript' in href or '#' in href: continue
        
        # 키워드 매칭 (공백 제거 후 확인)
        clean_text = text.replace(" ", "")
        clean_keyword = keyword.replace(" ", "")
        
        if clean_keyword in clean_text:
            if not href.startswith("http"):
                if href.startswith("/"):
                    full_url = f"{parsed.scheme}://{parsed.netloc}{href}"
                else:
                    path_dir = "/".join(parsed.path.split('/')[:-1])
                    full_url = f"{parsed.scheme}://{parsed.netloc}{path_dir}/{href}"
            else:
                full_url = href
            
            if full_url not in seen_links:
                results.append({"title": text, "link": full_url})
                seen_links.add(full_url)

    return results

@app.route('/', methods=['GET'])
def home():
    return "V16: Server is Running! (Port Fixed)"

@app.route('/search', methods=['GET'])
def search_api():
    target_url = request.args.get('url')
    keyword = request.args.get('keyword')
    
    if not target_url: return jsonify({"status": "error", "message": "URL 필요"})
    if not keyword: return jsonify({"status": "error", "message": "키워드 필요"})

    results = search_jbnu_logic(target_url, keyword)
    
    if not results:
        return jsonify({"status": "success", "data": [], "message": "검색 결과 없음"})
        
    return jsonify({"status": "success", "data": results})

# === ⭐️ 여기가 문제였습니다! 포트 번호 수정 ===
if __name__ == "__main__":
    # Render가 주는 포트 번호를 받아서 씁니다. 없으면 5001번.
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port)