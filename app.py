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
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
        }
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        # ⭐️ [핵심] params를 따로 넘겨서 requests 라이브러리가 알아서 인코딩하게 함
        response = session.get(url, headers=headers, params=params, timeout=10, verify=False)
        response.encoding = 'utf-8' 
        return BeautifulSoup(response.text, 'html.parser'), response.url
    except Exception as e:
        print(f"Error: {e}")
        return None, ""

# === 2. V15: 파라미터 정밀 조립기 ===
def precise_search(target_url, keyword):
    if not target_url.startswith("http"): target_url = "https://" + target_url
    
    print(f"🚀 [V15] 정밀 분석 시작: {target_url} + 키워드: {keyword}")

    # 1. URL에서 ? 앞부분(Base)과 뒷부분(Params)을 분리
    parsed = urlparse(target_url)
    base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    
    # 기존 파라미터 (menu=2377 등)를 딕셔너리로 변환
    # 예: {'menu': ['2377'], 'pageIndex': ['1']}
    current_params = parse_qs(parsed.query)
    
    # 딕셔너리 단순화 (리스트 벗기기)
    clean_params = {k: v[0] for k, v in current_params.items()}
    
    # 2. 검색어 강제 주입 (덮어쓰기)
    # 전북대 표준 파라미터
    clean_params['searchKeyword'] = keyword
    clean_params['searchCondition'] = '0' # 0: 제목, 1: 내용, 2: 작성자
    
    # 3. 요청 보내기 (requests가 알아서 한글을 %EA%B5... 로 변환해줌)
    soup, final_url = get_soup(base_url, params=clean_params)
    
    print(f"   👉 실제로 접속한 URL: {final_url}") # 로그 확인용
    
    if not soup:
        return []

    # 4. 결과 추출
    results = []
    seen_links = set()
    links = soup.find_all('a')
    
    for link in links:
        text = link.get_text().strip()
        href = link.get('href')
        
        if not text or not href: continue
        if 'javascript' in href or '#' in href: continue
        
        # 검색 결과 매칭 (공백 제거 후 비교)
        clean_text = text.replace(" ", "")
        clean_keyword = keyword.replace(" ", "")
        
        if clean_keyword in clean_text:
            # 주소 합치기 로직
            if not href.startswith("http"):
                if href.startswith("/"):
                    full_url = f"{parsed.scheme}://{parsed.netloc}{href}"
                else:
                    # 상대 경로 처리
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
    return "V15: Precision Parameter Engine (파라미터 정밀 제어 모드)"

@app.route('/search', methods=['GET'])
def search_api():
    target_url = request.args.get('url')
    keyword = request.args.get('keyword')
    
    if not target_url: return jsonify({"status": "error", "message": "URL 필요"})
    if not keyword: return jsonify({"status": "error", "message": "키워드 필요"})

    results = precise_search(target_url, keyword)
    
    if not results:
        # 실패 시 팁 제공
        return jsonify({
            "status": "success", 
            "data": [], 
            "message": "결과 없음. (Render 로그에서 '실제로 접속한 URL'을 확인해보세요)"
        })
        
    return jsonify({"status": "success", "data": results})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5001)