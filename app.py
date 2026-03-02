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

def get_request(method, url, params=None, data=None):
    try:
        session = requests.Session()
        session.mount('https://', LegacySSLAdapter())
        headers = {'User-Agent': 'Mozilla/5.0'}
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        if method == 'GET':
            response = session.get(url, headers=headers, params=params, timeout=8, verify=False)
        else: # POST
            response = session.post(url, headers=headers, data=data, timeout=8, verify=False)
            
        response.encoding = 'utf-8' 
        return BeautifulSoup(response.text, 'html.parser'), response.url
    except Exception as e:
        print(f"Error: {e}")
        return None, ""

# === 2. V19: 자동 학습형 하이브리드 검색 ===
def search_universal_v19(target_url, keyword):
    if not target_url.startswith("http"): target_url = "https://" + target_url
    
    print(f"🚀 [V19 범용] {target_url} 분석 시작...")

    # 1단계: 빈손으로 접속해서 '기존 데이터' 훔쳐오기 (Scraping Hidden Inputs)
    # 청원고 사이트처럼 URL이 안 바뀌는 곳은 페이지 안에 hidden input이 숨어있음
    soup_init, real_url = get_request('GET', target_url)
    if not soup_init: return []

    base_payload = {}
    
    # URL에 있는 파라미터(menu=2377 등) 가져오기
    parsed = urlparse(real_url)
    query_params = parse_qs(parsed.query)
    for k, v in query_params.items():
        base_payload[k] = v[0]

    # HTML 안에 숨겨진 값(hidden input) 가져오기
    # 이게 있어야 청원고 같은 사이트가 "어? 정상적인 요청이네?" 하고 받아줌
    inputs = soup_init.find_all('input', {'type': 'hidden'})
    for inp in inputs:
        name = inp.get('name')
        value = inp.get('value')
        if name and value:
            base_payload[name] = value
            # print(f"   🕵️ 숨겨진 데이터 발견: {name}={value}")

    # 2단계: 검색어 변수명 시도 리스트 (학교 사이트용 searchWrd 추가!)
    param_names = [
        "searchKeyword",   # 전북대, 공공기관
        "searchWrd",       # ⭐️ 청원고 등 교육청 사이트 필수
        "q",               # 구글
        "query",           # 네이버
        "srchWrd",         # 또 다른 학교 포맷
        "s"                # 워드프레스
    ]

    all_results = []
    seen_links = set()

    # 3단계: GET과 POST 번갈아가며 찌르기
    for param_name in param_names:
        # payload 복사 후 검색어 추가
        current_payload = base_payload.copy()
        current_payload[param_name] = keyword
        current_payload['searchCondition'] = '0' # 혹시 모르니 추가
        
        # (A) GET 시도 (주소창 방식)
        soup, _ = get_request('GET', target_url.split('?')[0], params=current_payload)
        
        # 결과 파싱
        found = parse_results(soup, keyword, target_url, seen_links)
        if found:
            print(f"   ✅ [GET 성공] 변수명 '{param_name}'에서 {len(found)}개 발견!")
            return found # 찾았으면 바로 리턴

        # (B) POST 시도 (숨겨서 보내기 방식 - 청원고 가능성 높음)
        # print(f"   👉 POST 시도: {param_name}={keyword}")
        soup_post, _ = get_request('POST', target_url.split('?')[0], data=current_payload)
        
        found_post = parse_results(soup_post, keyword, target_url, seen_links)
        if found_post:
             print(f"   ✅ [POST 성공] 변수명 '{param_name}'에서 {len(found_post)}개 발견!")
             return found_post

    return []

# 결과 html에서 링크 찾는 함수 (공통)
def parse_results(soup, keyword, base_url, seen_links):
    if not soup: return []
    results = []
    links = soup.find_all('a')
    
    parsed_base = urlparse(base_url)

    for link in links:
        text = link.get_text().strip()
        href = link.get('href')
        
        if not text or not href: continue
        if 'javascript' in href or '#' in href: continue
        
        clean_text = text.replace(" ", "")
        clean_keyword = keyword.replace(" ", "")
        
        if clean_keyword in clean_text:
            # URL 합치기
            if not href.startswith("http"):
                if href.startswith("/"):
                     full_url = f"{parsed_base.scheme}://{parsed_base.netloc}{href}"
                else:
                    path_dir = "/".join(parsed_base.path.split('/')[:-1])
                    full_url = f"{parsed_base.scheme}://{parsed_base.netloc}{path_dir}/{href}"
            else:
                full_url = href
            
            if full_url not in seen_links:
                results.append({"title": text, "link": full_url})
                seen_links.add(full_url)
    return results

@app.route('/', methods=['GET'])
def home():
    return "V19: Universal Hybrid (Auto-Learning Input)"

@app.route('/search', methods=['GET'])
def search_api():
    target_url = request.args.get('url')
    keyword = request.args.get('keyword')
    
    if not target_url: return jsonify({"status": "error", "message": "URL 필요"})
    if not keyword: return jsonify({"status": "error", "message": "키워드 필요"})

    results = search_universal_v19(target_url, keyword)
    
    if not results:
        return jsonify({"status": "success", "data": [], "message": "결과 없음 (GET/POST 모두 실패)"})
        
    return jsonify({"status": "success", "data": results})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    app.run(host='0.0.0.0', port=port)