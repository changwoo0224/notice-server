from flask import Flask, request, jsonify
import requests
import ssl
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.poolmanager import PoolManager
from urllib3.util import ssl_
import urllib3

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
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
        }
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        response = session.get(url, headers=headers, timeout=10, verify=False)
        response.encoding = 'utf-8' 
        return BeautifulSoup(response.text, 'html.parser')
    except Exception as e:
        print(f"Error: {e}")
        return None

# === 2. V11: 주소 원형 보존 검색 (No-Cut Logic) ===
def smart_search_v11(base_url, keyword):
    base_url = base_url.strip()
    if not base_url.startswith("http"): base_url = "https://" + base_url
    
    print(f"🚀 [V11 정밀 검색] 원본 주소 유지한 채 '{keyword}' 주입 시도")
    
    # ⭐️ 국내 웹사이트 표준 검색 변수들
    search_params = [
        "searchKeyword",  # 대학/공공기관 표준
        "q",              # 구글 표준
        "query",          # 네이버/포털 표준
        "s",              # 워드프레스 표준
        "srSearchVal"     # 구형 게시판
    ]
    
    all_results = []
    seen_links = set()
    
    # URL 연결자 결정 (이미 ?가 있으면 &를 쓰고, 없으면 ?를 씀)
    # 🚨 실수 수정: 기존 파라미터를 절대 삭제하지 않음!
    connector = "&" if "?" in base_url else "?"
    
    for param in search_params:
        # 예: .../sub01.do?menu=101 + & + searchKeyword=교비
        target_url = f"{base_url}{connector}{param}={keyword}"
        
        # 꿀팁: 한국 사이트는 searchCondition(검색조건)이 없으면 검색 안 되는 경우가 있음. '0'(제목)을 추가해봄.
        if param == "searchKeyword":
            target_url += "&searchCondition=0"

        # print(f"   👉 찌르는 중: {target_url}") # 로그 확인용
        
        soup = get_soup(target_url)
        if not soup: continue
        
        links = soup.find_all('a')
        found_count = 0
        
        for link in links:
            text = link.get_text().strip()
            href = link.get('href')
            
            if not text or not href: continue
            if 'javascript' in href or '#' in href: continue
            
            clean_text = text.replace(" ", "")
            clean_keyword = keyword.replace(" ", "") if keyword else ""
            
            # 검색 결과 매칭
            if clean_keyword in clean_text:
                # URL 합치기
                if not href.startswith("http"):
                    # 절대 경로 변환 로직 강화
                    if href.startswith("/"):
                        # 도메인만 남기고 합치기 (https://jbnu.ac.kr + /web/...)
                        domain = "/".join(base_url.split('/')[:3])
                        full_url = domain + href
                    else:
                        # 현재 경로 기준 합치기 (쿼리 스트링 제거 후 결합)
                        url_path = base_url.split('?')[0]
                        parent_path = "/".join(url_path.split('/')[:-1])
                        full_url = parent_path + "/" + href
                else:
                    full_url = href
                
                if full_url not in seen_links:
                    all_results.append({"title": text, "link": full_url})
                    seen_links.add(full_url)
                    found_count += 1
        
        if found_count > 0:
            print(f"   ✅ 발견! '{param}' 파라미터가 정답이었습니다.")
            break
            
    return all_results

# === 서버 경로 ===
@app.route('/', methods=['GET'])
def home():
    return "V11: No-Cut Search Injector (주소 원형 보존 모드)"

@app.route('/search', methods=['GET'])
def search_api():
    target_url = request.args.get('url')
    keyword = request.args.get('keyword')
    
    if not target_url:
        return jsonify({"status": "error", "message": "URL 필요"})
    
    # 키워드가 없으면 그냥 기본 긁어오기 (상위 15개)
    if not keyword:
        # (기본 로직 생략 - 검색어 있을 때가 중요하므로)
        return jsonify({"status": "success", "data": [], "message": "키워드를 입력해야 검색됩니다."})
        
    results = smart_search_v11(target_url, keyword)
    
    if not results:
        return jsonify({"status": "success", "data": [], "message": "검색 결과 0건 (주소 뒤에 검색어가 안 먹히는 사이트일 수 있습니다)"})
        
    return jsonify({"status": "success", "data": results})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001)