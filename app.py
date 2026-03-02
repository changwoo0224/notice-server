import os
from flask import Flask, request, jsonify
import requests
import ssl
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from urllib3.util import ssl_
import urllib3
from urllib.parse import urlparse, parse_qs

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
        
        response = session.get(url, headers=headers, params=params, timeout=5, verify=False)
        response.encoding = 'utf-8' 
        return BeautifulSoup(response.text, 'html.parser'), response.url
    except Exception as e:
        print(f"Error: {e}")
        return None, ""

# === 2. V17: 방 번호(Menu ID) 자동 탐지 및 검색 ===
def search_smart_auto(target_url, keyword):
    if not target_url.startswith("http"): target_url = "https://" + target_url
    
    # 1. 일단 접속해서 '방 번호(menu)'가 있는지 확인
    parsed = urlparse(target_url)
    current_params = parse_qs(parsed.query)
    clean_params = {k: v[0] for k, v in current_params.items()}
    
    # 기본 URL (파라미터 뗀 것)
    base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    # 만약 URL에 'menu'가 없으면? -> 직접 페이지 뜯어서 찾아냄!
    if 'menu' not in clean_params:
        print(f"🕵️ [자동 탐지] URL에 방 번호가 없습니다. {base_url}에서 찾는 중...")
        soup_init, _ = get_soup(base_url, params=clean_params)
        
        if soup_init:
            # HTML 안에 숨겨진 <input name="menu" value="2377"> 을 찾는다.
            hidden_menu = soup_init.find('input', {'name': 'menu'})
            if hidden_menu and hidden_menu.get('value'):
                found_menu = hidden_menu.get('value')
                clean_params['menu'] = found_menu
                print(f"   ✅ 방 번호 발견! 자동 적용: menu={found_menu}")
            else:
                print("   ⚠️ 방 번호를 못 찾았습니다. 그냥 진행합니다.")

    # 2. 검색 조건 강제 주입
    clean_params['searchKeyword'] = keyword
    clean_params['searchCondition'] = '0' # 제목 검색
    
    # 3. 진짜 검색 접속
    soup, final_url = get_soup(base_url, params=clean_params)
    print(f"👉 최종 접속 URL: {final_url}") 

    if not soup: return []

    results = []
    seen_links = set()
    links = soup.find_all('a')
    
    for link in links:
        text = link.get_text().strip()
        href = link.get('href')
        
        if not text or not href: continue
        if 'javascript' in href or '#' in href: continue
        
        clean_text = text.replace(" ", "")
        clean_keyword = keyword.replace(" ", "")
        
        # 키워드 매칭
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
    return "V17: Auto-Menu Detection (짧은 주소 지원 모드)"

@app.route('/search', methods=['GET'])
def search_api():
    target_url = request.args.get('url')
    keyword = request.args.get('keyword')
    
    if not target_url: return jsonify({"status": "error", "message": "URL 필요"})
    if not keyword: return jsonify({"status": "error", "message": "키워드 필요"})

    results = search_smart_auto(target_url, keyword)
    
    if not results:
        return jsonify({"status": "success", "data": [], "message": "검색 결과 없음"})
        
    return jsonify({"status": "success", "data": results})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port)