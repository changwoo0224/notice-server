import os
from flask import Flask, request, jsonify
import requests
import ssl
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from urllib3.util import ssl_
import urllib3
from urllib.parse import urlparse, parse_qs, urljoin

app = Flask(__name__)

# === 1. 보안 인증서 무시 설정 (한국 관공서 필수) ===
class LegacySSLAdapter(HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False):
        context = ssl_.create_urllib3_context(ciphers='DEFAULT@SECLEVEL=1')
        context.check_hostname = False 
        context.verify_mode = ssl.CERT_NONE
        self.poolmanager = PoolManager(num_pools=connections, maxsize=maxsize, block=block, ssl_context=context)

def get_request(method, url, params=None, data=None):
    try:
        session = requests.Session()
        session.mount('https://', LegacySSLAdapter())
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        }
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        if method == 'GET':
            response = session.get(url, headers=headers, params=params, timeout=10, verify=False)
        else: # POST
            response = session.post(url, headers=headers, data=data, timeout=10, verify=False)
            
        response.encoding = 'utf-8' 
        return BeautifulSoup(response.text, 'html.parser'), response.url
    except Exception as e:
        print(f"Connection Error: {e}")
        return None, ""

# === 2. V20: 진짜 범용 검색 (Hidden Input + Multi-Param) ===
def search_universal_v20(target_url, keyword):
    if not target_url.startswith("http"): target_url = "https://" + target_url
    
    print(f"🚀 [V20 분석 시작] {target_url}")

    # (1) 일단 접속해서 사이트 구조 파악 (Hidden Input 털기)
    # 청원고 같은 사이트는 게시판 ID 등이 hidden으로 숨겨져 있음
    soup_init, real_url = get_request('GET', target_url)
    if not soup_init: return []

    base_payload = {}
    
    # URL에 있는 파라미터(menu=2377 등) 가져오기
    parsed = urlparse(real_url)
    query_params = parse_qs(parsed.query)
    for k, v in query_params.items():
        base_payload[k] = v[0]

    # HTML 안에 숨겨진 <input type="hidden"> 싹 긁어오기
    inputs = soup_init.find_all('input', {'type': 'hidden'})
    for inp in inputs:
        name = inp.get('name')
        value = inp.get('value')
        if name and value:
            base_payload[name] = value

    # (2) 검색어 변수명 후보군 (한국, 외국, 교육청, 워드프레스 총망라)
    param_names = [
        "searchKeyword",   # 전북대, 공공기관 표준
        "searchWrd",       # ⭐️ 교육청(청원고) 표준
        "srchWrd",         # 일부 학교
        "q",               # 구글, 글로벌
        "query",           # 네이버
        "s",               # 워드프레스
        "stx"              # 그누보드
    ]

    all_results = []
    seen_links = set()

    # (3) GET(주소창)과 POST(숨김전송) 모두 시도
    # 청원고는 POST 방식일 확률이 높음
    methods = ['GET', 'POST']

    for method in methods:
        for param_name in param_names:
            # Payload 복사 및 검색어 주입
            current_payload = base_payload.copy()
            current_payload[param_name] = keyword
            current_payload['searchCondition'] = '0' # 제목 검색 (혹시 모르니)
            
            # 요청 전송
            base_url_only = real_url.split('?')[0]
            if method == 'GET':
                soup, final_url = get_request('GET', base_url_only, params=current_payload)
            else:
                soup, final_url = get_request('POST', base_url_only, data=current_payload)
            
            if not soup: continue

            # 결과 파싱
            links = soup.find_all('a')
            found_count = 0
            
            for link in links:
                text = link.get_text().strip()
                href = link.get('href')
                
                if not text or not href: continue
                if 'javascript' in href or '#' in href: continue
                
                # 키워드 매칭
                if keyword.replace(" ", "") in text.replace(" ", ""):
                    # URL 합치기
                    full_url = urljoin(real_url, href)
                    
                    if full_url not in seen_links:
                        all_results.append({"title": text, "link": full_url})
                        seen_links.add(full_url)
                        found_count += 1
            
            if found_count > 0:
                print(f"   ✅ [성공] {method} 방식 / 변수명 '{param_name}' / {found_count}개 발견")
                return all_results # 찾았으면 즉시 반환 (속도 최적화)

    return []

@app.route('/', methods=['GET'])
def home():
    return "V20: Server Running. (Port Binding Fixed)"

@app.route('/search', methods=['GET'])
def search_api():
    target_url = request.args.get('url')
    keyword = request.args.get('keyword')
    
    if not target_url: return jsonify({"status": "error", "message": "URL을 입력하세요."})
    if not keyword: return jsonify({"status": "error", "message": "키워드를 입력하세요."})

    results = search_universal_v20(target_url, keyword)
    
    if not results:
        return jsonify({"status": "success", "data": [], "message": "검색 실패 (사이트 보안이 강력하거나 키워드가 없음)"})
        
    return jsonify({"status": "success", "data": results})

# === 3. ⭐️ 포트 에러 해결의 핵심 ===
if __name__ == "__main__":
    # Render는 PORT라는 환경변수를 줍니다. 그걸 받아먹어야 합니다.
    port = int(os.environ.get("PORT", 10000)) 
    app.run(host='0.0.0.0', port=port)