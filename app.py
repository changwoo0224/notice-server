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

def get_soup(url):
    try:
        session = requests.Session()
        session.mount('https://', LegacySSLAdapter())
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        }
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        response = session.get(url, headers=headers, timeout=5, verify=False)
        response.encoding = 'utf-8' 
        return BeautifulSoup(response.text, 'html.parser')
    except:
        return None

# === 2. 링크 추출기 (공통 함수) ===
def extract_links(soup, base_url, keyword):
    results = []
    seen_links = set()
    
    if not soup: return []

    links = soup.find_all('a')
    for link in links:
        text = link.get_text().strip()
        href = link.get('href')
        
        if not text or not href: continue
        if 'javascript' in href or '#' in href: continue
        
        clean_text = text.replace(" ", "")
        clean_keyword = keyword.replace(" ", "")
        
        # 키워드 포함 여부 확인
        if clean_keyword in clean_text:
            # URL 절대경로 변환
            if not href.startswith("http"):
                parsed_base = urlparse(base_url)
                if href.startswith("/"):
                    # 도메인 + 경로
                    full_url = f"{parsed_base.scheme}://{parsed_base.netloc}{href}"
                else:
                    # 현재 경로 + 상대 경로
                    path = "/".join(parsed_base.path.split('/')[:-1])
                    full_url = f"{parsed_base.scheme}://{parsed_base.netloc}{path}/{href}"
            else:
                full_url = href
            
            if full_url not in seen_links:
                results.append({"title": text, "link": full_url})
                seen_links.add(full_url)
    
    return results

# === 3. V14 하이브리드 검색 로직 ===
def hybrid_search(target_url, keyword):
    if not target_url.startswith("http"): target_url = "https://" + target_url
    
    print(f"🚀 [V14] 하이브리드 검색 시작: {target_url} (키워드: {keyword})")
    
    all_results = []
    
    # ---------------------------------------------------------
    # [1단계] 스마트 검색 주입 (전북대, 네이버, 워드프레스 등)
    # ---------------------------------------------------------
    parsed_url = urlparse(target_url)
    current_params = parse_qs(parsed_url.query)
    
    # 전 세계 주요 검색 파라미터 전략
    strategies = [
        # 1. 한국 공공기관/대학 (searchCondition 필수)
        {"searchKeyword": keyword, "searchCondition": "0"}, 
        # 2. 구글/글로벌 표준
        {"q": keyword},
        # 3. 네이버/포털
        {"query": keyword},
        # 4. 워드프레스/블로그
        {"s": keyword},
        # 5. 구형 게시판
        {"srSearchVal": keyword},
        # 6. 그누보드/한국 커뮤니티
        {"stx": keyword} 
    ]
    
    # 전략들을 하나씩 시도
    for strategy in strategies:
        # 기존 파라미터 유지하면서 새 파라미터 덮어쓰기
        new_params = current_params.copy()
        for k, v in strategy.items():
            new_params[k] = v
            
        new_query = urlencode(new_params, doseq=True)
        search_url = urlunparse((
            parsed_url.scheme, parsed_url.netloc, parsed_url.path,
            parsed_url.params, new_query, parsed_url.fragment
        ))
        
        # print(f"   👉 검색 시도: {search_url}")
        soup = get_soup(search_url)
        found_links = extract_links(soup, search_url, keyword)
        
        if found_links:
            print(f"   ✅ [성공] 자동 검색('{list(strategy.keys())[0]}')으로 {len(found_links)}개 발견!")
            return found_links # 찾았으면 바로 반환 (Best Case)

    # ---------------------------------------------------------
    # [2단계] 최후의 수단: 그냥 입력된 페이지 긁기 (Fallback)
    # ---------------------------------------------------------
    print("   ⚠️ 자동 검색 실패. 입력된 페이지를 직접 뒤집니다.")
    
    # 사용자가 준 URL 그대로 접속
    soup = get_soup(target_url)
    found_links = extract_links(soup, target_url, keyword)
    
    if found_links:
        print(f"   ✅ [성공] 페이지 직접 분석으로 {len(found_links)}개 발견!")
        return found_links
        
    return []

# === 서버 경로 ===
@app.route('/', methods=['GET'])
def home():
    return "V14: Hybrid Universal Engine (검색 + 직접수집)"

@app.route('/search', methods=['GET'])
def search_api():
    target_url = request.args.get('url')
    keyword = request.args.get('keyword')
    
    if not target_url: return jsonify({"status": "error", "message": "URL 필요"})
    if not keyword: return jsonify({"status": "success", "data": [], "message": "키워드 필요"})

    results = hybrid_search(target_url, keyword)
    
    if not results:
        return jsonify({"status": "success", "data": [], "message": "검색 결과 0건. (검색된 화면의 주소를 넣어보세요)"})
        
    return jsonify({"status": "success", "data": results})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001)